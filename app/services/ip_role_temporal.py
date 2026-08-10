"""
V4.6 ip_role 시간축(bitemporal) 구간 계산 + call_center 분포임계 — 순수 모듈 (DB 의존 0).

used_ip 엣지의 valid_from/to 를 시간구간으로 분할하여 구간별 IP 역할(ip_role)을
산출하고(#1), call_center 경계를 분포 기반 이상치로 산출한다(#3).
rdb_to_graph_service 가 재계산(S4) 시 이 함수들을 호출한다.

설계: docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md
분류 정의(번들 CLAUDE.md 실측): single_user(entity 1) · shared_small(2..θ-1) ·
  call_center(entity ≥ θ) · infra(hosting). θ(call_center 경계)는 기존 고정 5(임의값)를
  #3에서 분포기반으로 대체 — 이 데이터는 5↑ 32개·10↑ 12개로 골이 없어 고정값 근거 약함.
핵심 원칙:
  - sameAs 해소 **후** entity 기준으로 판정 (subject 기준 선계산은 오분류; HANDOFF G12)
  - 인접 동일 role 구간은 coalesce (구간 폭발 방지)
"""
from __future__ import annotations
import math

# valid_from/to 미상 처리용 sentinel (ISO 문자열은 사전순 == 시간순)
_NEG = '0000-01-01'   # valid_from 미상 → 최소
_INF = '9999-12-31'   # valid_to 미상(진행중) → 최대


def _vf(edge):
    v = edge.get('valid_from')
    return _NEG if v in (None, '', 'null') else str(v)


def _vt(edge):
    v = edge.get('valid_to')
    return _INF if v in (None, '', 'null') else str(v)


def _median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0
    m = n // 2
    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2


def classify_role(entity_cnt, *, theta_call_center=5, is_hosting=False):
    """구간 내 역할 분류 (번들 CLAUDE.md 실측 정의).

    우선순위: hosting(대역) > single_user(1) > shared_small(2..θ-1) > call_center(≥θ).
    - hosting 최우선: 호스팅 대역은 사용자 수와 무관한 인프라라 덮어써선 안 됨.
    - call_center = 다수 실체가 공유하는 상위 구간(콜센터 인프라 IP). θ 는 #3 분포임계.
    """
    if entity_cnt <= 0:
        return None
    if is_hosting:
        return 'infra'
    if entity_cnt == 1:
        return 'single_user'
    if entity_cnt < theta_call_center:
        return 'shared_small'
    return 'call_center'


def call_center_threshold(entity_cnts, *, method='percentile', p=98, k=3.0, floor=2):
    """공유 IP(entity_cnt≥floor)의 분포에서 call_center 경계 θ 산출 (#3).

    고정 임계(5)는 이 데이터에 뚜렷한 골이 없어 근거가 약하므로, 분포의 꼬리로 경계를
    잡는다. entity_cnt 는 대부분 1(single)이라 floor 이상(=공유)만 대상으로 한다.

    Args:
        entity_cnts: IP별 linked_entity_cnt 리스트(전체; 내부에서 floor 이상만 사용)
        method: 'percentile'(상위 p 백분위) | 'mad'(median + k·MAD, 로버스트)
        p:  percentile 기준(기본 98 = 상위 2%)
        k:  mad 배수(기본 3.0)
        floor: 공유로 볼 최소 entity_cnt(기본 2). 반환 θ 는 항상 floor+1 이상.
    Returns:
        int θ — classify_role(theta_call_center=θ) 로 사용.
    """
    vals = sorted(v for v in entity_cnts if v is not None and v >= floor)
    if not vals:
        return floor + 1
    if method == 'percentile':
        idx = min(len(vals) - 1, int(math.ceil(p / 100.0 * len(vals))) - 1)
        th = vals[max(0, idx)]
    elif method == 'mad':
        med = _median(vals)
        mad = _median([abs(v - med) for v in vals]) or 1
        th = med + k * mad
    else:
        raise ValueError(f'unknown method: {method}')
    return max(floor + 1, int(round(th)))


def compute_ip_role_timeline(edges, sameas_map=None, *, theta_call_center=5,
                             is_hosting=False):
    """used_ip 엣지들로부터 구간별 ip_role timeline 산출.

    Args:
        edges: [{'subject': id, 'valid_from': 'YYYY-MM-DD',
                 'valid_to': 'YYYY-MM-DD'|None}, ...]  (한 IP에 붙는 used_ip 전체)
        sameas_map: {subject_id: entity_id} — sameAs 해소맵(없으면 subject=entity)
        theta_call_center: call_center 경계(#3 call_center_threshold 산출값 주입)
        is_hosting: 이 IP가 호스팅 대역인지
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
        role = classify_role(len(entities), theta_call_center=theta_call_center,
                             is_hosting=is_hosting)
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
