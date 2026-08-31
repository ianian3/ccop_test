#!/usr/bin/env python3
"""070 인터넷전화 가입자 회신(docx) → 그래프 적재 (결정론 정규식, LLM 무관).

EP3 013 통화영장 회신: 070번호별 docx = 가입자 정보 + 최종접속 IP + 통화내역(발신/착신).
온톨로지 매핑 (V4.7):
  070번호(파일명)  → vt_telno {telno, join_typ:'070'}
  가입자 이름      → vt_psn   ; 070 -[registered_to]-> 가입자 (명의)
  최종접속 IP      → vt_ip    ; 070 -[used_ip]-> IP
  통화 상대번호    → vt_telno ; 070 -[contacted]-> 상대 (연락관계 요약)
멱등(MERGE). 실행: python3 scripts/ingest_070_subscriber.py --graph ep3_graph [--dry-run]
"""
import argparse
import glob
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
from app.services import document_extraction_service as dx
import psycopg2

GRAPH = 'ep3_graph'
ROOT = ('/Users/iankwon/Downloads/00_종합시나리오 및 데이터셋/데이터셋/'
        'EP3. DS-03(비식별화)/013_영장(0000-000000)_통화_비식별화/070번호(주)유윈_비식별화')
SRC_ID = 'EP3-013-070'
PHONE_RE = re.compile(r'\b(01[016789]\d{7,8}|070\d{7,8})\b')
IPV4_RE = re.compile(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b')


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def parse_file(path):
    txt = dx._parse_docx(path) or ''
    # macOS 파일명은 NFD(자모분리) → NFC 정규화 후 070 번호 추출(replace 의존 회피)
    base = unicodedata.normalize('NFC', os.path.basename(path))
    mo = re.match(r'(070\d{7,8})', base)
    own = mo.group(1) if mo else None
    m = re.search(r'가입자\s*이름\s*:\s*([가-힣]{2,4})', txt)
    name = m.group(1) if m else None
    ipm = re.search(r'최종접속\s*IP\s*주소\s*:\s*([\d.]+)', txt)
    ip = ipm.group(1) if ipm and IPV4_RE.fullmatch(ipm.group(1)) else None
    peers = set(PHONE_RE.findall(txt))
    if own:
        peers.discard(own)
    return own, name, ip, sorted(peers)


def build(root=ROOT, src_id=SRC_ID):
    files = [p for p in glob.glob(root + '/*.docx') if not os.path.basename(p).startswith('~')]
    nodes, edges = {}, []

    def node(label, key, props):
        k = (label, key); nodes.setdefault(k, {})
        nodes[k].update({a: b for a, b in props.items() if b}); return k

    def edge(rel, a, b, props):
        edges.append((rel, a, b, props))

    n_files, n_named = 0, 0
    for f in files:
        own, name, ip, peers = parse_file(f)
        if not own:
            continue
        n_files += 1
        own_k = node('vt_telno', own, {'telno': own, 'join_typ': '070', 'source_id': src_id})
        if name:
            n_named += 1
            p_k = node('vt_psn', name, {'name': name, 'source_id': src_id})
            edge('registered_to', own_k, p_k, {'source_id': src_id})   # Phone->Person(명의)
        if ip:
            ip_k = node('vt_ip', ip, {'ip_addr': ip, 'source_id': src_id})
            edge('used_ip', own_k, ip_k, {'source_id': src_id})
        for pe in peers:
            pe_k = node('vt_telno', pe, {'telno': pe, 'source_id': src_id})
            edge('contacted', own_k, pe_k, {'channel': 'call', 'source_id': src_id})
    return nodes, edges, n_files, n_named


def merge_cypher(nodes, edges):
    KP = {'vt_telno': 'telno', 'vt_psn': 'name', 'vt_ip': 'ip_addr'}
    stmts = []
    for (label, key), props in nodes.items():
        setp = ', '.join(f"n.{a} = '{esc(b)}'" for a, b in props.items())
        stmts.append(f"MERGE (n:{label} {{{KP[label]}:'{esc(props[KP[label]])}'}})" + (f" SET {setp}" if setp else ""))
    for rel, (fl, fk), (tl, tk), props in edges:
        a = f"(a:{fl} {{{KP[fl]}:'{esc(nodes[(fl,fk)][KP[fl]])}'}})"
        b = f"(b:{tl} {{{KP[tl]}:'{esc(nodes[(tl,tk)][KP[tl]])}'}})"
        sp = ', '.join(f"e.{a2} = '{esc(b2)}'" for a2, b2 in props.items())
        stmts.append(f"MATCH {a}, {b} MERGE (a)-[e:{rel}]->(b)" + (f" SET {sp}" if sp else ""))
    return stmts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', default=GRAPH)
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--src-id', default=SRC_ID)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    nodes, edges, nf, nn = build(args.root, args.src_id)
    from collections import Counter
    print(f"[빌드] 070 파일 {nf}개(가입자명 {nn}) → 노드 {len(nodes)} / 엣지 {len(edges)}")
    print("  노드:", dict(Counter(l for (l, _) in nodes)))
    print("  엣지:", dict(Counter(r for (r, *_) in edges)))
    stmts = merge_cypher(nodes, edges)
    if args.dry_run:
        for s in stmts[:4]:
            print("  ", s[:150])
        return
    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG']); conn.autocommit = False
        cur = conn.cursor()
        try:
            safe_set_graph_path(cur, args.graph)
            for vl in sorted({l for (l, _) in nodes}):
                cur.execute(f"CREATE VLABEL IF NOT EXISTS {vl};")
            for el in sorted({r for (r, *_) in edges}):
                cur.execute(f"CREATE ELABEL IF NOT EXISTS {el};")
            for s in stmts:
                cur.execute(s)
            conn.commit()
            print(f"[적재 완료] {len(stmts)}개 MERGE → {args.graph}")
        except Exception as e:
            conn.rollback(); print(f"[롤백] {e}"); raise
        finally:
            conn.close()


if __name__ == '__main__':
    main()
