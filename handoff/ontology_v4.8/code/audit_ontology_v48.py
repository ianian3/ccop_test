#!/usr/bin/env python3
"""CCOP 온톨로지 V4.8 정합 감사 — 협력기관 자체 검증용 (독립 실행)

CCOP 내부용 `scripts/audit_ep_v48.py` 를 외부에서 쓸 수 있게 일반화한 것.
내부판은 그래프명(ep1_graph~ep10_graph)이 하드코딩돼 있으나, 이 버전은 인자로 받는다.

검사 항목
  ① 정경 외 라벨 — V4.8 ENTITIES(노드 25종)에 없는 라벨이 적재됐는지
  ② 정경 외 엣지 — V4.8 RELATIONSHIPS(엣지 72종)에 없는 관계가 적재됐는지
  ③ deprecated 사용 — 폐기 예정 엣지(clusters_with·owns_device) 사용 여부
  ④ domain/range 위반 — 엣지가 정의된 출발/도착 라벨을 벗어났는지('Any' 는 와일드카드)
  ⑤ 키 속성 충전율 — 각 라벨의 canonical key(account_no·telno 등) 누락률
  ⑥ provenance — source_id 보유율(원본 대조 가능성)

전제
  · AgensGraph(PostgreSQL 확장) + psycopg2
  · 같은 폴더의 ccop_ontology_v48.py (정의 SoT, 외부 의존 없음)

실행
  DB_HOST=... DB_PORT=... DB_NAME=... DB_USER=... DB_PASSWORD=... \
  python3 audit_ontology_v48.py --graph my_graph [another_graph ...]

종료 코드: 위반 있으면 1, 없으면 0 (CI 게이트로 쓸 수 있음)
"""
import argparse
import os
import re
import sys

try:
    import psycopg2
except ImportError:
    sys.exit('psycopg2 가 필요합니다:  pip install psycopg2-binary')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ccop_ontology_v48 import KICSCrimeDomainOntology as O   # noqa: E402

DEPRECATED = {k for k in O.RELATIONSHIPS if k not in O.active_relationships()}

# 키 속성은 스펙(NODE_ID_STANDARD.canonical_field)에서 파생한다.
# 관례명 테이블을 손으로 들고 있으면, 스펙이 선언한 키가 적재에서 0% 여도
# 대체 이름으로 조회돼 '정상' 으로 보인다 — 정확히 이 감사가 잡아야 할 상황이 가려진다.
label_of = O.label_of
# 전 노드·엣지에 공통으로 붙는 메타 — 식별자 진단 힌트에서 제외한다
COMMON_META = set(O.EDGE_META_SCHEMA) | {'rec_created', 'verified', 'confidence', 'is_anonymous'}


def key_fields(label):
    """라벨의 키 속성 목록. 복합키는 여러 개를 돌려준다.

    주의: 스펙의 canonical_field 는 복합키를 사람이 읽는 문자열로 적어둔 곳이 있다
    (vt_id → '(platform, id_val)'). 그대로 쓰면 속성명으로 조회돼 문법 오류가 나므로
    괄호 표기를 풀어서 개별 속성으로 만든다.
    """
    k = O.key_field(label)
    if not k:
        return []
    if isinstance(k, (list, tuple)):
        return [str(x).strip() for x in k]
    s = str(k).strip()
    if s.startswith('(') and s.endswith(')'):
        return [p.strip() for p in s[1:-1].split(',') if p.strip()]
    return [s]


def allowed_labels():
    return {label_of(k) for k in O.ENTITIES} | set(O.ENTITIES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', nargs='+', required=True, help='감사할 그래프(스키마) 이름')
    ap.add_argument('--min-key-fill', type=float, default=0.95,
                    help='키 속성 충전율 경고 임계(기본 0.95)')
    args = ap.parse_args()

    for g in args.graph:
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', g):
            sys.exit(f'invalid graph name: {g}')

    conn = psycopg2.connect(host=os.getenv('DB_HOST', 'localhost'),
                            port=os.getenv('DB_PORT', '5432'),
                            dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                            password=os.getenv('DB_PASSWORD'), connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()
    ok_labels = allowed_labels()
    ok_edges = set(O.RELATIONSHIPS)
    violations = 0

    for g in args.graph:
        print(f'\n══ {g} ══')
        cur.execute(f'SET graph_path = {g}')

        # ① 라벨 정경
        cur.execute('MATCH (n) RETURN DISTINCT label(n)')
        labels = [r[0] for r in cur.fetchall()]
        bad_l = [l for l in labels if l not in ok_labels and not l.startswith('ag_')]
        print(f'  노드 라벨 {len(labels)}종' + (f' · ⛔ 정경 외 {bad_l}' if bad_l else ' · 정경 준수'))
        violations += len(bad_l)

        # ②③ 엣지 정경 / deprecated
        cur.execute('MATCH ()-[r]->() RETURN DISTINCT type(r)')
        edges = [r[0] for r in cur.fetchall()]
        bad_e = [e for e in edges if e not in ok_edges]
        dep_e = [e for e in edges if e in DEPRECATED]
        print(f'  엣지 {len(edges)}종' + (f' · ⛔ 정경 외 {bad_e}' if bad_e else ' · 정경 준수')
              + (f' · ⚠ deprecated {dep_e}' if dep_e else ''))
        violations += len(bad_e) + len(dep_e)

        # ④ domain/range
        cur.execute('MATCH (a)-[r]->(b) RETURN DISTINCT label(a), type(r), label(b)')
        dr_bad = []
        for s, t, o in cur.fetchall():
            spec = O.RELATIONSHIPS.get(t)
            if not isinstance(spec, dict):
                continue
            dom, rng = spec.get('domain'), spec.get('range')
            for side, want, got in (('domain', dom, s), ('range', rng, o)):
                if not want or want == 'Any':
                    continue                      # 와일드카드 — 검사 제외
                allow = {label_of(w.strip()) for w in str(want).split('|')}
                if got not in allow:
                    dr_bad.append(f'({s})-[{t}]->({o}) {side}≠{want}')
        if dr_bad:
            print(f'  ⛔ domain/range 위반 {len(dr_bad)}:')
            for x in dr_bad[:8]:
                print(f'      {x}')
        else:
            print('  domain/range 준수')
        violations += len(dr_bad)

        # ⑤ 키 충전율 — 스펙이 선언한 canonical_field 기준
        low = []
        for l in labels:
            ks = key_fields(l)
            if not ks:
                continue
            cur.execute(f'MATCH (n:{l}) RETURN count(n)')
            tot = cur.fetchone()[0] or 0
            if not tot:
                continue
            for k in ks:
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', k):
                    continue
                cur.execute(f'MATCH (n:{l}) WHERE n.{k} IS NOT NULL RETURN count(n)')
                has = cur.fetchone()[0] or 0
                if has / tot >= args.min_key_fill:
                    continue
                msg = f'{l}.{k} {has}/{tot} ({has/tot:.0%})'
                # 진단 힌트: 선언된 다른 속성 중 실제로 채워진 것을 찾아 알려준다
                # (적재가 다른 이름을 식별자로 썼다면 그게 스펙↔적재 불일치 지점이다)
                ent = O.ENTITIES.get(O.concept_of(l)) or {}
                for alt in (ent.get('attributes') or [])[:12]:
                    # 공통 메타(source_id·rec_created 등)는 설계상 모든 노드에 있어 힌트가 못 된다
                    if alt == k or alt in COMMON_META \
                            or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', alt):
                        continue
                    cur.execute(f'MATCH (n:{l}) WHERE n.{alt} IS NOT NULL RETURN count(n)')
                    if (cur.fetchone()[0] or 0) / tot >= 0.99:
                        msg += f' → 실제 채워진 속성: {alt}'
                        break
                low.append(msg)
        if low:
            print('  ⚠ 키 충전율 미달(스펙 canonical_field 기준):')
            for x in low:
                print(f'      {x}')
        else:
            print('  키 충전율: 정상')

        # ⑥ provenance
        cur.execute('MATCH (n) RETURN count(n)')
        tot = cur.fetchone()[0] or 1
        cur.execute('MATCH (n) WHERE n.source_id IS NOT NULL RETURN count(n)')
        src = cur.fetchone()[0] or 0
        print(f'  source_id 보유: {src:,}/{tot:,} ({src/tot:.0%})'
              + ('' if src / tot >= 0.99 else '  ⚠ 원본 대조 불가 노드 존재'))

    conn.close()
    print(f'\n{"⛔ 위반 " + str(violations) + "건" if violations else "✅ 위반 0"}')
    sys.exit(1 if violations else 0)


if __name__ == '__main__':
    main()
