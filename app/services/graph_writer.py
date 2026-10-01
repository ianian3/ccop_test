"""
공용 그래프 쓰기 계층 (2026-10-01 정합 2단계 2a).

그래프에 쓰는 경로가 13갈래(RDB 적재기·ETL·모델러·통합 빌더·OSINT·ingest_* 등)로 나뉘어 MERGE 키·정규화·
이스케이프·집계 규칙이 제각각이던 것을 한 곳으로 모은다. 모든 규칙은 SoT(KICSCrimeDomainOntology)에서 온다.

  키        NODE_ID_STANDARD.canonical_field (복합키 '(platform, id_val)' 포함)
            ID 가 없고 synthesize 규칙이 있으면 출처 범위 결정적 ID — 예) vt_psn: 'psn:{scope}:{name}' (A안)
  정규화    normalize_key (계좌 하이픈 제거·전화 숫자만) + 이메일 계정 소문자 — MERGE 와 MATCH 에 똑같이
  허용 목록 라벨·엣지·방향(edge_rules)·속성(ENTITIES + 파생 등록부 + 공통 그룹 / RELATIONSHIPS + EDGE_META_SCHEMA)
            mode='strict' 거부 · 'warn' 기록 후 기록 · 'off' 검사 생략(식별자 안전 검사는 항상)
  값        app.database.cypher_str (백슬래시 2배 + '') — AgensGraph 실측 규칙
  쓰기      MERGE … SET n += {…} (다른 적재기가 넣은 속성을 지우지 않음), UNWIND 일괄
  집계      RELATIONSHIPS[e]['aggregation'] (min·max·sum·union) — 같은 쌍을 한 엣지로 접는다(배치 범위)
  통계      엣지는 MATCH 된 건수를 실제로 센다(양끝 노드가 없으면 'edges_unmatched')

사용:
    w = GraphWriter(cur, 'ccop_ep_integrated', scope='EP5')
    w.node('vt_bacnt', {'account_no': '110-123-456', 'bank_cd': '004'})
    w.edge('has_account', ('vt_psn', {'name': '김철수'}), ('vt_bacnt', {'account_no': '110123456'}))
    stats = w.flush()

주의: 집계는 이 Writer 인스턴스(한 적재 실행) 안에서만 접는다. 기존 DB 엣지 값과 합치지 않으므로
같은 원천을 다시 적재하면 같은 값이 다시 쓰인다(멱등). 원천을 나눠 여러 번 적재하면 마지막 값이 남는다.
"""
import json
import logging
import re

from app.database import cypher_str, safe_ident, safe_set_graph_path, validate_graph_path
from app.services.ontology_service import KICSCrimeDomainOntology as O

logger = logging.getLogger(__name__)


class GraphWriteError(ValueError):
    """SoT 정책 위반(strict) 또는 키를 만들 수 없는 입력."""


def _lit(v):
    """Cypher 리터럴. 문자열은 cypher_str, 리스트·딕트는 JSON 문자열로 저장."""
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (list, tuple, dict, set)):
        v = json.dumps(list(v) if isinstance(v, (set, tuple)) else v, ensure_ascii=False, default=str)
    return f"'{cypher_str(v)}'"


def _map(d):
    return '{' + ', '.join(f'{safe_ident(k, "속성 키")}: {_lit(v)}' for k, v in d.items()) + '}'


def _key_fields(label):
    canon = (O.NODE_ID_STANDARD.get(label) or {}).get('canonical_field')
    if not canon:
        return []
    return [f.strip() for f in canon.strip('()').split(',')]


class GraphWriter:
    MODES = ('strict', 'warn', 'off')

    def __init__(self, cur, graph, mode='strict', scope=None, batch_size=500, prop_mode=None, key_override=None):
        """mode: 라벨·엣지·방향·키 정책 / prop_mode: 사전 밖 속성 정책(기본 mode 와 같음).
        예) CSV ETL 은 구조 strict + 속성 warn — 사용자가 고른 임의 열을 속성으로 싣는 도구라서.
        key_override: {라벨: [키 필드]} — 사용자가 키를 직접 고르는 자유 설계(모델러)용. strict 에선 SoT 와 다르면 거부."""
        if not validate_graph_path(graph):
            raise GraphWriteError(f'허용되지 않는 그래프명: {graph!r}')
        if mode not in self.MODES or (prop_mode or mode) not in self.MODES:
            raise GraphWriteError(f'mode 는 {self.MODES} 중 하나: {mode!r}/{prop_mode!r}')
        self.prop_mode = prop_mode or mode
        self._key_override = {}
        self.cur, self.graph, self.mode, self.scope, self.batch_size = cur, graph, mode, scope, batch_size
        self._labels = {v['label'] for v in O.ENTITIES.values()}
        self._rules = O.edge_rules()
        common = set(O.ATTRIBUTE_DICTIONARY.get('common_attrs', {})) | {a for g in O.NODE_COMMON_GROUPS.values() for a in g}
        derived = {}
        for a, d in O.DERIVED_PROPERTY_REGISTRY.items():
            for l in str(d.get('node', '')).split('|'):
                derived.setdefault(l.strip(), set()).add(a)
        self._node_props = {v['label']: set(v.get('properties', [])) | set(v.get('attributes', []))
                            | derived.get(v['label'], set()) | common for v in O.ENTITIES.values()}
        self._edge_meta = set(O.EDGE_META_SCHEMA) | {a for g in getattr(O, 'EDGE_COMMON_GROUPS', {}).values() for a in g}
        self._nodes = {}        # label → {key_tuple: props}
        self._edges = {}        # (etype, src_label, dst_label) → {(skey, dkey): props}
        self.stats = {'nodes': 0, 'edges': 0, 'edges_unmatched': 0, 'rejected': [], 'warnings': []}
        for label, fields in (key_override or {}).items():
            fields = [safe_ident(f, '키 필드') for f in fields]
            if _key_fields(label) and sorted(fields) != sorted(_key_fields(label)):
                self._violation(f'{label}: 키 {fields} ≠ SoT 정경 키 {_key_fields(label)}')
            self._key_override[label] = fields
        safe_set_graph_path(cur, graph)

    # ── 정책 ────────────────────────────────────────────────────────
    def _violation(self, msg, prop=False):
        mode = self.prop_mode if prop else self.mode
        if mode == 'strict':
            raise GraphWriteError(msg)
        if mode == 'warn':                             # 같은 경고는 한 번만 기록하고 횟수만 센다
            cnt = self.stats.setdefault('warning_counts', {})
            if msg not in cnt:
                self.stats['warnings'].append(msg)
                logger.warning('[GraphWriter] %s', msg)
            cnt[msg] = cnt.get(msg, 0) + 1

    def _check_label(self, label):
        safe_ident(label, '라벨')
        if label not in self._labels:
            self._violation(f'SoT 밖 노드 라벨: {label}')

    def _clean(self, props):
        return {k: v for k, v in (props or {}).items() if v is not None and v != ''}

    # ── 키 ──────────────────────────────────────────────────────────
    def _resolve_key(self, label, props, scope=None):
        """props 에서 정경 키를 찾고(없으면 synthesize) 정규화해 (key_dict, props) 반환."""
        props = dict(props)
        fields = self._key_override.get(label) or _key_fields(label)
        if not fields:                                   # SoT 밖 라벨(warn/off 모드) — 첫 속성을 키로
            if not props:
                raise GraphWriteError(f'{label}: 키로 쓸 속성이 없음')
            fields = [next(iter(props))]
        missing = [f for f in fields if props.get(f) in (None, '')]
        if missing:
            syn = (O.NODE_ID_STANDARD.get(label) or {}).get('synthesize')
            src = props.get(syn['from']) if syn else None
            sc = 'g' if (syn or {}).get('scope') == 'global' else (scope or self.scope)   # global = EP 간 공유
            if syn and fields == _key_fields(label) and len(fields) == 1 and src not in (None, '') and sc:
                props[fields[0]] = f"{syn['prefix']}:{sc}:{str(src).strip()}"
            else:
                hint = f" (또는 {syn['from']} + scope)" if syn else ''
                raise GraphWriteError(f'{label}: 키 {missing} 없음{hint}')
        key = {}
        for f in fields:
            v = O.normalize_key(label, f, props[f])
            if label == 'vt_id' and f == 'id_val' and str(props.get('platform', '')).lower() == 'email':
                v = v.lower()
            key[f] = v
            props[f] = v
        return key, props

    def key_for(self, label, props, scope=None):
        """버퍼에 넣지 않고 정규화된 키만 계산 — 호출자가 같은 노드를 모아 메타(ep_origin 등)를 붙일 때."""
        self._check_label(label)
        return self._resolve_key(label, self._clean(props), scope)[0]

    # ── 노드 ────────────────────────────────────────────────────────
    def node(self, label, props, scope=None):
        """노드 1건을 버퍼에 쌓는다. 반환: 정규화된 키 dict (엣지 지정에 그대로 사용 가능)."""
        key, props = self.node_props(label, props, scope)
        bucket = self._nodes.setdefault(label, {})
        kt = tuple(key[f] for f in sorted(key))
        bucket.setdefault(kt, {}).update(props)
        return key

    # ── 엣지 ────────────────────────────────────────────────────────
    def _end(self, end, scope):
        label, props = end
        self._check_label(label)
        key, _ = self._resolve_key(label, self._clean(props), scope)
        return label, key

    def edge(self, etype, src, dst, props=None, scope=None):
        """엣지 1건. src/dst = (라벨, 키 또는 키를 만들 수 있는 속성 dict)."""
        safe_ident(etype, '엣지 타입')
        (sl, sk), (dl, dk) = self._end(src, scope), self._end(dst, scope)
        rule = self._rules.get(etype)
        if rule is None:
            self._violation(f'SoT 밖 엣지: {etype}')
        else:
            s_ok = rule[0] is None or sl in rule[0]
            d_ok = rule[1] is None or dl in rule[1]
            if not (s_ok and d_ok):
                self._violation(f'{etype}: 방향·라벨 위반 ({sl})->({dl})')
        props = self._clean(props)
        allowed = set((O.RELATIONSHIPS.get(etype) or {}).get('properties') or []) | self._edge_meta
        for k in props:
            safe_ident(k, '속성 키')
            if rule is not None and k not in allowed:
                self._violation(f'{etype}.{k}: 사전에 없는 속성', prop=True)
        bucket = self._edges.setdefault((etype, sl, dl), {})
        pair = (tuple(sk[f] for f in sorted(sk)), tuple(dk[f] for f in sorted(dk)))
        if pair not in bucket:
            bucket[pair] = {'_sk': sk, '_dk': dk, 'p': {}}
        self._merge_edge_props(etype, bucket[pair]['p'], props)

    def check_edge(self, etype, src_label, dst_label, props=None):
        """키 없이(요소 id 로) 잇는 경우의 정책 검사 — 엣지 타입·방향·속성. 정리된 props 반환."""
        safe_ident(etype, '엣지 타입')
        rule = self._rules.get(etype)
        if rule is None:
            self._violation(f'SoT 밖 엣지: {etype}')
        elif not ((rule[0] is None or src_label in rule[0]) and (rule[1] is None or dst_label in rule[1])):
            self._violation(f'{etype}: 방향·라벨 위반 ({src_label})->({dst_label})')
        props = self._clean(props)
        allowed = set((O.RELATIONSHIPS.get(etype) or {}).get('properties') or []) | self._edge_meta
        for k in props:
            safe_ident(k, '속성 키')
            if rule is not None and k not in allowed:
                self._violation(f'{etype}.{k}: 사전에 없는 속성', prop=True)
        return props

    def node_props(self, label, props, scope=None):
        """버퍼 없이 노드 정책 검사 + 키 정규화 — 단건 MERGE 후 id 가 필요한 호출자(수동 생성)용."""
        self._check_label(label)
        props = self._clean(props)
        key, props = self._resolve_key(label, props, scope)
        allowed = self._node_props.get(label)
        for k in props:
            safe_ident(k, '속성 키')
            if allowed is not None and k not in allowed:
                self._violation(f'{label}.{k}: 사전에 없는 속성', prop=True)
        return key, props

    @staticmethod
    def literal_map(d):
        return _map(d)

    @staticmethod
    def _merge_edge_props(etype, cur, new):
        agg = (O.RELATIONSHIPS.get(etype) or {}).get('aggregation') or {}
        mins, maxs = set(agg.get('min', ())), set(agg.get('max', ()))
        sums, unions = set(agg.get('sum', ())), set(agg.get('union', ()))
        for k, v in new.items():
            if k not in cur:
                cur[k] = v
            elif k in mins:
                cur[k] = min(cur[k], v)
            elif k in maxs:
                cur[k] = max(cur[k], v)
            elif k in sums:
                try:
                    cur[k] = cur[k] + v
                except TypeError:
                    cur[k] = v
            elif k in unions:
                vals = list(dict.fromkeys(str(cur[k]).split('|') + str(v).split('|')))
                cur[k] = '|'.join(x for x in vals if x)
            else:
                cur[k] = v
        return cur

    # ── 기록 ────────────────────────────────────────────────────────
    def _exec(self, q):
        self.cur.execute(q)
        row = self.cur.fetchone() if self.cur.description else None
        return int(row[0]) if row and row[0] is not None else 0

    def _chunks(self, items):
        items = list(items)
        for i in range(0, len(items), self.batch_size):
            yield items[i:i + self.batch_size]

    def flush(self):
        """버퍼를 DB 에 쓴다. 라벨이 없으면 만든다. 반환: 통계 dict."""
        for label, rows in self._nodes.items():
            self.cur.execute(f'CREATE VLABEL IF NOT EXISTS {safe_ident(label, "라벨")}')
            fields = sorted(self._key_override.get(label) or _key_fields(label)) or None
            for chunk in self._chunks(rows.values()):
                flds = fields or [next(iter(chunk[0]))]
                recs = ', '.join('{' + ', '.join(f'k{i}: {_lit(p[f])}' for i, f in enumerate(flds))
                                 + f', p: {_map(p)}' + '}' for p in chunk)
                match = ', '.join(f'{f}: r.k{i}' for i, f in enumerate(flds))
                self.stats['nodes'] += self._exec(
                    f'UNWIND [{recs}] AS r MERGE (n:{label} {{{match}}}) SET n += r.p RETURN count(n)')
        for (etype, sl, dl), pairs in self._edges.items():
            self.cur.execute(f'CREATE ELABEL IF NOT EXISTS {safe_ident(etype, "엣지 타입")}')
            for chunk in self._chunks(pairs.values()):
                sf, df = sorted(chunk[0]['_sk']), sorted(chunk[0]['_dk'])
                recs = ', '.join('{' + ', '.join([f'a{i}: {_lit(e["_sk"][f])}' for i, f in enumerate(sf)]
                                                 + [f'b{i}: {_lit(e["_dk"][f])}' for i, f in enumerate(df)])
                                 + f', p: {_map(e["p"])}' + '}' for e in chunk)
                am = ', '.join(f'{f}: r.a{i}' for i, f in enumerate(sf))
                bm = ', '.join(f'{f}: r.b{i}' for i, f in enumerate(df))
                n = self._exec(f'UNWIND [{recs}] AS r MATCH (a:{sl} {{{am}}}), (b:{dl} {{{bm}}}) '
                               f'MERGE (a)-[e:{etype}]->(b) SET e += r.p RETURN count(e)')
                self.stats['edges'] += n
                self.stats['edges_unmatched'] += len(chunk) - n
        self._nodes, self._edges = {}, {}
        return self.stats
