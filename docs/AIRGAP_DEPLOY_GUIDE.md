# CCOP v1.0 — 폐쇄망(Air-gap) 설치 및 운영 가이드

> 인터넷이 완전히 차단된 폐쇄망 VM에 CCOP 플랫폼을 설치·운영하기 위한 절차.
> 인터넷 환경 운영은 [`VM_DEPLOY_OPERATIONS_GUIDE.md`](VM_DEPLOY_OPERATIONS_GUIDE.md) 참고.
>
> **핵심 원리**: 모든 외부 의존성을 **인터넷 가능한 staging 머신에서 번들로 패키징** → **승인된 반입 매체로 이동** → **폐쇄망 내부에서 오프라인 설치**. 폐쇄망 안에서는 `docker pull` · `pip install` · `apt-get` · OpenAI · HuggingFace · GitHub 모두 불가.

---

## 0. 폐쇄망에서 달라지는 것 (인터넷 운영 대비)

| 구성 | 인터넷 운영 | 폐쇄망 |
|------|------------|--------|
| **LLM** | OpenAI GPT-4o + 엘리스 vLLM 터널 | **내부망 GPU + vLLM 자체 서빙만** (외부 터널·OpenAI 전부 불가) |
| **Docker 이미지** | `docker pull` (Docker Hub) | **`docker save`→반입→`docker load`** |
| **Python 패키지** | `pip install` (PyPI) | **사전 빌드 이미지** 또는 wheelhouse 반입 |
| **apt 패키지** | `apt-get install` | 이미지 빌드 시 staging에서 포함 |
| **코드 배포** | `git pull origin dev` (GitHub) | **내부 Gitea(cslee)** 또는 tar 반입 |
| **그래프 데이터** | 원격 DB(49.50.128.28) | **로컬 AgensGraph 컨테이너 + 덤프 복원** |
| **임베딩 모델** | HuggingFace 런타임 다운로드 | (Legal RAG 사용 시) **모델 사전 번들** |
| **시간 동기화** | 외부 NTP | 내부 NTP 서버 |
| **인증서** | 기관 발급/Let's Encrypt | 내부 CA 또는 자체서명 |

> ⚠️ **LLM 품질 주의**: 현 코드(`app/services/ai_service.py`)의 **Router·reflection 노드는 `OPENAI_API_KEY`가 있을 때만 `gpt-4o-mini`를 사용**하고, 없으면 `SLLM_MODEL_NAME`으로 폴백한다. 폐쇄망엔 OpenAI 키가 없으므로 라우팅/리플렉션도 sLLM이 담당 → 학습 모델(qwen25-t2c-v42)은 의도 분류 JSON에 최적화돼 있지 않아 **잡담/가드 분기 정확도 저하 가능**. 폐쇄망 전용으로는 라우터를 규칙 기반으로 단순화하거나 의도 분류 데이터로 보강 학습 필요.

---

## 1. 반입 번들 매니페스트 (staging 머신에서 준비)

인터넷 가능한 staging 머신(폐쇄망 VM과 **동일 아키텍처 `linux/amd64`**)에서 아래를 모두 모은다.

```
ccop_airgap_bundle/
├── images/
│   ├── ccop_app_1.0.tar          # 사전 빌드한 앱 이미지 (핵심)
│   ├── agensgraph_2.13.2.tar      # bitnine/agensgraph:v2.13.2
│   ├── nginx_alpine.tar           # nginx:alpine
│   └── vllm_openai.tar            # vllm/vllm-openai (GPU 서빙용)
├── model/
│   └── qwen25-t2c-v42/            # T2C 머지 풀웨이트 (~15GB, 4 샤드+config+tokenizer+chat_template.jinja)
├── db/
│   └── tccopdb_dump.sql.gz        # 그래프 데이터 (pg_dump -F c)
├── embed_model/                   # (선택) Legal RAG 사용 시 임베딩 모델
├── src/
│   └── ccop_test.tar.gz           # 소스 코드 (git bundle 또는 tar)
├── deploy/
│   ├── docker-compose.cslee.yml
│   ├── .env.airgap                # 폐쇄망 .env (아래 §4)
│   └── nginx.cslee.conf + ssl/    # 내부 인증서
└── SHA256SUMS                     # 전체 체크섬 (반입 후 무결성 검증)
```

### 1.1 앱 이미지 사전 빌드 (가장 중요)

폐쇄망에선 Dockerfile의 `apt-get`·`pip install`이 불가하므로, **staging에서 완성 이미지를 빌드해 통째로 반출**한다.

```bash
# staging (인터넷 O) — 동일 아키텍처
cd ccop_test
docker build --platform linux/amd64 -t ccop_app:1.0 -f Dockerfile .
docker save ccop_app:1.0 -o images/ccop_app_1.0.tar
```

### 1.2 베이스/서빙 이미지 내려받아 저장

```bash
docker pull bitnine/agensgraph:v2.13.2
docker pull nginx:alpine
docker pull vllm/vllm-openai:latest      # 폐쇄망 GPU 드라이버와 CUDA 호환 태그 고정 권장
docker save bitnine/agensgraph:v2.13.2 -o images/agensgraph_2.13.2.tar
docker save nginx:alpine -o images/nginx_alpine.tar
docker save vllm/vllm-openai:latest -o images/vllm_openai.tar
```

> vLLM 이미지는 폐쇄망 GPU의 드라이버/CUDA 버전과 맞는 태그를 고정해야 한다. (엘리스 사례: 드라이버 535/CUDA 12.2 → cu121 호환 필요. 폐쇄망 GPU 사양 확인 후 결정.)

### 1.3 모델 가중치 / DB 덤프

```bash
# 모델: GPU 학습 머신에서 머지 풀웨이트 복사 (rsync/tar)
#   원본: ai-kyw-dev@192.168.1.133:.../qwen25_t2c_v42_v1_merged/  (~15GB)

# DB 덤프: 현 운영 DB에서 (또는 데이터 보유처에서)
pg_dump -h 49.50.128.28 -p 5333 -U <user> -d tccopdb -F c -f db/tccopdb_dump.dump
gzip db/tccopdb_dump.dump

# 체크섬
( cd ccop_airgap_bundle && find . -type f ! -name SHA256SUMS -exec sha256sum {} \; > SHA256SUMS )
```

---

## 2. 반입 및 무결성 검증 (폐쇄망 VM에서)

```bash
# 승인된 매체로 번들 반입 후
cd /opt/ccop_airgap_bundle
sha256sum -c SHA256SUMS        # 전 파일 OK 확인 (전송 손상/변조 점검)
```

---

## 3. 이미지 적재 및 컴포즈 전환

```bash
# 이미지 load
for t in images/*.tar; do docker load -i "$t"; done
docker images   # ccop_app:1.0, bitnine/agensgraph, nginx, vllm/vllm-openai 확인
```

폐쇄망에선 빌드를 하지 않으므로 `docker-compose.cslee.yml`의 app 서비스를 **`build:` → `image:`** 로 전환:

```yaml
  app:
    image: ccop_app:1.0       # build: 블록 제거 (폐쇄망은 사전 적재 이미지 사용)
    container_name: ccop_app
    ...
```

> 이렇게 하면 운영 시 `docker compose ... up -d app`(빌드 없이)로 기동된다. 갱신 배포(§8)도 새 이미지 tar 반입 → load → `up -d` 흐름이 된다.

---

## 4. 환경변수 (.env) — 폐쇄망 기준

```ini
# ── DB: 로컬 AgensGraph 컨테이너 ──
DB_NAME=tccopdb
DB_USER=ccop
DB_PASSWORD=<강력한_비밀번호>
DB_HOST=agensgraph        # 컴포즈 내부 서비스명 (원격 49.50.x 아님)
DB_PORT=5432

# ── LLM: 내부망 vLLM 자체 서빙만 ──
SLLM_ENDPOINT=http://<내부GPU호스트>:8000/v1   # 같은 폐쇄망 내 GPU
SLLM_MODEL_NAME=qwen25-t2c-v42
# OPENAI_API_KEY  ← 절대 설정하지 않음 (있어도 외부 호출 실패로 행 유발)

# ── 그래프 기본값 ──
DEFAULT_GRAPH_PATH=tccop_graph_v6

# ── 보안 ──
SECRET_KEY=<랜덤 32자+>
ADMIN_PASSWORD=<관리자 비밀번호>
CORS_ORIGINS=https://<내부 플랫폼 도메인>,http://localhost
LOG_LEVEL=INFO
```

> `SLLM_ENDPOINT`만 있고 `OPENAI_API_KEY`가 없으면 앱은 모든 LLM 호출을 sLLM으로 보낸다(`base_url=endpoint, api_key="EMPTY"`). §0의 라우터 품질 주의를 반드시 고려.

---

## 5. 데이터베이스 기동 및 복원

```bash
cd /opt/ccop  # 컴포즈 위치

# 1) DB 컨테이너만 먼저 기동 (AGE 확장은 init_db.sh가 자동 생성)
docker compose -f docker-compose.cslee.yml up -d agensgraph
docker compose -f docker-compose.cslee.yml logs -f agensgraph   # "initialization complete" 확인

# 2) 덤프 복원
gunzip -k db/tccopdb_dump.dump.gz
docker cp db/tccopdb_dump.dump ccop_agensgraph:/tmp/dump.dump
docker exec -it ccop_agensgraph \
  pg_restore -U ccop -d tccopdb --clean --if-exists /tmp/dump.dump

# 3) 그래프 적재 확인
docker exec -it ccop_agensgraph psql -U ccop -d tccopdb \
  -c "LOAD 'age'; SET search_path=ag_catalog; SELECT name FROM ag_graph;"
```

> 복원 후 `tccop_graph_v6` 등 그래프가 보여야 한다. AGE 확장 미로드 에러 시 `init_db.sh`(AGE extension 생성)가 정상 실행됐는지 로그 확인.

---

## 6. sLLM(vLLM) 자체 서빙 — 내부 GPU

폐쇄망 안의 GPU 서버(또는 GPU를 가진 동일 VM)에서 vLLM을 기동한다. 외부 엘리스 터널은 폐쇄망에선 불가하므로, **vLLM이 내부망에 직접 떠 있어야** 한다.

### 6.1 컴포즈 sllm 서비스 사용 (GPU가 같은 VM일 때)

`docker-compose.cslee.yml`의 주석 처리된 `sllm:` 블록을 폐쇄망용으로 수정:

```yaml
  sllm:
    image: vllm/vllm-openai:latest      # §3에서 load한 이미지
    container_name: ccop_sllm
    runtime: nvidia
    command: >
      --model /models/qwen25-t2c-v42
      --served-model-name qwen25-t2c-v42
      --host 0.0.0.0 --port 8000
      --max-model-len 16384 --gpu-memory-utilization 0.9
      --dtype auto
      --chat-template /models/qwen25-t2c-v42/chat_template.jinja
    volumes:
      - ./model/qwen25-t2c-v42:/models/qwen25-t2c-v42:ro   # 반입한 가중치
    networks: [ccop_internal]
    deploy:
      resources:
        reservations:
          devices: [{ driver: nvidia, count: 1, capabilities: [gpu] }]
    restart: unless-stopped
```

이 경우 `.env`의 `SLLM_ENDPOINT=http://sllm:8000/v1` (컴포즈 내부 서비스명).

### 6.2 별도 GPU 호스트일 때

GPU 서버에서 vLLM을 직접 기동(컨테이너 또는 venv)하고, `.env`의 `SLLM_ENDPOINT`를 그 호스트의 내부 IP로 지정. 영속화는 `restart: unless-stopped`(컨테이너) 또는 systemd(host)로.

### 6.3 검증

```bash
curl -s http://<sllm호스트>:8000/v1/models    # qwen25-t2c-v42 응답
```

---

## 7. 앱·프록시 기동 및 e2e 검증

```bash
cd /opt/ccop
docker compose -f docker-compose.cslee.yml up -d        # app + nginx (+ sllm)
docker compose -f docker-compose.cslee.yml ps           # 전부 healthy
curl -sk https://localhost/api/v1/health                # {"status":"healthy"}

# 그래프 목록 — 빈 그래프가 아닌 실데이터 확인
curl -sk https://localhost/api/v1/graph/list

# 자연어 e2e: UI 또는 API
#   "피의자2의 계좌를 보여줘" → vLLM → Cypher(vt_*) → AgensGraph → 결과
```

폐쇄망에서 검증해야 할 경로: **브라우저(내부망) → nginx(443) → app(5001) → ① AgensGraph(로컬) ② vLLM(내부 GPU)**. 모든 홉이 폐쇄망 내부로 완결되는지 확인(외부 호출 0건).

---

## 8. 운영 — 갱신 배포 (폐쇄망)

git pull이 불가하므로 **번들 반입 방식**으로 갱신한다.

**코드/이미지 갱신**
1. staging에서 새 `ccop_app:<버전>` 빌드 → `docker save` → 체크섬.
2. 반입 → `sha256sum -c` → `docker load`.
3. `docker-compose.cslee.yml`의 `image:` 태그 갱신 → `docker compose ... up -d app`.
4. 헬스체크. 실패 시 직전 이미지 태그로 되돌려 `up -d`(이미지 롤백).

**모델 갱신** (v44 등): 새 가중치 디렉토리 반입 → vLLM 볼륨 교체 → sllm 재기동 → `/v1/models` 확인.

> 내부 Gitea(cslee, 211.188.50.27)가 폐쇄망 내부에 있다면, 소스는 git bundle 대신 내부 Gitea push/pull로 운영 가능(이미지 빌드만 별도 처리).

---

## 9. 운영 — 백업 / 모니터링

```bash
# DB 백업 (스크립트 내장: 30일 경과분 자동 정리)
docker exec ccop_agensgraph bash -c \
  'DB_NAME=tccopdb DB_USER=ccop /scripts/backup_db.sh'
# 또는 호스트에서 pg_dump -F c 후 폐쇄망 백업 정책에 따라 보관

# 로그
docker compose -f docker-compose.cslee.yml logs -f app
#   Gunicorn: ./logs/gunicorn_access.log, gunicorn_error.log
```

- **시간 동기화**: 폐쇄망 내부 NTP로 VM·GPU 시각 일치(인증서·로그·토큰 정합).
- **인증서 만료**: 자체서명/내부 CA 인증서 만료일 추적(외부 갱신 불가).
- **디스크**: 모델(~15GB)·이미지·DB·로그 증가 모니터링.

---

## 10. 폐쇄망 사전 점검 체크리스트

| 항목 | 확인 |
|------|------|
| 아키텍처 일치 | staging 빌드와 폐쇄망 VM 모두 `linux/amd64` |
| GPU/드라이버 | 폐쇄망 GPU 드라이버·CUDA와 vLLM 이미지 태그 호환 |
| 이미지 적재 | app·agensgraph·nginx·vllm 4종 `docker load` 완료 |
| 무결성 | 반입 번들 `sha256sum -c` 전부 OK |
| .env | `OPENAI_API_KEY` 미설정, `SLLM_ENDPOINT` 내부 지정, `DB_HOST=agensgraph` |
| DB | 덤프 복원 후 `tccop_graph_v6` 등 그래프 존재 |
| sLLM | `/v1/models`가 `qwen25-t2c-v42` 반환 |
| e2e | 자연어 질의가 외부 호출 0건으로 결과 반환 |
| LLM 품질 | 라우터 sLLM 폴백 영향 평가(§0) — 필요 시 규칙 라우터/보강 학습 |
| 백업/NTP/인증서 | 내부 정책으로 운영 |

---

## 부록. 의존성 인벤토리 (반입 대상 원천)

| 의존성 | 원천 (인터넷) | 폐쇄망 반입물 |
|--------|--------------|---------------|
| 앱 런타임 | PyPI(`requirements.txt`) + apt(gcc/libpq-dev/postgresql-client) | `ccop_app:1.0` 이미지 tar |
| 그래프 DB | Docker Hub `bitnine/agensgraph:v2.13.2` | 이미지 tar |
| 프록시 | Docker Hub `nginx:alpine` | 이미지 tar |
| LLM 서빙 | Docker Hub `vllm/vllm-openai` | 이미지 tar (CUDA 호환 태그) |
| T2C 모델 | GPU 학습 머신 머지 풀웨이트 | `qwen25-t2c-v42/` (~15GB) |
| 그래프 데이터 | 운영 DB `tccopdb` | `pg_dump -F c` 덤프 |
| 임베딩(선택) | HuggingFace | (Legal RAG 사용 시) 모델 디렉토리 |
| 소스 | GitHub `ianian3/ccop_test` | git bundle/tar 또는 내부 Gitea |
