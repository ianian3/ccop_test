# CCOP v1.0 — VM 배포 및 운영 개발 가이드

> 운영 VM(skai2_vm)에 CCOP 플랫폼을 배포·운영·유지보수하기 위한 통합 런북.
> 인프라 점검 이력은 [`CHECKPOINT_20260616.md`](CHECKPOINT_20260616.md), 브랜치/배포 워크플로우는 [`DEV_WORKFLOW.md`](DEV_WORKFLOW.md), 최초 배포 패키징은 [`../deploy/DEPLOY_CSLEE.md`](../deploy/DEPLOY_CSLEE.md) 참고.
>
> **최종 갱신: 2026-06-26**

---

## 0. 한눈에 보기 (운영 토폴로지)

```
                    ┌────────────────────────── 운영 VM (skai2_vm) ──────────────────────────┐
[외부 기관 브라우저] │  Naver Cloud · Rocky 9.6 · 175.45.205.106                              │
        │           │                                                                        │
   HTTPS 443        │   ┌─────────┐    ┌──────────┐                                          │
        └──ACG──────┼──▶│ nginx   │───▶│ ccop_app │  Gunicorn (CPU*2+1 workers)              │
    (소스 IP 제한)  │   │ :80/443 │    │  :5001   │──┐                                       │
                    │   └─────────┘    └────┬─────┘  │                                       │
                    │                       │        │ SLLM_ENDPOINT                         │
                    │                  ccop_agensgraph│ (172.19.0.1:8000)                    │
                    │                  (로컬 컨테이너) │                                       │
                    │                       │        │                                       │
                    └───────────────────────┼────────┼───────────────────────────────────────┘
                                            │        │
                              ┌─────────────┘        │ SSH 터널 (systemd 영속)
                       원격 DB (실데이터)             │
                       49.50.128.28:5333        ┌────▼──────────────────┐
                       AgensGraph / tccopdb     │ 엘리스 GPU (T2C 서빙)  │
                       기본그래프 tccop_graph_v6 │ vLLM qwen25-t2c-v42   │
                                                │ watchdog 영속          │
                                                └───────────────────────┘
```

| 구성요소 | 위치 | 역할 | 영속화 |
|----------|------|------|--------|
| **ccop_app** | skai2_vm 컨테이너 | Flask + Gunicorn 앱 | `restart: unless-stopped` |
| **ccop_nginx** | skai2_vm 컨테이너 | 리버스 프록시(SSL) | `restart: unless-stopped` |
| **ccop_agensgraph** | skai2_vm 컨테이너 | (현재 미사용) 로컬 그래프 DB | `restart: unless-stopped` |
| **실데이터 DB** | 49.50.128.28:5333 | AgensGraph `tccopdb` | 원격, 배포와 무관 |
| **vLLM (sLLM)** | 엘리스 GPU | Text2Cypher 모델 서빙 | watchdog (수동 부팅) |
| **SSH 터널** | skai2_vm → 엘리스 | vLLM 경로 `172.19.0.1:8000` | systemd (자동 부팅) |

> ⚠️ **명칭 혼동 주의**: "CSLEE"는 **배포 패키지명**(`docker-compose.cslee.yml`)이고, Git 서버 `cslee`(211.188.50.27, Gitea)는 **운영 VM이 아니다**. 실제 운영 VM은 **skai2_vm(175.45.205.106)**.

---

## 1. 접속 정보

| 대상 | 접속 명령 | 비고 |
|------|-----------|------|
| 운영 VM | `ssh -p 10022 root@175.45.205.106` | Rocky 9.6, 작업 경로 `/root/ccop_test` |
| 엘리스 GPU | `ssh elice_police` | MIG 3g.40gb(40GB), `~/vllm_env`, `~/models/qwen25-t2c-v42` |
| GPU 학습 머신 | `ssh ai-kyw-dev@192.168.1.133` | 머지 모델 원본 보관 |
| 원격 DB | `49.50.128.28:5333` | AgensGraph, `tccopdb`. **변경 금지** |
| Git origin | `github.com/ianian3/ccop_test.git` | CI 트리거 |
| Git 미러 | `211.188.50.27:8446/cslee/skai-vm.git` (Gitea) | dual-push 미러 |
| UI | `https://175.45.205.106/` | 자체서명 인증서, ACG 소스IP 제한 |

> SSH(10022)는 어떤 경우에도 `0.0.0.0/0` 개방 금지. 본인/관리 IP만 허용.

---

## 2. 배포 아키텍처 원칙

1. **VM은 배포 대상, 개발은 개발 머신에서만.** ⛔ VM(skai2_vm)에서 직접 코드 커밋 금지. VM은 GitHub 자격증명이 없어 push도 불가.
2. **CI는 검증, CD는 수동.** dev push → GitHub Actions가 import/기동 검증만 수행. 실제 배포는 VM에서 수동 실행.
3. **app만 VM에서 빌드.** `app` 컨테이너는 Dockerfile로 VM에서 직접 빌드(`--build` 필수). DB/nginx 컨테이너는 이미지 그대로 유지.
4. **운영 컴포즈는 `docker-compose.cslee.yml`** 단일 진실. 루트의 `docker-compose.yml`은 로컬 개발용 — 운영에 쓰지 말 것.
5. **`.env`는 VM 로컬 전용.** gitignore라 `git pull`이 덮어쓰지 않음. 운영값(DB=tccopdb, SLLM_ENDPOINT)이 여기 있음.

---

## 3. 일상 배포 절차 (권장 경로)

### 3.1 개발 머신: 코드 push

```bash
# (선택) 기능 브랜치
git switch -c feature/my-change dev
# ... 작업 + 커밋 ...
git switch dev && git merge --no-ff feature/my-change
git branch -d feature/my-change

# origin(GitHub) + cslee(Gitea) 동시 push (dual-push 설정 시 1회로 둘 다)
git push origin dev
```

push 후 **GitHub Actions CI(test) green 확인** → 배포 진행.

<details>
<summary>dual-push 설정 (개발 머신, 최초 1회)</summary>

```bash
git remote set-url --add --push origin https://github.com/ianian3/ccop_test.git
git remote set-url --add --push origin http://<gitea-cred>@211.188.50.27:8446/cslee/skai-vm.git
git remote get-url --push --all origin   # 확인: 2개 URL
```
</details>

### 3.2 운영 VM: 배포 실행 (헬퍼 스크립트)

```bash
ssh -p 10022 root@175.45.205.106
cd /root/ccop_test
bash scripts/deploy.sh
```

`scripts/deploy.sh` 동작: **현재 커밋 기록 → `origin/dev` fast-forward pull → app 재빌드·재기동 → 헬스체크(최대 60초) → 실패 시 직전 커밋으로 자동 롤백.**

### 3.3 수동 단계 (스크립트 미사용 시 참고)

```bash
cd /root/ccop_test
git pull --ff-only origin dev
docker compose -f docker-compose.cslee.yml up -d --build app
curl -sk https://localhost/api/v1/health      # {"status":"healthy"}
```

### 3.4 배포 성공 → 릴리스 태그 (개발 머신)

```bash
git tag -a prod-$(date +%Y%m%d) <배포커밋> -m "운영 배포: <요약>"
git push origin prod-$(date +%Y%m%d)
```

> stable 표식은 **release 브랜치가 아니라 태그**(`prod-YYYYMMDD`, `v1.x.x`)로 관리한다.

---

## 4. 롤백

```bash
# VM: 직전 stable 태그로 되돌려 재빌드
cd /root/ccop_test
git checkout prod-<직전날짜>
docker compose -f docker-compose.cslee.yml up -d --build app
curl -sk https://localhost/api/v1/health
```

- `scripts/deploy.sh`는 헬스체크 실패 시 **직전 커밋으로 자동 롤백**한다.
- 근본 수정은 VM이 아니라 **dev에서 `git revert` → 재배포** 순서로.

---

## 5. 환경변수 (.env) — 운영 기준값

`deploy/.env.cslee.template`을 복사해 작성하되, **운영 VM의 실제값은 아래 기준**:

```ini
# ── DB (실데이터, 원격) ──
DB_NAME=tccopdb               # ⚠️ ccopdb(빈 DB) 아님
DB_USER=<운영계정>
DB_PASSWORD=<비밀>
DB_HOST=49.50.128.28          # 원격 AgensGraph
DB_PORT=5333

# ── LLM: 온프레미스 sLLM (운영 표준) ──
SLLM_ENDPOINT=http://172.19.0.1:8000/v1   # 엘리스 vLLM (SSH 터널 게이트웨이)
SLLM_MODEL_NAME=qwen25-t2c-v42
# OPENAI_API_KEY 는 비우거나 미설정 (placeholder면 자연어 질의 401 실패)

# ── 그래프 기본값 ──
DEFAULT_GRAPH_PATH=tccop_graph_v6   # ⚠️ osint_ontology(6.89M노드) 기본값 금지

# ── 보안 ──
SECRET_KEY=<랜덤 32자+>
ADMIN_PASSWORD=<관리자 비밀번호>
CORS_ORIGINS=https://cslee-platform.internal,http://localhost
LOG_LEVEL=INFO
```

> `SLLM_ENDPOINT`가 설정되면 앱(`config.py`/`ai_service.py`)은 자동으로 sLLM 경로(`base_url=endpoint, api_key="EMPTY"`)를 사용한다. OpenAI 키는 인터넷 환경 fallback일 뿐, 운영 표준은 vLLM 자체 서빙이다.

### tccopdb 그래프 목록 (참고)

| 그래프 | 노드/엣지 | 용도 |
|--------|-----------|------|
| **`tccop_graph_v6`** | 149 / 144 | **기본 그래프** |
| `osint_ontology` | 6.89M / 10.94M | ⛔ 기본값 금지(대용량) |
| `ccop_osint_v40_proper` | 6464 / 1175 | OSINT V4.0 |
| `ccop_osint_demo` | 5177 / 1035 | 데모 |
| `ccop_fraud_graph` | 225 / 15186 | 사기 분석 |
| 기타 | — | `ku_graphs_test`, `v40_demo_528_1035`, `tccop_v40_demo`, `ku_graphs_test_petition` |

---

## 6. LLM(vLLM) 서빙 운영

### 6.1 평소 무조치 원칙

skai2_vm 터널은 **systemd로 영속**(부팅 자동기동·`Restart=always`), 엘리스 vLLM은 **watchdog로 자동복구**되므로 평소 개입 불필요.

### 6.2 단, 엘리스 온디맨드 인스턴스 ⚠️

엘리스는 **온디맨드 인스턴스**라 인스턴스가 재시작/종료되면 watchdog가 죽는다. **인스턴스가 켜져 있어야** 하며, 꺼졌다 켜지면 엘리스에서 watchdog를 수동 재기동:

```bash
ssh elice_police
setsid bash ~/vllm_watchdog.sh < /dev/null > /dev/null 2>&1 &   # 반드시 setsid
```

### 6.3 상태 점검

```bash
# VM에서: 터널 systemd 상태
systemctl status elice-vllm-tunnel.service

# VM에서: vLLM 경로 직접 확인
curl -s http://172.19.0.1:8000/v1/models

# 엘리스에서: vLLM 헬스
curl -s http://localhost:8000/v1/models
```

### 6.4 watchdog 운영 함정 (디버깅 시 주의)

1. **pkill self-match** — `pkill -f "vllm.entrypoints"`는 그 문자열을 가진 SSH 셸까지 죽인다. 수동 명령은 브래킷 트릭 `[v]llm.entrypoints` 사용.
2. **orphan 엔진 워커** — `vllm.entrypoints`만 죽이면 multiprocessing 워커가 GPU를 점유해 다음 기동이 `NVML INTERNAL ASSERT`로 실패. `vllm_env/bin/python` 패턴으로 전부 정리.
3. **포트 미해제** — 재기동 시 `Address already in use`. 포트 해제 + 프로세스 종료 대기 필수.

상세 서빙 재현 절차(cu121 호환 설치, chat_template 등)는 [`CHECKPOINT_20260616.md` 부록 A](CHECKPOINT_20260616.md) 참고.

---

## 7. 외부 기관 시연 — 네트워크 접근

UI는 `https://175.45.205.106/`로 개방돼 있으나(nginx 0.0.0.0:443, 호스트 방화벽 inactive), **Naver Cloud ACG가 소스 IP 화이트리스트로 제한**한다. 외부 기관이 자기 망에서 접속하려면 ACG에 그 공인 IP를 허용해야 한다.

> **중요**: 클라이언트 망은 LLM 동작과 무관하다. vLLM/DB 경로는 전부 서버 측이므로 **UI(443)만 닿으면 어디서 접속하든 T2C는 동일하게 작동**한다.

| 방식 | 매번 관리 | 보안 | 적합 |
|------|----------|------|------|
| IP 화이트리스트(현행) | 네트워크마다 추가 | 높음 | 고정 IP 기관 |
| `0.0.0.0/0` 임시 개방 + nginx Basic Auth | 불필요 | 중 | 떠돌이 시연 |
| 기관 고정 IP/CIDR 허용 | 기관당 1회 | 높음 | 고정 공인망 기관 |

> 모바일/핫스팟 IP는 동적이라 매번 추가해야 한다. SSH(10022)는 절대 전체 개방 금지.

---

## 8. 운영 점검 체크리스트

배포 전후 확인:

| 항목 | 확인 |
|------|------|
| **CI** | dev push 후 GitHub Actions test green |
| **컨테이너** | `docker compose -f docker-compose.cslee.yml ps` — app/nginx healthy |
| **헬스체크** | `curl -sk https://localhost/api/v1/health` → `{"status":"healthy"}` |
| **DB 연결** | `/api/v1/graph/list`가 빈 그래프가 아닌 실데이터 9개 반환 |
| **LLM 경로** | `curl -s http://172.19.0.1:8000/v1/models` 응답 정상 |
| **엘리스 인스턴스** | 온디맨드 인스턴스 ON 상태 |
| **터널** | `systemctl status elice-vllm-tunnel.service` active |
| **자연어 e2e** | UI에서 "피의자2의 계좌를 보여줘" → Cypher(`vt_*`) → 결과 |
| **미러** | cslee(Gitea) dual-push 동기화 |

---

## 9. 로그 / 트러블슈팅

### 로그 위치

```bash
cd /root/ccop_test
docker compose -f docker-compose.cslee.yml logs -f app      # 앱 실시간 로그
docker compose -f docker-compose.cslee.yml logs -f nginx    # nginx
# Gunicorn 접근/에러 로그: ./logs/gunicorn_access.log, gunicorn_error.log
```

### 증상별 대응

| 증상 | 원인 후보 | 대응 |
|------|-----------|------|
| 자연어 질의 401/실패 | OPENAI_API_KEY placeholder, vLLM 다운 | `.env`에서 OpenAI 키 제거 + SLLM 경로 확인, vLLM watchdog 재기동 |
| `/graph/list` 빈 그래프만 | `.env` DB_NAME=ccopdb(빈 DB) | `DB_NAME=tccopdb`로 교정 후 app 재생성 |
| `172.19.0.1` 연결 거부 | docker 네트워크 재생성으로 게이트웨이 변동, 터널 끊김 | 터널 systemd 재시작, 게이트웨이 IP 재확인 |
| 외부에서 접속 불가 | ACG 소스 IP 차단 | 기관 공인 IP를 ACG에 허용 |
| 배포 후 헬스체크 실패 | 코드/의존성 오류 | deploy.sh 자동 롤백 확인, 로그 점검 후 dev에서 revert |

---

## 10. 미해결 / 개선 과제

1. **외부 시연 접근** — ACG에 기관 IP 허용 또는 `0.0.0.0/0` + nginx Basic Auth.
2. **docker IP 고정** — `172.19.0.1` 자동할당 의존 → compose `ccop_external`에 IPAM 고정(네트워크 재생성 시 vLLM 경로 중단 방지).
3. **정식 인증서** — 외부 시연용 도메인 + 정식 SSL 인증서(현재 자체서명).
4. **엘리스 상시 인스턴스 전환** — 온디맨드 재시작 시 watchdog 수동 재기동 필요 → 상시 인스턴스가 근본 해결.
5. **커밋된 시크릿 정리** — `deploy/DEPLOY_CSLEE.md` 평문 API키, git remote 평문 자격증명 제거.
6. **자동 CD 검토** — 필요 시 GitHub 시크릿(`DOCKER_*`, `VPS_*`) 등록 + 타깃을 `docker-compose.cslee.yml`로 재구성.

---

## 부록. 관련 문서

| 문서 | 내용 |
|------|------|
| [`DEV_WORKFLOW.md`](DEV_WORKFLOW.md) | 브랜치 전략(trunk-based on dev), dual-push |
| [`CHECKPOINT_20260616.md`](CHECKPOINT_20260616.md) | 인프라 점검 이력, vLLM 서빙 재현, systemd 유닛 전문 |
| [`../deploy/DEPLOY_CSLEE.md`](../deploy/DEPLOY_CSLEE.md) | 최초 배포 패키징, API 엔드포인트 요약 |
| [`../deploy/.env.cslee.template`](../deploy/.env.cslee.template) | 환경변수 템플릿 |
| [`EXTERNAL_CYPHER_QUERY_HOWTO.md`](EXTERNAL_CYPHER_QUERY_HOWTO.md) | 외부 기관용 그래프 조회 API |
