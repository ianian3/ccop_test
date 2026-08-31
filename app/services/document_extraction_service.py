"""document_extraction_service.py — 비정형 수사문서 → 온톨로지 엔티티/관계 LLM 추출.

CCOP PoC: i2 Text Chart(수동 마크업)를 AI 자동 추출로 대체.
핵심: 온톨로지 스키마(V4.4 25노드/66엣지)로 LLM 출력을 제약 → 스키마 밖 타입 생성 억제
     (Text2Cypher와 동일 철학, arXiv 2505.05118 schema-guided).

재활용: LangGraphAgent._format_schema_b(스키마 주입), AIService.get_client(LLM).
설계: docs/DOC_TO_GRAPH_POC_DESIGN_20260804.md
"""
import json
import logging
import re
import zipfile
from flask import current_app

from app.services.ai_service import AIService
from app.services.langgraph_agent import LangGraphAgent

logger = logging.getLogger(__name__)


# ── 다형식 파서 어댑터 (설계 ③ — 지연 import로 base 의존성 0 유지) ──

def _clean(text: str) -> str:
    text = re.sub(r'그림입니다[^가-힣]*?pixel', ' ', text)   # hwp/hwpx 이미지 캡션 노이즈
    return re.sub(r'\s+', ' ', text).strip()


def _parse_hwpx(path: str) -> str:
    z = zipfile.ZipFile(path)
    parts = [re.sub(r'<[^>]+>', '', z.read(n).decode('utf-8', 'ignore'))
             for n in z.namelist() if 'section' in n.lower() and n.endswith('.xml')]
    return _clean(' '.join(parts))


def _parse_docx(path: str) -> str:
    z = zipfile.ZipFile(path)
    xml = z.read('word/document.xml').decode('utf-8', 'ignore')
    xml = re.sub(r'</w:p>', ' ', xml)                        # 문단 구분 보존
    return _clean(re.sub(r'<[^>]+>', '', xml))


def _parse_pdf(path: str) -> str:
    from pypdf import PdfReader                              # 지연 import (선택 의존성)
    r = PdfReader(path)
    return _clean(' '.join((p.extract_text() or '') for p in r.pages))


def _parse_hwp(path: str) -> str:
    # 구형 hwp(OLE 복합문서). olefile 있으면 PrvText(미리보기 텍스트) 스트림 추출.
    try:
        import olefile                                       # 지연 import (선택 의존성)
    except ImportError:
        logger.warning("[DocExtract] hwp 파서 미설치 — pip install olefile (또는 pyhwp)")
        return ''
    if not olefile.isOleFile(path):
        return ''
    ole = olefile.OleFileIO(path)
    try:
        if ole.exists('PrvText'):
            return _clean(ole.openstream('PrvText').read().decode('utf-16', 'ignore'))
    finally:
        ole.close()
    return ''


_PARSERS = {'hwpx': _parse_hwpx, 'docx': _parse_docx, 'pdf': _parse_pdf, 'hwp': _parse_hwp}


def parse_document(path: str) -> str:
    """비정형 문서 → 평문 텍스트 (확장자 dispatch). 미지원/실패 시 ''."""
    ext = path.rsplit('.', 1)[-1].lower() if '.' in path else ''
    try:
        if ext == 'txt':
            with open(path, encoding='utf-8', errors='ignore') as f:
                return _clean(f.read())
        fn = _PARSERS.get(ext)
        return fn(path) if fn else ''
    except Exception as e:
        logger.warning(f"[DocExtract] 파싱 실패 {path}: {e}")
        return ''


def ontology_schema_text() -> str:
    """온톨로지 노드 타입을 간결 리스트로 (작은 특화모델 v46 친화 — 66엣지 전체 주입은 과부하)."""
    from app.middleware.services.ontology_service import KICSCrimeDomainOntology as O
    return ' '.join(f'{k}({v})' for k, v in O.LABEL_KO_MAP.items())


def valid_types():
    """온톨로지 유효 노드/엣지 타입 집합 (추출 후 검증용)."""
    schema = LangGraphAgent._POLE_SCHEMA
    nodes = set(schema.get('node_labels', {}).keys()) | {'pt_cluster', 'site_cluster'}
    edges = set(schema.get('edge_directions', {}).keys()) | set(schema.get('edge_types', []))
    return nodes, edges


_SYSTEM = """문서에서 아래 온톨로지 노드·관계 타입의 엔티티와 관계를 추출해 JSON으로만 출력하세요.

[노드 타입 — 이것만 사용]
{schema}

[주요 관계 타입]
owns_phone(인물→전화) has_account(인물→계좌) member_of(인물→조직) uses_id(인물→계정) used_ip(인물→IP)
from_account(계좌→이체) to_account(이체→계좌) transferred_to(계좌→계좌) caller(전화→통화) callee(통화→전화)
contacted(전화↔전화) access_via(접속→수단) suspect_in/victim_in(인물→사건) resolves_to(사이트→IP)

[규칙] 문서에 명시된 것만. 추측 금지. 식별자(전화/계좌/IP/URL)는 원문 그대로. 없는 타입 만들지 마세요.

[출력 JSON — 반드시 type 포함]
{{"entities":[{{"type":"vt_psn","local_id":"e1","props":{{"name":"홍길동"}}}}],
 "relations":[{{"type":"owns_phone","from":"e1","to":"e2","props":{{"confidence":0.9}}}}]}}

[예시]
문서: "홍길동은 휴대폰 01011112222로 판매자와 통화하고 계좌 1002-123-456으로 이체했다. 판매자는 IP 203.0.113.5로 접속했다."
출력: {{"entities":[{{"type":"vt_psn","local_id":"e1","props":{{"name":"홍길동"}}}},{{"type":"vt_telno","local_id":"e2","props":{{"telno":"01011112222"}}}},{{"type":"vt_bacnt","local_id":"e3","props":{{"account_no":"1002-123-456"}}}},{{"type":"vt_ip","local_id":"e4","props":{{"ip_addr":"203.0.113.5"}}}}],"relations":[{{"type":"owns_phone","from":"e1","to":"e2","props":{{"confidence":0.95}}}}]}}
"""


def _salvage_array(content: str, key: str) -> list:
    """잘린 JSON에서 특정 배열(key)의 완결된 {...} 객체만 개별 파싱해 복구.

    max_tokens 초과로 응답이 중간에 끊겨도 그때까지의 완전한 객체는 살린다.
    """
    m = re.search(rf'"{key}"\s*:\s*\[', content)
    if not m:
        return []
    out, depth, start = [], 0, None
    for i in range(m.end(), len(content)):
        ch = content[i]
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    out.append(json.loads(content[start:i + 1]))
                except Exception:
                    pass
                start = None
        elif ch == ']' and depth == 0:
            break  # 배열 정상 종료
    return out


def extract(chunk: str, model: str = None) -> dict:
    """문서 청크 → {entities, relations} (온톨로지 스키마 제약)."""
    client = AIService.get_client()
    model = model or current_app.config.get('SLLM_MODEL_NAME', 'gpt-4o')
    system = _SYSTEM.format(schema=ontology_schema_text())
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"[문서]\n{chunk}\n\n[출력 JSON]"},
            ],
            temperature=0,
            max_tokens=4096,
        )
        content = resp.choices[0].message.content.strip()
        # 코드펜스/잡텍스트 제거 후 JSON 블록 추출
        content = re.sub(r'```[a-zA-Z]*\n?', '', content).replace('```', '').strip()
        m = re.search(r'\{.*\}', content, re.DOTALL)
        try:
            raw = json.loads(m.group(0) if m else content)
            return {"entities": raw.get("entities", []), "relations": raw.get("relations", [])}
        except json.JSONDecodeError:
            # 응답이 max_tokens에서 잘린 경우 — 완결 객체만 복구
            ents = _salvage_array(content, "entities")
            rels = _salvage_array(content, "relations")
            if ents or rels:
                logger.info(f"[DocExtract] 잘린 JSON 복구: ent {len(ents)} rel {len(rels)}")
                return {"entities": ents, "relations": rels, "truncated": True}
            raise
    except Exception as e:
        logger.warning(f"[DocExtract] 추출 실패: {e}")
        return {"entities": [], "relations": [], "error": str(e)}


def validate(result: dict) -> dict:
    """온톨로지 스키마 밖 타입 폐기 (할루시네이션 필터 — 타입 환각)."""
    nodes, edges = valid_types()
    ents = [e for e in result.get('entities', []) if e.get('type') in nodes]
    dropped_e = [e.get('type') for e in result.get('entities', []) if e.get('type') not in nodes]
    ids = {e.get('local_id') for e in ents}
    rels = [r for r in result.get('relations', [])
            if r.get('type') in edges and r.get('from') in ids and r.get('to') in ids]
    dropped_r = [r.get('type') for r in result.get('relations', []) if r.get('type') not in edges]
    return {"entities": ents, "relations": rels,
            "dropped": {"entity_types": dropped_e, "edge_types": dropped_r}}


_GROUND_PROPS = ['telno', 'account_no', 'ip_addr', 'wallet_addr', 'imei', 'url', 'name', 'atm_id']


def ground_to_source(result: dict, source_text: str) -> dict:
    """원문 대조 검증 (할루시네이션 필터 — 값 환각).

    추출된 식별자(전화/계좌/IP/이름 등)가 원문 텍스트에 실제로 존재하는지 확인.
    온톨로지 스키마 필터는 '타입' 환각만 잡지만, 이 필터는 v46가 지어낸 '값'을 폐기.
    식별 prop이 없는 엔티티(title/content 요약형)는 verified=False로 통과(폐기 안 함).
    """
    nt = re.sub(r'[-\s]', '', source_text)
    kept, dropped = [], []
    for e in result.get('entities', []):
        idv = next((e['props'][p] for p in _GROUND_PROPS if e.get('props', {}).get(p)), None)
        if idv is None:
            e['verified'] = False
            kept.append(e)                                   # 식별자 없음 → 판정 보류(통과)
        elif re.sub(r'[-\s]', '', str(idv)) in nt or str(idv) in source_text:
            e['verified'] = True
            kept.append(e)                                   # 원문 존재 → 검증됨
        else:
            dropped.append(e.get('type'))                    # 원문 없음 → 값 환각 폐기
    kept_ids = {e.get('local_id') for e in kept}
    rels = [r for r in result.get('relations', []) if r.get('from') in kept_ids and r.get('to') in kept_ids]
    return {"entities": kept, "relations": rels, "dropped_values": dropped,
            "dropped": result.get("dropped", {"entity_types": [], "edge_types": []})}
