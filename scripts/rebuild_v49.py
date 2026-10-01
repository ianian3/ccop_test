#!/usr/bin/env python3
"""V4.9 그래프 재구축 (정합 2단계 2e) — 기존 그래프는 그대로 두고 '<이름><접미사>' 로 나란히 새로 만든다.

대상
  integrated  EP 원본(ep1~ep10_graph) → <ccop_ep_integrated><sfx>
              build_integrated_graph → refine_integrated_graph → graph_analytics --set  (rebuild_all.sh ①~③)
  v40         스테이징(test_v40)의 적재 배치(source_id)마다 → <v40_배치><sfx>   ※ 기본 제외(--only v40 로만)
              ⚠ 2026-10-01 리허설 결과 '재현'이 되지 않는다: 운영 v40_* 는 만든 경로가 제각각이다
                (업로드 당시 스테이징 전체 스냅숏, 규격 CSV 참조 적재기 scripts/load_partner_csv.py 직행 등).
                배치 필터로는 다른 배치에 있던 마스터(전화·계좌)가 빠져 통화·이체 엣지가 비고(예: 0921_01 노드 11,682→5,317),
                규격 CSV 직행분(0922_01)은 원본 CSV 가 있어야 같은 내용이 된다. 비교·진단용으로만 쓴다

안전장치
  · 기본은 계획만 출력(dry-run). 실제로 쓰려면 --apply
  · 산출 그래프 이름은 반드시 접미사로 끝나야 하고(기존 그래프 덮어쓰기 금지), 이미 있으면 --replace 가 있어야 지운다
  · 비교 DB(--compare-env)는 읽기 전용 세션으로만 연다 — 리허설 때 운영 DB 의 기존 그래프 수치를 읽는 용도

결과: 그래프별 SoT 감사(scripts/audit_v49.audit) + 기존 그래프와 라벨·엣지 수 비교 → results/rebuild_v49_<시각>.json

예)
  # 로컬 리허설: 로컬 DB 에 만들고, 운영 DB(읽기 전용)의 기존 그래프와 비교
  DB_HOST=127.0.0.1 DB_PORT=5434 DB_NAME=tccopdb DB_USER=ccop DB_PASSWORD=… \\
    python3 scripts/rebuild_v49.py --compare-env .env --apply
  # 운영(2e-2, 쓰기 계정·반영 승인 후): 같은 DB 에 만들고 같은 DB 의 기존 그래프와 비교
  python3 scripts/rebuild_v49.py --apply
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

import psycopg2  # noqa: E402

from app.database import validate_graph_path  # noqa: E402

INTEGRATED = 'ccop_ep_integrated'
EP_GRAPHS = [f'ep{i}_graph' for i in range(1, 11)]
STAGING = 'test_v40'


def _connect(env, readonly=False):
    conn = psycopg2.connect(dbname=env['DB_NAME'], user=env['DB_USER'], password=env.get('DB_PASSWORD'),
                            host=env['DB_HOST'], port=env['DB_PORT'], connect_timeout=10)
    if readonly:
        conn.set_session(readonly=True, autocommit=True)
    else:
        conn.autocommit = True
    return conn


def _graphs(cur):
    cur.execute('SELECT graphname FROM ag_graph')
    return {r[0] for r in cur.fetchall()}


def _batches(cur):
    cur.execute('SELECT DISTINCT source_id FROM "test_v40".tb_prsn UNION SELECT DISTINCT source_id FROM "test_v40".tb_fin_bacnt '
                'UNION SELECT DISTINCT source_id FROM "test_v40".tb_telno_mst UNION SELECT DISTINCT source_id FROM "test_v40".tb_incdnt_mst '
                'UNION SELECT DISTINCT source_id FROM "test_v40".tb_fin_bacnt_dlng UNION SELECT DISTINCT source_id FROM "test_v40".tb_telno_call_dtl')
    return sorted(r[0] for r in cur.fetchall() if r[0])


def plan(cur, cmp_cur, sfx, only):
    have, old = _graphs(cur), _graphs(cmp_cur)
    steps, notes = [], []
    if 'integrated' in only:
        miss = [g for g in EP_GRAPHS if g not in have]
        if miss:
            notes.append(f'통합: 원본 EP 그래프 없음 {miss} — 건너뜀')
        else:
            steps.append({'kind': 'integrated', 'target': INTEGRATED + sfx, 'old': INTEGRATED if INTEGRATED in old else None})
    if 'v40' in only:
        for sid in _batches(cur):
            g = sid.lower()                                # 운영 그래프명은 소문자 (v40_20260813_EP02 → v40_20260813_ep02)
            if not validate_graph_path(g):
                notes.append(f'v40: 그래프명으로 쓸 수 없는 배치 {sid!r} — 건너뜀')
            elif g in old:
                steps.append({'kind': 'v40', 'source_id': sid, 'target': g + sfx, 'old': g})
            else:
                notes.append(f'v40: 배치 {sid} 에 대응하는 기존 그래프 없음 — 건너뜀')
        for g in sorted(x for x in old if x.startswith('v40_2026') and not x.endswith(sfx)):
            if g not in {s.get('old') for s in steps}:
                notes.append(f'v40: 기존 그래프 {g} 의 배치가 스테이징에 없음 — 재현 불가(유지)')
    for s in steps:
        s['exists'] = s['target'] in have
    return steps, notes


def _run(cmd, env):
    t = time.time()
    p = subprocess.run([sys.executable] + cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    tail = (p.stdout or '').strip().splitlines()[-3:]
    if p.returncode:
        raise RuntimeError(f'{cmd[0]} 실패(rc={p.returncode}): {(p.stderr or "").strip()[-800:]}')
    return {'cmd': ' '.join(cmd), 'sec': round(time.time() - t, 1), 'tail': tail}


def build(step, env):
    tgt = step['target']
    if step['kind'] == 'integrated':
        return [_run(['scripts/build_integrated_graph.py', '--target', tgt], env),
                _run(['scripts/refine_integrated_graph.py', '--graph', tgt], env),
                _run(['scripts/graph_analytics.py', '--graph', tgt, '--set'], env)]
    from app import create_app
    from app.services.rdb_to_graph_service import RdbToGraphService
    app = create_app()
    with app.app_context():
        t = time.time()
        ok, stats = RdbToGraphService.transfer_data(tgt, source_schema=STAGING, source_ids=[step['source_id']])
        if not ok:
            raise RuntimeError(f'transfer_data 실패: {stats}')
        return [{'cmd': f'transfer_data({tgt}, source_ids=[{step["source_id"]}])', 'sec': round(time.time() - t, 1),
                 'tail': [json.dumps({k: v for k, v in stats.items() if k != 'v37'}, ensure_ascii=False)]}]


def compare(old, new):
    def diff(a, b):
        return {k: [a.get(k, 0), b.get(k, 0)] for k in sorted(set(a) | set(b)) if a.get(k, 0) != b.get(k, 0)}
    def by_type(et):
        out = {}
        for k, n in et.items():
            t = k.split('|')[0]
            out[t] = out.get(t, 0) + n
        return out
    return {'nodes': [old['nodes'], new['nodes']], 'edges': [old['edges'], new['edges']],
            'labels': diff(old['labels'], new['labels']),
            'edge_types': diff(by_type(old['edge_types']), by_type(new['edge_types']))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--suffix', default='_v49')
    ap.add_argument('--only', nargs='+', choices=['integrated', 'v40'], default=['integrated'])
    ap.add_argument('--batches', nargs='+', help='v40 배치(source_id)만 골라서')
    ap.add_argument('--compare-env', help='기존 그래프를 읽을 DB 의 env 파일(읽기 전용). 없으면 대상 DB')
    ap.add_argument('--apply', action='store_true', help='실제로 쓴다 (없으면 계획만)')
    ap.add_argument('--replace', action='store_true', help='산출 그래프가 이미 있으면 지우고 다시 만든다')
    a = ap.parse_args()
    if not validate_graph_path('x' + a.suffix) or not a.suffix.startswith('_'):
        sys.exit(f'허용되지 않는 접미사: {a.suffix!r}')

    env = dict(os.environ)
    if not env.get('DB_HOST'):
        from dotenv import dotenv_values
        env.update({k: v for k, v in dotenv_values(os.path.join(ROOT, '.env')).items() if k.startswith('DB_')})
    conn = _connect(env)
    cur = conn.cursor()
    if a.compare_env:
        from dotenv import dotenv_values
        cenv = dotenv_values(a.compare_env)
        cmp_conn = _connect(cenv, readonly=True)
        cmp_label = f"{cenv['DB_HOST']}:{cenv['DB_PORT']} (읽기 전용)"
    else:
        cmp_conn, cmp_label = _connect(env, readonly=True), '대상 DB'
    cmp_cur = cmp_conn.cursor()

    steps, notes = plan(cur, cmp_cur, a.suffix, a.only)
    if a.batches:
        steps = [s for s in steps if s['kind'] != 'v40' or s['source_id'] in a.batches]
    print(f"[대상 DB] {env['DB_HOST']}:{env['DB_PORT']}/{env['DB_NAME']} · [비교 DB] {cmp_label}")
    for s in steps:
        flag = ' (이미 있음 — --replace 필요)' if s['exists'] and not a.replace else (' (재생성)' if s['exists'] else '')
        print(f"  {s['kind']:10} {s['target']:32} ← 비교 {s['old'] or '-'}{flag}")
    for n in notes:
        print(f'  · {n}')
    if not a.apply:
        print('[dry-run] 쓰지 않았습니다. 실제로 만들려면 --apply')
        return

    import importlib.util
    _sp = importlib.util.spec_from_file_location("audit_v49", os.path.join(ROOT, "scripts", "audit_v49.py"))
    _m = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_m)
    audit = _m.audit
    report = {'at': datetime.datetime.now().isoformat(timespec='seconds'), 'target_db': f"{env['DB_HOST']}:{env['DB_PORT']}",
              'compare_db': cmp_label, 'suffix': a.suffix, 'notes': notes, 'graphs': []}
    for s in steps:
        tgt = s['target']
        assert tgt.endswith(a.suffix) and validate_graph_path(tgt)    # 기존 그래프 덮어쓰기 금지
        if s['exists']:
            if not a.replace:
                print(f'[건너뜀] {tgt} 이미 있음'); continue
            cur.execute(f'DROP GRAPH {tgt} CASCADE')
        print(f'[생성] {tgt} …', flush=True)
        rec = {**s, 'log': build(s, env)}
        rec['audit'] = audit(cur, tgt)
        if s['old']:
            rec['compare'] = compare(audit(cmp_cur, s['old']), rec['audit'])
        v, c = rec['audit']['violation_count'], rec.get('compare', {})
        print(f"  노드 {c.get('nodes', ['-', rec['audit']['nodes']])} · 엣지 {c.get('edges', ['-', rec['audit']['edges']])}"
              f" · 위반 {v}{'' if not v else ' ' + json.dumps({k: d for k, d in rec['audit']['violations'].items() if d}, ensure_ascii=False)[:300]}",
              flush=True)
        report['graphs'].append(rec)
    os.makedirs(os.path.join(ROOT, 'results'), exist_ok=True)
    out = os.path.join(ROOT, 'results', f"rebuild_v49_{datetime.datetime.now():%Y%m%d_%H%M%S}.json")
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    bad = sum(g['audit']['violation_count'] for g in report['graphs'])
    print(f"[완료] 그래프 {len(report['graphs'])}개 · 위반 합계 {bad} · 보고서 {os.path.relpath(out, ROOT)}")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
