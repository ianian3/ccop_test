#!/usr/bin/env python3
"""EP9 수동 확정 시드 → ep9_graph (결정론, LLM 무관).

EP9(049~052 수사보고 4차 ①~④)는 정형 없음(PDF) — EP10-053이 '前보고서 ①~④'로
인용한 확정 사실 중 **EP9 고유분**(해외송금 4차 단계)을 별도 그래프로 적재.
  · IP 27.193.61.154(중국)에서 인터넷뱅킹으로 계좌 8개에 합계 159,522,500원 송금
    (수취명 WANG/ZHAO/DEI/ZHENG 등 중국계 — 개인명 마스킹이라 수취인 노드는 제외)
  · 계좌번호 8개는 EP10-053 p3·p5 차트에서 판독 (별지 그대로)
검토 근거: docs/EP910_SEED_DRAFT_20260902.md (EP9는 인용 정본 원칙).
실행: python3 scripts/ingest_ep9_seed.py   (멱등: DROP 후 재생성)
"""
import sys
import os
from datetime import datetime, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
import psycopg2

GRAPH = 'ep9_graph'
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')
SRC = 'EP9-050(인용:EP10-053)'   # 4차-② 보고 내용, EP10-053 p3~5 인용 정본

CASE_FLNM = 'EP10-2017-사기'      # ep10 시드와 동일 사건 — 통합 시 병합
IP_ADDR = '27.193.61.154'

# EP10-053 p5 차트 판독 — 해외송금 수취 계좌 8개 (합계 159,522,500원)
REMIT_ACCOUNTS = ['3560030496013', '91930201681135', '79660104108561', '110426116935',
                  '3020925365091', '52780201358711', '110448413581', '39191113092807']


def meta(alias):
    return (f"{alias}.source_id='{SRC}', {alias}.creation_method='manual', "
            f"{alias}.verified='true', {alias}.rec_created='{NOW}'")


def main():
    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"DROP GRAPH IF EXISTS {GRAPH} CASCADE")
        cur.execute(f"CREATE GRAPH {GRAPH}")
        safe_set_graph_path(cur, GRAPH)
        for lb in ['vt_case', 'vt_bacnt', 'vt_ip']:
            cur.execute(f"CREATE VLABEL IF NOT EXISTS {lb}")
        cur.execute("CREATE ELABEL IF NOT EXISTS eg_used_account")

        cur.execute(f"MERGE (c:vt_case {{flnm:'{CASE_FLNM}'}}) SET c.case_type='사기(네이버 중고나라)', "
                    f"c.evid_grade='B', c.note='EP9 4차보고 — 해외송금 단계(ep10 시드와 동일 사건)', {meta('c')}")
        cur.execute(f"MERGE (i:vt_ip {{ip_addr:'{IP_ADDR}'}}) SET i.country='중국', "
                    f"i.role='crime_070_last_hop|banking_access|remit_origin', "
                    f"i.note='이 IP의 뱅킹 접속으로 8계좌 해외성 송금 실행(4차-②)', i.evid_grade='A', {meta('i')}")
        for acc in REMIT_ACCOUNTS:
            cur.execute(f"MERGE (b:vt_bacnt {{account_no:'{acc}'}}) SET "
                        f"b.tier='4차 해외송금 수취', b.remit_via_ip='{IP_ADDR}', "
                        f"b.remit_total_grp='159522500(8계좌 합계, 개별액 마스킹)', "
                        f"b.recipient_hint='중국계 수취명(WANG/ZHAO/DEI/ZHENG 등)', b.evid_grade='A', {meta('b')}")
            cur.execute(f"MATCH (c:vt_case {{flnm:'{CASE_FLNM}'}}), (b:vt_bacnt {{account_no:'{acc}'}}) "
                        f"MERGE (c)-[e:eg_used_account]->(b) SET e.role='4차 해외송금 수취', {meta('e')}")

        cur.execute("MATCH (n) RETURN label(n), count(n)")
        print('[노드]', dict(cur.fetchall()))
        cur.execute("MATCH ()-[e]->() RETURN type(e), count(e)")
        print('[엣지]', dict(cur.fetchall()))
        cur.execute("MATCH ()-[e]->() WHERE e.source_id IS NULL RETURN count(e)")
        print('[provenance 누락]', cur.fetchone()[0])
        conn.close()
        print(f"[완료] {GRAPH} — EP9 해외송금 4차 단계 시드")


if __name__ == '__main__':
    main()
