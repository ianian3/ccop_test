#!/usr/bin/env python3
"""PoC: 비정형 수사문서(hwpx) → 온톨로지 엔티티/관계 자동 추출.
파이프라인: 파싱(hwpx) → 청킹 → LLM 추출(온톨로지 제약) → 검증 → 출력.
설계: docs/DOC_TO_GRAPH_POC_DESIGN_20260804.md
실행: python scripts/poc_doc_to_graph.py
"""
import zipfile, re, json, sys, os
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services import document_extraction_service as dx

HWPX = '/Users/iankwon/Downloads/1차년도/05_4차 시나리오 및 데이터셋(1년차 PoC 시나리오)/인터넷 물품 사기 사건 시나리오(동심우)_250721.hwpx'


def parse_hwpx(path):
    z = zipfile.ZipFile(path)
    texts = [re.sub(r'<[^>]+>', '', z.read(n).decode('utf-8', 'ignore'))
             for n in z.namelist() if 'section' in n.lower() and n.endswith('.xml')]
    t = ' '.join(texts)
    t = re.sub(r'그림입니다[^가-힣]*?pixel', ' ', t)   # 이미지 캡션 노이즈 제거
    return re.sub(r'\s+', ' ', t).strip()


def chunk(text, size=1200, overlap=150):
    # v46 응답이 max_tokens 안에 완결되도록 작게 + 경계 엔티티 손실 방지 오버랩
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step)]


# 엔티티 식별 prop 우선순위 (④ 엔티티 해소용 — 정규화 키 생성)
_ID_PROPS = ['telno', 'account_no', 'ip_addr', 'url', 'wallet_addr', 'imei', 'name', 'title', 'content']


def entity_key(e):
    """엔티티의 전역 식별 키 (type + 정규화된 대표 식별자). 청크 간 중복 통합용."""
    props = e.get('props', {})
    for p in _ID_PROPS:
        if props.get(p):
            val = re.sub(r'[-\s]', '', str(props[p]))          # 전화/계좌 하이픈 제거 정규화
            return (e['type'], val[:60])
    return (e['type'], f"_{e.get('local_id')}")                 # 식별자 없으면 local_id 폴백


def main():
    app = create_app(); app.app_context().push()
    text = parse_hwpx(HWPX)
    print(f'문서: {os.path.basename(HWPX)}  | 길이 {len(text)}자')
    chunks = chunk(text)
    print(f'청크: {len(chunks)}개  | 추출 모델: {app.config.get("SLLM_MODEL_NAME")}\n')

    ents_by_key, rels, dropped = {}, [], []   # 전역 엔티티(키→노드) · 리매핑된 관계
    rel_seen = set()
    for i, c in enumerate(chunks, 1):
        v = dx.validate(dx.extract(c))
        # 청크 로컬 local_id → 전역 키 매핑 (④ 엔티티 해소)
        local2key = {}
        for e in v['entities']:
            k = entity_key(e)
            local2key[e.get('local_id')] = k
            if k not in ents_by_key:
                ents_by_key[k] = {'type': e['type'], 'key': f'{k[0]}:{k[1]}', 'props': e.get('props', {})}
            else:
                ents_by_key[k]['props'].update({kk: vv for kk, vv in e.get('props', {}).items() if vv})
        # 관계를 전역 키로 리매핑 + 중복 제거
        for r in v['relations']:
            fk, tk = local2key.get(r.get('from')), local2key.get(r.get('to'))
            if not fk or not tk:
                continue
            sig = (r['type'], fk, tk)
            if sig in rel_seen:
                continue
            rel_seen.add(sig)
            rels.append({'type': r['type'], 'from': f'{fk[0]}:{fk[1]}', 'to': f'{tk[0]}:{tk[1]}',
                         'props': r.get('props', {})})
        dropped += v['dropped']['entity_types'] + v['dropped']['edge_types']
        print(f'  청크{i:2d}: 엔티티 {len(v["entities"])} · 관계 {len(v["relations"])} · 폐기 {len(v["dropped"]["entity_types"]) + len(v["dropped"]["edge_types"])}')

    all_e = list(ents_by_key.values())
    ne, nr = Counter(e['type'] for e in all_e), Counter(r['type'] for r in rels)
    print(f'\n=== 추출 결과 (엔티티 해소 후) ===')
    print(f'엔티티 {len(all_e)} 종류분포: {dict(ne)}')
    print(f'관계  {len(rels)} 종류분포: {dict(nr)}')
    print(f'스키마 밖 폐기: {len(dropped)} {dict(Counter(dropped)) if dropped else ""}')
    print('\n엔티티 샘플:')
    for e in all_e[:12]:
        print(f'  {e["type"]:12s} {e.get("props")}')
    print('관계 샘플:')
    for r in rels[:10]:
        print(f'  {r["from"]:24s} -[{r["type"]}]-> {r["to"]}')

    os.makedirs('results', exist_ok=True)
    json.dump({'doc': os.path.basename(HWPX), 'n_entities': len(all_e), 'n_relations': len(rels),
               'entities': all_e, 'relations': rels},
              open('results/poc_doc_graph.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\n저장: results/poc_doc_graph.json')


if __name__ == '__main__':
    main()
