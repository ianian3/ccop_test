#!/usr/bin/env python3
"""더치트 검색 확장 시트('검색대상 → 추가단서') → 그래프 적재 (결정론, LLM 무관).

004 '02_더치트 검색 방법' 등: 계좌/전화를 더치트에 검색 → 발견된 추가단서(전화 / 명의·은행·계좌).
접수내역(사건-피해자)과 구조가 달라 별도 매핑:
  검색대상(계좌/전화)  --[linked_to {via:'thecheat', victims, damage}]-->  발견단서(전화/계좌)
  발견단서가 '명의·은행·계좌' 형식이면  vt_psn -[has_account]-> vt_bacnt 로 분해.
  모든 노드는 vt_src('더치트')로 sourced_from (OSINT tier4 provenance).

멱등(MERGE). 실행: python3 scripts/ingest_thecheat_search.py --xlsx <f> --sheet '02_더치트 검색 방법' [--dry-run]
"""
import argparse
import re
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
import psycopg2

GRAPH = 'tccop_graph_v6'
BANK_RE = re.compile(r'(농협|신한|국민|우리|기업|하나|카카오|SC|씨티|수협|우체국|새마을|신협|부산|대구|경남|광주|전북|제주)')


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def norm_num(v):
    return re.sub(r'[-\s]', '', str(v)) if v else ''


def classify(v):
    """단서/검색대상 문자열 분류 → ('telno'|'account'|'holder', 파싱결과)."""
    s = str(v).strip()
    if '·' in s or '،' in s:                      # 명의·은행·계좌 형식
        parts = [p.strip() for p in re.split(r'[·,]', s) if p.strip()]
        name = parts[0] if parts else ''
        bank = ''
        acct = ''
        for p in parts[1:]:
            if BANK_RE.search(p):
                bank = BANK_RE.search(p).group(1)
            elif norm_num(p).isdigit() and len(norm_num(p)) >= 10:
                acct = norm_num(p)
        return 'holder', {'name': name, 'bank': bank, 'acct': acct}
    n = norm_num(s)
    if re.fullmatch(r'0(10|70)\d{7,8}', n):
        return 'telno', {'telno': n}
    if n.isdigit() and len(n) >= 10:
        return 'account', {'acct': n}
    return 'other', {'raw': s}


def _map_cols(rows):
    """헤더(병합 2~3행) 기반 컬럼 매핑 — 검색대상/피해자/피해금/추가단서 컬럼 + 데이터 시작행.
    002(피해금 있음, 단서 col4+)·015(피해금 없음, 단서 col3+) 모두 대응."""
    ncol = max(len(r) for r in rows[:4])
    _KWS = ['검색대상', '피해자', '피해금', '단서', '연번', '검색결과']
    def is_hdr(r):
        return sum(1 for c in r if c and any(k in str(c).replace('\n', '') for k in _KWS)) >= 2
    hdr_rows = [i for i in range(min(4, len(rows))) if is_hdr(rows[i])]
    htext = [''] * ncol
    for i in hdr_rows:                        # 헤더행만(데이터행 오염 방지), 위→아래 세부 우선
        for j, c in enumerate(rows[i]):
            if c and str(c).strip():
                htext[j] = str(c).strip().replace('\n', '')
    _data_start = (max(hdr_rows) + 1) if hdr_rows else 0
    def find(kw):
        for i, h in enumerate(htext):
            if kw in h:
                return i
        return None
    target = find('검색대상')
    victim = find('피해자')
    damage = find('피해금')
    clues = [i for i, h in enumerate(htext) if '단서' in h]
    seq = find('연번')
    seq = seq if seq is not None else 0
    start = _data_start
    for j in range(_data_start, len(rows)):
        r = rows[j]
        v = r[seq] if seq < len(r) else None
        tv = r[target] if target is not None and target < len(r) else None
        if v is not None and str(v).strip().isdigit() and tv:
            start = j
            break
    return target, victim, damage, clues, start


def build(xlsx, sheet, src_id):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    ws = wb[sheet]
    if ws.sheet_state != 'visible':
        raise SystemExit(f"'{sheet}'는 숨김 시트(state={ws.sheet_state}).")
    rows = list(ws.iter_rows(values_only=True))
    t_col, v_col, d_col, clue_cols, start = _map_cols(rows)
    if t_col is None or not clue_cols:
        raise SystemExit(f"검색대상/추가단서 컬럼 미발견 (헤더 확인). target={t_col} clues={clue_cols}")
    nodes, edges = {}, []

    def node(label, key, props):
        k = (label, key)
        nodes.setdefault(k, {})
        nodes[k].update({kk: vv for kk, vv in props.items() if vv not in (None, '')})
        return k

    def edge(rel, a, b, props):
        edges.append((rel, a, b, props))

    src_k = node('vt_src', 'src:더치트', {'src_id': 'src:더치트', 'src_name': '더치트',
                                        'src_type': 'osint', 'reliability_tier': '4'})

    def id_node(kind, info):
        if kind == 'telno':
            k = node('vt_telno', info['telno'], {'telno': info['telno'], 'source_id': src_id})
        elif kind == 'account':
            k = node('vt_bacnt', info['acct'], {'account_no': info['acct'], 'source_id': src_id})
        elif kind == 'holder':
            k = node('vt_bacnt', info['acct'], {'account_no': info['acct'], 'bank_nm': info.get('bank', ''),
                                                'dpstr': info.get('name', ''), 'source_id': src_id})
            if info.get('name') and info.get('acct'):
                p = node('vt_psn', info['name'], {'name': info['name'], 'source_id': src_id})
                edge('has_account', p, k, {'source_id': src_id})
        else:
            return None
        edge('sourced_from', k, src_k, {'source_id': src_id})
        return k

    def cell(r, i):
        return r[i] if i is not None and i < len(r) else None
    for r in rows[start:]:
        if not r or cell(r, 0) is None:
            continue
        target = cell(r, t_col)
        if not target or not str(target).strip():
            continue
        victims = str(cell(r, v_col)).strip() if cell(r, v_col) else ''
        damage = norm_num(cell(r, d_col)) if d_col is not None else ''
        clues = [cell(r, i) for i in clue_cols if cell(r, i) and str(cell(r, i)).strip()]
        tk_kind, tk_info = classify(target)
        t_k = id_node(tk_kind, tk_info)
        if not t_k:
            continue
        for clue in clues:
            ck_kind, ck_info = classify(clue)
            c_k = id_node(ck_kind, ck_info)
            if c_k:
                edge('linked_to', t_k, c_k,
                     {'via': 'thecheat', 'victims': victims, 'damage': damage, 'source_id': src_id})
    return nodes, edges


_KEYPROP = {'vt_bacnt': 'account_no', 'vt_telno': 'telno', 'vt_psn': 'name', 'vt_src': 'src_id'}


def merge_cypher(nodes, edges):
    stmts = []
    for (label, key), props in nodes.items():
        setp = ', '.join(f"n.{k} = '{esc(v)}'" for k, v in props.items())
        kp = _KEYPROP[label]
        stmts.append(f"MERGE (n:{label} {{{kp}:'{esc(props[kp])}'}})" + (f" SET {setp}" if setp else ""))
    for rel, (fl, fk), (tl, tk), props in edges:
        pa = nodes[(fl, fk)]; pb = nodes[(tl, tk)]
        a = f"(a:{fl} {{{_KEYPROP[fl]}:'{esc(pa[_KEYPROP[fl]])}'}})"
        b = f"(b:{tl} {{{_KEYPROP[tl]}:'{esc(pb[_KEYPROP[tl]])}'}})"
        sp = ', '.join(f"e.{k} = '{esc(v)}'" for k, v in props.items() if v not in (None, ''))
        stmts.append(f"MATCH {a}, {b} MERGE (a)-[e:{rel}]->(b)" + (f" SET {sp}" if sp else ""))
    return stmts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xlsx', required=True)
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--src-id', default='Y2-EP1-04-02-thecheat')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--graph', default=GRAPH)
    args = ap.parse_args()

    nodes, edges = build(args.xlsx, args.sheet, args.src_id)
    from collections import Counter
    print(f"[빌드] 노드 {len(nodes)} / 엣지 {len(edges)}")
    print("  노드:", dict(Counter(l for (l, _) in nodes)))
    print("  엣지:", dict(Counter(r for (r, *_) in edges)))
    stmts = merge_cypher(nodes, edges)
    if args.dry_run:
        print(f"[dry-run] MERGE {len(stmts)}개. 샘플:")
        for s in stmts[:4]:
            print("  ", s[:150])
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
