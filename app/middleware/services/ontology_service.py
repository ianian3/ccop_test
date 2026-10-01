"""
온톨로지 서비스 — 호환성 re-export 모듈 (2026-10-01)

정의(SoT)는 app/services/ontology_service.py 로 되돌렸다.
이 경로는 외부 스크립트·이전 문서의 import 를 깨지 않기 위한 연결 파일이며, 새 코드는
`from app.services.ontology_service import KICSCrimeDomainOntology` 를 쓴다.

변경 이력:
  v3.0~v3.2 : app/services/ontology_service.py 에 정의
  v3.3~V4.9 : 이 파일(app/middleware/services/)에 정의, app/services 쪽은 re-export
  2026-10-01: 정의를 app/services 로 복귀 — 서비스 활성본 규칙(app/services)과 일치
"""
from app.services.ontology_service import (  # noqa: F401
    KICSCrimeDomainOntology,
    OntologyEnricher,
    SemanticAnalyzer,
)

__all__ = [
    "KICSCrimeDomainOntology",
    "OntologyEnricher",
    "SemanticAnalyzer",
]
