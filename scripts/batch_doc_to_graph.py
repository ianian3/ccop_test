#!/usr/bin/env python3
"""1차년도 데이터 폴더 → 비정형 문서 배치 추출 → 크로스-문서 수사 그래프.

하이브리드 파이프라인의 **비정형 트랙**:
  폴더 워크 → 파서 dispatch(pdf/hwpx/docx/hwp/txt) → LLM 추출(온톨로지 제약)
  → 검증 → 크로스-문서 엔티티 해소(전화/계좌 정규화) → provenance 집계.
정형(xlsx/xls/csv)은 ETL 트랙(etl_service)에서 별도 처리 — 여기 대상 아님.

설계: docs/DOC_TO_GRAPH_POC_DESIGN_20260804.md (③④⑤ 확장)
실행: python scripts/batch_doc_to_graph.py --root "/path/to/폴더" --ext pdf,hwpx,txt --limit 5
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services import document_extraction_service as dx

_ID_PROPS = ['telno', 'account_no', 'ip_addr', 'url', 'wallet_addr', 'imei', 'name', 'title', 'content']
_SUPPORTED = ['pdf', 'hwpx', 'docx', 'hwp', 'txt']


def entity_key(e):
    """전역 식별 키 (type + 정규화 대표 식별자) — 문서 간 동일 실체 통합."""
    props = e.get('props', {})
    for p in _ID_PROPS:
        if props.get(p):
            val = re.sub(r'[-\s]', '', str(props[p]))
            return (e['type'], val[:60])
    return (e['type'], f"_{e.get('local_id')}")


def reliability_tier(path):
    """문서 유형 → 신뢰도 tier(1공식~3기타). provenance 증거등급."""
    n = os.path.basename(path)
    if re.search(r'영장|판결|공소|결정문|처분', n):
        return 1        # 사법 공식문서
    if re.search(r'수사보고|보고서|조서|의견서', n):
        return 2        # 수사기관 작성
    return 3


def chunk(text, size=1200, overlap=150):
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step)]


def walk(root, exts):
    files = []
    for ext in exts:
        files += glob.glob(os.path.join(root, '**', f'*.{ext}'), recursive=True)
    return sorted(set(files))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, help='입력 폴더 (재귀)')
    ap.add_argument('--ext', default='pdf,hwpx,txt,docx', help='처리 확장자 (콤마)')
    ap.add_argument('--limit', type=int, default=5, help='최대 문서 수 (비용 통제)')
    ap.add_argument('--out', default='results/batch_doc_graph.json')
    args = ap.parse_args()

    exts = [e.strip().lower() for e in args.ext.split(',') if e.strip() in _SUPPORTED]
    app = create_app(); app.app_context().push()

    all_files = walk(args.root, exts)
    files = all_files[:args.limit]
    print(f'대상 폴더: {args.root}')
    print(f'매칭 문서: {len(all_files)}개 (확장자 {exts}) · 처리: {len(files)}개 (--limit {args.limit})')
    print(f'추출 모델: {app.config.get("SLLM_MODEL_NAME")}\n')

    # 전역 그래프 (크로스-문서 해소)
    ents = {}          # key → {type, key, props, sources:set, tier}
    rels = {}          # (type,fk,tk) → {type, from, to, props, sources:set}
    per_doc = []       # 문서별 통계
    fmt_count = Counter()
    dropped_total = Counter()
    hallucinated = []  # 원문에 없는 값 환각 (grounding 폐기)

    for path in files:
        base = os.path.basename(path)
        ext = base.rsplit('.', 1)[-1].lower()
        text = dx.parse_document(path)
        if not text or len(text) < 30:
            per_doc.append((base, ext, 0, 0, 'parse_empty'))
            print(f'  ✗ {base[:50]:52s} 파싱 실패/빈문서')
            continue

        tier = reliability_tier(path)
        d_ent, d_rel = 0, 0
        for c in chunk(text):
            v = dx.validate(dx.extract(c))
            v = dx.ground_to_source(v, c)        # 원문 대조 — 값 환각 폐기 (2차 방어선)
            hallucinated.extend(v.get('dropped_values', []))
            local2key = {}
            for e in v['entities']:
                k = entity_key(e)
                if k[1].startswith('_'):        # 식별자 없는 폴백 → 문서 스코프 격리 (문서 간 오통합 방지)
                    k = (k[0], f'{base}{k[1]}')
                local2key[e.get('local_id')] = k
                if k not in ents:
                    ents[k] = {'type': e['type'], 'key': f'{k[0]}:{k[1]}',
                               'props': dict(e.get('props', {})), 'sources': set(), 'tier': tier,
                               'verified': e.get('verified', False)}
                    d_ent += 1
                else:
                    ents[k]['props'].update({kk: vv for kk, vv in e.get('props', {}).items() if vv})
                    ents[k]['tier'] = min(ents[k]['tier'], tier)
                    ents[k]['verified'] = ents[k]['verified'] or e.get('verified', False)
                ents[k]['sources'].add(base)
            for r in v['relations']:
                fk, tk = local2key.get(r.get('from')), local2key.get(r.get('to'))
                if not fk or not tk:
                    continue
                sig = (r['type'], fk, tk)
                if sig not in rels:
                    rels[sig] = {'type': r['type'], 'from': f'{fk[0]}:{fk[1]}',
                                 'to': f'{tk[0]}:{tk[1]}', 'props': dict(r.get('props', {})), 'sources': set()}
                    d_rel += 1
                rels[sig]['sources'].add(base)
            for t in v['dropped']['entity_types'] + v['dropped']['edge_types']:
                dropped_total[t] += 1

        fmt_count[ext] += 1
        per_doc.append((base, ext, d_ent, d_rel, 'ok'))
        print(f'  ✓ {base[:50]:52s} [{ext}] 신규 엔티티 {d_ent:2d} · 관계 {d_rel:2d} · tier{tier}')

    # ── 크로스-문서 분석 (핵심 가치: i2 수동 연결을 자동화) ──
    cross = [e for e in ents.values() if len(e['sources']) > 1]
    node_types = Counter(e['type'] for e in ents.values())
    edge_types = Counter(r['type'] for r in rels.values())

    print(f'\n{"="*60}')
    print(f'=== 배치 결과 (크로스-문서 엔티티 해소 후) ===')
    print(f'처리 문서: {sum(1 for p in per_doc if p[4]=="ok")}/{len(files)}  형식별 {dict(fmt_count)}')
    print(f'고유 엔티티: {len(ents)}  관계: {len(rels)}')
    print(f'노드 타입 {len(node_types)}종: {dict(node_types.most_common(8))}')
    print(f'엣지 타입 {len(edge_types)}종: {dict(edge_types.most_common(6))}')
    verified_n = sum(1 for e in ents.values() if e['verified'])
    print(f'스키마밖 폐기(타입 환각): {sum(dropped_total.values())} {dict(dropped_total.most_common(5))}')
    print(f'원문대조 폐기(값 환각): {len(hallucinated)} {dict(Counter(hallucinated).most_common(5))}')
    print(f'원문검증 통과: {verified_n}/{len(ents)} (나머지는 식별자 없어 판정보류)')
    print(f'\n🔗 크로스-문서 엔티티 (≥2 문서 교차 = i2 수동연결을 자동): {len(cross)}건')
    for e in sorted(cross, key=lambda x: -len(x['sources']))[:10]:
        lbl = e['props'].get('name') or e['props'].get('telno') or e['props'].get('account_no') \
              or e['props'].get('title') or e['key'].split(':', 1)[1]
        print(f'   {e["type"]:12s} {str(lbl)[:28]:30s} ← {len(e["sources"])}개 문서')

    # ── 저장 (set → list, provenance 포함) ──
    out_ents = [{'type': e['type'], 'key': e['key'], 'props': e['props'],
                 'sources': sorted(e['sources']), 'reliability_tier': e['tier'],
                 'verified': e['verified']} for e in ents.values()]
    out_rels = [{'type': r['type'], 'from': r['from'], 'to': r['to'], 'props': r['props'],
                 'sources': sorted(r['sources'])} for r in rels.values()]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({'root': args.root, 'n_docs': len(files), 'formats': dict(fmt_count),
               'n_entities': len(ents), 'n_relations': len(rels), 'n_cross_doc': len(cross),
               'dropped_types': sum(dropped_total.values()), 'dropped_values': len(hallucinated),
               'verified': verified_n,
               'per_doc': [{'file': p[0], 'ext': p[1], 'entities': p[2], 'relations': p[3], 'status': p[4]}
                           for p in per_doc],
               'entities': out_ents, 'relations': out_rels},
              open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n저장: {args.out}')


if __name__ == '__main__':
    main()
