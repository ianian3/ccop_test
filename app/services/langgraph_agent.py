import json
import logging
import re
from typing import TypedDict, List, Dict, Any, Optional, Union
from langgraph.graph import StateGraph, END, START
from flask import current_app
from openai import OpenAI

from app.services.ai_service import AIService
from app.services.graph_service import GraphService
from app.services.vector_rag_service import VectorRAGService
from app.services.schema_tools_server import SchemaToolServer

logger = logging.getLogger(__name__)

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
    error_count: int
    reflection_log: List[str]
    final_response: Any

class LangGraphAgent:
    """
    제안된 LangGraph 기반의 AI 수사 에이전트 아키텍처 구현 클래스.
    순환형 구조(Reflection 루프)를 통해 쿼리 정확도를 스스로 개선합니다.
    """
    
    _workflow_app = None

    def __init__(self):
        if LangGraphAgent._workflow_app is None:
            workflow = self._build_workflow()
            LangGraphAgent._workflow_app = workflow.compile()
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
        
        return {
            "final_response": {
                "status": "success" if success else "no_path",
                "results": elements,
                "type": "path"
            }
        }

    def context_retrieval_node(self, state: AgentState) -> Dict:
        """Context Retrieval: Vector DB를 사용하여 질문 내 엔티티의 실제 DB 정보를 매칭"""
        logger.info(f"--- CONTEXT RETRIEVAL NODE ---")
        # 이미 라우터에서 추출된 키워드 사용
        keyword = state.get('keyword')
        entities = []
        
        if keyword and len(keyword) >= 2:
            try:
                res = VectorRAGService.semantic_search_entities(keyword, state['graph_path'], limit=3)
                if res:
                    entities = res
            except Exception as e:
                logger.error(f"Vector Retrieval Error: {e}")
        
        return {"entities": entities}

    def schema_fetching_node(self, state: AgentState) -> Dict:
        """Schema Fetching: 현재 DB에 존재하는 라벨과 엣지 목록을 실시간으로 가져옴"""
        logger.info(f"--- SCHEMA FETCHING NODE ---")
        schema = GraphService.get_current_schema(state['graph_path'])
        schema_str = json.dumps(schema, ensure_ascii=False)
        return {"schema_info": schema_str}

    def synthesis_node(self, state: AgentState) -> Dict:
        """Query Synthesis: 수집된 컨텍스트와 스키마를 바탕으로 LLM이 Cypher 쿼리 작성"""
        logger.info(f"--- SYNTHESIS NODE (Attempt: {state['error_count'] + 1}) ---")
        
        client = self._get_client()
        
        # 성찰 로그가 있다면 프롬프트에 추가하여 '똑똑한 재시도' 유도
        reflection_context = ""
        if state['reflection_log']:
            reflection_context = "\n\n[이전 재시도 실패 및 개선 가이드]\n" + "\n".join(state['reflection_log'])

        # 엔티티 정보 포맷팅
        entity_context = ""
        if state['entities']:
            entity_context = "\n[참고 엔티티 정보]\n"
            for e in state['entities']:
                entity_context += f"- {e.get('label')}: {e.get('props')}\n"

        prompt = f"""
        당신은 AgensGraph용 쿼리를 생성하는 전문 수사관입니다.
        반드시 아래 SQL-Wrapped Cypher 문법(EBNF)을 준수하여 쿼리를 생성하십시오.
        
        === AgensGraph Grammar (EBNF) ===
        root ::= "SELECT * FROM cypher('{state['graph_path']}', $$ " cypher_body " $$) AS (...);"
        cypher_body ::= MATCH ... (WHERE ...)? RETURN ...
        return_item ::= variable "->'" property_name "'" 
        [데이터베이스 스키마 (반드시 이 정보만 사용)]
        {state['schema_info']}
        
        [수사 도메인 및 AgensGraph 매핑 가이드 (매우 중요!)]
        1. 속성 및 타입 매칭:
           - 인물 이름(예: '피의자1')은 반드시 `vt_psn` 노드의 `name` 속성을 사용.
           - 계좌는 `vt_bacnt`의 `actno`, 전화번호는 `vt_telno`의 `telno` 속성 사용.
           - **금액(amount)과 통화시간(duration)은 '문자열(String)'로 취급**됩니다. 비교 시 반드시 따옴표를 쓰세요. (예: `WHERE t->>'amount' = '500000'`, `WHERE c->>'duration' = '180'`)
        2. 정렬 및 집계 주의사항:
           - `ORDER BY`나 `count()` 사용 시 `c.duration`이 아닌 반드시 `c->>'duration'` 구문을 사용해 문자열로 뽑아낸 후 처리하세요. (예: `ORDER BY c->>'duration' DESC`)
        3. 엣지 방향성(Directionality) 강제:
           - 사건과 인물의 관계 방향은 무조건 `(c:vt_case)-[:involves]->(p:vt_psn)` 입니다. 반대 방향 `(p)-[:involves]->(c)`로 쓰지 마세요.
        4. 최단 경로 (shortestPath):
           - `shortestPath` 사용 시 `nodes(p)`나 `label(p)` 같은 복잡한 함수 사용 시 에러가 납니다. 오직 `RETURN p` 로 단순하게 경로 전체를 반환하세요.
        
        [참고 엔티티 정보]
        {entity_context}
        
        [이전 실패 피드백]
        {reflection_context}
        
        [Few-Shot 예제 (반드시 참고)]
        1. 질문: "피해자1의 연결 계좌 정보 보여줘"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn {{name: '피해자1'}})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b $$) AS (p agtype, r agtype, b agtype);
        2. 질문: "계좌 '110-3333-3333'에서 나간 이체 내역 전체 조회"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (b:vt_bacnt {{actno: '110-3333-3333'}})-[r:from_account]->(t:vt_transfer) RETURN b, r, t $$) AS (b agtype, r agtype, t agtype);
        3. 질문: "전화번호 '1000000001'을 소유한 사람"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno {{telno: '1000000001'}}) RETURN p, r, t $$) AS (p agtype, r agtype, t agtype);
        4. 질문: "피의자1 이 사용한 IP 주소들"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (p:vt_psn {{name: '피의자1'}})-[r:used_ip]->(i:vt_ip) RETURN p, r, i $$) AS (p agtype, r agtype, i agtype);
        5. 질문: "전화번호 '010-1111-2222' 에서 발신한 통화 기록"
           응답: SELECT * FROM cypher('{state['graph_path']}', $$ MATCH (t:vt_telno {{telno: '010-1111-2222'}})-[r:caller]->(c:vt_call) RETURN t, r, c $$) AS (t agtype, r agtype, c agtype);
        
        [질문]
        {state['question']}
        
        [작성 규칙]
        1. **스키마 준수**: 위 [데이터베이스 스키마]에 명시된 라벨, 속성, 관계만 사용하세요.
        2. **SQL Wrapper**: 무조건 `SELECT * FROM cypher('{state['graph_path']}', $$ ... $$) AS (...);` 구조만 출력하세요.
        3. **관계 선별**: 계좌 연결은 `has_account`, 전화번호 연결은 `owns_phone`, IP는 `used_ip`, 사건 가담은 `involves`를 정확히 구분하여 사용하세요.
        4. **최소한의 쿼리**: 질문에서 요구하지 않은 추가 관계(예: involves)를 억지로 MATCH에 넣지 마세요. AND 조건으로 인해 결과가 0건이 될 수 있습니다.
        5. **속성 접근**: `n->'prop_name'` 형식을 우선적으로 사용하세요. (예: `p->'name'`)
        6. **반환 형식**: 모든 결과 컬럼은 `agtype`으로 지정하십시오.
        7. **결과 시각화**: 노드와 관계를 모두 RETURN에 포함하세요 (예: `RETURN p, r, b`).
        8. **범죄 수사 및 그래프 분석과 무관한 일반 상식, 코딩 질문 등이라면 쿼리 대신 오직 `GENERAL: [자연어 답변]` 형태로만 출력하십시오.**
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
            for keyword in forbidden_keywords:
                # 간단한 단어 매칭으로 치명적 쓰기 작업 탐지
                if re.search(r'\b' + keyword + r'\b', upper_cypher):
                    return {
                        "cypher_query": cypher, 
                        "error_message": f"보안 정책 위반: 데이터 변경 명령어({keyword})가 감지되어 차단되었습니다."
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
            if not result and state.get('entities') and state['error_count'] < 1:
                target_name = state['entities'][0]['props'].get('name', '엔티티')
                logger.info(f"▶ 결과가 0건입니다. (엔티티 '{target_name}' 존재함) -> 성찰 루프 진입")
                return {
                    "execution_result": [],
                    "error_message": f"QUERY_ZERO_RESULTS: 엔티티 '{target_name}'가 DB에 존재함에도 결과가 없습니다. 관계 방향(A->B)이나 레이블(label)이 틀렸을 가능성이 높습니다.",
                    "error_count": state["error_count"] + 0.5 # 0.5점만 감점
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
        
        prompt = f"""
        당신은 수사관 AI를 돕는 시니어 데이터 엔지니어입니다. 다음 쿼리 실행 중 문제가 발생했습니다.
        
        [잘못된 쿼리]
        {last_query}
        
        [에러/문제 상황]
        {error_msg}
        
        [수정 지시사항]
        1. 쿼리 문법 에러라면 문법을 고치세요.
        2. 결과가 0건(QUERY_ZERO_RESULTS)이라면, 관계 방향 (A)-[:rel]->(B) 이 반대로 되어있는지, 혹은 잘못된 관계 레이블을 썼는지 분석하세요.
           (예: (p:vt_psn)-[:has_account]->(b:vt_bacnt) 가 맞는지 확인)
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
            return {"error_count": state['error_count'] + 1}

    def data_view_node(self, state: AgentState) -> Dict:
        """Data View: 실행 결과를 사용자에게 보여줄 최종 포맷(JSON/Summary)으로 가공"""
        logger.info(f"--- DATA VIEW NODE ---")
        
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
            return "data_view" # 바로 보고서 생성으로 이동 가능
        else:
            # QUERY 및 PATH 인텐트 모두 V3 모델이 직접 Cypher를 생성하도록 유도
            return "context_retrieval"

    def _route_after_execution(self, state: AgentState):
        """Execution 노드 이후의 분기 결정 (성공 시 종료, 실패 시 성찰 루프)"""
        if state.get("error_message"):
            if state["error_message"] == "GENERAL_CHAT" or "보안 정책 위반" in state["error_message"]:
                return "data_view" # 가드레일 위반 및 일반 대화는 즉시 종료
                
            if state["error_count"] < 2: # 최대 2번까지만 재시도
                return "reflection"
            else:
                return "data_view" # 실패한 채로 종료
        return "data_view"

    def _route_after_path(self, state: AgentState):
        """Path Finding 노드 이후의 분기 결정 (실패 시 QUERY로 전환 여부)"""
        if state["intent"] == "QUERY":
            return "context_retrieval"
        return "end"

    # --- Build Workflow ---

    def _build_workflow(self):
        workflow = StateGraph(AgentState)

        # 노드 등록
        workflow.add_node("router", self.router_node)
        workflow.add_node("context_retrieval", self.context_retrieval_node)
        workflow.add_node("schema_fetching", self.schema_fetching_node)
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
                "context_retrieval": "context_retrieval"
            }
        )

        # Query Flow
        workflow.add_edge("context_retrieval", "schema_fetching")
        workflow.add_edge("schema_fetching", "synthesis")
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

    def run(self, question: str, graph_path: str = "demo_tst1") -> Dict:
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
            "reflection_log": [],
            "final_response": None
        }
        
        result = self.app.invoke(initial_state)
        return result.get("final_response", {"status": "error", "message": "에이전트 응답 생성 실패"})
