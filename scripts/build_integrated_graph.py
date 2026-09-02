#!/usr/bin/env python3
"""EP1~8 → ccop_ep_integrated 통합 그래프 병합.

각 ep_graph의 노드/엣지를 공유 키(계좌·전화·IP·카카오ID·이메일·조직·ATM·사건·출처)로 MERGE.
EP마다 가명이 달라도 물리 식별자(계좌/전화/IP/ID)가 겹치면 자동 교차 연결된다.
각 노드에 ep_origin='ep3,ep6,ep7' 을 부여해 어느 EP들에서 공유되는지(콜센터 IP 등) 추적.
멱등(MERGE). 실행: python3 scripts/build_integrated_graph.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
import psycopg2

KP = {'vt_bacnt': 'account_no', 'vt_case': 'flnm', 'vt_id': 'id_val', 'vt_psn': 'name',
      'vt_telno': 'telno', 'vt_ip': 'ip_addr', 'vt_org': 'org_name', 'vt_atm': 'atm_nm',
      'vt_email': 'email_addr', 'vt_src': 'src_name',
      'vt_movement': 'mov_id'}   # EP9/10 시드: 출입국 이벤트 (V4.8)
EDGES = ['eg_used_account', 'eg_used_phone', 'eg_used_id', 'has_account', 'victim_in',
         'transferred_to', 'belongs_to', 'registered_to', 'used_ip', 'contacted',
         'sourced_from', 'linked_to', 'uses_id', 'uses_email', 'owns_phone', 'same_as',
         'suspect_in', 'performed_by']   # V4.8: same_as 개명 + EP9/10 시드 엣지
GRAPHS = ['ep1_graph', 'ep2_graph', 'ep3_graph', 'ep4_graph',
          'ep5_graph', 'ep6_graph', 'ep7_graph', 'ep8_graph',
          'ep9_graph', 'ep10_graph']   # EP9/10: 정형 없음 → 수동 확정 시드(docs/EP910_SEED_DRAFT_20260902.md)
INTEG = 'ccop_ep_integrated'


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def main():
    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG']); conn.autocommit = True
        cur = conn.cursor()
        nodes = {}   # (label,key) -> {'props':{}, 'origins':set()}
        edges = []   # (el, (la,fk), (lb,tk), props)
        # ── 수집 ──
        for g in GRAPHS:
            gs = g.replace('_graph', '')
            safe_set_graph_path(cur, g)
            for label, kp in KP.items():
                try:
                    cur.execute(f"MATCH (n:{label}) RETURN properties(n)")
                except Exception:
                    safe_set_graph_path(cur, g); continue
                for (props,) in cur.fetchall():
                    if not props or kp not in props or props[kp] in (None, ''):
                        continue
                    k = (label, str(props[kp]))
                    if k not in nodes:
                        nodes[k] = {'props': {}, 'origins': set()}
                    nodes[k]['props'].update({a: b for a, b in props.items() if b not in (None, '')})
                    nodes[k]['origins'].add(gs)
            for el in EDGES:
                try:
                    cur.execute(f"MATCH (a)-[r:{el}]->(b) "
                                f"RETURN label(a),properties(a),label(b),properties(b),properties(r)")
                except Exception:
                    safe_set_graph_path(cur, g); continue
                for la, pa, lb, pb, pr in cur.fetchall():
                    if la in KP and lb in KP and pa and pb and KP[la] in pa and KP[lb] in pb:
                        edges.append((el, (la, str(pa[KP[la]])), (lb, str(pb[KP[lb]])), pr or {}))
        print(f"[수집] 노드 {len(nodes)} · 엣지 {len(edges)}", flush=True)

        # ── 통합 그래프 생성 ──
        cur.execute(f"DROP GRAPH IF EXISTS {INTEG} CASCADE;")
        cur.execute(f"CREATE GRAPH IF NOT EXISTS {INTEG};")
        safe_set_graph_path(cur, INTEG)
        for vl in KP:
            cur.execute(f"CREATE VLABEL IF NOT EXISTS {vl};")
        for el in sorted(set(e[0] for e in edges)):
            cur.execute(f"CREATE ELABEL IF NOT EXISTS {el};")

        # ── 노드 MERGE (배치 커밋) ──
        conn.autocommit = False
        cnt = 0
        for (label, key), d in nodes.items():
            props = dict(d['props'])
            props['ep_origin'] = ','.join(sorted(d['origins']))
            props['ep_count'] = str(len(d['origins']))
            setp = ', '.join(f"n.{a} = '{esc(b)}'" for a, b in props.items())
            cur.execute(f"MERGE (n:{label} {{{KP[label]}:'{esc(key)}'}}) SET {setp}")
            cnt += 1
            if cnt % 3000 == 0:
                conn.commit(); print(f"  노드 {cnt}/{len(nodes)}", flush=True)
        conn.commit(); print(f"[노드 완료] {cnt}", flush=True)

        # ── 엣지 MERGE ──
        cnt, skip = 0, 0
        for el, (fl, fk), (tl, tk), pr in edges:
            sp = ', '.join(f"e.{k2} = '{esc(v2)}'" for k2, v2 in pr.items() if v2 not in (None, ''))
            q = (f"MATCH (a:{fl} {{{KP[fl]}:'{esc(fk)}'}}), (b:{tl} {{{KP[tl]}:'{esc(tk)}'}}) "
                 f"MERGE (a)-[e:{el}]->(b)" + (f" SET {sp}" if sp else ""))
            try:
                cur.execute(q); cnt += 1
            except Exception:
                conn.rollback(); skip += 1; continue
            if cnt % 3000 == 0:
                conn.commit(); print(f"  엣지 {cnt}/{len(edges)}", flush=True)
        conn.commit(); print(f"[엣지 완료] {cnt} (스킵 {skip})", flush=True)
        print(f"[통합 완료] {INTEG}", flush=True)
        conn.close()


if __name__ == '__main__':
    main()
