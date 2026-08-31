#!/usr/bin/env python3
"""문서→그래프 배치 추출 결과 2건(baseline vs candidate) 비교 리포트.

용도: v46 대비 v47 재추출 개선 측정 (2차년도 docx 8건 등).
  - 총량: 엔티티/관계/크로스-문서/폐기/검증통과
  - 분포: 노드 타입(전화 과다생성 지표), 관계 타입
  - 방향 정합: 온톨로지 SoT domain/range 대조 — 위반 수 + "뒤집으면 맞는" 확정 방향오류
  - 연결성: 관계/엔티티 비율 (노드만 만들고 관계를 못 거는 문제의 지표)
  - per-doc 대조표

실행:
  python3 scripts/compare_extraction_runs.py results/batch_y2_docx.json results/batch_y2_docx_v47.json
  (단일 파일만 주면 그 파일의 기준선 품질 리포트만 출력)
"""
import json
import os
import sys
import importlib.util
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_ONTO_PATH = os.path.join(_HERE, '..', 'app', 'middleware', 'services', 'ontology_service.py')


def _load_ontology():
    spec = importlib.util.spec_from_file_location('onto', _ONTO_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.KICSCrimeDomainOntology


def _allowed_pairs(O):
    """엣지 타입 → 허용 (from_label, to_label) 집합. 'Any'는 와일드카드('*')."""
    concept2label = dict(O.GDB_LABEL_MAP)
    out = {}
    for name, r in O.RELATIONSHIPS.items():
        def labels(side):
            v = r.get(side)
            items = []
            for part in (v if isinstance(v, list) else [v]):
                for c in str(part).split('|'):
                    c = c.strip()
                    items.append('*' if c == 'Any' else concept2label.get(c, c))
            return items
        out[name] = {(d, g) for d in labels('domain') for g in labels('range')}
    return out


def _direction_check(relations, allowed):
    """(위반 수, 확정 방향오류 수, 위반 예시) — 확정 방향오류 = 뒤집으면 스키마에 맞는 경우."""
    def fits(pairs, ft, tt):
        return any((d in ('*', ft)) and (g in ('*', tt)) for d, g in pairs)
    viol, flipped, samples = 0, 0, []
    for r in relations:
        pairs = allowed.get(r.get('type'))
        if not pairs:
            continue  # SoT에 없는 타입은 추출기 검증 단계 소관
        ft = str(r.get('from', '')).split(':', 1)[0]
        tt = str(r.get('to', '')).split(':', 1)[0]
        if fits(pairs, ft, tt):
            continue
        viol += 1
        if fits(pairs, tt, ft):
            flipped += 1
            if len(samples) < 5:
                samples.append(f"{ft}-[{r['type']}]->{tt} (역방향이 정답)")
        elif len(samples) < 5:
            samples.append(f"{ft}-[{r['type']}]->{tt}")
    return viol, flipped, samples


def profile(path, allowed):
    d = json.load(open(path))
    ents, rels = d.get('entities', []), d.get('relations', [])
    etypes, rtypes = Counter(e.get('type') for e in ents), Counter(r.get('type') for r in rels)
    viol, flipped, samples = _direction_check(rels, allowed)
    n_e = len(ents) or 1
    return {
        'file': os.path.basename(path),
        'n_docs': d.get('n_docs'),
        'entities': len(ents), 'relations': len(rels),
        'cross_doc': d.get('n_cross_doc'),
        'dropped': f"{d.get('dropped_types')}타입·{d.get('dropped_values')}값",
        'verified': d.get('verified'),
        'etypes': etypes, 'rtypes': rtypes,
        'telno_ratio': 100.0 * etypes.get('vt_telno', 0) / n_e,
        'rel_per_ent': len(rels) / n_e,
        'dir_violation': viol, 'dir_flipped': flipped, 'dir_samples': samples,
        'per_doc': {p['file']: p for p in d.get('per_doc', [])},
    }


def _fmt_counter(c, other_keys=()):
    keys = sorted(set(c) | set(other_keys), key=lambda k: -c.get(k, 0))
    return ', '.join(f"{k}:{c.get(k, 0)}" for k in keys)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    O = _load_ontology()
    allowed = _allowed_pairs(O)
    base = profile(sys.argv[1], allowed)
    cand = profile(sys.argv[2], allowed) if len(sys.argv) > 2 else None

    def row(label, key, fmt=lambda v: v):
        b = fmt(base[key])
        print(f"  {label:<22} {b!s:<26}" + (f" → {fmt(cand[key])}" if cand else ''))

    print(f"\n=== 추출 결과 비교: {base['file']}" + (f"  vs  {cand['file']}" if cand else ' (기준선 단독)') + ' ===')
    row('문서 수', 'n_docs')
    b = f"{base['entities']} / {base['relations']}"
    c = f"{cand['entities']} / {cand['relations']}" if cand else ''
    print(f"  {'엔티티 / 관계':<20} {b:<26}" + (f" → {c}" if cand else ''))
    row('크로스-문서 해소', 'cross_doc')
    row('스키마 폐기(환각)', 'dropped')
    row('검증 통과', 'verified')
    row('전화노드 비중(%)', 'telno_ratio', lambda v: f"{v:.1f}")
    row('관계/엔티티 비율', 'rel_per_ent', lambda v: f"{v:.3f}")
    row('방향 위반(잔존)', 'dir_violation')
    row('└ 확정 방향오류', 'dir_flipped')
    for tag, p in (('기준선', base),) + ((('후보', cand),) if cand else ()):
        print(f"\n  [{tag}] 노드: {_fmt_counter(p['etypes'])}")
        print(f"  [{tag}] 관계: {_fmt_counter(p['rtypes'])}")
        if p['dir_samples']:
            print(f"  [{tag}] 방향 위반 예시: " + ' | '.join(p['dir_samples']))
    if cand:
        print('\n  per-doc (엔티티/관계):')
        for f in sorted(set(base['per_doc']) | set(cand['per_doc'])):
            b, c = base['per_doc'].get(f, {}), cand['per_doc'].get(f, {})
            print(f"    {f[:44]:<46} {b.get('entities','-')}/{b.get('relations','-'):<6} → {c.get('entities','-')}/{c.get('relations','-')}")
    print()


if __name__ == '__main__':
    main()
