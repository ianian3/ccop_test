#!/usr/bin/env python3
"""v3 재비식별(260828) 데이터로 ep2/ep3/ep4 재적재 오케스트레이터.

DA가 2026-08-28 비식별값을 _v3 로 재생성(EP3/EP4 전화·070 대량, EP2 2건). 원본 폴더가
구/v3 혼재이므로 v3 우선 탐색 + 구 역발신 배제(ingest_call_records 필터)로 신값만 적재.
ep1(무변경) 유지. EP3의 011 kakao·012 ipmac(인라인·불변)은 이번 범위 제외.
실행: python3 scripts/reload_v3.py
"""
import subprocess, os, unicodedata, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
import psycopg2

BASE = '/Users/iankwon/Downloads/00_종합시나리오 및 데이터셋/데이터셋'
SC = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SC, '..'))


def N(p):
    return unicodedata.normalize('NFC', str(p))


def epdir(pfx):
    return [os.path.join(BASE, x) for x in os.listdir(BASE) if N(x).startswith(pfx)][0]


def find_one(d, needle, ext):
    hits = [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs
            if needle in N(f) and f.lower().endswith(ext) and not f.startswith(('.', '~'))]
    v3 = [p for p in hits if '_v3' in N(os.path.basename(p))]
    if v3:
        return v3[0]
    fix = [p for p in hits if '_수정' in N(os.path.basename(p))]
    return (fix or hits)[0] if hits else None


def find_dir(d, needle):
    for r, _, fs in os.walk(d):
        if needle in N(r) and any(not f.startswith('.') for f in fs):
            return r
    return None


def run(args, label):
    print(f'\n>>> {label}')
    r = subprocess.run(['python3'] + args, cwd=ROOT, capture_output=True, text=True)
    for line in (r.stdout + r.stderr).splitlines():
        if any(k in line for k in ['빌드', '적재', '노드:', '엣지:', '롤백', 'Error', 'Traceback', '필수', '스킵']):
            print('   ', line)
    if r.returncode != 0:
        print('   [실패] rc=', r.returncode)
        print((r.stdout + r.stderr)[-800:])
        sys.exit(1)


S = lambda f: os.path.join(SC, f)

# 1) DROP + CREATE (ep1 은 무변경 → 유지)
app = create_app()
with app.app_context():
    conn = psycopg2.connect(**app.config['DB_CONFIG']); conn.autocommit = True; cur = conn.cursor()
    for g in ['ep2_graph', 'ep3_graph', 'ep4_graph']:
        cur.execute(f"DROP GRAPH IF EXISTS {g} CASCADE;")
        cur.execute(f"CREATE GRAPH IF NOT EXISTS {g};")
        print('[reset]', g)
    conn.close()

# 2) EP2 (017 v3 일람표 + 002 v3 더치트 + 015 더치트확장)
d2 = epdir('EP2.')
run([S('ingest_receipt_ledger.py'), '--graph', 'ep2_graph', '--xlsx', find_one(d2, '017', '.xlsx'),
     '--sheet', '01_일람표(더치트 2차)', '--src-id', 'EP2-017-01', '--case-prefix', 'EP2-DC'], 'EP2 017 일람표')
run([S('ingest_thecheat_search.py'), '--graph', 'ep2_graph', '--xlsx', find_one(d2, '002', '.xlsx'),
     '--sheet', '더치트요약', '--src-id', 'EP2-002-thecheat'], 'EP2 002 더치트')
run([S('ingest_thecheat_search.py'), '--graph', 'ep2_graph', '--xlsx', find_one(d2, '015', '.xlsx'),
     '--sheet', '더치트단서요약-전체', '--src-id', 'EP2-015'], 'EP2 015 더치트확장')

# 3) EP3 / EP4 (070 v3 + 통화 v3필터 + 012 김은희 불변)
for ep, g, s070 in [('EP3.', 'ep3_graph', 'EP3-013-070'), ('EP4.', 'ep4_graph', 'EP4-070')]:
    d = epdir(ep)
    r070 = find_dir(d, '070번호'); rcall = find_dir(d, '휴대전화번호'); fkim = find_one(d, '김은희', '.xlsx')
    run([S('ingest_070_subscriber.py'), '--graph', g, '--root', r070, '--src-id', s070], f'{ep} 070 가입자')
    run([S('ingest_call_records.py'), '--graph', g, '--root', rcall], f'{ep} 통화(v3필터)')
    if fkim:
        run([S('ingest_account_txn.py'), '--graph', g, '--xlsx', fkim, '--sheet', '정리',
             '--owner-name', '김은희', '--owner-bank', '농협', '--src-id', 'EP3-012'], f'{ep} 012 김은희 자금')
    else:
        print(f'   {ep} 김은희 파일 없음 — 스킵')

print('\n[완료] ep2/ep3/ep4 v3 재적재 (ep1 유지 · EP3 kakao/ipmac 별도)')
