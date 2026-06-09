import json
import logging
from openai import OpenAI
from flask import current_app

logger = logging.getLogger(__name__)

class AIService:

    @staticmethod
    def get_client():
        """OpenAI 혹은 온프레미스 sLLM 클라이언트 생성"""
        endpoint = current_app.config.get('SLLM_ENDPOINT')
        if endpoint:
            return OpenAI(base_url=endpoint, api_key="EMPTY")
        return OpenAI(api_key=current_app.config['OPENAI_API_KEY'])

    @staticmethod
    def route_question(question):
        """질문을 분석하여 의도 분기 및 핵심 키워드 추출 (최적화)"""
        client = AIService.get_client()

        prompt = f"""
        당신은 범죄 수사 질문의 의도를 분석하는 지능형 라우터입니다.
        질문의 목표에 따라 아래 의도 중 하나로 분류하고, 검색에 필요한 핵심 키워드와 '예상 노드 레이블'을 추출하세요.

        [의도 종류]
        1. "PATH": 두 개체 사이의 최단 경로 추적 (예: "A와 B의 관계", "A에서 B로 가는 경로")
        2. "REPORT": 특정 주제에 대한 심층 분석 보고서 (예: "이 사건 요약해줘", "전체 자금 흐름 분석")
        3. "QUERY": 노드 검색 및 관계 확장 (예: "홍길동 연결 노드", "이 계좌의 이체 내역")
        4. "GENERAL": 수사와 무관한 일반 상식/코딩/개념 질문 (예: "한국 수도는?")

        [레이블 추측 — v3.5 POLE 6레이어 온톨로지 (23노드)]
        CASE 레이어:
        - 사건/범죄/수사 -> vt_case
        - 진정서/신고/접수 -> vt_petition

        PERSON 레이어:
        - 사람/피의자/피해자/참고인/용의자 -> vt_psn
        - 조직/단체/범죄조직/회사/기관/은행/검찰/경찰 -> vt_org

        OBJECT 레이어:
        - 계좌/은행/통장/대포통장 -> vt_bacnt
        - 전화/핸드폰/번호/SIM/사칭번호 -> vt_telno
        - IP/로그인/접속주소 -> vt_ip
        - 사이트/URL/도메인/웹 -> vt_site
        - 파일/악성코드/해시 -> vt_file
        - ID/계정/닉네임/아이디 -> vt_id
        - 이메일/메일주소 -> vt_email
        - 가상화폐/지갑/코인/블록체인 -> vt_crypto
        - 차량/번호판/자동차 -> vt_vhcl
        - 기기/스마트폰/PC/단말 -> vt_dev
        - ATM/현금인출기 -> vt_atm

        LOCATION 레이어:
        - 위치/주소/좌표/기지국/CCTV -> vt_loc

        EVENT 레이어:
        - 이체/송금/거래/출금/입금 -> vt_transfer
        - 통화/전화기록/통화내역 -> vt_call
        - 접속/로그/접속기록 -> vt_access
        - 문자/메시지/채팅 -> vt_msg
        - 이동/LPR/교통카드/기지국이동 -> vt_movement
        - 사칭/위장/가장/스푸핑 이벤트 -> vt_impersonation  [V3.3 신설]

        [주요 관계 힌트 — v3.5 온톨로지 패턴]
        - 사칭/위장/스푸핑: (수단노드)-[used_for]->(vt_impersonation)-[targets]->(vt_org)
          예) "국민은행 사칭 번호" → MATCH (t:vt_telno)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org {{org_name:'국민은행'}}) RETURN t,imp,o
        - 사건 관련 인물: (vt_psn)-[suspect_in|victim_in|witness_in]->(vt_case)
          예) "C001 사건 피의자" → MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case {{flnm:'C001'}}) RETURN p,c
        - 사건 증거 직접 연결: (vt_case)-[eg_used_account|eg_used_phone|eg_used_ip]->(vt_bacnt|vt_telno|vt_ip)
        - 유사 사건 연결: (vt_case)-[related_case]->(vt_case)
        - 플랫폼 운영자: (vt_psn)-[operates]->(vt_site)
        - 공범 모집: (vt_psn)-[recruits]->(vt_psn)
        - 협박 관계: (vt_psn)-[blackmails]->(vt_psn)
        - 서버 호스팅: (vt_ip)-[hosts]->(vt_site)
        - 파일 증거: (vt_site|vt_msg)-[contains_file]->(vt_file)
        - ATM 위치: (vt_atm)-[located_at]->(vt_loc)
        - 네트워크 접속: (vt_access)-[accessed_from]->(vt_ip), (vt_access)-[accessed_to]->(vt_site)
        - 메시지 발신/수신: (vt_telno)-[sent_msg]->(vt_msg)-[received_msg]->(vt_telno)
        - 계좌 언급(보이스피싱): (vt_msg)-[mentions_account]->(vt_bacnt)
        - 차량 소유: (vt_psn)-[owns_vehicle]->(vt_vhcl) / 운행: (vt_psn)-[drives]->(vt_vhcl)
        - 전화 명의자: (vt_telno)-[registered_to]->(vt_psn)

        [출력 JSON 포맷]
        {{
            "intent": "PATH" | "QUERY" | "REPORT" | "GENERAL",
            "keyword": "핵심 검색어 (고유명사 또는 식별자 우선)",
            "labels": ["예상레이블1", "예상레이블2"],
            "term1": "경로시작 개체명 (PATH 전용)",
            "term2": "경로끝 개체명 (PATH 전용)"
        }}

        질문: {question}
        """

        try:
            resp = client.chat.completions.create(
                model=current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            content = resp.choices[0].message.content.strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"!!! Intent/Keyword Routing Error: {e}")
            words = question.split()
            return {"intent": "QUERY", "keyword": words[0] if words else ""}
