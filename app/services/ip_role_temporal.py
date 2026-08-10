"""
V4.6 ip_role 시간축(bitemporal) 구간 계산 — 순수 모듈 (DB 의존 0).

used_ip 엣지의 valid_from/to 를 시간구간으로 분할하여 구간별 IP 역할(ip_role)을
산출한다. rdb_to_graph_service 가 재계산(S4) 시 이 함수를 호출한다.

설계: docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md
핵심 원칙:
  - sameAs 해소 **후** entity 기준으로 판정 (subject 기준 선계산은 오분류; HANDOFF G12)
  - 인접 동일 role 구간은 coalesce (구간 폭발 방지)
  - theta_shared / call_center 판정은 v4.6 #3(분포기반 임계)에서 주입 — 여기선 파라미터
"""
from __future__ import annotations

# valid_from/to 미상 처리용 sentinel (ISO 문자열은 사전순 == 시간순)
_NEG = '0000-01-01'   # valid_from 미상 → 최소
_INF = '9999-12-31'   # valid_to 미상(진행중) → 최대


def _vf(edge):
    v = edge.get('valid_from')
    return _NEG if v in (None, '', 'null') else str(v)


def _vt(edge):
    v = edge.get('valid_to')
    return _INF if v in (None, '', 'null') else str(v)


def classify_role(entity_cnt, *, theta_shared=5, is_hosting=False,
                  is_call_center=False):
    """구간 내 역할 분류.

    우선순위: hosting(대역) > single_user(1) > call_center(착신전용) >
              shared_small(2..θ-1) > shared(≥θ).
    hosting 을 최우선으로 두는 이유: 호스팅 대역은 사용자 수와 무관한 인프라라
    entity_cnt 로 덮어써선 안 된다.
    """
    if entity_cnt <= 0:
        return None
    if is_hosting:
        return 'infra'
    if entity_cnt == 1:
        return 'single_user'
    if is_call_center:
        return 'call_center'
    if entity_cnt < theta_shared:
        return 'shared_small'
    return 'shared'


def compute_ip_role_timeline(edges, sameas_map=None, *, theta_shared=5,
                             is_hosting=False, call_center_pred=None):
    """used_ip 엣지들로부터 구간별 ip_role timeline 산출.

    Args:
        edges: [{'subject': id, 'valid_from': 'YYYY-MM-DD',
                 'valid_to': 'YYYY-MM-DD'|None}, ...]  (한 IP에 붙는 used_ip 전체)
        sameas_map: {subject_id: entity_id} — sameAs 해소맵(없으면 subject=entity)
        theta_shared: shared_small/shared 경계 (v4.6 #3에서 분포기반 산출 예정)
        is_hosting: 이 IP가 호스팅 대역인지
        call_center_pred: fn(active_edges)->bool — 착신전용 판정(주입, 기본 None)

    Returns:
        [{'from','to','role','entity_cnt','subject_cnt'}, ...] (coalesce 적용).
        ip_role_current 는 ip_role_current(timeline) 으로 얻는다.
    """
    if not edges:
        return []
    sameas_map = sameas_map or {}

    # 1) 경계점: 모든 valid_from/to (중복 제거·정렬; ISO 문자열 사전순)
    bounds = sorted({_vf(e) for e in edges} | {_vt(e) for e in edges})

    # 2) 인접 구간 [b0, b1) 별 활성 주체 → entity 해소(G12) → 분류
    raw = []
    for b0, b1 in zip(bounds, bounds[1:]):
        active = [e for e in edges if _vf(e) <= b0 and _vt(e) > b0]
        if not active:
            continue  # 공백 구간(활성 주체 없음)
        subjects = {e['subject'] for e in active}
        entities = {sameas_map.get(s, s) for s in subjects}
        is_cc = bool(call_center_pred(active)) if call_center_pred else False
        role = classify_role(len(entities), theta_shared=theta_shared,
                             is_hosting=is_hosting, is_call_center=is_cc)
        raw.append({'from': b0, 'to': b1, 'role': role,
                    'entity_cnt': len(entities), 'subject_cnt': len(subjects)})

    # 3) coalesce: 맞닿은 동일 role 구간 병합
    return _coalesce(raw)


def _coalesce(timeline):
    if not timeline:
        return []
    out = [dict(timeline[0])]
    for seg in timeline[1:]:
        last = out[-1]
        # 맞닿음(경계 일치) + 동일 role → 병합. 대표 cnt 는 보수적으로 max.
        if seg['role'] == last['role'] and seg['from'] == last['to']:
            last['to'] = seg['to']
            last['entity_cnt'] = max(last['entity_cnt'], seg['entity_cnt'])
            last['subject_cnt'] = max(last['subject_cnt'], seg['subject_cnt'])
        else:
            out.append(dict(seg))
    return out


def ip_role_current(timeline):
    """timeline 최신 구간(마지막)의 role — vt_ip.ip_role_current 값."""
    return timeline[-1]['role'] if timeline else None
