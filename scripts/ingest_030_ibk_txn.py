#!/usr/bin/env python3
"""EP5 030 기업은행 수신거래내역(계좌별거래명세표) → ep5_graph 적재.

배경: 이 xls 2본은 크로스워크에 '비밀번호 암호화 → 복호화 필요'로 미적재 기록돼 있었으나
      2026-08-28 비식별화 재배포(v3) 이후 암호 없이 열린다(2026-09-08 실측). 내용은
      조지영 3차집금 계좌의 건별 거래 ~1,650건 — 기존 그래프에 없던 세 가지가 들어 있다:
        ① 거래 IP 481건(고유 ~100, 기존 핵심 IP 59.21.209.237 포함 → 교차 실증)
        ② 상대계좌 1,549건 → 건별 transferred_to 보강
        ③ 거래점 1,601건(동·지점 단위) → 인출/입금 위치

매핑(V4.8 정경 내):
  본계좌/상대계좌      vt_bacnt {account_no(숫자만), dpstr, bank_nm}
  이체(입금/출금 방향)  (송금측)-[transferred_to {first/last_dlng_dt, total_amount, txn_count}]->(수취측)
  거래 IP             (본계좌)-[used_ip {creation_method:'etl'}]->(vt_ip)
  거래점              (본계좌)-[located_at {tx_count, wd_count, dep_count, first_dt, last_dt}]->(vt_loc)
                      · vt_loc {loc_id:'기업은행 <지점>', loc_type:'atm_loc', address}
                      · located_at 은 V4.8 정의(domain=Any, range=Location) 재사용.
                        의미상 '고정 객체의 정적 위치'를 '계좌 거래 발생 지점(집계)'으로 확장 사용
                        — 이벤트 노드 없이 건별 위치를 남기는 최소 표현. 감사는 Any 와일드카드로 통과.
  '제휴영업점'·'SPEED4' 등 채널명은 위치가 아니므로 vt_loc 제외(blocklist).

주의:
  · 거래내용(적요)의 사람이름은 노드로 만들지 않는다 — EP5 크로스워크의 명의 오추출 사례 참조.
  · '출금취소'는 건수만 세고 스킵(상쇄 처리 불가).
  · 시트에 페이지 헤더가 반복 삽입돼 있어 거래일 파싱 실패 행은 전부 스킵.
  · 멱등(MERGE). source_id='EP5-030-ibk'.

실행: DB_HOST=localhost DB_PORT=5434 DB_USER=ccop DB_PASSWORD=... \
      python3 scripts/ingest_030_ibk_txn.py [--graph ep5_graph]
"""
import argparse
import os
import pathlib
import re
import unicodedata as ud
from collections import defaultdict

import psycopg2
import xlrd
from dotenv import load_dotenv

SRC_ID = 'EP5-030-ibk'
DATASET = pathlib.Path('/Users/iankwon/Desktop/SKAI/01.연구과제/01.진행과제/경찰청과제/2026')
# 위치가 아닌 거래 채널/기기 명칭 — vt_loc 생성 제외
BRANCH_BLOCKLIST = {'제휴영업점', 'SPEED4', '취급자', '거래점'}


def nfc(v):
    return ud.normalize('NFC', str(v)).strip()


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def norm_acct(v, cell_type=None):
    """계좌번호 정규화 — 숫자만. 숫자셀(float)로 저장된 경우 지수표기 방지."""
    if cell_type == xlrd.XL_CELL_NUMBER:
        s = ('%d' % v) if float(v) == int(v) else str(v)
    else:
        s = str(v)
    d = re.sub(r'\D', '', s)
    return d if len(d) >= 6 else ''


def parse_date(v, book):
    """거래일 셀 → 'YYYY-MM-DD' (텍스트/엑셀날짜 겸용). 실패 시 ''."""
    if isinstance(v, float) and v > 20000:          # 엑셀 날짜 serial
        try:
            y, m, d, *_ = xlrd.xldate_as_tuple(v, book.datemode)
            return f'{y:04d}-{m:02d}-{d:02d}'
        except Exception:
            return ''
    m = re.match(r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', nfc(v))
    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''


def find_files():
    p = [c for c in DATASET.iterdir() if nfc(c.name).startswith('20280831')][0]
    ds = p / '00_종합시나리오 및 데이터셋' / '데이터셋'
    ep5 = [c for c in ds.iterdir() if nfc(c.name).startswith('EP5')][0]
    d030 = [c for c in ep5.iterdir() if nfc(c.name).startswith('030')][0]
    ibk = [c for c in d030.iterdir() if '기업은행' in nfc(c.name)][0]
    out = []
    for tgt in sorted(c for c in ibk.iterdir() if c.is_dir()):
        out += [c for c in tgt.iterdir()
                if '수신거래내역' in nfc(c.name) and c.suffix == '.xls']
    return out


def parse_file(path):
    """xls 1본 → (계좌메타, 거래행 리스트)"""
    wb = xlrd.open_workbook(str(path))
    sh = [s for s in wb.sheets() if '거래내역' in nfc(s.name)][0]
    meta = {'acct': '', 'owner': ''}

    def right_val(i, j):
        """라벨 셀 오른쪽의 첫 비공백 셀 — 병합 셀 때문에 j+1 이 아닐 수 있다(실측 j+3)."""
        for k in range(j + 1, min(j + 6, sh.ncols)):
            v = nfc(sh.cell_value(i, k))
            if v:
                return v
        return ''

    for i in range(min(8, sh.nrows)):
        for j in range(sh.ncols - 1):
            c = nfc(sh.cell_value(i, j))
            if c == '계좌번호' and not meta['acct']:
                meta['acct'] = norm_acct(right_val(i, j))
            elif c == '예금주명' and not meta['owner']:
                meta['owner'] = right_val(i, j)
    hi = next(i for i in range(15)
              if nfc(sh.cell_value(i, 0)) == '거래일')
    hdr = {nfc(sh.cell_value(hi, j)): j for j in range(sh.ncols)}
    col = {k: hdr[k] for k in ('거래일', '구분', '거래금액', '거래점', '송금은행', '상대계좌번호', 'IP')}
    rows, cancel = [], 0
    for i in range(hi + 1, sh.nrows):
        dt = parse_date(sh.cell_value(i, col['거래일']), wb)
        if not dt:
            continue                                 # 반복 페이지헤더/메타 행
        gu = nfc(sh.cell_value(i, col['구분']))
        if gu == '출금취소':
            cancel += 1
            continue
        if gu not in ('입금', '출금'):
            continue
        amt_cell = sh.cell_value(i, col['거래금액'])
        try:
            amt = int(float(amt_cell))
        except (TypeError, ValueError):
            amt = 0
        ip = nfc(sh.cell_value(i, col['IP']))
        rows.append({
            'dt': dt, 'gu': gu, 'amt': amt,
            'branch': nfc(sh.cell_value(i, col['거래점'])),
            'bank': nfc(sh.cell_value(i, col['송금은행'])).replace('은행', ''),
            'cp': norm_acct(sh.cell_value(i, col['상대계좌번호']),
                            sh.cell_type(i, col['상대계좌번호'])),
            'ip': ip if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', ip) else '',
        })
    return meta, rows, cancel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', default='ep5_graph')
    args = ap.parse_args()
    load_dotenv()                                    # 내보낸 환경변수가 우선

    conn = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'),
                            dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                            password=os.getenv('DB_PASSWORD'), connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', args.graph):
        raise SystemExit(f'invalid graph: {args.graph}')
    cur.execute(f'SET graph_path = {args.graph}')
    cur.execute('CREATE VLABEL IF NOT EXISTS vt_loc')
    cur.execute('CREATE ELABEL IF NOT EXISTS located_at')

    n_node = n_edge = 0

    def merge_acct(acct, props):
        nonlocal n_node
        setp = ', '.join(f"b.{k} = '{esc(v)}'" for k, v in props.items() if v)
        q = f"MERGE (b:vt_bacnt {{account_no: '{esc(acct)}'}})"
        cur.execute(q + (f' SET {setp}' if setp else ''))
        n_node += 1

    for f in find_files():
        meta, rows, cancel = parse_file(f)
        if not meta['acct']:
            print(f'  ⚠ 계좌번호 미검출 — 스킵: {nfc(f.name)}')
            continue
        acct = meta['acct']
        print(f'[{nfc(f.name)[:46]}] 계좌 {acct}({meta["owner"]}) · '
              f'거래 {len(rows)}건 · 출금취소 스킵 {cancel}')
        merge_acct(acct, {'dpstr': meta['owner'], 'bank_nm': '기업', 'source_id': SRC_ID})

        # ── ① 이체 집계: (상대→본) 입금 / (본→상대) 출금 ──
        agg = defaultdict(lambda: {'n': 0, 'amt': 0, 'first': '9999', 'last': ''})
        # ── ② IP / ③ 거래점 집계 ──
        ipagg = defaultdict(lambda: {'n': 0, 'first': '9999', 'last': ''})
        bragg = defaultdict(lambda: {'n': 0, 'wd': 0, 'dep': 0, 'first': '9999', 'last': ''})
        cp_bank = {}
        for r in rows:
            if r['cp'] and r['cp'] != acct:
                key = (r['cp'], acct) if r['gu'] == '입금' else (acct, r['cp'])
                a = agg[key]
                a['n'] += 1
                a['amt'] += r['amt']
                a['first'] = min(a['first'], r['dt'])
                a['last'] = max(a['last'], r['dt'])
                if r['bank']:
                    cp_bank[r['cp']] = r['bank']
            if r['ip']:
                a = ipagg[r['ip']]
                a['n'] += 1
                a['first'] = min(a['first'], r['dt'])
                a['last'] = max(a['last'], r['dt'])
            br = r['branch']
            if br and br not in BRANCH_BLOCKLIST and not re.match(r'^[A-Z0-9]+$', br):
                a = bragg[br]
                a['n'] += 1
                a['wd' if r['gu'] == '출금' else 'dep'] += 1
                a['first'] = min(a['first'], r['dt'])
                a['last'] = max(a['last'], r['dt'])

        for (src, dst), a in agg.items():
            for cp in (src, dst):
                if cp != acct:
                    merge_acct(cp, {'bank_nm': cp_bank.get(cp, ''), 'source_id': SRC_ID})
            cur.execute(
                f"MATCH (a:vt_bacnt {{account_no: '{esc(src)}'}}), "
                f"(b:vt_bacnt {{account_no: '{esc(dst)}'}}) "
                f"MERGE (a)-[r:transferred_to]->(b) "
                f"SET r.first_dlng_dt = '{a['first']}', r.last_dlng_dt = '{a['last']}', "
                f"r.total_amount = {a['amt']}, r.txn_count = {a['n']}, "
                f"r.source_id = '{SRC_ID}'")
            n_edge += 1

        for ip, a in ipagg.items():
            cur.execute(f"MERGE (i:vt_ip {{ip_addr: '{esc(ip)}'}}) "
                        f"SET i.source_id = '{SRC_ID}'")
            cur.execute(
                f"MATCH (b:vt_bacnt {{account_no: '{esc(acct)}'}}), "
                f"(i:vt_ip {{ip_addr: '{esc(ip)}'}}) "
                f"MERGE (b)-[r:used_ip]->(i) "
                f"SET r.source_id = '{SRC_ID}', r.creation_method = 'etl', "
                f"r.tx_count = {a['n']}, r.first_dt = '{a['first']}', r.last_dt = '{a['last']}'")
            n_node += 1
            n_edge += 1

        for br, a in bragg.items():
            lid = f'기업은행 {br}'
            cur.execute(f"MERGE (l:vt_loc {{loc_id: '{esc(lid)}'}}) "
                        f"SET l.loc_type = 'atm_loc', l.address = '{esc(lid)}', "
                        f"l.source_id = '{SRC_ID}'")
            cur.execute(
                f"MATCH (b:vt_bacnt {{account_no: '{esc(acct)}'}}), "
                f"(l:vt_loc {{loc_id: '{esc(lid)}'}}) "
                f"MERGE (b)-[r:located_at]->(l) "
                f"SET r.tx_count = {a['n']}, r.wd_count = {a['wd']}, r.dep_count = {a['dep']}, "
                f"r.first_dt = '{a['first']}', r.last_dt = '{a['last']}', "
                f"r.source_id = '{SRC_ID}'")
            n_node += 1
            n_edge += 1
        print(f'  이체쌍 {len(agg)} · IP {len(ipagg)} · 거래점 {len(bragg)}'
              f'(채널 제외 {len(set(r["branch"] for r in rows if r["branch"]) - set(bragg))})')

    print(f'[완료] MERGE 노드 {n_node} · 엣지 {n_edge}')
    cur.execute('MATCH (l:vt_loc) RETURN count(l)')
    print(f'[검증] vt_loc {cur.fetchone()[0]} · ', end='')
    cur.execute("MATCH ()-[r:used_ip]->() WHERE r.source_id = 'EP5-030-ibk' RETURN count(r)")
    print(f'used_ip(신규) {cur.fetchone()[0]} · ', end='')
    cur.execute("MATCH ()-[r:transferred_to]->() WHERE r.source_id = 'EP5-030-ibk' RETURN count(r)")
    print(f'transferred_to(신규) {cur.fetchone()[0]}')
    conn.close()


if __name__ == '__main__':
    main()
