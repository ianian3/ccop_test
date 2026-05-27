"""V4.0 온톨로지 자연어 쿼리 종합 테스트 (40 케이스)
============================================================
대상 그래프: tccop_v40_demo (178 노드 / 207 엣지)
모델:       qwen25_t2c_v39_v1 (현행 운영)

카테고리:
  A. 단일 노드 (4)        B. V3.7 신규 (5)
  C. 1-hop 관계 (8)       D. 2-hop 체인 (4)
  E. 3-hop+ 체인 (3)      F. V4.0 메타 필터 (5)
  G. 집계/통계 (4)        H. ORDER BY / LIMIT (3)
  I. 복합 조건 (4)        J. 자연어 변형 (5 — 동일 의도, 표현 변화)

실행:
    python3 scripts/test_v40_natural_query.py [--limit N]
"""
import sys, time, json, os, argparse
sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')

from app import create_app
from app.services.langgraph_agent import LangGraphAgent

GRAPH = 'tccop_v40_demo'

# ────────────────────────────────────────────────────────────
# 40 테스트 케이스: (category, question, must_contain_keywords)
# ────────────────────────────────────────────────────────────
TESTS = [
    # ═════════════════ A. 단일 노드 조회 (4) ═════════════════
    ('A.단일', 'vt_psn 노드 5개 보여줘',                            ['vt_psn', 'LIMIT 5']),
    ('A.단일', 'vt_bacnt 노드 전부 출력',                           ['vt_bacnt']),
    ('A.단일', '사건 노드 보여줘',                                  ['vt_case']),
    ('A.단일', '중계기 노드 보여줘',                                ['vt_dev']),

    # ═════════════════ B. V3.7 신규 (5) ═════════════════
    ('B.V3.7', "dev_type 이 'relay_station' 인 기기 보여줘",        ['vt_dev', 'relay_station']),
    ('B.V3.7', 'is_anonymous 가 true 인 인물 보여줘',               ['vt_psn', 'is_anonymous']),
    ('B.V3.7', 'site_cluster 노드 보여줘',                          ['site_cluster']),
    ('B.V3.7', 'pt_cluster 노드 보여줘',                            ['pt_cluster']),
    ('B.V3.7', 'belongs_to_campaign 엣지 보여줘',                   ['belongs_to_campaign']),

    # ═════════════════ C. 1-hop 관계 (8) ═════════════════
    ('C.1hop', '사건의 피의자 목록',                                ['vt_case', 'vt_psn', 'suspect_in']),
    ('C.1hop', '사건의 피해자 목록',                                ['vt_case', 'vt_psn', 'victim_in']),
    ('C.1hop', '피의자가 보유한 계좌 보여줘',                       ['vt_psn', 'has_account', 'vt_bacnt']),
    ('C.1hop', '인물이 소유한 전화 보여줘',                         ['vt_psn', 'owns_phone', 'vt_telno']),
    ('C.1hop', '전화가 발신한 통화 보여줘',                         ['vt_telno', 'caller', 'vt_call']),
    ('C.1hop', '사이트에 호스팅된 IP 보여줘',                       ['vt_ip', 'hosts', 'vt_site']),
    ('C.1hop', '진정서에서 전환된 사건',                            ['vt_petition', 'filed_as', 'vt_case']),
    ('C.1hop', '중계기를 경유한 전화 보여줘',                       ['vt_telno', 'used_in_device', 'vt_dev']),

    # ═════════════════ D. 2-hop 체인 (4) ═════════════════
    ('D.2hop', '사건과 관련된 피의자가 보유한 계좌',                ['vt_case', 'vt_psn', 'vt_bacnt']),
    ('D.2hop', '피의자가 소유한 전화의 통화 기록',                  ['vt_psn', 'vt_telno', 'vt_call']),
    ('D.2hop', '사이트 클러스터에 속한 사이트의 IP',                ['site_cluster', 'vt_site', 'vt_ip']),
    ('D.2hop', '익명 인물이 소유한 계좌 보여줘',                    ['vt_psn', 'is_anonymous', 'vt_bacnt']),

    # ═════════════════ E. 3-hop+ 체인 (3) ═════════════════
    ('E.3hop', '계좌간 자금 이체 흐름 추적',                        ['vt_bacnt', 'vt_transfer', 'from_account', 'to_account']),
    ('E.3hop', '사건 피의자가 보유한 계좌의 이체 내역',             ['vt_case', 'vt_psn', 'vt_bacnt', 'vt_transfer']),
    ('E.3hop', '피싱 캠페인의 사이트의 호스팅 IP',                  ['site_cluster', 'vt_site', 'vt_ip']),

    # ═════════════════ F. V4.0 메타 필터 (5) ═════════════════
    ('F.메타', "source_domain 이 'osint' 인 노드 보여줘",          ['source_domain', 'osint']),
    ('F.메타', "source_domain 이 'investigation' 인 계좌",         ['vt_bacnt', 'source_domain', 'investigation']),
    ('F.메타', 'reliability_tier 가 1 인 노드',                     ['reliability_tier']),
    ('F.메타', 'reliability_tier 4 이상 노드 보여줘',               ['reliability_tier']),
    ('F.메타', 'OSINT 도메인 계좌의 이체 내역',                     ['vt_bacnt', 'source_domain', 'vt_transfer']),

    # ═════════════════ G. 집계/통계 (4) ═════════════════
    ('G.집계', '사건별 피의자 수 세어줘',                           ['vt_case', 'COUNT', 'suspect_in']),
    ('G.집계', '도메인별 노드 수',                                  ['source_domain', 'COUNT']),
    ('G.집계', '신뢰도 등급별 노드 수',                             ['reliability_tier', 'COUNT']),
    ('G.집계', '이체 총 금액 합계',                                 ['vt_transfer', 'SUM', 'amount']),

    # ═════════════════ H. ORDER BY / LIMIT (3) ═════════════════
    ('H.정렬', '금액이 큰 순으로 이체 5건',                         ['vt_transfer', 'ORDER BY', 'amount', 'DESC', 'LIMIT 5']),
    ('H.정렬', '통화 시간 긴 순으로 10건',                          ['vt_call', 'ORDER BY', 'duration', 'LIMIT 10']),
    ('H.정렬', '최근 이체 5건',                                     ['vt_transfer', 'ORDER BY', 'LIMIT 5']),

    # ═════════════════ I. 복합 조건 (4) ═════════════════
    ('I.복합', '익명이면서 OSINT 출처인 인물 보여줘',                ['vt_psn', 'is_anonymous', 'osint']),
    ('I.복합', "VOIP 통신사이면서 중계기 경유 전화",                ['vt_telno', 'VOIP']),
    ('I.복합', "사건번호 'CASE-2026-A-001' 의 피의자",              ['vt_case', 'CASE-2026-A-001', 'vt_psn']),
    ('I.복합', '금액 100만원 이상 이체',                            ['vt_transfer', 'amount']),

    # ═════════════════ J. 자연어 변형 (5 — 동일 의도) ═════════════════
    ('J.변형', '계좌가 몇 개 있어?',                                ['vt_bacnt', 'COUNT']),
    ('J.변형', '계좌 총 개수 알려줘',                               ['vt_bacnt', 'COUNT']),
    ('J.변형', '강남 사건의 피의자가 누군지 보여줘',                ['vt_case', 'vt_psn', 'suspect_in']),
    ('J.변형', '강남 보이스피싱 일당',                              ['vt_case', 'vt_psn']),
    ('J.변형', '익명 사용자 누구야?',                               ['vt_psn', 'is_anonymous']),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None, help='첫 N 케이스만 실행')
    parser.add_argument('--category', default=None, help='특정 카테고리 prefix (예: B.)')
    args = parser.parse_args()

    cases = TESTS
    if args.category:
        cases = [t for t in cases if t[0].startswith(args.category)]
    if args.limit:
        cases = cases[:args.limit]

    app = create_app(); app.app_context().push()
    agent = LangGraphAgent()

    print('=' * 72)
    print(f'  V4.0 자연어 쿼리 종합 테스트 — 그래프: {GRAPH}')
    print(f'  모델: qwen25_t2c_v39_v1 / 총 {len(cases)} 케이스')
    print('=' * 72)

    results = []
    passed = 0
    cat_stats = {}
    t_total = time.time()

    for i, (cat, q, must) in enumerate(cases, 1):
        t0 = time.time()
        try:
            out = agent.run(q, GRAPH)
            elapsed = (time.time() - t0) * 1000
            cypher = (out or {}).get('cypher') or ''
            elements = (out or {}).get('elements') or []
            err = (out or {}).get('error')

            kw_ok = all(kw.lower() in cypher.lower() for kw in must)
            res_ok = (not err) and (len(elements) > 0 or 'COUNT' in cypher.upper() or 'SUM' in cypher.upper())
            ok = kw_ok and res_ok

            stat = cat_stats.setdefault(cat, {'pass': 0, 'total': 0, 'time_sum': 0})
            stat['total'] += 1
            stat['time_sum'] += elapsed
            if ok: stat['pass'] += 1; passed += 1

            short = (cypher[:90] + '…') if len(cypher) > 90 else cypher
            print(f'  {"✅" if ok else "❌"} [{cat:8s}] {elapsed:5.0f}ms el={len(elements):4d}  ({i:2d}/{len(cases)})')
            print(f'     Q: {q}')
            print(f'     C: {short}')
            if not ok and err: print(f'     E: {str(err)[:80]}')
            results.append({'cat': cat, 'q': q, 'cypher': cypher, 'elements': len(elements),
                            'ok': ok, 'kw_ok': kw_ok, 'res_ok': res_ok,
                            'elapsed_ms': elapsed, 'err': err})
        except Exception as e:
            print(f'  ⚠️  [{cat:8s}] 예외: {e}')
            results.append({'cat': cat, 'q': q, 'ok': False, 'err': str(e)})

    total_time = time.time() - t_total
    print()
    print('=' * 72)
    print(f'  종합: {passed}/{len(cases)} PASS  ({100*passed/len(cases):.1f}%)  /  총 {total_time:.0f}초')
    print('=' * 72)
    print('  카테고리별:')
    for cat in sorted(cat_stats):
        s = cat_stats[cat]
        avg_ms = s['time_sum'] / s['total'] if s['total'] else 0
        print(f"    {cat:10s} {s['pass']:2d}/{s['total']:2d}  ({100*s['pass']/s['total']:5.1f}%)  평균 {avg_ms:.0f}ms")
    print('=' * 72)

    os.makedirs('results', exist_ok=True)
    with open('results/test_v40_natural_query.json', 'w', encoding='utf-8') as f:
        json.dump({'graph': GRAPH, 'model': 'qwen25_t2c_v39_v1',
                   'passed': passed, 'total': len(cases),
                   'category_stats': cat_stats,
                   'total_time_sec': total_time,
                   'results': results}, f, ensure_ascii=False, indent=2)
    print(f'  결과 저장: results/test_v40_natural_query.json')


if __name__ == '__main__':
    main()
