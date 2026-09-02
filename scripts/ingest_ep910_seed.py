#!/usr/bin/env python3
"""EP9/EP10 수동 확정 시드 → ep10_graph (결정론, LLM 무관).

근거·검토: docs/EP910_SEED_DRAFT_20260902.md (승인본 — 초안 결정 반영:
마스킹 계좌·네이버ID 제외, 피해자 황민규 1인, 2차→3차 transferred_to 보류
→ 3차계좌에 tier/inflow_total 속성, 뱅킹 IP는 role 속성으로 기록).
원본: EP10 053_특정 · 054_범죄인지(피의자추가) · 055_체포영장 (EP9 049~052는 인용 정본).
온톨로지: V4.8 — 전 엣지 domain/range 정합 확인(performed_by=Any→Person 포함).
실행: python3 scripts/ingest_ep910_seed.py   (멱등: DROP 후 재생성)
"""
import sys
import os
from datetime import datetime, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
import psycopg2

GRAPH = 'ep10_graph'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def meta(alias, src):
    """공통 provenance SET 절 (V4.8 EDGE_META: source_id MANDATORY)."""
    return (f"{alias}.source_id='{src}', {alias}.creation_method='manual', "
            f"{alias}.verified='true', {alias}.rec_created='{NOW}'")


# ── 시드 정의 (문서 인용 확정 사실만) ────────────────────────────────
CASE = {'flnm': 'EP10-2017-사기', 'case_type': '사기(네이버 중고나라)', 'evid_grade': 'B',
        'note': '사건번호 마스킹→합성ID. 피해자 23명·편취 22,727,000원(055)', 'src': 'EP10-054'}

SUSPECTS = [  # (name, birth_partial, addr_base, role, 출국일, src)
    ('조정모', '860210-1', '남양주시',    '주범(특정 1순위)', '2017-05-07', 'EP10-053'),
    ('최철민', '860505-1', '충북 음성군', '공범',            '2017-05-13', 'EP10-054'),
    ('김혁주', '861201-1', '서울 동대문구', '공범',           '2017-05-10', 'EP10-054'),
    ('최성혁', '850223-1', '충북 음성군', '공범(최철민 형)',  '2017-05-13', 'EP10-054'),
    ('남혁건', '890511-1', '경북 봉화군', '공범',            '2017-05-12', 'EP10-054'),
    ('이정',   '901129-1', '서울 은평구', '공범',            '2017-05-27', 'EP10-054'),
]

VICTIM = ('황민규', 'EP10-054')     # 범죄사실 명시 대표 피해자 1인 (나머지 22명 마스킹)

PERSONS_3RD = [('신민우', 'EP10-054'), ('문범수', 'EP10-054')]  # 기존 vt_psn과 name 병합

ACCOUNTS = [  # (account_no, bank, dpstr, extra_props, src)
    ('49537520206057', '기업', '이진아',
     {'tier': '1차 사기수취', 'note': 'EP1 40사건 수렴 계좌와 동일(통합 병합)'}, 'EP10-054'),
    ('22997642209622', '기업', '신민우',
     {'tier': '3차집금', 'inflow_total': '353330000', 'inflow_period': '2017-03-01~2017-04-04',
      'note': '2차계좌들로부터 수금(054 각주③) — 2차 상세 미상이라 transferred_to 보류'}, 'EP10-054'),
    ('1000333632707', '우리', '문범수',
     {'tier': '3차집금', 'inflow_total': '206450000', 'inflow_period': '2017-03-01~2017-03-21',
      'note': '054 각주④'}, 'EP10-054'),
]

IP = {'ip_addr': '27.193.61.154', 'country': '중국',
      'role': 'crime_070_last_hop|banking_access',
      'note': '범행 070 최종접속(네이버 역추적→조정모)·㈜제이* 농협계좌 뱅킹 IP 4/5', 'src': 'EP10-053'}

PHONE = {'telno': '01008945949', 'note': '조정모 사용(054 p6) — 공범 통화·카톡 연결 단서', 'src': 'EP10-054'}
KAKAO = {'id_val': '카카오톡-8210423', 'platform': 'kakao', 'note': '조정모 사용(053 p5)', 'src': 'EP10-053'}

# 엣지: (설명, MATCH 패턴, 엣지타입, src)
def edge_specs():
    E = []
    for name, _, _, _, dt, src in SUSPECTS:
        E.append((f"suspect_in {name}",
                  f"(a:vt_psn {{name:'{esc(name)}'}}), (b:vt_case {{flnm:'{CASE['flnm']}'}})",
                  'suspect_in', src))
        mov_id = f"EP10-MOV-{name}-{dt.replace('-', '')}"
        E.append((f"performed_by {name} 출국",
                  f"(a:vt_movement {{mov_id:'{esc(mov_id)}'}}), (b:vt_psn {{name:'{esc(name)}'}})",
                  'performed_by', src))
    E.append(("victim_in 황민규",
              f"(a:vt_psn {{name:'황민규'}}), (b:vt_case {{flnm:'{CASE['flnm']}'}})", 'victim_in', 'EP10-054'))
    E.append(("owns_phone 조정모",
              f"(a:vt_psn {{name:'조정모'}}), (b:vt_telno {{telno:'{PHONE['telno']}'}})", 'owns_phone', 'EP10-054'))
    E.append(("uses_id 조정모",
              f"(a:vt_psn {{name:'조정모'}}), (b:vt_id {{id_val:'{esc(KAKAO['id_val'])}'}})", 'uses_id', 'EP10-053'))
    E.append(("used_ip 카톡→중국IP",
              f"(a:vt_id {{id_val:'{esc(KAKAO['id_val'])}'}}), (b:vt_ip {{ip_addr:'{IP['ip_addr']}'}})", 'used_ip', 'EP10-053'))
    E.append(("eg_used_account 사건→이진아계좌",
              f"(a:vt_case {{flnm:'{CASE['flnm']}'}}), (b:vt_bacnt {{account_no:'49537520206057'}})", 'eg_used_account', 'EP10-054'))
    for name, acc in [('신민우', '22997642209622'), ('문범수', '1000333632707')]:
        E.append((f"has_account {name}",
                  f"(a:vt_psn {{name:'{esc(name)}'}}), (b:vt_bacnt {{account_no:'{acc}'}})", 'has_account', 'EP10-054'))
    return E


def main():
    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"DROP GRAPH IF EXISTS {GRAPH} CASCADE")
        cur.execute(f"CREATE GRAPH {GRAPH}")
        safe_set_graph_path(cur, GRAPH)
        for lb in ['vt_case', 'vt_psn', 'vt_bacnt', 'vt_ip', 'vt_telno', 'vt_id', 'vt_movement']:
            cur.execute(f"CREATE VLABEL IF NOT EXISTS {lb}")
        for eb in ['suspect_in', 'victim_in', 'owns_phone', 'uses_id', 'used_ip',
                   'eg_used_account', 'has_account', 'performed_by']:
            cur.execute(f"CREATE ELABEL IF NOT EXISTS {eb}")

        # ── 노드 ──
        cur.execute(f"MERGE (c:vt_case {{flnm:'{CASE['flnm']}'}}) SET c.case_type='{esc(CASE['case_type'])}', "
                    f"c.evid_grade='{CASE['evid_grade']}', c.note='{esc(CASE['note'])}', {meta('c', CASE['src'])}")
        for name, birth, addr, role, _, src in SUSPECTS:
            cur.execute(f"MERGE (p:vt_psn {{name:'{esc(name)}'}}) SET p.role='{esc(role)}', "
                        f"p.birth_partial='{birth}', p.addr_base='{esc(addr)}', p.evid_grade='A', {meta('p', src)}")
        cur.execute(f"MERGE (p:vt_psn {{name:'{esc(VICTIM[0])}'}}) SET p.role='피해자', p.evid_grade='A', {meta('p', VICTIM[1])}")
        for name, src in PERSONS_3RD:
            cur.execute(f"MERGE (p:vt_psn {{name:'{esc(name)}'}}) SET p.role='3차집금 명의', p.evid_grade='A', {meta('p', src)}")
        for acc, bank, dpstr, props, src in ACCOUNTS:
            extra = ", ".join(f"b.{k}='{esc(v)}'" for k, v in props.items())
            cur.execute(f"MERGE (b:vt_bacnt {{account_no:'{acc}'}}) SET b.bank_nm='{bank}', "
                        f"b.dpstr='{esc(dpstr)}', {extra}, b.evid_grade='A', {meta('b', src)}")
        cur.execute(f"MERGE (i:vt_ip {{ip_addr:'{IP['ip_addr']}'}}) SET i.country='{IP['country']}', "
                    f"i.role='{IP['role']}', i.note='{esc(IP['note'])}', i.evid_grade='A', {meta('i', IP['src'])}")
        cur.execute(f"MERGE (t:vt_telno {{telno:'{PHONE['telno']}'}}) SET t.note='{esc(PHONE['note'])}', "
                    f"t.evid_grade='A', {meta('t', PHONE['src'])}")
        cur.execute(f"MERGE (d:vt_id {{id_val:'{esc(KAKAO['id_val'])}'}}) SET d.platform='{KAKAO['platform']}', "
                    f"d.note='{esc(KAKAO['note'])}', d.evid_grade='A', {meta('d', KAKAO['src'])}")
        for name, _, _, _, dt, src in SUSPECTS:
            mov_id = f"EP10-MOV-{name}-{dt.replace('-', '')}"
            cur.execute(f"MERGE (mv:vt_movement {{mov_id:'{esc(mov_id)}'}}) SET mv.mov_type='출국', "
                        f"mv.subtype='immigration', mv.mov_dt='{dt}', mv.dest='중국', mv.evid_grade='A', {meta('mv', src)}")

        # ── 엣지 ──
        for desc, match, etype, src in edge_specs():
            cur.execute(f"MATCH {match} MERGE (a)-[e:{etype}]->(b) SET {meta('e', src)}")

        # ── 검증 출력 ──
        cur.execute("MATCH (n) RETURN label(n), count(n)")
        print('[노드]', dict(cur.fetchall()))
        cur.execute("MATCH ()-[e]->() RETURN type(e), count(e)")
        print('[엣지]', dict(cur.fetchall()))
        cur.execute("MATCH ()-[e]->() WHERE e.source_id IS NULL RETURN count(e)")
        print('[provenance 누락]', cur.fetchone()[0])
        conn.close()
        print(f"[완료] {GRAPH} — 수동 확정 시드 (EP10-053/054/055)")


if __name__ == '__main__':
    main()
