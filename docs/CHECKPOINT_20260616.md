# CCOP v1.0 운영/배포 체크포인트 — 2026-06-16

**범위**: 운영 VM 배포 점검 · DB 연결 교정 · 엘리스 vLLM(sLLM) 자체 서빙 구축 · 영속화 · 외부 시연 점검
**대상 환경**: skai2_vm(운영 VM) · 엘리스 GPU(T2C 서빙) · GPU 학습 머신
**상태**: 자연어 질의 end-to-end 동작 ✅ / 외부 시연 접근만 ACG 작업 대기 ⚠️

---

## 0. TL;DR

- 운영 스택은 **skai2_vm(175.45.205.106)** 에서 이미 가동 중이었음 ("CSLEE"는 배포 패키지명, Git 서버 cslee와 구분).
- 앱이 **빈 DB(ccopdb)** 를 보고 있던 문제 → **tccopdb(실데이터)** 로 교정.
- OpenAI 키 placeholder로 자연어 질의가 401로 깨져 있던 것 → **엘리스 vLLM에 v42 자체 서빙**으로 전환, end-to-end 복구.
- vLLM·터널 **영속화**(watchdog + systemd) 및 자동복구 검증 완료.
- **외부 임의 네트워크는 Naver Cloud ACG 소스 IP 제한으로 차단** → 시연 시 ACG 허용 필요.

---

## 1. 현재 운영 상태 (스냅샷)

| 구성 | 상태 | 비고 |
|------|------|------|
| 앱 스택(skai2_vm) | ✅ healthy | `ccop_app` + `ccop_agensgraph` + `ccop_nginx`, `docker-compose.cslee.yml` |
| 데이터베이스 | ✅ **tccopdb** | 그래프 9개(실데이터). 기본 그래프 `tccop_graph_v6` |
| LLM | ✅ 엘리스 vLLM **qwen25-t2c-v42** | watchdog 영속 |
| 네트워크 경로 | ✅ skai2_vm→엘리스 SSH 터널 `172.19.0.1:8000` | systemd 유닛(enabled) |
| 자연어 질의 e2e | ✅ 동작 | 자연어→vLLM→Cypher(`vt_*`)→AgensGraph |
| UI 외부 접속 | ⚠️ ACG 소스IP 제한 | 시연 기관 IP 허용 필요 |

---

## 2. Text2Cypher 모델 분석 (요약)

- **운영 표준 = v42 + Router (86.6%, 201/232)**.
- 단, v42 대비 개선분(+13문항)은 전부 **general/guard 카테고리(라우팅)** 에서 발생 — 21개 Cypher 카테고리는 v42와 **완전 동일**.
  → Router는 "잡담/가드 분기"이지 모델 실력 향상이 아님.
- 신규엣지 정확도만 보면 v41(66.1%)이 최고(트레이드오프). 모델 약점(1hop_event/meta_condition 60%, chain 67% 등)은 라우터로 해결 불가 → **v44 continue-learning** 과제로 잔존.

---

## 3. 배포 인프라 점검 + 백업

- 운영 VM은 **skai2_vm**. (메모리 혼동 주의: cslee[211.188.50.27]는 Git/Gitea 서버, 운영 VM 아님)
- 기존에 `docker-compose.cslee.yml`로 3컨테이너가 healthy 가동 중이었음(신규 배포 아님).
- **VM에만 있던 커밋 `d2c907d`(부팅 차단 이슈 3종 수정)를 origin/dev에 push 백업** — VM은 GitHub 자격증명이 없어 직접 push 불가하므로, Mac에서 `git fetch ssh://root@175.45.205.106:10022/root/ccop_test dev`로 가져와 push.
  - 수정 내용: agensgraph 이미지 `v2.13→v2.13.2`, `requirements.txt`에 `langgraph` 추가, compose DB_HOST/PORT env 오버라이드 허용.

---

## 4. DB 연결 교정

- **증상**: 앱 `/api/graph/list`가 빈 그래프 3개만 반환.
- **원인**: `.env`의 `DB_NAME=ccopdb`(빈 DB)를 보고 있었음. 실데이터는 **tccopdb**.
- **조치**: `.env` 수정 후 app 재생성.

```diff
- DB_NAME=ccopdb
+ DB_NAME=tccopdb
- DEFAULT_GRAPH_PATH=ccop_tst_graph
+ DEFAULT_GRAPH_PATH=tccop_graph_v6
```

- tccopdb 그래프(노드/엣지): `osint_ontology`(6.89M/10.94M, 기본값 금지), `ccop_osint_v40_proper`(6464/1175), `ccop_osint_demo`(5177/1035), `ku_graphs_test`(1292/1404), `v40_demo_528_1035`(443/735), `ccop_fraud_graph`(225/15186), `tccop_v40_demo`(178/207), **`tccop_graph_v6`(149/144)**, `ku_graphs_test_petition`(60/71).

---

## 5. sLLM(vLLM) 자체 서빙 구축 ⭐

이전엔 OpenAI 키가 placeholder(`sk-REPLACE..._KEY`)라 모든 질의가 401로 실패. 엘리스 GPU에 운영 표준 v42를 자체 서빙으로 전환.

### 5.1 모델 전송
- 출처: GPU 머신 `ai-kyw-dev@192.168.1.133:/home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v42_v1_merged/` (머지 풀웨이트 15GB).
- 전송: GPU 머신 → 엘리스, `rsync` (엘리스 pem 경유). 수신 무결성(4 샤드+config+tokenizer) 검증.

### 5.2 vLLM 설치 (드라이버 호환)
- 엘리스: **MIG 3g.40gb(40GB)**, 드라이버 `535.161.07`(CUDA 12.2). VRAM 40GB라 **FP16 그대로(양자화 불필요)**.
- 최신 `pip install vllm`은 cu13/torch2.11을 끌어와 드라이버 불일치(`torch.cuda=False`) → **cu121 호환으로 재설치**:
  - `vllm==0.6.3.post1` (torch 2.4.0+cu121 동반)
  - `transformers==4.46.3`로 다운그레이드 (기본 5.x는 `Qwen2Tokenizer ... all_special_tokens_extended` 에러)
  - `pyairports` 0.0.1(깨짐)·인덱스에 2.x 없음 → **스텁 모듈** 생성
  - 모델이 transformers5로 저장돼 chat_template 분리 → `--chat-template <jinja>` 명시

### 5.3 네트워크 경로 (경로 B)
- skai2_vm → 엘리스 SSH 터널: `ssh -N -L 172.19.0.1:8000:localhost:8000 -p 21866 -i /root/elice.pem elicer@central-01.tcp.tunnel.elice.io`
- `172.19.0.1` = 앱이 붙은 docker bridge `ccop_test_ccop_external` 게이트웨이.

### 5.4 앱 전환
- `.env`: `SLLM_ENDPOINT=http://172.19.0.1:8000/v1`, `SLLM_MODEL_NAME=qwen25-t2c-v42`.
- `docker-compose.cslee.yml` app `environment:`에 `SLLM_ENDPOINT`/`SLLM_MODEL_NAME` 주입(주석 해제).
- 앱 로직(`config.py`/`ai_service.py`): `SLLM_ENDPOINT` 있으면 sLLM 사용(`base_url=endpoint, api_key="EMPTY"`).

### 5.5 검증
- `자연어("피의자2의 계좌를 보여줘") → vLLM v42 → Cypher(vt_psn/vt_bacnt) → AgensGraph → 결과` 정상.

---

## 6. 영속화 (systemd / watchdog) + 검증

### 6.1 skai2_vm 터널 — systemd 유닛
- `/etc/systemd/system/elice-vllm-tunnel.service` (active, **enabled**=부팅 자동기동).
- `Restart=always` + keepalive + `ExitOnForwardFailure` + `StartLimitIntervalSec=0`(부팅 시 docker 네트워크 생길 때까지 무한재시도).
- autossh 미설치/EPEL 없음 → systemd Restart=always로 대체(동등).
- **검증**: 강제 kill → 새 PID로 자동재기동(NRestarts=1).

### 6.2 엘리스 vLLM — watchdog
- 엘리스는 systemd 불가(PID1=init, `systemctl is-system-running`=offline) → `~/vllm_watchdog.sh`.
- 동작: healthy면 15s 점검 / unhealthy면 정리(`pkill vllm_env/bin/python`)→포트해제 대기→재기동→grace 120s.
- **반드시 `setsid`로 완전분리 기동** (SSH 세션 종료 시 프론트엔드 사망 방지).
- **검증**: vLLM 강제 kill → **~60초 자동복구**, 단일 클린 사이클, 포트충돌 0회.

### 6.3 디버깅 중 잡은 함정 3종
1. **pkill self-match** — `pkill -f "vllm.entrypoints"`가 그 문자열 든 SSH 셸까지 죽임 → 수동 명령은 `[v]llm.entrypoints` 브래킷 트릭.
2. **orphan 엔진 워커** — `vllm.entrypoints`만 죽이면 multiprocessing 워커(`python -c from multiprocessing.spawn...`, RSS~8GB)가 GPU 점유 → 다음 기동 `NVML INTERNAL ASSERT`/`Engine process failed`. `vllm_env/bin/python` 패턴으로 전부 정리.
3. **포트 미해제** — 재기동 시 `Address already in use` → 포트 해제 + 프로세스 종료 대기 필수.

---

## 7. 외부 시연 점검 (미해결)

- UI는 `https://175.45.205.106/`로 개방(nginx 0.0.0.0:443), 호스트 방화벽 없음(firewalld inactive).
- **핫스팟(106.101.11.9) 테스트 → 443/80/10022/5001 전 포트 차단** (일반 인터넷은 정상).
  → **Naver Cloud ACG가 소스 IP 화이트리스트로 제한** 확인. 기존 접속망 IP만 허용돼 있던 것.
- **의미**: 외부 기관이 자기 망에서 접속하려면 ACG에 그 공인 IP 허용 필요. 모바일/핫스팟 IP는 동적이라 매번 추가해야 함.
- **클라이언트 망은 LLM 동작에 무관** — vLLM/DB 경로는 전부 서버 측. UI(443)만 닿으면 어디서 접속하든 T2C 동일 작동.

### 시연 옵션
| 방식 | 매번 관리 | 보안 | 적합 |
|------|----------|------|------|
| IP 화이트리스트(현행) | 네트워크마다 추가 | 높음 | 고정 IP 기관 |
| `0.0.0.0/0` 임시 개방 + nginx Basic Auth | 불필요 | 중 | 떠돌이 시연 |
| 기관 고정 IP/CIDR 허용 | 기관당 1회 | 높음 | 고정 공인망 기관 |

> SSH(10022)는 어떤 경우에도 `0.0.0.0/0` 개방 금지(본인 IP만). DB는 내부망 전용이라 무관.

---

## 8. 미해결 / 다음 단계

1. **외부 시연 접근** — ACG에 시연 기관 IP 허용, 또는 `0.0.0.0/0` 개방 + **nginx Basic Auth**.
2. **docker IP 고정** — `172.19.0.1` 자동할당 의존 → compose `ccop_external`에 IPAM 고정(시연 중 네트워크 재생성 시 중단 방지).
3. **자체서명 인증서** — 외부 시연용 정식 인증서(도메인 필요) 검토.
4. **엘리스 부팅 자동기동** — 온디맨드 인스턴스라 재시작 시 watchdog 수동 재기동 필요(`setsid bash ~/vllm_watchdog.sh`). 상시 인스턴스 전환이 근본 해결.
5. **커밋된 시크릿 정리** — `deploy/DEPLOY_CSLEE.md` 평문 API키, git remote 평문 자격증명.
6. **(모델) v44 continue-learning** — 약점 카테고리 보강.

---

## 부록 A. vLLM 서빙 재현 (엘리스)

```bash
# (최초 1회) cu121 호환 설치
python3 -m venv ~/vllm_env
~/vllm_env/bin/pip install --upgrade pip
~/vllm_env/bin/pip install "vllm==0.6.3.post1"
~/vllm_env/bin/pip install "transformers==4.46.3"
# pyairports 스텁
mkdir -p ~/vllm_env/lib/python3.10/site-packages/pyairports
: > ~/vllm_env/lib/python3.10/site-packages/pyairports/__init__.py
echo "AIRPORT_LIST = []" > ~/vllm_env/lib/python3.10/site-packages/pyairports/airports.py

# serve_v42.sh
exec ~/vllm_env/bin/python -m vllm.entrypoints.openai.api_server \
  --model /home/elicer/models/qwen25-t2c-v42 --served-model-name qwen25-t2c-v42 \
  --host 0.0.0.0 --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.9 \
  --dtype auto --chat-template /home/elicer/models/qwen25-t2c-v42/chat_template.jinja

# watchdog 기동 (반드시 setsid)
setsid bash ~/vllm_watchdog.sh < /dev/null > /dev/null 2>&1 &
```

## 부록 B. skai2_vm 터널 systemd 유닛

```ini
# /etc/systemd/system/elice-vllm-tunnel.service
[Unit]
Description=SSH tunnel: skai2_vm -> Elice vLLM (bind 172.19.0.1:8000)
After=network-online.target docker.service
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=/usr/bin/ssh -N -L 172.19.0.1:8000:localhost:8000 -p 21866 -i /root/elice.pem -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -o BatchMode=yes -o ConnectTimeout=20 elicer@central-01.tcp.tunnel.elice.io
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 부록 C. 주요 호스트/경로

| 대상 | 접속 | 비고 |
|------|------|------|
| 운영 VM | `ssh -p 10022 root@175.45.205.106` | Rocky 9.6, `/root/ccop_test` |
| 엘리스 GPU | `ssh elice_police` | MIG 3g.40gb, `~/vllm_env`, `~/models/qwen25-t2c-v42` |
| GPU 학습 머신 | `ssh ai-kyw-dev@192.168.1.133` | 머지 모델 보관 |
| 원격 DB | `49.50.128.28:5333` | AgensGraph, DB=tccopdb |
| UI | `https://175.45.205.106/` | 자체서명 인증서, ACG 제한 |
