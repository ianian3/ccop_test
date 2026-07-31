"""
온톨로지 서비스 — 호환성 re-export 모듈

이 파일은 app.middleware.services.ontology_service의 alias입니다.
소스 오브 트루스: app/middleware/services/ontology_service.py (V4.0)

변경 이력:
  v3.0~v3.2: 이 파일이 직접 정의를 포함
  v3.3      : middleware 버전으로 통합, 이 파일은 re-export shim으로 전환
              (기존 import 경로 호환성 유지)
"""

# v3.3 정의 파일에서 모두 re-export — 기존 import 경로 무변경 유지
from app.middleware.services.ontology_service import (
    KICSCrimeDomainOntology,
    OntologyEnricher,
    SemanticAnalyzer,
)

__all__ = [
    "KICSCrimeDomainOntology",
    "OntologyEnricher",
    "SemanticAnalyzer",
]
