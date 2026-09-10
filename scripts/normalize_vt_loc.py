#!/usr/bin/env python3
"""vt_loc 속성 일관화 — loc_type 3종이 같은 속성 셋을 갖게 채운다.

문제(2026-09-10 실측): loc_type 별로 보유 속성이 달라 T2C 가 어떤 속성을 고르든 0건이 났다.
  cell_tower : bsst_addr 만 (sido_nm·sigungu_nm·place_name 없음)
  atm_loc    : address·sido_nm·sigungu_nm·place_name 완비 (ATM 적재 시 채움)
  poi        : loc_id·address 만 (place_name 없음)
→ 모델이 `sido_nm:'경기도'`(기지국)·`place_name:'기업은행 상동'`(거래점)을 쓰면 조용히 0건.

조치: 있는 값에서 파생 가능한 것만 채운다(추정·외부조회 없음).
  cell_tower : bsst_addr('경기도 포천시') → sido_nm·sigungu_nm·place_name·address
  poi        : loc_id('기업은행 상동')     → place_name(loc_id 전체 — 부분매칭 양방향 대응)
  atm_loc    : 이미 완비 — 손대지 않음

멱등. 실행: DB_HOST=localhost DB_PORT=5434 DB_USER=ccop DB_PASSWORD=... \
      python3 scripts/normalize_vt_loc.py [--graph ep3_graph ep5_graph ...]
"""
import argparse
import os
import re

import psycopg2
from dotenv import load_dotenv

# '경기도 포천시' · '서울특별시' · '경기 안산시' · '충청남도 홍성군'
RE_ADMIN = re.compile(r'^(?P<sido>[가-힣]+?(?:특별자치도|특별자치시|특별시|광역시|도|남도|북도)?)'
                      r'(?:\s+(?P<sigungu>[가-힣]+?[시군구]))?\s*$')
SIDO_ONLY = ('특별시', '광역시', '특별자치시')


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def split_admin(addr):
    """행정구역 문자열 → (sido, sigungu). 파싱 불가 시 (None, None)."""
    a = (addr or '').strip()
    if not a:
        return None, None
    parts = a.split()
    if len(parts) == 1:
        return (parts[0], None) if any(parts[0].endswith(s) for s in SIDO_ONLY) or len(parts[0]) >= 3 \
            else (None, None)
    m = RE_ADMIN.match(a)
    if m and m.group('sido'):
        return m.group('sido'), m.group('sigungu')
    # '경기 안산시' 처럼 약칭 + 시군 — 앞 토큰을 시도로 본다
    return parts[0], (parts[1] if re.search(r'[시군구]$', parts[1]) else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', nargs='+', default=['ep3_graph', 'ep5_graph', 'ccop_ep_integrated'])
    args = ap.parse_args()
    load_dotenv()

    conn = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'),
                            dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                            password=os.getenv('DB_PASSWORD'), connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()

    for g in args.graph:
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', g):
            raise SystemExit(f'invalid graph: {g}')
        cur.execute(f'SET graph_path = {g}')
        try:
            cur.execute("MATCH (l:vt_loc) RETURN count(l)")
        except Exception:
            conn.rollback()
            print(f'  [{g}] vt_loc 없음 — 스킵')
            continue
        if not cur.fetchone()[0]:
            print(f'  [{g}] vt_loc 0건 — 스킵')
            continue

        # ── cell_tower: bsst_addr 에서 행정구역·이름 파생 ──
        cur.execute("MATCH (l:vt_loc {loc_type:'cell_tower'}) RETURN l.loc_id, l.bsst_addr")
        ct = 0
        for lid, addr in cur.fetchall():
            sido, sigungu = split_admin(addr)
            setp = [f"l.address = '{esc(addr)}'", f"l.place_name = '{esc(addr)}'"]
            if sido:
                setp.append(f"l.sido_nm = '{esc(sido)}'")
            if sigungu:
                setp.append(f"l.sigungu_nm = '{esc(sigungu)}'")
            cur.execute(f"MATCH (l:vt_loc {{loc_id: '{esc(lid)}'}}) SET {', '.join(setp)}")
            ct += 1

        # ── poi(은행 영업점): loc_id 에서 지점명 파생('기업은행 상동' → '상동') ──
        cur.execute("MATCH (l:vt_loc {loc_type:'poi'}) RETURN l.loc_id")
        po = 0
        for (lid,) in cur.fetchall():
            # 지점명을 축약하지 않고 loc_id 전체를 쓴다 — 질문이 '기업은행 상동'처럼 길게 와도
            # CONTAINS 로 잡히고, '상동'처럼 짧게 와도 잡힌다(축약하면 긴 질문이 0건이 된다).
            place = lid or ''
            cur.execute(f"MATCH (l:vt_loc {{loc_id: '{esc(lid)}'}}) "
                        f"SET l.place_name = '{esc(place)}'")
            po += 1

        cur.execute("MATCH (l:vt_loc) WHERE l.place_name IS NOT NULL RETURN count(l)")
        has_place = cur.fetchone()[0]
        cur.execute("MATCH (l:vt_loc) WHERE l.sido_nm IS NOT NULL RETURN count(l)")
        has_sido = cur.fetchone()[0]
        cur.execute("MATCH (l:vt_loc) RETURN count(l)")
        tot = cur.fetchone()[0]
        print(f'  [{g}] cell_tower {ct} · poi {po} 보강 → '
              f'place_name {has_place}/{tot} · sido_nm {has_sido}/{tot}')
    conn.close()


if __name__ == '__main__':
    main()
