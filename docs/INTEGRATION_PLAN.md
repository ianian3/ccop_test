# CCOP × cslee 통합 계획서

> 작성일: 2026-04-14
> 작성: SKAI AI R&D Team
> 상태: **개발 진행 중 (통합 보류)**

---

## 1. 관계자 및 목적

| 구분 | 내용 |
|------|------|
| **SKAI** | CCOP 플랫폼 개발사 (우리 회사) |
| **cslee** | 통합 플랫폼 개발사 (파트너사) |
| **목적** | SKAI의 3가지 핵심 기능을 cslee 통합 플랫폼에 연동 |
| **VM 서버** | `http://211.188.50.27:8446` (cslee 제공) |
| **skai-vm 저장소** | `http://211.188.50.27:8446/cslee/skai-vm.git` |

---

## 2. 통합 대상 기능 3가지

### 2-1. 온톨로지 (Ontology)
- **파일**: `app/services/ontology_service.py`
- **내용**: KICS 기반 POLE v3.0 6계층 온톨로지
- **cslee 활용**: 노드/엣지 타입 스키마 참조, 데이터 매핑 기준

### 2-2. Text2Cypher
- **파일**: `app/services/langgraph_agent.py`, `app/services/ai_service.py`
- **내용**: 자연어 → Cypher 쿼리 자동 변환 (LangGraph 기반)
- **cslee 활용**: 자연어 검색 인터페이스 연동

### 2-3. 모델링 (Modeling / ETL)
- **파일**: `app/services/rdb_to_graph_service.py`, `app/services/etl_service.py`, `app/services/schema_mapper.py`
- **내용**: RDB → AgensGraph 온톨로지 변환 파이프라인
- **cslee 활용**: 수사 데이터를 그래프 DB로 자동 적재

---

## 3. skai-vm 저장소 구성 (납품 패키지)

```
skai-vm/
├── app/
│   ├── __init__.py
│   └── services/
│       ├── __init__.py
│       ├── ontology_service.py        # 온톨로지
│       ├── etl_service.py             # 모델링
│       ├── schema_mapper.py           # 모델링
│       └── rdb_to_graph_service.py    # 모델링
├── tests/
│   ├── verify_standardization.py     # ETL 표준화 검증
│   └── verify_ontology_edges.py      # 온톨로지 엣지 검증
├── requirements.txt
├── CHANGELOG.md
└── README.md
```

> **포함하지 않는 것**: Flask 앱, Admin 대시보드, API 키 인증, .env, chroma_data/

---

## 4. cslee 통합 방식

```python
# cslee 플랫폼에서 import하여 사용
from app.services.ontology_service import OntologyService
from app.services.rdb_to_graph_service import RdbToGraphService
from app.services.etl_service import StandardCodeMapper

# 온톨로지 스키마 참조
labels = OntologyService.get_node_labels()

# 데이터 표준화 (은행코드, 통신사 등)
mapper = StandardCodeMapper()
enriched = mapper.auto_enrich('vt_bacnt', raw_data)

# RDB → 그래프 모델링
service = RdbToGraphService(db_config={...})
service.load_table('TB_FIN_BACNT', graph_path='cslee_graph')
```

---

## 5. 버전 관리 전략

### 저장소별 역할
| 저장소 | 브랜치 | 용도 |
|--------|--------|------|
| GitHub (ccop_test) | main / develop / feature/* | 전체 플랫폼 개발 |
| skai-vm (cslee VM) | main | cslee 납품 모듈만 |

### 버전 체계 (SemVer)
```
v1.2.0
│ │ │
│ │ └── PATCH: 버그 수정
│ └──── MINOR: 기능 추가 (하위 호환)
└────── MAJOR: 온톨로지 구조 변경, 파괴적 변경
```

### skai-vm 동기화 절차
```bash
# coop_v1.0에서 skai-vm으로 동기화
bash sync_to_skai_vm.sh v1.x.x
```

---

## 6. 배포 파이프라인 (준비 완료)

```
[로컬 개발]
    │ git commit + tag
    ▼
[GitHub main 브랜치]
    │ GitHub Actions 자동 실행 (.github/workflows/deploy.yml)
    ├── Job 1: test  (온톨로지 import, Flask 앱 생성 검증)
    ├── Job 2: build (Docker 이미지 빌드 & DockerHub push)
    └── Job 3: deploy (SSH → VM, docker-compose up, 헬스체크)
            │ 실패 시 자동 롤백
            ▼
    [VM: /api/v1/health 200 확인]
            │
            ▼
    [skai-vm 수동 동기화]
    bash sync_to_skai_vm.sh v1.x.x
```

### GitHub Secrets 필요 항목
```
DOCKER_USERNAME    DockerHub 계정
DOCKER_PASSWORD    DockerHub 패스워드
VPS_HOST           VM IP
VPS_USER           VM 접속 계정
VPS_SSH_KEY        SSH 개인키
```

---

## 7. 테스트 항목

| 테스트 파일 | 대상 | skai-vm 포함 |
|------------|------|:------------:|
| `verify_standardization.py` | StandardCodeMapper 단위 | ✅ |
| `verify_ontology_edges.py` | 온톨로지 엣지 검증 | ✅ |
| `test_security.py` | SQL injection, XSS | ✗ |
| `test_api_persistence.py` | API 키 영속성 | ✗ |
| `test_offline_mock.py` | DB 없이 모의 실행 | ✗ |
| `test_ui_question_*.py` | Text2Cypher E2E | ✗ |

---

## 8. 통합 실행 체크리스트 (추후 진행)

```
[ ] 1. 온톨로지 개발 완료 및 안정화
[ ] 2. Text2Cypher 정확도 개선 완료
[ ] 3. 모델링(ETL) 파이프라인 안정화
[ ] 4. coop_v1.0 v1.x.0 태그 생성 & GitHub 푸시
[ ] 5. GitHub Actions CI/CD 정상 동작 확인
[ ] 6. skai-vm 저장소에 4개 서비스 파일 업로드
[ ] 7. tests/ 파일 2개 포함 (verify_*)
[ ] 8. requirements.txt, CHANGELOG.md 작성
[ ] 9. cslee 담당자에게 연동 가이드 공유
[ ] 10. cslee 플랫폼에서 import 테스트 확인
```

---

## 9. 현재 개발 상태 (2026-04-14 기준)

| 기능 | 상태 | 비고 |
|------|------|------|
| 온톨로지 v3.0 | 🔧 개발 중 | POLE 6계층, 추가 개발 필요 |
| Text2Cypher | 🔧 개발 중 | LangGraph 에이전트, 정확도 개선 필요 |
| 모델링 (ETL) | 🔧 개발 중 | RDB→Graph 파이프라인, 안정화 필요 |
| 파트너 API v1 | ✅ 완성 | X-API-Key 인증, 티어 시스템 |
| CI/CD | ✅ 완성 | deploy.yml (GitHub Actions) |
| skai-vm 업로드 | ⏸ 보류 | 개발 완료 후 진행 |
