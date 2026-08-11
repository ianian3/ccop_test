"""
V4.6 #2 지연 확장(lazy expansion) — 순수 로직 (DB 의존 0).

집약 노드(vt_access/vt_msg)의 event_count/sample_event_ids 를 원본 RDB로
드릴다운하기 위한 판정·조회대상 생성. 저장소는 원본 RDB(Bridge Key) 재사용 —
신규 저장소를 만들지 않는다(#2 설계의 핵심).

설계: docs/ONTOLOGY_V46_LAZY_EXPANSION_DESIGN.md
- E2(본 모듈): should_expand·build_expansion·sample_ids — DB 무관, 여기서 완결
- E3(조회 어댑터)·E4(적재): 운영 DB 의존, 별도
"""
from __future__ import annotations

# 집약 노드 → (원본 RDB 테이블, PK 컬럼) Bridge Key 매핑.
# ENTITIES[*].description 의 'Bridge Key: lgn_sn → TB_SYS_LGN_EVT' 와 일치.
BRIDGE_KEY = {
    'vt_access': ('TB_SYS_LGN_EVT', 'LGN_SN'),
    'vt_msg':    ('TB_TELNO_SMS_MSG', 'MSG_SN'),   # 메신저 원본은 TB_CHAT_MSG 병행
}

SAMPLE_CAP = 20   # sample_event_ids 표본 상한


def should_expand(event_count, *, requested=False, evidence=False, theta=100):
    """지연 확장 3조건 — 하나라도 충족하면 원본 조회(True).

    - requested: 수사 관심(노드 선택/확장 요청)
    - evidence:  증거 특정(개별 이벤트 필요)
    - event_count >= theta: 임계 초과(표본만으론 부족한 대량 집약)
    미충족 시 event_count·sample_event_ids(표본)만으로 응답(경량, 원본 조회 안 함).
    """
    if event_count is None:
        event_count = 0
    return bool(requested or evidence or event_count >= theta)


def build_expansion(label, pks):
    """집약노드 label + 원본 PK 목록 → 원본 조회 대상 명세.

    Bridge Key 매핑으로 (원본 테이블, PK 컬럼)을 확정한다. 실제 SELECT 실행은
    조회 어댑터(E3, 운영 DB)의 몫 — 여기서는 무엇을 어디서 읽을지만 결정한다.

    Returns: {'table', 'pk_col', 'pks', 'count'}
    Raises: ValueError — Bridge Key 없는(지연확장 미지원) 노드.
    """
    if label not in BRIDGE_KEY:
        raise ValueError(f'지연확장 미지원 노드: {label} (Bridge Key 없음)')
    table, pk_col = BRIDGE_KEY[label]
    ids = list(pks or [])
    return {'table': table, 'pk_col': pk_col, 'pks': ids, 'count': len(ids)}


def sample_ids(all_pks, cap=SAMPLE_CAP):
    """원본 PK 전체 → sample_event_ids 표본(상한 cap).

    앞에서부터 대표 표본을 취한다(전량은 event_count 가 가리키고, 상세는
    Bridge Key 재조회). 그래프 노드를 경량으로 유지하기 위함.
    """
    ids = list(all_pks or [])
    return ids[:cap]
