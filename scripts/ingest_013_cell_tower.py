#!/usr/bin/env python3
"""EP3 013 통화내역의 발신기지국주소 → ep3_graph 적재 (V4.8 vt_loc/located_at).

데이터 실측(2026-09-08 전수):
  · tongwha CSV(euc-kr) 중 기지국 값 85건/395행 — 음성·VOLTE '착신' 행에만 존재(SMS 310건 없음)
  · 값은 시·군 단위 주소 문자열 34종(좌표 없음 — 비식별화로 절삭된 것으로 보임)
  · 의미: '발신기지국주소' = **발신번호(상대방) 회선의 기지국**. 이 파일은 대상 회선의
    착신 기록이므로 위치는 전화를 건 쪽(발신자)에 귀속된다 — 대상 회선 위치가 아님!
  · EP4 의 013 은 EP3 와 동일 사본(행수·분포 일치) → EP3 만 적재

매핑(V4.8 정경 — 온톨로지 변경 없음):
  vt_loc {loc_id:'기지국 <주소>', loc_type:'cell_tower', bsst_addr:'<주소>', address}
  (발신 vt_telno)-[located_at {call_count(숫자), first_dt, last_dt}]->(vt_loc)

멱등(MERGE). source_id='EP3-013-cell'.
실행: DB_HOST=localhost DB_PORT=5434 DB_USER=ccop DB_PASSWORD=... \
      python3 scripts/ingest_013_cell_tower.py [--graph ep3_graph]
"""
import argparse
import csv
import os
import pathlib
import re
import unicodedata as ud
from collections import defaultdict

import psycopg2
from dotenv import load_dotenv

SRC_ID = 'EP3-013-cell'
DATASET = pathlib.Path('/Users/iankwon/Desktop/SKAI/01.연구과제/01.진행과제/경찰청과제/2026')


def nfc(v):
    return ud.normalize('NFC', str(v)).strip()


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def find_csvs():
    p = [c for c in DATASET.iterdir() if nfc(c.name).startswith('20280831')][0]
    ds = p / '00_종합시나리오 및 데이터셋' / '데이터셋'
    ep3 = [c for c in ds.iterdir() if nfc(c.name).startswith('EP3')][0]
    d013 = [c for c in ep3.iterdir() if nfc(c.name).startswith('013')][0]
    hp = [c for c in d013.iterdir() if '휴대전화' in nfc(c.name)][0]
    return sorted(hp.glob('*.csv'))


def parse(files):
    """(발신번호, 기지국주소) 집계 — call_count · first/last 통화일."""
    agg = defaultdict(lambda: {'n': 0, 'first': '9999', 'last': ''})
    scanned = 0
    for f in files:
        rows = list(csv.reader(open(f, encoding='euc-kr')))
        hdr = [nfc(c) for c in rows[0]]
        if '발신기지국주소' not in hdr:
            continue                                   # KT유선 등 — 컬럼 없음
        bi = hdr.index('발신기지국주소')
        si = hdr.index('발신번호')
        ti = hdr.index('통화시작시간')
        for r in rows[1:]:
            if len(r) <= bi:
                continue
            addr = nfc(r[bi])
            tel = re.sub(r'\D', '', r[si])
            # 통화시작시간 값에 선행 아포스트로피가 붙어 있다("'2017-03-14 10:28:03")
            m = re.search(r'(\d{4}-\d{2}-\d{2})', r[ti])
            if not addr or not tel or len(tel) < 9 or not m:
                continue
            scanned += 1
            a = agg[(tel, addr)]
            a['n'] += 1
            a['first'] = min(a['first'], m.group(1))
            a['last'] = max(a['last'], m.group(1))
    return agg, scanned


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', default='ep3_graph')
    args = ap.parse_args()
    load_dotenv()
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', args.graph):
        raise SystemExit(f'invalid graph: {args.graph}')

    agg, scanned = parse(find_csvs())
    addrs = sorted(set(a for _, a in agg))
    print(f'[파싱] 기지국 통화 {scanned}건 → (번호,기지국) {len(agg)}쌍 · 기지국 {len(addrs)}종')

    conn = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'),
                            dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                            password=os.getenv('DB_PASSWORD'), connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f'SET graph_path = {args.graph}')
    cur.execute('CREATE VLABEL IF NOT EXISTS vt_loc')
    cur.execute('CREATE ELABEL IF NOT EXISTS located_at')

    for addr in addrs:
        lid = f'기지국 {addr}'
        cur.execute(f"MERGE (l:vt_loc {{loc_id: '{esc(lid)}'}}) "
                    f"SET l.loc_type = 'cell_tower', l.bsst_addr = '{esc(addr)}', "
                    f"l.address = '{esc(lid)}', l.source_id = '{SRC_ID}'")

    n_edge = 0
    for (tel, addr), a in agg.items():
        cur.execute(f"MERGE (t:vt_telno {{telno: '{esc(tel)}'}}) "
                    f"SET t.source_id = coalesce(t.source_id, '{SRC_ID}')")
        cur.execute(
            f"MATCH (t:vt_telno {{telno: '{esc(tel)}'}}), "
            f"(l:vt_loc {{loc_id: '기지국 {esc(addr)}'}}) "
            f"MERGE (t)-[r:located_at]->(l) "
            f"SET r.call_count = {a['n']}, r.first_dt = '{a['first']}', "
            f"r.last_dt = '{a['last']}', r.source_id = '{SRC_ID}'")
        n_edge += 1

    cur.execute("MATCH (l:vt_loc) RETURN count(l)")
    nl = cur.fetchone()[0]
    cur.execute("MATCH ()-[r:located_at]->() WHERE r.source_id = '" + SRC_ID + "' RETURN count(r)")
    ne = cur.fetchone()[0]
    print(f'[완료] {args.graph}: vt_loc {nl} · located_at(기지국) {ne} (엣지 MERGE {n_edge})')
    conn.close()


if __name__ == '__main__':
    main()
