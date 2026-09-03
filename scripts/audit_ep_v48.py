#!/usr/bin/env python3
"""EP1~EP10 + 통합 그래프 — V4.8 온톨로지 정합 전수 감사 (rebuild_all.sh ④단계).
실행: python3 scripts/audit_ep_v48.py
① 노드 라벨 정경 대조 ② 엣지 타입 정경/deprecated ③ domain/range 위반
④ 핵심 식별자(KP) 충전율 ⑤ provenance(source_id) 충전율"""
import sys, os, json
sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')
os.chdir('/Users/iankwon/test/coop_v1.0')
from dotenv import load_dotenv
load_dotenv()
import psycopg2
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as O

CANON_LABELS = set(O.GDB_LABEL_MAP.values())
REL = O.RELATIONSHIPS
CANON_EDGES = set(REL.keys())
DEPRECATED = {k for k, v in REL.items() if v.get('deprecated')}
C2L = O.GDB_LABEL_MAP  # Concept → vt_label

KP = {'vt_psn': 'name', 'vt_bacnt': 'account_no', 'vt_telno': 'telno', 'vt_ip': 'ip_addr',
      'vt_id': 'id_val', 'vt_case': 'flnm', 'vt_org': 'org_name', 'vt_atm': 'atm_nm',
      'vt_email': 'email_addr', 'vt_src': 'src_name', 'vt_site': 'url_addr'}

conn = psycopg2.connect(dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                        password=os.getenv('DB_PASSWORD'), host=os.getenv('DB_HOST'),
                        port=os.getenv('DB_PORT'))
conn.autocommit = True
cur = conn.cursor()

def allowed_labels(spec):
    """'BankAccount|CryptoWallet' → {vt_bacnt, vt_crypto}. 'Any'=와일드카드(빈 set=검사 안 함)"""
    if 'Any' in (spec or ''):
        return set()
    out = set()
    for c in (spec or '').split('|'):
        c = c.strip()
        if c in C2L:
            out.add(C2L[c])
        elif c:
            out.add('?' + c)  # 매핑 없는 개념
    return out

GRAPHS = [f'ep{i}_graph' for i in range(1, 11)] + ['ccop_ep_integrated']
report = {}
for g in GRAPHS:
    cur.execute(f"SET graph_path = {g}")
    r = {'labels': {}, 'edges': {}, 'unknown_labels': [], 'unknown_edges': [],
         'deprecated_edges': [], 'dr_violations': [], 'kp_fill': {}, 'prov': {}}
    # ① 노드 라벨
    cur.execute("MATCH (n) RETURN label(n), count(n)")
    for lbl, cnt in cur.fetchall():
        r['labels'][lbl] = cnt
        if lbl not in CANON_LABELS:
            r['unknown_labels'].append(lbl)
    # ② 엣지 타입
    cur.execute("MATCH ()-[e]->() RETURN type(e), count(e)")
    for et, cnt in cur.fetchall():
        r['edges'][et] = cnt
        if et not in CANON_EDGES:
            r['unknown_edges'].append(et)
        elif et in DEPRECATED:
            r['deprecated_edges'].append(et)
    # ③ domain/range (엣지 타입별 실제 엔드포인트 라벨 조합)
    for et in r['edges']:
        if et not in REL:
            continue
        dom = allowed_labels(REL[et].get('domain', ''))
        rng = allowed_labels(REL[et].get('range', ''))
        cur.execute(f"MATCH (a)-[e:{et}]->(b) RETURN label(a), label(b), count(*)")
        for la, lb, cnt in cur.fetchall():
            bad_d = dom and la not in dom
            bad_r = rng and lb not in rng
            if bad_d or bad_r:
                r['dr_violations'].append(f"{et}: ({la})->({lb}) ×{cnt}"
                                          + (" [domain]" if bad_d else "") + (" [range]" if bad_r else ""))
    # ④ KP 충전율
    for lbl, key in KP.items():
        tot = r['labels'].get(lbl, 0)
        if not tot:
            continue
        cur.execute(f"MATCH (n:{lbl}) WHERE n.{key} IS NOT NULL AND n.{key} <> '' RETURN count(n)")
        r['kp_fill'][lbl] = (cur.fetchone()[0], tot)
    # ⑤ provenance (source_id) — 노드/엣지
    cur.execute("MATCH (n) WHERE n.source_id IS NOT NULL RETURN count(n)")
    ns = cur.fetchone()[0]
    cur.execute("MATCH ()-[e]->() WHERE e.source_id IS NOT NULL RETURN count(e)")
    es = cur.fetchone()[0]
    ntot, etot = sum(r['labels'].values()), sum(r['edges'].values())
    r['prov'] = {'node': (ns, ntot), 'edge': (es, etot)}
    report[g] = r

# ── 출력 ──
print(f"V4.7 정경: 노드라벨 {len(CANON_LABELS)} · 엣지 {len(CANON_EDGES)}(deprecated {len(DEPRECATED)}: {sorted(DEPRECATED)})\n")
for g, r in report.items():
    ntot, etot = sum(r['labels'].values()), sum(r['edges'].values())
    print(f"══ {g} — 노드 {ntot:,} · 엣지 {etot:,} ══")
    print(f"  라벨({len(r['labels'])}): " + " ".join(f"{k}:{v}" for k, v in sorted(r['labels'].items(), key=lambda x: -x[1])))
    print(f"  엣지({len(r['edges'])}): " + " ".join(f"{k}:{v}" for k, v in sorted(r['edges'].items(), key=lambda x: -x[1])))
    if r['unknown_labels']:
        print(f"  ❌ 정경 외 라벨: {r['unknown_labels']}")
    if r['unknown_edges']:
        print(f"  ❌ 정경 외 엣지: {r['unknown_edges']}")
    if r['deprecated_edges']:
        print(f"  ⚠️ deprecated 사용: {r['deprecated_edges']}")
    if r['dr_violations']:
        print(f"  ⚠️ domain/range 위반 {len(r['dr_violations'])}종:")
        for v in r['dr_violations'][:6]:
            print(f"     {v}")
    low = {k: f"{a}/{t}" for k, (a, t) in r['kp_fill'].items() if t and a / t < 0.99}
    print(f"  KP 충전율: " + ("전항목 ≥99%" if not low else f"미달 {low}"))
    pn, pe = r['prov']['node'], r['prov']['edge']
    print(f"  provenance(source_id): 노드 {pn[0]}/{pn[1]} ({pn[0]/max(1,pn[1])*100:.0f}%) · 엣지 {pe[0]}/{pe[1]} ({pe[0]/max(1,pe[1])*100:.0f}%)")
    print()
conn.close()
