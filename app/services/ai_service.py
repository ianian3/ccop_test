import json
import re
import ast
import os
from datetime import datetime
from openai import OpenAI
from flask import current_app
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate

logger = logging.getLogger(__name__)

class AIService:
    
    @staticmethod
    def get_client():
        """OpenAI 혹은 온프레미스 sLLM 클라이언트 생성"""
        endpoint = current_app.config.get('SLLM_ENDPOINT')
        if endpoint:
            # 온프레미스 sLLM (vLLM/Ollama 등)
            return OpenAI(base_url=endpoint, api_key="EMPTY")
        return OpenAI(api_key=current_app.config['OPENAI_API_KEY'])

    @staticmethod
    def route_question(question):
        """질문을 분석하여 의도 분기 및 핵심 키워드 추출 (최적화)"""
        client = AIService.get_client()
        
        prompt = f"""
        당신은 범죄 수사 질문의 의도를 분석하고 상부 보고 형식을 결정하는 지능형 라우터입니다.
        질문의 목표에 따라 아래 의도 중 하나로 분류하고, 검색에 필요한 핵심 키워드와 '예상 노드 레이블'을 추출하세요.
        
        [의도 종류]
        1. "PATH": 두 개체 사이의 최단 경로 추적 (예: "A와 B의 관계")
        2. "REPORT": 특정 주제에 대한 심층 분석 보고서 (예: "이 사건 요약해줘")
        3. "QUERY": 노드 검색 및 확장 (예: "홍길동 연결 노드")
        4. "GENERAL": 수사외적인 일반 상식/코딩/개념 질문 (예: "한국 수도는?")
        
        [레이블 추측]
        - 사람/피의자/피해자 -> vt_psn
        - 계좌/은행 -> vt_bacnt
        - 전화/핸드폰 -> vt_telno
        - 사건/범죄 -> vt_case
        - IP/로그인 -> vt_ip
        - 이체/송금 -> vt_transfer
        
        [출력 JSON 포맷]
        {{
            "intent": "PATH" | "QUERY" | "REPORT" | "GENERAL",
            "keyword": "핵심어",
            "labels": ["예상레이블1", "예상레이블2"],
            "term1": "경로시작(PATH 전용)",
            "term2": "경로끝(PATH 전용)"
        }}
        
        질문: {question}
        """
        
        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={ "type": "json_object" }
            )
            content = resp.choices[0].message.content.strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"!!! Intent/Keyword Routing Error: {e}")
            # Fallback: 단순 공백 분리
            words = question.split()
            return {"intent": "QUERY", "keyword": words[0] if words else ""}

    @staticmethod
    def generate_cypher(question, graph_path="demo_tst1"):
        """자연어 질문을 Cypher 쿼리로 변환 (LangChain Few-Shot 기반)"""
        # 동적 스키마 로드는 이제 Tool Call로 처리되므로 초기 프롬프트에는 포함하지 않음
        
        system_instruction = "You are an expert AgensGraph Cypher query generator for a Cybercrime Investigation System."
        
        # 1. AgensGraph 및 온톨로지 설명 (sLLM 최적화 가이드라인 - 2026 최상위 전략)
        ontology_context = f"""
[AgensGraph 쿼리 작성 가이드라인 (2026 최선 전략)]
당신은 PostgreSQL 기반의 AgensGraph에 최적화된 SQL-Wrapped Cypher를 생성합니다.

=== 정밀 온톨로지 매핑 (필히 준수) ===
1. 노드 및 속성:
   - `vt_psn` (인물): `name`(이름), `id`(주민번호), `nickname`(별명)
   - `vt_case` (사건): `flnm`(사건번호), `crime`(범죄명), `date`(날짜)
   - `vt_bacnt` (계좌): `actno`(계좌번호), `bank_name`(은행명), `bank_cd`(은행코드)
   - `vt_telno` (전화): `telno`(전화번호)
   - `vt_ip` (IP): `ip_addr`(IP주소)
   - `vt_transfer` (이체): `amount`(금액), `timestamp`(시간)

2. 관계 및 방향:
   - (p:vt_psn)-[:has_account]->(b:vt_bacnt)
   - (p:vt_psn)-[:owns_phone]->(t:vt_telno)
   - (p:vt_psn)-[:used_ip]->(i:vt_ip)
   - (c:vt_case)-[:involves]->(p:vt_psn)
   - (b:vt_bacnt)-[:from_account]->(t:vt_transfer)
   - (t:vt_transfer)-[:to_account]->(b:vt_bacnt)
   - (t:vt_transfer)-[:to_account]->(a:vt_atm)
   - (t:vt_telno)-[:caller]->(c:vt_call)
   - (c:vt_call)-[:callee]->(t:vt_telno)

=== AgensGraph Grammar (EBNF) ===
root ::= "SELECT * FROM cypher('{graph_path}', $$ " cypher_body " $$) AS (" columns ");"
cypher_body ::= MATCH_clause (WHERE_clause)? RETURN_clause
columns ::= col_name " agtype" (", " col_name " agtype")*

=== 작성 규칙 ===
1. 반드시 `SELECT * FROM cypher(...)` 구조를 사용하세요.
2. 속성 접근 시 `n->'prop_name'` 혹은 `n->>'prop_name'` 형식을 사용하세요.
3. 노드와 관계를 모두 RETURN 하세요 (예: `RETURN p, r, b`).
4. 설명 없이 쿼리 문자열만 반환하세요.
"""
        
        # 2. Few-Shot 예제 (전형적인 수사관 질문 패턴 추가)
        examples = [
            {
                "input": "피의자1이 보유한 계좌번호 찾아줘",
                "output": f"SELECT * FROM cypher('{graph_path}', $$ MATCH (p:vt_psn {{name: '피의자1'}})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b $$) AS (p agtype, r agtype, b agtype);"
            },
            {
                "input": "피해자1의 연결 계좌 정보 보여줘",
                "output": f"SELECT * FROM cypher('{graph_path}', $$ MATCH (p:vt_psn {{name: '피해자1'}})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b $$) AS (p agtype, r agtype, b agtype);"
            },
            {
                "input": "계좌 '110-1111-1111'에서 나간 이체 내역",
                "output": f"SELECT * FROM cypher('{graph_path}', $$ MATCH (b:vt_bacnt {{actno: '110-1111-1111'}})-[r:from_account]->(t:vt_transfer) RETURN b, r, t $$) AS (b agtype, r agtype, t agtype);"
            },
            {
                "input": "전화번호 '1000000001'을 소유한 사람",
                "output": f"SELECT * FROM cypher('{graph_path}', $$ MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno {{telno: '1000000001'}}) RETURN p, r, t $$) AS (p agtype, r agtype, t agtype);"
            }
        ]

        # 3. LangChain Prompt 설정
        example_prompt = ChatPromptTemplate.from_messages([
            ("human", "{input}"),
            ("ai", "{output}"),
        ])
        
        few_shot_prompt = FewShotChatMessagePromptTemplate(
            example_prompt=example_prompt,
            examples=examples,
        )
        
        # 3.5. Entity Resolution (Pre-matching using Vector DB)
        keyword = AIService.extract_keywords(question)
        entity_context = ""
        if keyword and len(keyword) >= 2:
            try:
                from app.services.vector_rag_service import VectorRAGService
                res = VectorRAGService.semantic_search_entities(keyword, graph_path, limit=3)
                
                if res:
                    entity_context = "\n\n[사전 검색된 엔티티 정보 (Vector DB Entity Resolution)]\n"
                    entity_context += f"사용자 질문의 '{keyword}' 키워드를 DB에서 의미론적으로 먼저 검색한 결과입니다. 쿼리 생성 시 일치하도록 작성하세요.\n"
                    for idx, entity in enumerate(res):
                        label = entity.get('label', 'Unknown')
                        props = entity.get('props', {})
                        if props:
                            prop_strs = [f"{k}: '{v}'" for k, v in list(props.items())[:2]]
                            prop_str = ", ".join(prop_strs)
                        else:
                            prop_str = f"id(n)='{entity.get('node_id', '')}'"
                        entity_context += f"- 검색된 노드 {idx+1}: 라벨={label}, 속성={{{prop_str}}}\n"
            except Exception as e:
                logger.error(f"VectorRAG Entity Pre-matching Error: {e}")
        
        # 4. Direct Schema Fetching (Alternative to Tool Calls for sLLM stability)
        try:
            from app.services.graph_service import GraphService
            schema = GraphService.get_current_schema(graph_path)
            schema_context = f"\n\n[실시간 DB 스키마 정보]\n{json.dumps(schema, ensure_ascii=False)}\n"
            
            client = AIService.get_client()
            
            # Few-shot 예제 포맷팅 및 주입
            formatted_few_shot = few_shot_prompt.format()
            
            messages = [
                {"role": "system", "content": system_instruction + "\n\n" + ontology_context + entity_context + schema_context},
            ]
            
            # 예제 추가 (Human/AI 쌍)
            for ex in examples:
                messages.append({"role": "user", "content": f"Question: {ex['input']}"})
                messages.append({"role": "assistant", "content": ex['output']})

            messages.append({"role": "user", "content": f"Question: {question}"})
            
            # 단일 Completion 호출 (Tool Call 없이 직접 생성)
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o'),
                messages=messages,
                temperature=0
            )
            
            content = resp.choices[0].message.content.strip()
            
            # 결과 후처리 (Markdown 코드 펜스 및 백틱 제거)
            content = content.replace("```cypher", "").replace("```sql", "").replace("```", "").replace("`", "").strip()
            
            # SQL Wrapper (SELECT) 또는 Cypher (MATCH) 시작 지점 찾기
            upper_content = content.upper()
            select_idx = upper_content.find("SELECT")
            match_idx = upper_content.find("MATCH")
            
            if select_idx != -1:
                content = content[select_idx:]
            elif match_idx != -1:
                content = content[match_idx:]
                
            # 마지막 세미콜론(;) 이후의 사족 제거
            if ";" in content:
                content = content.split(";")[0] + ";"

            # SFT 학습용 데이터 자동 수집 (질문-쿼리 쌍 저장)
            AIService._log_for_sft(question, content, graph_path)
            
            return content
            
        except Exception as e:
            logger.error(f"!!! Cypher Gen Error (Direct Schema): {e}")
            return ""

    @staticmethod
    def _log_for_sft(question, cypher, graph_path):
        """SFT 학습을 위한 데이터셋 자동 수집 로직"""
        try:
            log_file = os.path.join(current_app.root_path, 'data', 'sft_training_raw.jsonl')
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            
            # 유효한 쿼리인 경우만 저장 (간단한 검증)
            if "MATCH" in cypher.upper() and len(cypher) > 10:
                data = {
                    "instruction": question,
                    "input": f"Graph Context: {graph_path}",
                    "output": cypher,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"SFT Log Error: {e}")

    @staticmethod
    def extract_keywords(question):
        """질문에서 키워드 추출 - 단일 문자열 반환"""
        client = AIService.get_client()
        
        prompt = f"""
        다음 범죄 수사 질문에서 검색에 필요한 핵심 키워드 1개만 추출하세요.
        가장 중요한 단어 하나만 반환하세요.
        
        질문: {question}
        
        키워드:
        """
        
        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            content = resp.choices[0].message.content.strip()
            
            # sLLM의 사족(Explanations) 제거 및 정제
            # 1. 'The keyword is...', '키워드는...' 등의 문구 제거
            cleanup_patterns = ["The keyword in the question is", "The keyword is", "키워드는", "핵심 키워드는"]
            for pattern in cleanup_patterns:
                if pattern in content:
                    content = content.split(pattern)[-1].strip(": ").strip()
            
            # 2. 따옴표 제거
            content = content.replace('"', '').replace("'", "")
            
            # 3. 여러 단어인 경우 첫 번째 토큰 혹은 쉼표 앞부분 취득
            if ',' in content:
                keyword = content.split(',')[0].strip()
            elif '\n' in content:
                keyword = content.split('\n')[0].strip()
            else:
                # 공백으로 시작하는 경우 사족일 확률이 높으므로 단어들을 확인
                words = content.split()
                if len(words) > 5: # 너무 길면 사족으로 판단
                    # 숫자가 포함된 단어를 우선적으로 찾음 (계좌번호 등)
                    matching_words = [w for w in words if any(c.isdigit() for c in w)]
                    keyword = matching_words[0] if matching_words else words[0]
                else:
                    keyword = content
            
            return keyword.strip(".")  # 단일 문자열 반환
            
        except Exception as e:
            logger.error(f"!!! Keyword Extraction Error: {e}")
            # 실패 시 단순 단어 분리하여 문자열로 반환
            return " ".join(question.split()[:4])

    @staticmethod
    def generate_rag_report(question, context_texts, semantic_analysis=None):
        """그래프 조회 결과 기반 수사 보고서 생성"""
        client = AIService.get_client()
        
        # 온톨로지 분석 정보 추가
        ontology_info = ""
        if semantic_analysis:
            ontology_info = "\n\n[온톨로지 분석]\n" + semantic_analysis.get('summary', '')
        
        # 컨텍스트 제한 (너무 길면 OpenAI 토큰 초과)
        safe_context = str(context_texts[:80]) + ontology_info 
        
        prompt = f"""
        [사이버 범죄 수사 정보분석관 분석 보고서]

        당신은 경찰청 소속 최고 수준의 사이버 범죄 수사 정보분석관입니다. 
        제공된 그래프 데이터베이스의 노드와 엣지 추적 결과를 바탕으로, 아래 양식에 맞추어 명확하고 팩트 기반의 수사 보고서를 작성하십시오.

        [조회 결과 데이터]
        {safe_context}

        [작성 가이드라인]
        - 어조: 단호하고 객관적인 수사관 어조(~입니다, ~확인됨, ~가 필요함 등) 사용.
        - 구조: 사건(Case) 정보가 존재할 경우 반드시 그 사건을 중심축으로 하여 서술을 전개.
        - 원칙: 제공된 결과 데이터 외부에 있는 상상을 덧붙이지 말 것.

        [보고서 형태]
        ### 1. 사건 개요 및 분석 대상 (Overview)
        - 조회된 핵심 사건/트랜잭션/대상자의 요약.
        - 연관된 총 데이터(노드, 엣지)의 정량적 연결 규모.

        ### 2. 식별된 주요 개체 (Key Entities)
        - 사건 피의자/관계자 (Actor): 식별된 실명, ID 등
        - 혐의 입증 자산 (Evidence): 범행에 사용된 대포통장(계좌), 대포폰(전화), 접속 IP 등 확인된 노드 나열.

        ### 3. 자금 및 통신 흐름 분석 (Link Analysis / Activity)
        - 계좌 간의 송금 내역(Transfer)이나 통화 내역(Call)의 흐름 등 엣지 기반의 연결성 상세 서술.
        - 공범 간의 연결 고리(동일 IP 접속, 교차 송금 등 발견 시) 구체적 명시.

        ### 4. 수사 종합 평가 및 제언 (Recommendations)
        - 탐지된 그래프 데이터 구조에서 나타나는 특이점(Anomaly) 및 의심스러운 패턴 총평.
        - 후속 수사 방향 제언 (예: "A계좌에 대한 추가 자금추적 영장 필요", "공통 B IP 접속 단말기에 대한 포렌식 요망" 등)
        """
        
        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            return resp.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"!!! RAG Report Gen Error: {e}")
            return f"보고서 생성 실패: {e}"

    @staticmethod
    def suggest_schema_mapping(sample_rows):
        """CSV 샘플 데이터로부터 그래프 스키마 매핑 제안"""
        client = AIService.get_client()
        
        sample_preview = json.dumps(sample_rows[:5], ensure_ascii=False, indent=2)
        
        prompt = f"""
        다음은 사이버 범죄 수사 데이터의 CSV 샘플입니다.
        이 데이터를 그래프 데이터베이스에 적재하기 위한 노드/엣지 매핑을 제안하세요.
        
        [CSV 샘플]
        {sample_preview}
        
        [사용 가능한 노드 타입]
        - vt_flnm (접수번호/사건): flnm, receipt_no
        - vt_telno (전화번호): telno, phone
        - vt_bacnt (계좌): actno, bacnt, account
        - vt_site (사이트): site, url, domain
        - vt_ip (IP주소): ip, ip_addr
        - vt_file (파일): file, filename
        - vt_id (ID): id, user_id
        - vt_psn (사람): name
        - vt_atm (ATM): atm, atm_id
        
        [매핑 제안 형식]
        {{
            "source_node": {{
                "label": "vt_flnm",
                "property": "flnm",
                "column": "접수번호"
            }},
            "target_node": {{
                "label": "vt_bacnt",
                "property": "actno",
                "column": "계좌번호"
            }},
            "edge": {{
                "type": "used_account",
                "properties": ["등록일", "범죄유형"]
            }}
        }}
        
        매핑 제안:
        """
        
        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            content = resp.choices[0].message.content.strip()
            
            # JSON 추출
            try:
                # 마크다운 코드 블록 제거
                content = content.replace("```json", "").replace("```", "").strip()
                mapping = json.loads(content)
                return mapping
            except:
                return {"error": "JSON 파싱 실패", "raw_suggestion": content}
            
        except Exception as e:
            logger.error(f"!!! Schema Mapping Error: {e}")
            return {"error": str(e)}

    @staticmethod
    def infer_column_mapping_for_rdb(columns, sample_rows):
        """
        알 수 없는 CSV 컬럼들에 대해 KICS 온톨로지 기반의 의미론적 타입을 추론 (LLM 사용)
        """
        if not columns:
            return {}
            
        client = AIService.get_client()
        
        # 샘플 데이터 준비
        sample_preview = []
        for col in columns:
            values = [str(row.get(col, ""))[:50] for row in sample_rows[:3] if row.get(col)]
            sample_preview.append(f"- {col}: {values}")
            
        prompt = f"""
당신은 대한민국 경찰청 사이버 범죄 데이터베이스(RDB) 관리자입니다.
다음은 범죄 수사 증거 CSV 파일에서 의미를 알 수 없는 일부 컬럼명과 3건의 샘플 데이터입니다.

[분석할 컬럼 및 샘플 데이터]
{chr(10).join(sample_preview)}

[적재 가능한 RDB 스키마 타겟]
CSV 컬럼 데이터를 27개 표준 RDB 테이블의 어떤 '속성(컬럼)'에 적재해야 할지 판단하여 아래 키 중 하나로 매핑하세요.
- 'case': 사건번호/접수번호 (TB_INCDNT_MST.INCDNT_NO)
- 'crime': 사건개요/죄명 (TB_INCDNT_MST.INCDNT_NM)
- 'suspect': 피의자/주체 식별자 (TB_PRSN.PRSN_ID)
- 'person': 인물 성명 (TB_PRSN.KORN_FLNM)
- 'nickname': 닉네임/별명 (TB_PRSN.RMK_CN)
- 'phone': 일반 전화번호 (TB_TELNO_MST.TELNO)
- 'caller': 발신 전화번호 (TB_TELNO_CALL_DTL.DSPTCH_TELNO)
- 'callee': 수신 전화번호 (TB_TELNO_CALL_DTL.RCPTN_TELNO)
- 'account': 계좌번호 (TB_FIN_BACNT.BACNT_NO)
- 'sender': 출금/송금 계좌 (TB_FIN_BACNT_DLNG.BACNT_NO)
- 'receiver': 입금/수취 계좌 (TB_FIN_BACNT_DLNG.TRRC_BACNT_NO)
- 'amount': 거래/이체 금액 (TB_FIN_BACNT_DLNG.DLNG_AMT)
- 'date': 발생/거래 일시 (TB_INCDNT_MST.OCCRN_DT 또는 TB_FIN_BACNT_DLNG.DLNG_DT 등 공통 일시속성)
- 'ip': 접속 IP 주소 (TB_SYS_LGN_EVT.CNNT_IP_ADDR)
- 'site': 도메인/URL (TB_WEB_DMN.DMN_ADDR)
- 'file': 기기 내 파일명 (TB_DGTL_FILE_INVNT.FILE_NM)
- 'atm': ATM 관리번호 (TB_FIN_BACNT_DLNG.ATM_MNG_NO)
- 'ignore': 데이터베이스에 적재할 필요가 없는 무의미한 일련번호, 시스템 데이터인 경우

[출력 형식]
반드시 다음 JSON 형식으로만 응답하세요. (마크다운 포맷팅 ```json 등 사용 금지)
{{
  "컬럼명1": "phone",
  "컬럼명2": "ignore"
}}
"""
        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            
            content = resp.choices[0].message.content.strip()
            # JSON 클렌징
            content = content.replace("```json", "").replace("```", "").strip()
            
            result = json.loads(content)
            return result
            
        except Exception as e:
            logger.error(f"!!! LLM RDB Column Inference Error: {e}")
            return {}