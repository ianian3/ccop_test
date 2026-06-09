import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict, List, Dict, Any, Optional, Union
from langgraph.graph import StateGraph, END, START
from flask import current_app
from openai import OpenAI

from app.services.ai_service import AIService
from app.services.graph_service import GraphService

logger = logging.getLogger(__name__)


def _extract_property_hints(question: str) -> str:
    """질문에서 속성명/타입을 정규식으로 자동 추론하여 프롬프트 힌트 생성.
    LLM 호출 없이 순수 규칙 기반으로 동작하므로 레이턴시 0.
    """
    hints = []

    # 계좌번호 패턴 (XXX-XXXX-XXXX, 단 010/011/016/017/019 등 전화번호 제외)
    acct_match = re.search(r'(?<!\d)(?!01[0-9]-)(\d{3})-(\d{4})-(\d{4})(?!\d)', question)
    if acct_match:
        acct = acct_match.group()
        hints.append(f"- 계좌번호 '{acct}' 감지 → vt_bacnt 노드의 `actno` 속성 사용: {{actno: '{acct}'}}")

    # 전화번호 패턴 (010-XXXX-XXXX 또는 0X0XXXXXXXX)
    tel_match = re.search(r'0\d{1,2}-?\d{3,4}-?\d{4}', question)
    if tel_match:
        raw = tel_match.group().replace('-', '').replace(' ', '')
        hints.append(f"- 전화번호 감지 → vt_telno 노드의 `telno` 속성, 하이픈 없이 숫자만: {{telno: '{raw}'}}")

    # IP 주소 패턴
    if re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', question):
        ip = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', question).group()
        hints.append(f"- IP주소 '{ip}' 감지 → vt_ip 노드의 `ip_addr` 속성: {{ip_addr: '{ip}'}}")

    # 사건번호 패턴 (C001, CASE-XXXX-XXX 등)
    case_match = re.search(r'[Cc](?:ASE)?[-_]?\d[\w-]*', question)
    if case_match:
        hints.append(f"- 사건번호 '{case_match.group()}' 감지 → vt_case 노드의 `flnm` 속성: {{flnm: '{case_match.group()}'}}")

    # 은행명 힌트
    bank_map = {
        '농협': 'NH', '국민': 'KB', '신한': 'SH', '우리': 'WR',
        '하나': 'HN', '기업': 'IBK', '토스': 'TOSS', '카카오': 'KAKAO'
    }
    for bank_name, bank_cd in bank_map.items():
        if bank_name in question:
            hints.append(f"- 은행명 '{bank_name}' 감지 → vt_bacnt의 `bank_name` 속성 사용 (예: {{bank_name: '{bank_name}은행'}} 또는 bank_cd: '{bank_cd}')")
            break

    # 금액 패턴 (500만원, 5000000 등) → 문자열 타입 경고
    amount_match = re.search(r'(\d[\d,]*)\s*만?\s*원', question)
    if amount_match:
        raw_num = amount_match.group(1).replace(',', '')
        amount_val = str(int(raw_num) * 10000) if '만' in amount_match.group() else raw_num
        hints.append(f"- 금액 감지 → vt_transfer의 `amount`는 **문자열** 타입: WHERE t->>'amount' >= '{amount_val}'")

    # ATM ID 패턴
    atm_match = re.search(r'ATM[-_\s]?[\w]+', question, re.IGNORECASE)
    if atm_match:
        hints.append(f"- ATM ID '{atm_match.group()}' 감지 → vt_atm 노드 경유 필수: (b:vt_bacnt)<-[:has_account]-(p:vt_psn)-[:has_account]->(b2:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(a:vt_atm)")

    if not hints:
        return ""

    return "\n[Schema Property Hint (자동 추출 — 반드시 반영)]\n" + "\n".join(hints) + "\n"


class AgentState(TypedDict):
    """LangGraph 에이전트의 상태 정의"""
    question: str
    graph_path: str
    intent: str
    keyword: Optional[str] # 추가됨
    labels: List[str] # [추가] 예상되는 노드 레이블 목록
    term1: Optional[str]
    term2: Optional[str]
    entities: List[Dict[str, Any]]
    schema_info: str
    cypher_query: str
    execution_result: Any
    error_message: Optional[str]
    error_count: int        # 실행 에러 횟수 (int, max 2)
    zero_result_count: int  # 결과 0건 횟수 (별도 관리)
    reflection_log: List[str]
    final_response: Any

class LangGraphAgent:
    """
    제안된 LangGraph 기반의 AI 수사 에이전트 아키텍처 구현 클래스.
    순환형 구조(Reflection 루프)를 통해 쿼리 정확도를 스스로 개선합니다.
    """
    
    _workflow_app = None
    _workflow_version = 5  # 변경 시 증가 → singleton 자동 재빌드

    def __init__(self):
        if LangGraphAgent._workflow_app is None:
            LangGraphAgent._workflow_app = self._build_workflow().compile()
        self.app = LangGraphAgent._workflow_app

    def _get_client(self):
        return AIService.get_client()

    # --- Node Implementations ---

    def router_node(self, state: AgentState) -> Dict:
        """의도 라우터: 질문의 목적에 따라 PATH, QUERY, REPORT 등으로 분기"""
        logger.info(f"--- ROUTER NODE: {state['question']} ---")
        res = AIService.route_question(state['question'])
        
        return {
            "intent": res.get("intent", "QUERY"),
            "keyword": res.get("keyword"),
            "labels": res.get("labels", []), # [추가]
            "term1": res.get("term1"),
            "term2": res.get("term2")
        }

    def path_finding_node(self, state: AgentState) -> Dict:
        """최단 경로 탐색 노드: 특정 알고리즘(BFS 등)을 사용하여 두 노드 간 연결 고리 탐색"""
        logger.info(f"--- PATH FINDING NODE: {state['term1']} -> {state['term2']} ---")
        
        def find_id(term):
            if not term: return None
            # 1. 원본 검색
            res = GraphService.search_nodes(term, state['graph_path'])
            if res:
                for item in res:
                    if item.get('group') == 'nodes': return item['data']['id']
            
            # 2. 정규화 검색 (수식어 제거)
            clean_term = re.sub(r'(계좌|번호|인물|사람|사이트|IP|주소|전화)', '', term).strip()
            if clean_term and clean_term != term:
                res = GraphService.search_nodes(clean_term, state['graph_path'])
                if res:
                    for item in res:
                        if item.get('group') == 'nodes': return item['data']['id']
            return None

        id1 = find_id(state['term1'])
        id2 = find_id(state['term2'])

        # 둘 중 하나라도 못 찾으면 일반 QUERY 흐름으로 Fallback 유도
        if not id1 or not id2:
            logger.warning(f"Node detection failed for PATH. Falling back to QUERY flow.")
            return {
                "intent": "QUERY", # 인텐트를 변경하여 다음 시도 시 QUERY 흐름을 타게 함 (라우터 이후 분기 로직 수정 필요)
                "error_message": f"노드 식별 실패 ({state['term1']}, {state['term2']}). 일반 질의로 전환합니다."
            }

        success, elements = GraphService.find_shortest_path(id1, id2, state['graph_path'])

        # data_view에서 일관된 포맷으로 처리하도록 execution_result에 저장
        return {
            "execution_result": elements,
            "error_message": None if success else "경로를 찾을 수 없습니다."
        }

    def context_and_schema_node(self, state: AgentState) -> Dict:
        """Context + Schema 병렬 조회: Vector DB 엔티티 매칭과 그래프 스키마 조회를 동시에 실행"""
        logger.info(f"--- CONTEXT & SCHEMA NODE (parallel) ---")

        keyword = state.get('keyword')
        graph_path = state['graph_path']

        def fetch_entities():
            if not keyword or len(keyword) < 2:
                return []
            try:
                nodes = GraphService.search_nodes(keyword, graph_path)
                return [
                    {"label": n["data"]["label"], "props": n["data"]["props"]}
                    for n in nodes[:3]
                    if n.get("group") == "nodes"
                ]
            except Exception as e:
                logger.error(f"Entity DB Search Error: {e}")
                return []

        def fetch_schema():
            try:
                schema = GraphService.get_current_schema(graph_path)
                return json.dumps(schema, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Schema Fetching Error: {e}")
                return "{}"

        with ThreadPoolExecutor(max_workers=2) as executor:
            entity_future = executor.submit(fetch_entities)
            schema_future = executor.submit(fetch_schema)
            entities = entity_future.result()
            schema_str = schema_future.result()

        return {"entities": entities, "schema_info": schema_str}

    def synthesis_node(self, state: AgentState) -> Dict:
        """Query Synthesis: 수집된 컨텍스트와 스키마를 바탕으로 LLM이 Cypher 쿼리 작성"""
        attempt = state['error_count'] + state['zero_result_count'] + 1
        logger.info(f"--- SYNTHESIS NODE (Attempt: {attempt}) ---")

        # graph_path SQL Injection 방지
        from app.database import validate_graph_path
        if not validate_graph_path(state['graph_path']):
            return {"error_message": f"보안 정책 위반: 유효하지 않은 graph_path '{state['graph_path']}'"}

        client = self._get_client()

        # 성찰 로그가 있다면 프롬프트에 추가하여 '똑똑한 재시도' 유도
        reflection_context = ""
        if state['reflection_log']:
            numbered = "\n".join(
                f"[{i+1}차 시도 피드백] {log}"
                for i, log in enumerate(state['reflection_log'])
            )
            reflection_context = f"\n\n[이전 재시도 실패 및 개선 가이드]\n{numbered}\n[지금 시도] 위 피드백을 모두 반영하여 수정하세요."

        # 엔티티 정보 포맷팅
        entity_context = ""
        if state['entities']:
            entity_context = "\n[참고 엔티티 정보]\n"
            for e in state['entities']:
                entity_context += f"- {e.get('label')}: {e.get('props')}\n"

        # 라우터가 예측한 노드 레이블 힌트
        labels_context = ""
        if state.get('labels'):
            labels_context = f"\n[라우터 예측 노드 레이블 (참고)]: {', '.join(state['labels'])}\n"

        # Schema Property Hint: 질문에서 속성명/타입 자동 추론
        property_hint_context = _extract_property_hints(state['question'])

        prompt = f"""
        당신은 AgensGraph용 쿼리를 생성하는 전문 수사관입니다.
        반드시 아래 SQL-Wrapped Cypher 문법(EBNF)을 준수하여 쿼리를 생성하십시오.

        === AgensGraph Grammar (EBNF) ===
        root ::= "SELECT * FROM cypher('{state['graph_path']}', $$ " cypher_body " $$) AS (...);"
        cypher_body ::= MATCH ... (WHERE ...)? RETURN ...
        return_item ::= variable "->'" property_name "'"
        [데이터베이스 스키마 (반드시 이 정보만 사용)]
        {state['schema_info']}
        {labels_context}
        [수사 도메인 및 AgensGraph 매핑 가이드 (매우 중요!)]
        1. 속성 및 타입 매칭:
           - 인물 이름(예: '피의자1')은 반드시 `vt_psn` 노드의 `name` 속성을 사용.
           - 계좌는 `vt_bacnt`의 `actno`, 전화번호는 `vt_telno`의 `telno` 속성 사용.
           - **금액(amount)과 통화시간(duration)은 '문자열(String)'로 취급**됩니다. 비교 시 반드시 따옴표를 쓰세요. (예: `WHERE t->>'amount' = '500000'`)
        2. 정렬 및 집계 주의사항:
           - `ORDER BY`나 `count()` 사용 시 반드시 `c->>'duration'` 구문을 사용하세요. (예: `ORDER BY c->>'duration' DESC`)
        3. ⚠️ 엣지 방향성 절대 준수 (v3.5 온톨로지 기준, 역방향 절대 금지!):

           관계(엣지)         | 올바른 방향
           -----------------------------------------------------------------
           suspect_in         | (p:vt_psn)-[:suspect_in]->(c:vt_case)
           victim_in          | (p:vt_psn)-[:victim_in]->(c:vt_case)
           witness_in         | (p:vt_psn)-[:witness_in]->(c:vt_case)
           eg_used_account    | (c:vt_case)-[:eg_used_account]->(b:vt_bacnt)
           eg_used_phone      | (c:vt_case)-[:eg_used_phone]->(t:vt_telno)
           eg_used_ip         | (c:vt_case)-[:eg_used_ip]->(i:vt_ip)
           has_account        | (p:vt_psn)-[:has_account]->(b:vt_bacnt)
           controls           | (p:vt_psn)-[:controls]->(b:vt_bacnt)
           owns_phone         | (p:vt_psn)-[:owns_phone]->(t:vt_telno)
           owns_vehicle       | (p:vt_psn)-[:owns_vehicle]->(v:vt_vhcl)
           drives             | (p:vt_psn)-[:drives]->(v:vt_vhcl)
           used_ip            | (p:vt_psn)-[:used_ip]->(i:vt_ip)
           registered_to      | (t:vt_telno)-[:registered_to]->(p:vt_psn)
           from_account       | (a:vt_bacnt)-[:from_account]->(t:vt_transfer)
           to_account         | (t:vt_transfer)-[:to_account]->(b:vt_bacnt)
           caller             | (t:vt_telno)-[:caller]->(c:vt_call)
           callee             | (c:vt_call)-[:callee]->(t:vt_telno)
           sent_msg           | (t:vt_telno)-[:sent_msg]->(m:vt_msg)
           received_msg       | (m:vt_msg)-[:received_msg]->(t:vt_telno)
           accessed_from      | (a:vt_access)-[:accessed_from]->(i:vt_ip)
           accessed_to        | (a:vt_access)-[:accessed_to]->(s:vt_site)
           mentions_account   | (m:vt_msg)-[:mentions_account]->(b:vt_bacnt)
           operates           | (p:vt_psn)-[:operates]->(s:vt_site)
           recruits           | (p:vt_psn)-[:recruits]->(p2:vt_psn)
           blackmails         | (p:vt_psn)-[:blackmails]->(p2:vt_psn)
           hosts              | (i:vt_ip)-[:hosts]->(s:vt_site)
           contains_file      | (s:vt_site)-[:contains_file]->(f:vt_file)
           located_at         | (a:vt_atm)-[:located_at]->(l:vt_loc)
           used_for           | (t:vt_telno)-[:used_for]->(imp:vt_impersonation)
           targets            | (imp:vt_impersonation)-[:targets]->(o:vt_org)
           used_for         | (t:vt_telno)-[:used_for]->(imp:vt_impersonation)
           targets          | (imp:vt_impersonation)-[:targets]->(o:vt_org)
           sent_msg         | (t:vt_telno)-[:sent_msg]->(m:vt_msg)
           accessed_from    | (a:vt_access)-[:accessed_from]->(i:vt_ip)

           ✅ 계좌↔전화번호 직접 관계 없음 → 인물(vt_psn) 경유 필수:
           (b:vt_bacnt)<-[:has_account]-(p:vt_psn)-[:owns_phone]->(t:vt_telno)

        4. 최단 경로 (shortestPath):
           - `shortestPath` 사용 시 오직 `RETURN p` 로 단순하게 경로 전체를 반환하세요.

        {entity_context}
        {property_hint_context}
        {reflection_context}

        [Few-Shot 예제 (반드시 참고)]
        1. 질문: "피해자1의 연결 계좌 정보 보여줘"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn {{name: '피해자1'}})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b $$) AS (p agtype, r agtype, b agtype);
        2. 질문: "계좌 '110-3333-3333'에서 나간 이체 내역 전체 조회"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (b:vt_bacnt {{actno: '110-3333-3333'}})-[r:from_account]->(t:vt_transfer) RETURN b, r, t $$) AS (b agtype, r agtype, t agtype);
        3. 질문: "전화번호 '1000000001'을 소유한 사람"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno {{telno: '1000000001'}}) RETURN p, r, t $$) AS (p agtype, r agtype, t agtype);
        4. 질문: "사건번호 C001에 연루된 인물을 모두 찾아라"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn)-[r:suspect_in|victim_in|witness_in]->(c:vt_case {{flnm: 'C001'}}) RETURN p, r, c $$) AS (p agtype, r agtype, c agtype);
        5. 질문: "계좌 '110-1111-1111'을 소유한 사람의 전화번호를 찾아라"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (b:vt_bacnt {{actno: '110-1111-1111'}})<-[r1:has_account]-(p:vt_psn)-[r2:owns_phone]->(t:vt_telno) RETURN b, p, t $$) AS (b agtype, p agtype, t agtype);
        6. 질문: "피의자1 이 사용한 IP 주소들"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn {{name: '피의자1'}})-[r:used_ip]->(i:vt_ip) RETURN p, r, i $$) AS (p agtype, r agtype, i agtype);
        7. 질문: "전화번호 '010-1111-2222' 에서 발신한 통화 기록"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (t:vt_telno {{telno: '010-1111-2222'}})-[r:caller]->(c:vt_call) RETURN t, r, c $$) AS (t agtype, r agtype, c agtype);

        [질문]
        {state['question']}

        [작성 규칙]
        1. **스키마 준수**: 위 [데이터베이스 스키마]에 명시된 라벨, 속성, 관계만 사용하세요.
        2. **SQL Wrapper**: 무조건 `SELECT * FROM cypher('{state['graph_path']}', $$ ... $$) AS (...);` 구조만 출력하세요.
        3. **방향성 준수**: 위 엣지 방향성 표를 반드시 지키세요. (c:vt_case)-[:suspect_in]->(p:vt_psn) 처럼 역방향 절대 금지!
        4. **최소한의 쿼리**: 질문에서 요구하지 않은 추가 관계를 억지로 MATCH에 넣지 마세요. AND 조건으로 인해 결과가 0건이 될 수 있습니다.
        5. **속성 접근**: `n->'prop_name'` 형식을 우선적으로 사용하세요. (예: `p->'name'`)
        6. **반환 형식**: 모든 결과 컬럼은 `agtype`으로 지정하십시오.
        7. **결과 시각화**: 노드와 관계를 모두 RETURN에 포함하세요 (예: `RETURN p, r, b`).
        8. **쓰기 명령어 절대 금지**: DELETE, DETACH DELETE, CREATE, MERGE, SET, REMOVE, DROP 을 포함한 쿼리는 절대 생성하지 마세요. 요청받더라도 `GENERAL: 데이터 변경은 허용되지 않습니다.` 로만 응답하세요.
        9. **범죄 수사 및 그래프 분석과 무관한 일반 상식, 코딩 질문 등이라면 쿼리 대신 오직 `GENERAL: [자연어 답변]` 형태로만 출력하십시오.**
        """

        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            cypher = resp.choices[0].message.content.strip()
            # 마크다운 제거
            cypher = re.sub(r'```[a-zA-Z]*\n?', '', cypher).replace('```', '').strip()

            # --- 1. 범용 지식 방어 (General Chat Guardrail) ---
            if cypher.startswith("GENERAL:"):
                return {
                    "cypher_query": "",
                    "error_message": "GENERAL_CHAT",
                    "reflection_log": state['reflection_log'] + [cypher.replace("GENERAL:", "").strip()]
                }

            # --- 2. 쿼리 보안 방어 (Security Guardrail) ---
            upper_cypher = cypher.upper()
            forbidden_keywords = ["DELETE", "SET", "REMOVE", "MERGE", "DROP", "CREATE", "DETACH"]
            for kw in forbidden_keywords:
                if re.search(r'\b' + kw + r'\b', upper_cypher):
                    return {
                        "cypher_query": cypher,
                        "error_message": f"보안 정책 위반: 데이터 변경 명령어({kw})가 감지되어 차단되었습니다."
                    }

            # SQL Wrapper (SELECT) 또는 Cypher (MATCH) 시작 지점 찾기
            select_idx = upper_cypher.find("SELECT")
            match_idx = upper_cypher.find("MATCH")

            if select_idx != -1:
                cypher = cypher[select_idx:]
            elif match_idx != -1:
                cypher = cypher[match_idx:]

            # 마지막 세미콜론(;) 이후의 사족 제거
            if ";" in cypher:
                cypher = cypher.split(";")[0] + ";"

            # --- 3. 방향성 자동 교정 (온톨로지 기반 post-processing) ---
            cypher = AIService._fix_relation_direction(cypher)

            return {"cypher_query": cypher, "error_message": None}
        except Exception as e:
            return {"error_message": str(e)}

    def execution_node(self, state: AgentState) -> Dict:
        """Execution: 생성된 Cypher 쿼리를 실제 DB에서 실행"""
        logger.info(f"--- EXECUTION NODE ---")
        
        if not state['cypher_query']:
            if state.get("error_message") == "GENERAL_CHAT":
                return {} # 에러 유지
            return {"error_message": "생성된 쿼리가 없습니다."}
            
        # 보안(Guardrail) 에러인 경우 실행하지 않고 통과
        if state.get("error_message") and "보안 정책 위반" in state.get("error_message", ""):
            logger.warning(f"Blocked Execution: {state['error_message']}")
            return {}

        # GraphService.execute_cypher 재사용 (Cytoscape 포맷 파싱 포함)
        success, result = GraphService.execute_cypher(state['cypher_query'], state['graph_path'])
        
        if success:
            # [개선] 결과가 0건인데 엔티티 정보가 있는 경우 -> 성찰 유도
            if not result and state.get('entities') and state['zero_result_count'] < 1:
                target_name = state['entities'][0]['props'].get('name', '엔티티')
                logger.info(f"▶ 결과가 0건입니다. (엔티티 '{target_name}' 존재함) -> 성찰 루프 진입")
                return {
                    "execution_result": [],
                    "error_message": f"QUERY_ZERO_RESULTS: 엔티티 '{target_name}'가 DB에 존재함에도 결과가 없습니다. 관계 방향(A->B)이나 레이블(label)이 틀렸을 가능성이 높습니다.",
                    "zero_result_count": state["zero_result_count"] + 1
                }
            
            return {
                "execution_result": result, # elements list
                "error_message": None
            }
        else:
            logger.warning(f"Query Execution Failed: {result}")
            return {"error_message": str(result)}

    def reflection_node(self, state: AgentState) -> Dict:
        """Reflection: 실행 에러 발생 시 원인을 분석하고 다음 시도를 위한 피드백 생성"""
        logger.info(f"--- REFLECTION NODE ---")

        client = self._get_client()
        error_msg = state['error_message']
        last_query = state['cypher_query']

        # ZERO_RESULTS 케이스에는 방향성 규칙을 명시적으로 포함
        direction_hint = ""
        if error_msg and "QUERY_ZERO_RESULTS" in error_msg:
            direction_hint = """
[엣지 방향성 정답표 v3.4 (역방향이 0건의 주원인)]
  suspect_in   : (p:vt_psn)-[:suspect_in]->(c:vt_case)     ← 인물→사건
  victim_in    : (p:vt_psn)-[:victim_in]->(c:vt_case)      ← 인물→사건
  witness_in   : (p:vt_psn)-[:witness_in]->(c:vt_case)     ← 인물→사건
  has_account  : (p:vt_psn)-[:has_account]->(b:vt_bacnt)   ← 인물→계좌
  controls     : (p:vt_psn)-[:controls]->(b:vt_bacnt)      ← 인물→계좌(실지배)
  owns_phone   : (p:vt_psn)-[:owns_phone]->(t:vt_telno)    ← 인물→전화
  used_ip      : (p:vt_psn)-[:used_ip]->(i:vt_ip)          ← 인물→IP
  from_account : (b:vt_bacnt)-[:from_account]->(t:vt_transfer)
  to_account   : (t:vt_transfer)-[:to_account]->(b:vt_bacnt)
  operates     : (p:vt_psn)-[:operates]->(s:vt_site)       ← 인물→사이트
  hosts        : (i:vt_ip)-[:hosts]->(s:vt_site)           ← IP→사이트
위 방향과 현재 쿼리를 비교하여 역방향 여부를 먼저 확인하세요.
"""

        prompt = f"""
        당신은 수사관 AI를 돕는 시니어 데이터 엔지니어입니다. 다음 쿼리 실행 중 문제가 발생했습니다.

        [잘못된 쿼리]
        {last_query}

        [에러/문제 상황]
        {error_msg}
        {direction_hint}
        [수정 지시사항]
        1. 쿼리 문법 에러라면 문법을 고치세요.
        2. 결과가 0건(QUERY_ZERO_RESULTS)이라면, 위 방향성 정답표와 비교하여 역방향 관계를 찾아 교정하세요.
        3. 다음 시도에서 반드시 고쳐야 할 짧고 명확한 지시사항 1가지만 작성하세요.

        [분석 결과 및 지시사항]
        """
        
        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            feedback = resp.choices[0].message.content.strip()

            new_log = state['reflection_log'] + [feedback]
            return {
                "reflection_log": new_log,
                "error_count": state['error_count'] + 1,
                "error_message": None # 루프 재진입을 위해 초기화
            }
        except Exception as e:
            logger.error(f"Reflection LLM 호출 실패: {e}")
            fallback_feedback = "이전 쿼리의 관계 방향과 속성명을 다시 확인하세요."
            return {
                "reflection_log": state['reflection_log'] + [fallback_feedback],
                "error_count": state['error_count'] + 1,
                "error_message": None
            }

    def data_view_node(self, state: AgentState) -> Dict:
        """Data View: 실행 결과를 사용자에게 보여줄 최종 포맷(JSON/Summary)으로 가공"""
        logger.info(f"--- DATA VIEW NODE ---")
        
        # PATH 인텐트 결과 처리
        if state['intent'] == "PATH":
            return {
                "final_response": {
                    "status": "success" if not state.get("error_message") else "no_path",
                    "elements": state.get("execution_result") or [],
                    "results_count": len(state.get("execution_result") or []),
                    "type": "path",
                    "intent": "PATH",
                    "error": state.get("error_message")
                }
            }

        # 쿼리가 성공했으면 그 결과를 정규화하여 반환
        if state['intent'] == "REPORT":
            # REPORT 인텐트의 경우 설명과 요소를 반환
            report, elements = GraphService.rag_query(state['question'], state['graph_path'])
            return {"final_response": {
                "status": "success", 
                "explanation": report, 
                "elements": elements, 
                "type": "report",
                "intent": "REPORT"
            }}
        
        # 일반 QUERY 결과 반환 전 가드레일 예외 처리
        if state.get("error_message") == "GENERAL_CHAT":
            return {
                "final_response": {
                    "status": "success",
                    "cypher": "일반 대화 응답",
                    "elements": [],
                    "results_count": 0,
                    "type": "general",
                    "intent": "GENERAL",
                    "error": state['reflection_log'][-1] if state['reflection_log'] else "답변 내용 반환"
                }
            }
            
        if state.get("error_message") and "보안 정책 위반" in state["error_message"]:
             return {
                "final_response": {
                    "status": "error",
                    "cypher": state.get('cypher_query', ''),
                    "elements": [],
                    "results_count": 0,
                    "type": "guardrail",
                    "intent": "QUERY",
                    "error": state["error_message"]
                }
             }

        # 일반 QUERY 결과 정상 반환
        return {
            "final_response": {
                "status": "success" if not state.get("error_message") else "partial_success",
                "cypher": state['cypher_query'],
                "elements": state['execution_result'] if state['execution_result'] else [],
                "results_count": len(state['execution_result']) if state['execution_result'] else 0,
                "type": "query",
                "intent": state['intent'],
                "error": state.get("error_message")
            }
        }

    # --- Router Logics ---

    def _route_after_router(self, state: AgentState):
        """Router 노드 이후의 분기 결정"""
        if state["intent"] == "REPORT":
            return "data_view"
        elif state["intent"] == "PATH":
            return "path_finding"
        else:
            return "context_and_schema"

    def _route_after_execution(self, state: AgentState):
        """Execution 노드 이후의 분기 결정 (성공 시 종료, 실패 시 성찰 루프)"""
        if state.get("error_message"):
            if state["error_message"] == "GENERAL_CHAT" or "보안 정책 위반" in state["error_message"]:
                return "data_view" # 가드레일 위반 및 일반 대화는 즉시 종료

            total_attempts = state["error_count"] + state["zero_result_count"]
            if total_attempts < 3: # 에러 + 0건 합산 최대 3번까지 재시도
                return "reflection"
            else:
                return "data_view" # 실패한 채로 종료
        return "data_view"

    def _route_after_path(self, state: AgentState):
        """Path Finding 노드 이후의 분기 결정 (노드 식별 실패 시 QUERY로 전환)"""
        if state["intent"] == "QUERY":
            # path_finding에서 노드를 못 찾아 QUERY로 전환된 경우
            return "context_and_schema"
        return "data_view"

    # --- Build Workflow ---

    def _build_workflow(self):
        workflow = StateGraph(AgentState)

        # 노드 등록
        workflow.add_node("router", self.router_node)
        workflow.add_node("path_finding", self.path_finding_node)
        workflow.add_node("context_and_schema", self.context_and_schema_node)
        workflow.add_node("synthesis", self.synthesis_node)
        workflow.add_node("execution", self.execution_node)
        workflow.add_node("reflection", self.reflection_node)
        workflow.add_node("data_view", self.data_view_node)

        # 엣지 연결
        workflow.add_edge(START, "router")

        # Router 분기
        workflow.add_conditional_edges(
            "router",
            self._route_after_router,
            {
                "data_view": "data_view",
                "path_finding": "path_finding",
                "context_and_schema": "context_and_schema"
            }
        )

        # Path Finding 분기 (노드 식별 실패 시 QUERY로 전환, 성공 시 data_view)
        workflow.add_conditional_edges(
            "path_finding",
            self._route_after_path,
            {
                "context_and_schema": "context_and_schema",
                "data_view": "data_view"
            }
        )

        # Query Flow (context + schema 병렬 → synthesis)
        workflow.add_edge("context_and_schema", "synthesis")
        workflow.add_edge("synthesis", "execution")
        
        # Execution 분기 (Reflection 루프)
        workflow.add_conditional_edges(
            "execution",
            self._route_after_execution,
            {
                "reflection": "reflection",
                "data_view": "data_view"
            }
        )
        
        workflow.add_edge("reflection", "synthesis") # 루프: 성찰 후 재합성
        

        workflow.add_edge("data_view", END)

        return workflow

    def run(self, question: str, graph_path: str = "tccop_graph_v6") -> Dict:
        """에이전트 실행"""
        initial_state: AgentState = {
            "question": question,
            "graph_path": graph_path,
            "intent": "QUERY",
            "keyword": None,
            "term1": None,
            "term2": None,
            "entities": [],
            "schema_info": "",
            "cypher_query": "",
            "execution_result": None,
            "error_message": None,
            "error_count": 0,
            "zero_result_count": 0,
            "reflection_log": [],
            "final_response": None
        }
        
        result = self.app.invoke(initial_state)
        return result.get("final_response", {"status": "error", "message": "에이전트 응답 생성 실패"})
