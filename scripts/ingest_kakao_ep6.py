#!/usr/bin/env python3
"""EP6 카카오톡 통신 로그(영장 회신 *.log) → 통신망 그래프 (결정론·LLM무관·내용 미저장).

EP6 "핵심 통신수단 수렴" — 034 예금주·035 피해자·047 범행의심 카톡 27개. 통일 형식:
  가입자 : 821004885379              (카카오ID = 국가코드+번호; 82=KR·852=HK·63/639=PH)
  = 대화상대목록 : 821004827553, ...
  821008551493 : 2017-03-18 17:08:57, 116.37.33.73   (상대ID : 시각, 접속IP)
대화 '내용'은 로그에 없음(시각+IP만) → 프라이버시 안전. 관계·빈도·접속IP만 적재.
온톨로지 매핑(V4.7):
  카카오ID       → vt_id {id_val, platform:'kakao', country}
  가입자↔상대    → (가입자)-[contacted {channel:'kakao', msg_count, first/last_dt}]->(상대)
  접속IP         → vt_ip ; (카카오ID)-[used_ip]->(IP)   (콜센터 IP 수렴 탐지)
멱등(MERGE). 실행: python3 scripts/ingest_kakao_ep6.py --graph ep6_graph [--dry-run]
"""
import argparse
import glob
import os
import re
import sys
import unicodedata
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
import psycopg2

GRAPH = 'ep6_graph'
SRC = 'EP6-kakao'
BASE = '/Users/iankwon/Downloads/00_종합시나리오 및 데이터셋/데이터셋'
IPV4 = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
IPV6 = re.compile(r'^(?=.*:.*:)[0-9a-fA-F:]+$')   # 콜론 2개 이상 hex (2001:2d8:...::d05:a5e6)
MSG = re.compile(r'^(\d{6,})\s*:\s*(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\s*,\s*(\S+)')


def N(p):
    return unicodedata.normalize('NFC', str(p))


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def country(kid):
    if kid.startswith('852'):
        return 'HK'
    if kid.startswith('639') or kid.startswith('63'):
        return 'PH'
    if kid.startswith('86') and not kid.startswith('852'):
        return 'CN'
    if kid.startswith('82'):
        return 'KR'
    return '?'


def read_text(path):
    for enc in ('utf-8', 'euc-kr', 'cp949'):
        try:
            return open(path, encoding=enc).read()
        except (UnicodeDecodeError, LookupError):
            continue
    return open(path, encoding='utf-8', errors='replace').read()


def find_logs(d6):
    return [os.path.join(r, f) for r, _, fs in os.walk(d6) for f in fs
            if f.lower().endswith('.log') and not f.startswith(('.', '~'))]


def build(d6, src=SRC):
    logs = find_logs(d6)
    nodes, ids = {}, set()
    contacts = defaultdict(lambda: {'n': 0, 'first': '', 'last': ''})
    ipuse = defaultdict(set)   # kid -> {ip}
    n_files, n_msg = 0, 0

    for path in logs:
        txt = read_text(path)
        owner = None
        for line in txt.splitlines():
            mo = re.match(r'가입자\s*:\s*(\d{6,})', line)
            if mo:
                owner = mo.group(1)
                ids.add(owner)
                continue
            mm = MSG.match(line.strip())
            if not mm or not owner:
                continue
            kid, dt, ip = mm.group(1), mm.group(2), mm.group(3)
            ids.add(kid)
            n_msg += 1
            if kid != owner:
                key = tuple(sorted([owner, kid]))   # 무방향 대화쌍(방향 불명확 — 로그는 발화자 기준)
                c = contacts[(owner, kid)]
                c['n'] += 1
                c['first'] = min(c['first'] or dt, dt)
                c['last'] = max(c['last'], dt)
            if IPV4.match(ip) or IPV6.match(ip):
                ipuse[kid].add(ip)
        n_files += 1

    edges = []
    for kid in ids:
        nodes[('vt_id', kid)] = {'id_val': kid, 'platform': 'kakao', 'country': country(kid), 'source_id': src}
    for (owner, kid), c in contacts.items():
        edges.append(('contacted', ('vt_id', owner), ('vt_id', kid),
                      {'channel': 'kakao', 'msg_count': c['n'], 'first_dt': c['first'],
                       'last_dt': c['last'], 'source_id': src}))
    for kid, ips in ipuse.items():
        for ip in ips:
            nodes[('vt_ip', ip)] = {'ip_addr': ip, 'source_id': src}
            edges.append(('used_ip', ('vt_id', kid), ('vt_ip', ip), {'source_id': src}))
    return nodes, edges, n_files, n_msg


KP = {'vt_id': 'id_val', 'vt_ip': 'ip_addr'}


def merge_cypher(nodes, edges):
    stmts = []
    for (label, key), props in nodes.items():
        setp = ', '.join(f"n.{a} = '{esc(b)}'" for a, b in props.items() if b != '')
        stmts.append(f"MERGE (n:{label} {{{KP[label]}:'{esc(props[KP[label]])}'}})" + (f" SET {setp}" if setp else ""))
    for rel, (fl, fk), (tl, tk), props in edges:
        a = f"(a:{fl} {{{KP[fl]}:'{esc(nodes[(fl,fk)][KP[fl]])}'}})"
        b = f"(b:{tl} {{{KP[tl]}:'{esc(nodes[(tl,tk)][KP[tl]])}'}})"
        sp = ', '.join(f"e.{k2} = '{esc(v2)}'" for k2, v2 in props.items() if v2 != '')
        stmts.append(f"MATCH {a}, {b} MERGE (a)-[e:{rel}]->(b)" + (f" SET {sp}" if sp else ""))
    return stmts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', default=GRAPH)
    ap.add_argument('--ep-prefix', default='EP6.')
    ap.add_argument('--src', default=SRC)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    d6 = [os.path.join(BASE, x) for x in os.listdir(BASE) if N(x).startswith(args.ep_prefix)][0]
    nodes, edges, nf, nm = build(d6, args.src)
    from collections import Counter
    print(f"[빌드] 카톡 로그 {nf}개 · 메시지 {nm:,} → 노드 {len(nodes)} / 엣지 {len(edges)}")
    print("  노드:", dict(Counter(l for (l, _) in nodes)))
    print("  엣지:", dict(Counter(r for (r, *_) in edges)))
    print("  국가분포:", dict(Counter(p['country'] for (l, _), p in nodes.items() if l == 'vt_id')))
    stmts = merge_cypher(nodes, edges)
    if args.dry_run:
        for s in stmts[:4]:
            print("  ", s[:140])
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
