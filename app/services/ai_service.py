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
        """자연어 질문을 Cypher 쿼리로 변환 (온톨로지 인식 강화)"""
        client = AIService.get_client()
        
        system_instruction = "You are a Cypher query generator for KICS-compliant cybercrime investigation graph database. Output ONLY the raw Cypher query string. Do not use Markdown formatting. Do not provide any explanation."
        
        # 🎯 온톨로지 인식 프롬프트
        prompt = f"""
[KICS 온톨로지 구조]

=== 엔티티 계층 (Entity Hierarchy) ===

1. Case (사건) - vt_flnm
   속성: flnm (접수번호), police_station (관서), crime_type (범죄유형: 몸캠피싱, 보이스피싱 등)
   
2. FinancialEvidence (금융증거)
   - BankAccount (계좌) - vt_bacnt
     속성: actno, bacnt (계좌번호), bank (은행), account (계좌)
   
3. DigitalEvidence (디지털증거)
   - WebTrace (사이트) - vt_site
     속성: site, url, domain (사이트/URL)
   - FileTrace (파일) - vt_file
     속성: file, filename, filepath (파일명/경로)
   - NetworkTrace (IP) - vt_ip
     속성: ip, ip_addr, ipaddr (IP주소)

4. Suspect (용의자)
   - DigitalIdentity (ID) - vt_id
     속성: id, user_id, userid (사용자ID)
   - ContactInfo (전화) - vt_telno
     속성: telno, phone (전화번호)
   - Person (인물) - vt_psn
     속성: name (이름)

5. PhysicalEvidence (물리증거)
   - ATM - vt_atm
     속성: atm, atm_id (ATM ID)

=== 의미론적 관계 (Semantic Relationships) ===

- used_account: 사건 → 계좌 (계좌 사용)
- digital_trace: 사건 → 디지털증거 (디지털 흔적)
- used_phone: 사건 → 전화 (전화 사용)
- related_to: 일반 관계

=== 범죄 패턴 (Crime Patterns) ===

몸캠피싱: (vt_flnm)-[:digital_trace]->(vt_site)-[:related_to]->(vt_file)
보이스피싱: (vt_flnm)-[:used_phone]->(vt_telno)-[:used_account]->(vt_bacnt)

=== 개념 매핑 (Concept Mapping) ===

"금융증거" → (n:vt_bacnt) 또는 WHERE n.ontology_type = 'FinancialEvidence'
"디지털증거" → (n:vt_site) OR (n:vt_file) OR (n:vt_ip) 또는 WHERE n.ontology_type = 'DigitalEvidence'
"계좌" → (n:vt_bacnt)
"사이트", "URL" → (n:vt_site)
"IP", "IP주소" → (n:vt_ip)
"전화", "전화번호" → (n:vt_telno)
"파일" → (n:vt_file)
"사건" → (n:vt_flnm)
"몸캠피싱" → WHERE n.crime_type CONTAINS '몸캠'
"보이스피싱" → WHERE n.crime_type CONTAINS '보이스'

=== 쿼리 규칙 (Query Rules) ===

1. 노드 레이블은 vt_* 형식 사용 (vt_flnm, vt_bacnt, vt_site 등)
2. 문자열은 반드시 단일 따옴표 (') 사용
3. 부분 일치는 CONTAINS 사용 (NOT regex =~)
4. 속성 검색은 OR로 여러 속성 검색 가능
5. 결과 반환: id(v), labels(v), properties(v)
6. 기본 제한: LIMIT 30
7. PostgreSQL 캐스팅 사용 금지 (::text, ::graphid 등)

[Examples]
✅ Good: WHERE v.flnm CONTAINS '2019-001' OR v.bacnt CONTAINS '2019-001'
❌ Bad:  WHERE v.flnm CONTAINS "2019-001"
✅ Good: MATCH (n:vt_bacnt) RETURN id(n), labels(n), properties(n) LIMIT 30
✅ Good: MATCH (case:vt_flnm)-[:used_account]->(account:vt_bacnt) RETURN case, account

질문: "{question}"

Cypher 쿼리:
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
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            content = resp.choices[0].message.content.strip()
            # 첫 번째 단어만 반환 (리스트가 아닌 문자열)
            if ',' in content:
                keyword = content.split(',')[0].strip()
            else:
                keyword = content
            
            return keyword  # 단일 문자열 반환
            
        except Exception as e:
            print(f"!!! Keyword Extraction Error: {e}")
            # 실패 시 단순 단어 분리
            return question.split()[:4]

    @staticmethod
    def generate_rag_report(elements, context_texts):
        """그래프 조회 결과 기반 수사 보고서 생성"""
        client = AIService.get_client()
        
        # 온톨로지 분석 추가
        ontology_info = ""
        if elements:
            try:
                from app.services.ontology_service import SemanticAnalyzer
                semantic_analysis = SemanticAnalyzer.analyze(elements, context_texts)
                ontology_info = "\n\n[온톨로지 분석]\n" + semantic_analysis.get('summary', '')
            except:
                pass
        
        # 컨텍스트 제한 (너무 길면 OpenAI 토큰 초과)
        safe_context = str(context_texts[:80]) + ontology_info 
        
        prompt = f"""
        [사이버 범죄 수사 그래프 분석 보고서 작성]
        
        당신은 사이버 범죄 수사 전문가입니다. 
        그래프 데이터베이스에서 조회된 결과를 바탕으로 간결하고 명확한 수사 보고서를 작성하세요.
        
        [조회 결과 데이터]
        {safe_context}
        
        [보고서 작성 가이드]
        1. **분석 개요**: 조회 결과 요약 (노드 개수, 주요 패턴)
        2. **핵심 발견사항**: 중요한 연결 관계 및 패턴
        3. **수사 제안사항**: 추가 수사 방향 또는 주목할 점
        
        보고서:
        """
        
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            return resp.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"!!! RAG Report Gen Error: {e}")
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
                model="gpt-4o",
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
            print(f"!!! Schema Mapping Error: {e}")
            return {"error": str(e)}