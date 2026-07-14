# 폐쇄망 방문설치 — 사전 준비 상태 점검 (2026-07-14)

**목적**: 방문설치 D-day 전에 "무엇이 준비됐고, 무엇이 남았는가"를 한 장으로 관리.
**기준 런북**: [`docs/AIRGAP_VISIT_INSTALL_RUNBOOK.md`](../docs/AIRGAP_VISIT_INSTALL_RUNBOOK.md) (2026-07-14 갱신본)
**대상**: Rocky Linux 10 · RTX 6000 Ada ×8 · USB 반입 · 1차(인프라)/2차(GPU+T2C) 분리

---

## 1. 자산 감사 결과 (2026-07-14 실시)

### ✅ 검증 통과

| 항목 | 결과 |
|---|---|
| `docker-compose.airgap.yml` 문법 | `docker compose config -q` 통과 (경고 0) |
| `scripts/build_airgap_bundle.sh` 문법 | `bash -n` 통과. 런북 §2 전 과정 자동화 확인 (슬림 Dockerfile 자동 선택, Ubuntu staging 대비 Rocky10 컨테이너 rpm 수집, pg_dump 컨테이너 폴백 포함) |
| sllm 서비스 정합 | `--chat-template` 명시 ✓ (운영 검증 레시피 항목) · `--tensor-parallel-size 1` ✓ (NVLink 부재 대응) · `profiles: [gpu]` ✓ |
| `.env.airgap.phase1.template` | fail-closed 필수값(SECRET_KEY/ADMIN_PASSWORD/LLM_API_KEY) 전부 포함, 1차 LLM 미설정 원칙 반영 |
| 슬림 이미지 구성 | `Dockerfile.airgap` + `requirements.airgap.txt`(pandas 포함 → numpy 확보) + `.dockerignore`(data/train/results/docs/age 제외) |
| 인증서 정합 | `gen_selfsigned_cert.sh` CN 기본값 = nginx `server_name`(ccop.cslee.internal) = 컴포즈 마운트 경로 일치 |
| **법률 RAG v2 폐쇄망 호환** | 신규 런타임 의존성 0 — 슬림 이미지 그대로 동작. 임베딩 백엔드 없이 **BM25-only 자동 강등** 설계. 적재: `ingest_legal_corpus.py --no-embed` (런북 1차 검증에 선택 항목으로 추가됨) |

### 🔧 금일 수정 (드리프트 해소)

1. `docker-compose.airgap.yml`: 죽은 `chroma_data` 마운트 제거(v1 RAG 잔재), obsolete `version:` 키 제거
2. `deploy/.env.airgap.phase1.template`: `VLLM_TAG` 권장값 **`v0.6.3.post1`** 로 확정 (근거 아래)
3. 런북: §0.2/§9.3 자산 표에 번들 자동화 스크립트·슬림 Dockerfile 반영, §2에 자동화 안내 추가, §5 vLLM 태그 확정, 1차 검증에 법률 RAG 선택 항목 추가

### 📌 vLLM 태그 결정 근거

`vllm/vllm-openai:v0.6.3.post1` — 운영에서 검증된 서빙 레시피(vllm 0.6.3.post1 + transformers 4.46.x + `--chat-template` 명시, `docs/CHECKPOINT_20260616.md`)와 동일 버전. cu121 빌드이므로 R530+ 드라이버(신규 Rocky 10 드라이버 포함)에서 동작. **다른 태그로 바꾸려면 staging GPU에서 모델 로드+추론 1회 검증 후 반입** (과거 transformers 5.x 토크나이저 호환 사고의 재발 방지).

---

## 2. 남은 결정 사항 (사람이 정해야 함)

| # | 결정 | 권고 | 상태 |
|---|---|---|---|
| D1 | **번들에 담을 소스 기준** — `feat/legal-rag-v2`(법률 RAG, CI 통과·커밋 완료)를 머지하고 번들할지, 현 dev 그대로일지 | **PR 머지 후 dev 기준 번들** 권장 — 번들 스크립트는 작업트리를 담으므로 기준 커밋을 하나로 고정하는 것이 재현성에 유리 | ⏳ |
| D2 | **staging 머신** — 런북 요건: linux/amd64 + 인터넷 + docker (Apple Silicon 금지) | **학습 GPU 머신(ai-kyw-dev@192.168.1.133, Ubuntu 24.04)로 확정** — 7/2에 1차 번들 생성 실적(982MB, 체크섬 145/145 OK). el10 rpm은 Rocky10 컨테이너로 수집(스크립트 자동) | ✅ |
| D3 | **2차 NVIDIA 드라이버 버전** — Rocky 10용 local-repo rpm 버전 선택 | 최신 프로덕션 브랜치(R570+ 계열) local repo. Secure Boot ON 대비 MOK 절차 숙지 | ⏳ |
| D4 | **DB 덤프 범위** — 전체 tccopdb vs 경량 그래프만 | 경량(tccop_graph_v6 등 데모 3~4개)만 — `osint_ontology`(689만 노드) 포함 금지 | ⏳ |

---

## 3. 실행 대기 작업 (staging에서 — 승인/접속 후)

> staging = 학습 GPU 머신(`ssh ai-kyw-dev@192.168.1.133`).
> ⚠️ **기존 1차 번들(7/2 생성, `~/ccop_bundle_p1` 982MB)은 구버전 소스 기준** — 법률 RAG·시나리오 A(nativedb compose)·VLLM_TAG 확정 반영 전. **PR 머지 후 재생성 필수** (앱 이미지+소스 tar 갱신; agens/nginx 이미지·rpm은 재사용됨).

```bash
# ── 3.1 staging 사전 점검 (읽기 전용) ──
uname -m                      # x86_64 필수
df -h /                      # 여유 ≥ 40GB
docker --version && docker compose version
git -C /root/ccop_test fetch && git -C /root/ccop_test status -sb   # 번들 기준 커밋 확인

# ── 3.2 1차 번들 생성 (런북 §2 자동화) ──
cd /root/ccop_test && git pull                  # D1 결정 반영된 기준 커밋으로
PGPASSWORD='<db비번>' bash scripts/build_airgap_bundle.sh \
  --db-host <DB호스트> --db-port <포트> --db-user ccop --db-name tccopdb
# 산출: ~/ccop_bundle_p1/ (images/rpms/db/src + SHA256SUMS) → exFAT USB 복사

# ── 3.3 2차 번들 생성 (런북 §5) ──
docker pull vllm/vllm-openai:v0.6.3.post1 && docker save ... (런북 §5 그대로)
rsync 으로 qwen25-t2c-v42_merged(15GB) 수집 → 4샤드+config+tokenizer+chat_template.jinja 확인
NVIDIA local-repo rpm(rhel10) + nvidia-container-toolkit rpm 수집 → SHA256SUMS
```

## 4. 물리·행정 준비 (기술 외)

- [ ] USB 2본: **exFAT** 포맷 — 1차 8GB↑ / 2차 64GB↑ (FAT32 금지)
- [ ] 기관 매체 반입 신청서 제출 → 사전 승인 확보
- [ ] 반입 게이트 백신 검사 대응, 매체 반출입 대장 양식 확인
- [ ] 현장 질문지 회신 확보: ① GPU 8장이 대상 VM에 passthrough 되는가(아니면 별도 GPU 노드 → `SLLM_ENDPOINT` 를 노드 IP로) ② BIOS **Secure Boot** ON/OFF ③ 내부 접속 도메인/IP (인증서 CN·`CORS_ORIGINS` 반영용)
- [ ] 런북 인쇄본 또는 오프라인 사본 (현장에서 인터넷 없음) — `scripts/build_doc_pdf.py docs/AIRGAP_VISIT_INSTALL_RUNBOOK.md` 로 PDF 생성 가능

## 5. D-day 시퀀스 요약 (런북 매핑)

```
[방문 1] 1차 — 인프라 (런북 §3~4)
  반입·무결성 검증(§4.1) → Docker 오프라인 설치(§4.2) → 이미지 load(§4.3)
  → 소스 복원+.env(§4.4) → DB 복원(§4.5) → 기동(§4.6) → 검증 체크리스트(§4.7)
  실패 시: sllm 없이 인프라만 유지 (자연어 질의만 유예)

[방문 2] 2차 — GPU+T2C (런북 §6~7, 1차 안정화 후)
  드라이버(+Secure Boot MOK) → container-toolkit → nvidia-smi 8장 확인
  → vLLM 이미지·모델 적재 → .env 세 줄 + --profile gpu → e2e 검증(§7.3)
  롤백: .env 세 줄 주석 → app 재기동 = 1차 상태 복귀
```

---

## 5. 🔔 현장 DB 선설치 반영 (2026-07-14 작업일지 접수)

현장 폐쇄망 VM에 **AgensGraph 16.9 네이티브 선설치 확인** (포트 5333, Rocky 10.1, shared_buffers 32GB 튜닝 완료) — 상세: [`AIRGAP_SITE_DB_LOG_20260714.md`](AIRGAP_SITE_DB_LOG_20260714.md)

**계획 변경**: 1차 설치는 **시나리오 A(네이티브 DB)** 가 기본 — `docker-compose.airgap.nativedb.yml` 사용, DB 컨테이너 미기동. agensgraph 이미지는 **폴백(시나리오 B) 보험으로 번들에 유지**(~수백MB). `.env` 템플릿은 `DB_HOST=host.docker.internal / DB_PORT=5333` 기본값으로 갱신됨.

**신규 검증 항목 (V1~V5, 현장 전 staging 리허설 권장)**:

- [ ] **V1 문법 호환**: 앱 Cypher 계층(`SET graph_path`·`cypher()` 래핑) ↔ AgensGraph 16.9 — 1차 검증의 '직접 Cypher 입력'으로 최우선 확인
- [ ] **V2 Extensions**: 작업일지 Extensions **공란** — 그래프 카탈로그·`uuid-ossp` 가용 여부 `\dx` 확인, 부족 시 DBA에 설치 요청
- [ ] **V3 덤프 호환**: 운영 덤프(2.13/PG13) → 16.9 복원 리허설. **실패 시 플랜 B**: 원천 CSV 반입 → 앱 ETL 재적재 (번들 db/ 에 CSV 세트 동봉 권장)
- [ ] **V4 DB·계정 정책**: `tccopdb` 신설 + 앱 전용 `ccop` 계정 (슈퍼유저 `hlucyber` 앱 사용 금지) — DBA 협의
- [ ] **V5 접근 경로**: `listen_addresses`·`pg_hba.conf`에 docker 브리지 대역 허용 — DBA 협의

**보안 지적 (고객사 전달)**: 기본 비밀번호 사용 중(일반/슈퍼유저) → 즉시 변경 권고. Archive Mode=No → 백업 정책 별도 수립.

---

*이 문서는 준비 진행에 따라 체크박스를 갱신한다. 기술 상세는 전부 런북을 따르고, 여기는 상태 추적만 담당.*
