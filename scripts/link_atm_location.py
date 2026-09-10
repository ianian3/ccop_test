#!/usr/bin/env python3
"""vt_atm(집금 ATM) → vt_loc 위치 정규화 + located_at 연결.

배경: ATM 63개는 위치를 `atm_nm` 통짜 문자열로만 갖고 있어 vt_loc 체계에서 빠져 있었다
      (기지국·거래점은 vt_loc 로 정규화됨 — 일관성 갭). 2026-09-10 사용자 지적으로 처리.

원본 형식 2종 (EP5-031 실측):
  A(46건) `경기 고양시덕양구 통일로 775 <벽제농협 0>`  — 도로명 주소 + 지점명
  B(17건) `포항농협 송도지점`                          — **지점명만, 주소 없음**(포항 피벗 시트)

처리 방침:
  · A → vt_loc {loc_type:'atm_loc', address, sido_nm, sigungu_nm, place_name} + located_at
  · B → **위치 노드 생성 안 함**. 지점명에서 지역을 추정하면('포항농협'→포항시) 근거 없는
        위치가 그래프에 들어가므로 하지 않는다. vt_atm.place_name 만 정규화해 남긴다.

loc_type 정정도 함께: 기업은행 거래점(EP5-030-ibk)은 은행 영업점이라 'atm_loc' 가 부정확했다
  → 'poi' 로 정정. 이로써 loc_type 이 cell_tower(기지국)/atm_loc(ATM)/poi(영업점) 3종으로 구분된다.

멱등(MERGE). source_id 는 원 ATM 의 것을 승계(EP5-031).
실행: DB_HOST=localhost DB_PORT=5434 DB_USER=ccop DB_PASSWORD=... \
      python3 scripts/link_atm_location.py [--graph ep5_graph]
"""
import argparse
import os
import re

import psycopg2
from dotenv import load_dotenv

# '주소 <지점명>' — 주소는 시도로 시작. 지점명에 '<출>'(출장소) 처럼 꺾쇠가 중첩돼
# 들어오는 케이스가 있어(실측 3건) 첫 '<' 부터 끝까지를 지점명으로 본다.
RE_ADDR = re.compile(r'^(?P<addr>\S+\s+\S*?[시군구].*?)\s*<\s*(?P<place>.+?)\s*>?\s*$')
RE_SIDO = re.compile(r'^(?P<sido>\S+)\s+(?P<sigungu>\S*?[시군구])')


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def parse_atm(nm):
    """atm_nm → (address, place_name, sido, sigungu) · 주소 없으면 address=None"""
    m = RE_ADDR.match(nm or '')
    if not m:
        return None, (nm or '').strip(), None, None
    addr = m.group('addr').strip()
    place = m.group('place').strip().rstrip('>').strip()   # 중첩 꺾쇠 잔여 제거
    s = RE_SIDO.match(addr)
    return addr, place, (s.group('sido') if s else None), (s.group('sigungu') if s else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', default='ep5_graph')
    ap.add_argument('--fix-branch-poi', action='store_true', default=True,
                    help='기업은행 거래점 loc_type atm_loc → poi 정정')
    args = ap.parse_args()
    load_dotenv()
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', args.graph):
        raise SystemExit(f'invalid graph: {args.graph}')

    conn = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'),
                            dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                            password=os.getenv('DB_PASSWORD'), connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f'SET graph_path = {args.graph}')
    cur.execute('CREATE VLABEL IF NOT EXISTS vt_loc')
    cur.execute('CREATE ELABEL IF NOT EXISTS located_at')

    cur.execute("MATCH (a:vt_atm) RETURN a.atm_nm, a.source_id")
    atms = cur.fetchall()
    linked = noaddr = 0
    for nm, src in atms:
        addr, place, sido, sigungu = parse_atm(nm)
        src = src or 'EP5-031'
        if not addr:
            # 주소 미보유 — 위치 노드 없이 지점명만 정규화(추정 금지)
            if place:
                cur.execute(f"MATCH (a:vt_atm {{atm_nm: '{esc(nm)}'}}) "
                            f"SET a.place_name = '{esc(place)}'")
            noaddr += 1
            continue
        lid = f'ATM {addr}'
        setp = [f"l.loc_type = 'atm_loc'", f"l.address = '{esc(addr)}'",
                f"l.place_name = '{esc(place)}'", f"l.source_id = '{esc(src)}'"]
        if sido:
            setp.append(f"l.sido_nm = '{esc(sido)}'")
        if sigungu:
            setp.append(f"l.sigungu_nm = '{esc(sigungu)}'")
        cur.execute(f"MERGE (l:vt_loc {{loc_id: '{esc(lid)}'}}) SET {', '.join(setp)}")
        cur.execute(f"MATCH (a:vt_atm {{atm_nm: '{esc(nm)}'}}), "
                    f"(l:vt_loc {{loc_id: '{esc(lid)}'}}) "
                    f"MERGE (a)-[r:located_at]->(l) "
                    f"SET r.source_id = '{esc(src)}', r.creation_method = 'etl'")
        cur.execute(f"MATCH (a:vt_atm {{atm_nm: '{esc(nm)}'}}) "
                    f"SET a.place_name = '{esc(place)}'")
        linked += 1

    print(f'[ATM] {len(atms)}개 · 위치 연결 {linked} · 주소 미보유 {noaddr}(위치 노드 미생성)',
          flush=True)

    if args.fix_branch_poi:
        # 기업은행 거래점: 은행 영업점이므로 atm_loc → poi (ATM 과 구분)
        cur.execute("MATCH (l:vt_loc) WHERE l.loc_type = 'atm_loc' AND l.loc_id STARTS WITH '기업은행' "
                    "SET l.loc_type = 'poi' RETURN count(l)")
        try:
            n = cur.fetchone()[0]
        except Exception:
            n = 0
        print(f'[정정] 거래점 loc_type atm_loc → poi: {n}건', flush=True)

    for t in ('atm_loc', 'poi', 'cell_tower'):
        cur.execute(f"MATCH (l:vt_loc) WHERE l.loc_type = '{t}' RETURN count(l)")
        print(f'  loc_type={t}: {cur.fetchone()[0]}', flush=True)
    cur.execute("MATCH (a:vt_atm)-[r:located_at]->() RETURN count(r)")
    print(f'  ATM located_at: {cur.fetchone()[0]}', flush=True)
    conn.close()


if __name__ == '__main__':
    main()
