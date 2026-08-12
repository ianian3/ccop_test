"""
V4.6 시간순 연속성 — 쿼리 후처리 주입 (순수 로직, DB 무관).

[시간순 연속성 적용] ON 시, sLLM이 생성한 기본 Cypher의 경로를 파싱해
인접 구간에 T(e_i) <= T(e_{i+1}) 조건을 결정론적으로 주입한다. 시간 정확성을
sLLM 성능이 아닌 온톨로지 분류표(SoT)에 의존시킨다.

설계: docs/TEMPORAL_CONTINUITY_QUERY_DESIGN.md
분류: docs/TEMPORAL_CONTINUITY_EDGE_CLASSIFICATION_20260812.md (V/E/N)
  V형 = 경유 Event 노드 시각 · E형 = 엣지 시각속성 · N형 = 없음(warnings)
"""
from __future__ import annotations
import re
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as O

# Event 노드 라벨 → 발생시각 속성 (V형 기준)
EVENT_VT = {
    'vt_transfer': 'dlng_dt', 'vt_call': 'call_strt_dt', 'vt_access': 'access_dt',
    'vt_msg': 'dsptch_dt', 'vt_movement': 'timestamp', 'vt_impersonation': 'start_dt',
}
# 도메인/레인지 개념명 (Event) — V형 판정
EVENT_CONCEPTS = {'Transfer', 'Call', 'Access', 'Message', 'Movement', 'Impersonation', 'Event'}
_EVENT_LC = {c.lower() for c in EVENT_CONCEPTS}
# E형 시각 속성 우선순위
E_TIME_PROPS = ['valid_from', 'transfer_date', 'exchanged_at', 'first_seen', 'detected_at']


def classify_edge(edge_label):
    """엣지 라벨 → ('V'|'E'|'N', 시각속성|None). 온톨로지 분류표(SoT) 파생."""
    spec = O.RELATIONSHIPS.get(edge_label, {})
    dom = str(spec.get('domain', '')); rng = str(spec.get('range', ''))
    concepts = set()
    for x in (dom + '|' + rng).replace('(', '').replace(')', '').split('|'):
        x = x.strip()
        concepts.add(x.capitalize() if x.lower() in _EVENT_LC else x)
    if concepts & EVENT_CONCEPTS:
        return ('V', None)              # 시각은 경유 Event 노드에서
    props = spec.get('properties', [])
    if isinstance(props, dict):
        props = list(props.keys())
    for p in E_TIME_PROPS:
        if p in props:
            return ('E', p)
    return ('N', None)


def _split_var_label(s):
    """'a:vt_bacnt {..}' → ('a', 'vt_bacnt'). 다중라벨은 첫 번째."""
    s = s.split('{')[0].strip()
    if ':' in s:
        var, label = s.split(':', 1)
        return var.strip(), label.strip().split(':')[0].split('|')[0].strip()
    return s.strip(), None


# 노드 (…) 또는 관계 (<-)[…](->) 를 순서대로 매칭
_TOKEN = re.compile(r'\(([^()]*)\)|(<-|-)\[([^\]]*)\](->|-)')


def parse_path(cypher):
    """MATCH 경로를 [('node',var,label) | ('edge',var,label,dir)] 시퀀스로 파싱."""
    m = re.search(r'\bMATCH\b(.+?)(?:\bWHERE\b|\bRETURN\b|\bWITH\b|\$\$|$)', cypher, re.S | re.I)
    if not m:
        return []
    seg = m.group(1)
    seq = []
    for mt in _TOKEN.finditer(seg):
        if mt.group(1) is not None:                       # 노드
            var, label = _split_var_label(mt.group(1))
            seq.append(('node', var, label))
        else:                                             # 엣지
            left, body, right = mt.group(2), mt.group(3), mt.group(4)
            var, label = _split_var_label(body)
            direction = '->' if right == '->' else ('<-' if left == '<-' else '-')
            seq.append(('edge', var, label, direction))
    return seq


def _time_expr(edge, prev_node, next_node):
    """엣지의 기준시각 표현식(str) 또는 None(N형/참조불가)."""
    _, evar, elabel, _ = edge
    cls, attr = classify_edge(elabel)
    if cls == 'E':
        return f"date({evar}.{attr})" if evar else None
    if cls == 'V':
        for nd in (prev_node, next_node):                 # 경유 Event 노드
            if nd and nd[0] == 'node' and nd[2] in EVENT_VT and nd[1]:
                return f"date({nd[1]}.{EVENT_VT[nd[2]]})"
        return None                                        # Event 미명시 → 강등
    return None                                            # N형


def _add_where(cypher, conds):
    """조건들을 WHERE 에 AND 결합. 기존 WHERE 있으면 확장, 없으면 RETURN 앞 신설."""
    if not conds:
        return cypher
    clause = ' AND '.join(conds)
    if re.search(r'\bWHERE\b', cypher, re.I):
        return re.sub(r'\bWHERE\b', f'WHERE ({clause}) AND', cypher, count=1, flags=re.I)
    return re.sub(r'\b(RETURN|WITH)\b', f'WHERE {clause} \\1', cypher, count=1, flags=re.I)


def inject(cypher):
    """시간순 연속성 조건 주입. 반환: (cypher', warnings[])."""
    seq = parse_path(cypher)
    edges = []
    for i, s in enumerate(seq):
        if s[0] == 'edge':
            prev = seq[i - 1] if i > 0 else None
            nxt = seq[i + 1] if i + 1 < len(seq) else None
            edges.append((s, prev, nxt))
    if len(edges) < 2:
        return cypher, []                                  # 단일 엣지: 선후 없음

    T = [_time_expr(e, p, n) for (e, p, n) in edges]
    labels = [e[0][2] for e in edges]

    conds, warnings = [], []
    for i in range(len(T) - 1):
        if T[i] and T[i + 1]:
            if T[i] == T[i + 1]:
                continue  # 동일 이벤트/시각 경유(예: 한 이체의 from/to) → 자명(T<=T), 생략
            conds.append(f"{T[i]} <= {T[i + 1]}")
        else:
            missing = labels[i] if not T[i] else labels[i + 1]
            warnings.append(f"구간 [{labels[i]} → {labels[i + 1]}]는 시간기준 없음(N형: {missing})")

    return _add_where(cypher, conds), warnings
