import json
import re
import ast
from openai import OpenAI
from flask import current_app

class AIService:
    
    @staticmethod
    def get_client():
        """OpenAI 클라이언트 생성 (Flask Config 사용)"""
        return OpenAI(api_key=current_app.config['OPENAI_API_KEY'])

    @staticmethod
    def generate_cypher(question):
        """자연어 질문을 Cypher 쿼리로 변환"""
        client = AIService.get_client()
        
        system_instruction = "You are a Cypher query generator. Output ONLY the raw Cypher query string. Do not use Markdown formatting. Do not provide any explanation."
        
        prompt = f"""
        [Schema Info - Cybercrime Investigation Graph]
        Node Labels & Properties:
        - vt_flnm: 접수번호 (flnm, police_station, investigator_department)
        - vt_telno: 전화번호 (telno, phone)
        - vt_bacnt: 계좌번호 (bacnt, actno, bank, account)
        - vt_site: 사이트/URL (site, url, domain)
        - vt_ip: IP주소 (ip, ip_addr, ipaddr)
        - vt_atm: ATM (atm, atm_id)
        - vt_file: 파일명 (file, filename, filepath)
        - vt_id: ID (id, user_id, userid)
        - vt_psn: 사람/기타 (name, dpstr)

        Edge Types:
        - digital_trace: 디지털 흔적 (접수→사이트)
        - used_account: 계좌 사용 (접수→계좌)
        - used_phone: 전화 사용 (접수→전화)

        [Query Rules]
        1. Use 'MATCH (v)' for generic node search
        2. Use CONTAINS for substring matching (NOT regex =~)
        3. **CRITICAL**: Use SINGLE QUOTES (') for ALL string literals
        4. Search across multiple properties with OR
        5. Return: id(v), labels(v), properties(v)
        6. LIMIT 30
        7. No PostgreSQL casting (::text, ::graphid)

        [Examples]
        ✅ Good: WHERE v.flnm CONTAINS '2019-001' OR v.telno CONTAINS '2019-001'
        ❌ Bad:  WHERE v.flnm CONTAINS "2019-001"
        ✅ Good: WHERE v.site CONTAINS 'example.com'
        ❌ Bad:  WHERE v.telno =~ '.*pattern.*'

        Question: "{question}"
        """
        
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_instruction}, 
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            content = resp.choices[0].message.content.strip()
            # 마크다운 및 불필요한 설명 제거
            content = content.replace("```cypher", "").replace("```", "").strip()
            
            if "MATCH" in content and not content.startswith("MATCH"):
                match_index = content.find("MATCH")
                content = content[match_index:]
                
            return content
            
        except Exception as e:
            print(f"!!! Cypher Gen Error: {e}")
            return ""

    @staticmethod
    def extract_keywords(question):
        """질문에서 핵심 키워드 추출 - 전체 식별자 유지"""
        import re
        
        # 패턴 매칭: 접수번호, 전화번호, 계좌번호 등
        patterns = [
            r'\d{4}-\d{6,}',        # 접수번호: 2019-000138
            r'\d{3}-\d{4}-\d{4}',   # 전화번호: 010-1234-5678
            r'\d{10,}',              # 계좌번호: 1002757733275
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',  # IP
        ]
        
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                return match.group()
        
        # 패턴 매칭 실패 시 전체 질문에서 공백 제거한 것 사용
        keywords = question.strip().split()
        if keywords:
            # 가장 긴 단어 반환 (일반적으로 식별자가 긴 편)
            return max(keywords, key=len)
        
        return question.strip()

    @staticmethod
    def generate_rag_report(question, context_texts, semantic_analysis=None):
        """수사 보고서 생성"""
        client = AIService.get_client()
        
        # 온톨로지 분석 추가
        ontology_info = ""
        if semantic_analysis:
            ontology_info = "\n\n[온톨로지 분석]\n" + semantic_analysis.get('summary', '')
        
        # 컨텍스트 길이 제한 (토큰 절약 및 에러 방지)
        safe_context = str(context_texts[:80]) + ontology_info 
        
        try:
            resp = client.chat.completions.create(
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": "당신은 지능형 수사관입니다. 데이터를 분석하여 '한국어'로 수사 보고서를 작성하세요."},
                    {"role": "user", "content": f"질문: {question}\n데이터:\n{safe_context}\n\n분석 보고서 작성:"}
                ],
                temperature=0.3
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"보고서 생성 중 오류 발생: {str(e)}"

    @staticmethod
    def suggest_mapping(headers, sample_row):
        """
        CSV 헤더 매핑 추천 (JSON Object 반환) - 사이버 범죄 수사 데이터 특화
        KICS 데이터(접수번호, 계좌, IP, 코인주소 등)의 연관 관계 분석을 위한 스키마 추천
        """
        client = AIService.get_client()
            
        # 이전에 추출한 KICS 데이터셋의 핵심 컬럼 키워드 정의
        kics_context = """
        [Domain Context: Cyber Financial Crime Investigation]
        The data involves phishing, smishing, and investment fraud.
        Key entities are 'Case'(Receipt No), 'Suspect Info'(Phone, Account, IP), and 'Trace'(URL, ID).
    
        [Standard Column Reference]
        - Case Info: 경찰서, 접수번호, 수사관, 범죄종류, 피해금액, 사건개요
        - Financial: 은행, 계좌번호, 투자자산종류, 거래소구분
        - Digital: IP 주소, URL, ID, 닉네임, 통신사, 휴대전화
        """

        prompt = f"""
        You are a Cybercrime Investigation Data Architect.
        Analyze the CSV headers and sample row to suggest the best Graph Database Schema mapping (Source -> Edge -> Target).

        {kics_context}

        [Input Data]
        Headers: {headers}
        Sample Row: {sample_row}

        [Mapping Logic Priorities]
        1. **Source Node (The Anchor)**:
       - **Priority 1**: Case Identifier ('접수번호', '사건번호'). This is usually the central node.
       - **Priority 2**: If analyzing suspect networks, Suspect Identifier ('용의자', '피의자') could be source.
       - **Default**: Set to '접수번호' (Case No) if present.

        2. **Target Node (The Link)**:
       - Identify the *strongest* connector entity in the row.
       - **Priority 1 (Financial)**: '계좌번호' (Account No), '지갑주소' (Wallet Addr).
       - **Priority 2 (Comms)**: '휴대전화' (Phone No), 'IP 주소' (IP Address).
       - **Priority 3 (Digital)**: 'URL', 'ID', '닉네임'.
       - **Strategy**: If multiple exist, prioritize '계좌번호' or '휴대전화' as they provide strong pivots for cross-case correlation.

        3. **Edge Type**:
       - If Target is Account/Finance -> "MONEY_FLOW" or "USED_ACCOUNT"
       - If Target is Phone/Comms -> "USED_PHONE" or "COMMUNICATION"
       - If Target is IP/URL -> "DIGITAL_TRACE"
       - Default -> "RELATED_TO"

        4. **Properties (Attributes)**:
       - Assign remaining columns as properties.
       - **Edge Properties**: Contextual info like '피해금액' (Amount), '범죄일' (Date), '범죄수법' (Method), '내용' (Content).
       - **Node Properties**: Static info like '은행' (Bank Name) belongs to the Account node context (or Edge if generic).

        [Task]
        Return a JSON object with the best guess mapping based on the provided headers.
    
        [Output JSON Format]
        {{
            "sourceCol": "EXACT_HEADER_NAME",
            "targetCol": "EXACT_HEADER_NAME",
        "edgeType": "SUGGESTED_EDGE_TYPE",
        "properties": [
            {{ "col": "EXACT_HEADER_NAME", "target": "edge", "key": "amount_krw" }}, 
            {{ "col": "EXACT_HEADER_NAME", "target": "source", "key": "investigator_name" }},
            {{ "col": "EXACT_HEADER_NAME", "target": "edge", "key": "crime_date" }}
        ]
    }}
    
    Constraint: Output RAW JSON ONLY. No markdown blocks. Use English keys for 'key' field if possible, but keep 'col' exactly as in headers.
    """
    
        try:
            resp = client.chat.completions.create(
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": "You are a JSON generator. Output raw JSON only. Do not include markdown formatting like ```json."}, 
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            content = resp.choices[0].message.content.strip()
            # 마크다운 방어 코드
            cleaned_json = content.replace("```json", "").replace("```", "").strip()
            
            return json.loads(cleaned_json)
            
        except json.JSONDecodeError:
            print("!!! AI Mapping JSON Parsing Failed")
            # 실패 시 기본값 반환 로직 추가 가능
            return None
        
        except Exception as e:
            print(f"!!! AI Mapping Error: {e}")
            return None