import json
import logging
import re
from openai import OpenAI
from flask import current_app

logger = logging.getLogger(__name__)

class AIService:

    @staticmethod
    def get_client():
        """OpenAI 혹은 온프레미스 sLLM 클라이언트 생성.

        sLLM 경로는 connect 실패 시 빠른 폴백을 위해 max_retries=0, timeout=15초로 설정.
        OpenAI 본가 경로는 기본값(자체 재시도 포함)을 사용.
        """
        endpoint = current_app.config.get('SLLM_ENDPOINT')
        if endpoint:
            return OpenAI(base_url=endpoint, api_key="EMPTY", max_retries=0, timeout=15.0)
        return OpenAI(api_key=current_app.config['OPENAI_API_KEY'])

    @staticmethod
    def _get_router_client():
        """Router 전용 클라이언트 — sLLM 학습 모델은 intent JSON 분류 미학습.
        reflection_node 와 동일하게 항상 OpenAI 사용 (OPENAI_API_KEY 있을 때).
        """
        from openai import OpenAI
        api_key = current_app.config.get('OPENAI_API_KEY')
        if api_key:
            return OpenAI(api_key=api_key)
        # OPENAI_API_KEY 없으면 폴백: sLLM (정확도 저하 가능)
        return AIService.get_client()

    # ──────────────────────────────────────────────────────────────
    # Sprint 1 — Router 캐시 + Rule-based pre-filter (Phase 7.1)
    # ──────────────────────────────────────────────────────────────
    _ROUTER_CACHE = {}          # 질문 hash → 분류 결과
    _ROUTER_CACHE_MAX = 1024    # LRU 크기
    _ROUTER_CACHE_HITS = 0
    _ROUTER_CACHE_MISSES = 0

    # 명백한 패턴 — LLM 호출 없이 즉시 분류
    _GENERAL_PATTERNS = re.compile(
        r'(한국\s*수도|날씨|코드.*짜|python.*코드|영어.*번역|시간.*몇|오늘.*날짜)',
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize_question(q: str) -> str:
        """캐시 키 정규화 — 공백/조사 변형 흡수."""
        return re.sub(r'\s+', ' ', (q or '').strip().lower())[:400]

    @staticmethod
    def _try_fast_route(question: str):
        """LLM 없이 분류 가능한 패턴 즉시 처리 (None 반환 시 LLM 사용)."""
        q = question or ''
        # 0) GENERAL — 명백한 비수사 질문
        if AIService._GENERAL_PATTERNS.search(q):
            return {"intent": "GENERAL", "keyword": "", "labels": []}
        return None

    @staticmethod
    def route_question(question):
        """질문 의도 분기 및 핵심 키워드 추출 (최적화: 캐시 + 사전필터)."""
        # ① 사전필터 — 명백한 패턴은 즉시 반환
        fast = AIService._try_fast_route(question)
        if fast is not None:
            return fast

        # ② 캐시 조회
        key = AIService._normalize_question(question)
        cached = AIService._ROUTER_CACHE.get(key)
        if cached is not None:
            AIService._ROUTER_CACHE_HITS += 1
            return dict(cached)  # 얕은 복사로 호출자 변경 차단
        AIService._ROUTER_CACHE_MISSES += 1

        client = AIService._get_router_client()

        prompt = f"""
        당신은 범죄 수사 질문의 의도를 분석하는 지능형 라우터입니다.
        질문의 목표에 따라 아래 의도 중 하나로 분류하고, 검색에 필요한 핵심 키워드와 '예상 노드 레이블'을 추출하세요.

        [의도 종류]
        1. "PATH": 두 개체 사이의 최단 경로 추적 (예: "A와 B의 관계", "A에서 B로 가는 경로")
        2. "REPORT": 서술형 종합 분석/요약 보고서 (예: "이 사건 요약해줘", "전체 자금 흐름 분석")
           ⚠️ 집계/통계/정렬/COUNT/SUM/평균/합계/순위 같은 단순 수치 질의는 REPORT 가 아님 → QUERY
        3. "QUERY": 노드 검색, 관계 확장, 집계, 통계, 정렬, 필터링 등 Cypher 변환 가능한 모든 질의
           (예: "홍길동 연결 노드", "이 계좌의 이체 내역", "사건별 피의자 수", "이체 금액 합계",
                "금액 순 정렬", "최근 5건", "OSINT 도메인 노드", "신뢰도 1 이상 계좌")
        4. "GENERAL": 수사와 무관한 일반 상식/코딩/개념 질문 (예: "한국 수도는?")

        [중요 분류 규칙]
        - "몇 개", "총", "합계", "평균", "순위", "Top N", "최대", "최소", "정렬", "그룹별",
          "통계", "분포", "비율" → REPORT 가 아니라 **QUERY** (COUNT/SUM/ORDER BY Cypher 생성 가능)
        - REPORT 는 오직 서술형 답변이 필요한 "요약/분석/설명" 요청일 때만 선택

        [레이블 추측 — V4.0 통합 온톨로지 (25노드, V3.7 신규 포함)]
        CASE 레이어:
        - 사건/범죄/수사 -> vt_case
        - 진정서/신고/접수 -> vt_petition
        - 캠페인/클러스터/조직군집 -> pt_cluster  [V3.7 신규]

        PERSON 레이어:
        - 사람/피의자/피해자/참고인/용의자/익명/익명사용자/닉네임 -> vt_psn (익명은 is_anonymous=true)
        - 조직/단체/범죄조직/회사/기관/은행/검찰/경찰 -> vt_org

        OBJECT 레이어:
        - 계좌/은행/통장/대포통장 -> vt_bacnt
        - 전화/핸드폰/번호/SIM/사칭번호 -> vt_telno
        - IP/로그인/접속주소 -> vt_ip
        - 사이트/URL/도메인/웹 -> vt_site
        - 사이트 군집/피싱 캠페인/사이트 클러스터 -> site_cluster  [V3.7 신규]
        - 파일/악성코드/해시 -> vt_file
        - ID/계정/닉네임/아이디 -> vt_id (익명 가능 is_anonymous=true)
        - 이메일/메일주소 -> vt_email
        - 가상화폐/지갑/코인/블록체인 -> vt_crypto
        - 차량/번호판/자동차 -> vt_vhcl
        - 기기/스마트폰/PC/단말/중계기/relay/IMEI -> vt_dev (중계기는 dev_type='relay_station')
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

        [주요 관계 힌트 — 사칭 질문 처리 (V3.3 패턴)]
        - 사칭/위장/가장/스푸핑 관련 질문: vt_impersonation 이벤트 노드 경유
          V3.3 패턴: (수단노드) -[used_for]-> (vt_impersonation) -[targets]-> (vt_org)
          예) "국민은행 사칭 번호" -> labels: ["vt_telno", "vt_impersonation", "vt_org"]
              Cypher: MATCH (t:vt_telno)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org {{org_name: '국민은행'}}) RETURN t, imp, o
          예) "검찰 사칭 계정" -> labels: ["vt_id", "vt_impersonation", "vt_org"]
              Cypher: MATCH (i:vt_id)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org) RETURN i, imp, o
          예) "사칭 이벤트 전체 목록" -> labels: ["vt_impersonation"]
              Cypher: MATCH (imp:vt_impersonation) RETURN imp LIMIT 20
          ※ 구버전 impersonates 엣지는 deprecated — 신규 쿼리에 사용 금지

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
            # Router 는 OpenAI gpt-4o-mini 사용 (sLLM 학습 모델은 intent JSON 미학습)
            api_key = current_app.config.get('OPENAI_API_KEY')
            router_model = 'gpt-4o-mini' if api_key else current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o')
            resp = client.chat.completions.create(
                model=router_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            content = resp.choices[0].message.content.strip()
            result = json.loads(content)
        except Exception as e:
            logger.error(f"!!! Intent/Keyword Routing Error: {e}")
            words = question.split()
            result = {"intent": "QUERY", "keyword": words[0] if words else ""}

        # ③ 캐시 저장 (LRU 크기 초과 시 가장 오래된 항목 제거)
        if len(AIService._ROUTER_CACHE) >= AIService._ROUTER_CACHE_MAX:
            try: AIService._ROUTER_CACHE.pop(next(iter(AIService._ROUTER_CACHE)))
            except StopIteration: pass
        AIService._ROUTER_CACHE[key] = dict(result)
        return result

    # V3.3 POLE 온톨로지 엣지 방향 규칙 (source → target)
    _EDGE_DIRECTION_MAP = {
        # 역할 (Person → Case)
        "suspect_in":     ("vt_psn",      "vt_case"),
        "victim_in":      ("vt_psn",      "vt_case"),
        "witness_in":     ("vt_psn",      "vt_case"),
        "involves":       ("vt_case",     "vt_psn"),
        # 사건·진정서
        "filed_as":       ("vt_petition", "vt_case"),
        "clusters_with":  ("vt_petition", "vt_petition"),
        "related_case":   ("vt_case",     "vt_case"),
        # 소유 (Person → Object)
        "has_account":    ("vt_psn",      "vt_bacnt"),
        "controls":       ("vt_psn",      "vt_bacnt"),
        "owns_phone":     ("vt_psn",      "vt_telno"),
        "owns_vehicle":   ("vt_psn",      "vt_vhcl"),
        "used_ip":        ("vt_psn",      "vt_ip"),
        "member_of":      ("vt_psn",      "vt_org"),
        "works_at":       ("vt_psn",      "vt_org"),
        "uses_id":        ("vt_psn",      "vt_id"),
        # 금융 이벤트
        "from_account":   ("vt_bacnt",    "vt_transfer"),
        "to_account":     ("vt_transfer", "vt_bacnt"),
        "transferred_to": ("vt_bacnt",    "vt_bacnt"),
        # 통신 이벤트
        "caller":         ("vt_telno",    "vt_call"),
        "callee":         ("vt_call",     "vt_telno"),
        "sent_msg":       ("vt_telno",    "vt_msg"),
        "received_msg":   ("vt_msg",      "vt_telno"),
        # 이동·위치
        "recorded_in":    ("vt_vhcl",     "vt_movement"),
        "occurred_at":    ("vt_movement", "vt_loc"),
        # 귀속·메타
        "belongs_to":     ("vt_bacnt",    "vt_org"),
        "resolves_to":    ("vt_site",     "vt_ip"),
        # sourced_from: 모든 노드 타입 → vt_src (None = Any)
        # 버그수정 v3.7: ("vt_psn","vt_src") 제한 → 방향 교정이 vt_case 등에서 무작동
        "sourced_from":   (None,          "vt_src"),
        # ── v3.7 신규 엣지 ────────────────────────────────────────────
        "belongs_to_cluster":  ("vt_petition", "pt_cluster"),
        "used_in_device":      ("vt_telno",    "vt_dev"),
        "belongs_to_campaign": ("vt_site",     "site_cluster"),
        # 사칭 V3.3 2-홉 패턴
        "used_for":       ("vt_telno",    "vt_impersonation"),  # 수단 → 사칭이벤트
        "targets":        ("vt_impersonation", "vt_org"),       # 사칭이벤트 → 대상기관
        # 사칭 V3.2 레거시 (deprecated — 읽기 전용)
        "impersonates":   ("vt_telno",    "vt_org"),
        # 엔티티 해소
        "sameAs":         ("vt_psn",      "vt_psn"),
        "contradicts":    ("vt_psn",      "vt_psn"),
    }

    @staticmethod
    def _fix_relation_direction(cypher: str) -> str:
        """LLM이 생성한 Cypher 쿼리의 엣지 방향을 V3.3 규칙에 따라 자동 교정.

        패턴: (a:LabelA)-[:EDGE]->(b:LabelB)
        규칙표에 따라 LabelA/LabelB의 위치가 뒤집혀 있으면 화살표를 반전시킨다.
        """
        # MATCH 절 내의 관계 패턴을 추출 (v3.7 버그수정)
        # 기존 버그: 이중 브래킷 패턴 '-[[\w:]*[: ...' 이 표준 Cypher에 매칭 안 됨
        # 수정: <?-\[...\]->? 단일 브래킷으로 변경, 양방향(<-[]-) 모두 처리
        pattern = re.compile(
            r'\((\w+):(\w+)(?:\s*\{[^}]*\})?\s*\)'        # group(1)=var_a, group(2)=label_a
            r'\s*(<?-\[(?:\w+:)?:?(\w+)(?:\s*\{[^}]*\})?\]->?)'  # group(3)=full_rel, group(4)=edge_type
            r'\s*\((\w+):(\w+)(?:\s*\{[^}]*\})?\s*\)',    # group(5)=var_b, group(6)=label_b
            re.IGNORECASE
        )

        def _fix_match(m):
            full = m.group(0)
            rel = m.group(3)       # e.g. "-[:suspect_in]->" or "<-[:suspect_in]-"
            edge_type = m.group(4)
            label_a = m.group(2)
            label_b = m.group(6)

            rule = AIService._EDGE_DIRECTION_MAP.get(edge_type)
            if not rule:
                return full

            expected_src, expected_tgt = rule
            src_ok = lambda l: expected_src is None or l == expected_src
            tgt_ok = lambda l: expected_tgt is None or l == expected_tgt

            is_forward = not rel.startswith('<')  # -[...]-> vs <-[...]-

            if is_forward and tgt_ok(label_a) and src_ok(label_b):
                # -[...]-> 방향이 뒤집힌 경우 → <-[...]-로 교정
                flipped = '<' + rel[:-1]           # add < at front, drop trailing >
                return full.replace(rel, flipped, 1)
            elif not is_forward and src_ok(label_a) and tgt_ok(label_b):
                # <-[...]- 방향이 뒤집힌 경우 → -[...]->로 교정
                flipped = rel[1:] + '>'            # drop leading <, add > at end
                return full.replace(rel, flipped, 1)

            return full

        try:
            fixed = pattern.sub(_fix_match, cypher)
            if fixed != cypher:
                logger.info(f"[Direction Fix] 엣지 방향 자동 교정 적용됨")
            return fixed
        except Exception as e:
            logger.debug(f"[Direction Fix] 교정 스킵: {e}")
            return cypher

