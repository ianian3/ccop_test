# CSLEE 통합 플랫폼 배포 가이드

## 1. 사전 준비 (CSLEE 서버에서)

```bash
# Docker + Docker Compose 설치 확인
docker --version          # 24.0+
docker compose version    # 2.20+

# 필요 포트 확인
netstat -tulpn | grep -E '80|443|5432'
```

## 2. 코드 복사

```bash
# CCOP 코드 서버에 복사
scp -r /Users/iankwon/test/coop_v1.0 cslee-server:/opt/ccop
ssh cslee-server
cd /opt/ccop
```

## 3. 환경 변수 설정

```bash
cp deploy/.env.cslee.template .env
vi .env   # 실제 값 입력:
           # DB_PASSWORD, SECRET_KEY, ADMIN_PASSWORD
           # OPENAI_API_KEY 또는 SLLM_ENDPOINT
           # CORS_ORIGINS=https://cslee-platform.internal
```

## 4. SSL 인증서 배치

```bash
mkdir -p deploy/ssl
# 자체서명 인증서 (테스트용):
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout deploy/ssl/key.pem \
  -out    deploy/ssl/cert.pem \
  -days   365 \
  -subj "/CN=ccop.cslee.internal"

# 운영용: 기관 발급 인증서를 deploy/ssl/ 에 배치
```

## 5. 배포 실행

```bash
# CSLEE 전용 컴포즈 파일로 실행
docker compose -f docker-compose.cslee.yml up -d

# 로그 확인
docker compose -f docker-compose.cslee.yml logs -f app
```

## 6. 헬스체크

```bash
curl https://ccop.cslee.internal/api/v1/health -k
# → {"status": "healthy", "version": "1.0.0"}
```

## 7. CSLEE 플랫폼에 API 키 등록

```
API Key: cslee-5d0afd2b2d12707c8196a2ea058ce1e65da20fc2
Tier:    enterprise
권한:    모든 엔드포인트 (*)
Rate:    500 req/min
```

---

## 기능별 통합 엔드포인트 요약

| 기능 | 엔드포인트 | 인증 | Timeout |
|------|-----------|------|---------|
| **Text2Cypher** | `POST /api/v1/text-to-cypher` | Bearer | 120s |
| **Agentic (LangGraph)** | `POST /api/v1/agentic-query` | Bearer | 180s |
| **1-mode 투영** | `POST /api/v1/network/project` | Bearer | 60s |
| **2-mode 통계** | `POST /api/v1/network/bipartite` | Bearer | 30s |
| **Cypher 직접실행** | `POST /api/v1/graph-query` | Bearer | 30s |
| **그래프 목록** | `GET /api/v1/graph/list` | Bearer | 10s |
| **헬스체크** | `GET /api/v1/health` | 없음 | 5s |

## Python SDK

```python
from sdk.cslee_integration import text_to_cypher, project_1mode

# 기능 1: 자연어 질문
result = text_to_cypher("피의자1 계좌 추적", "tccop_graph_v6")

# 기능 2: 공범 네트워크 투영
network = project_1mode("tccop_graph_v6", "vt_psn", "vt_bacnt", min_shared=2)
```

## 망분리 환경 (인터넷 없을 때)

`.env`에서:
```
# OPENAI_API_KEY 제거 또는 주석 처리
SLLM_ENDPOINT=http://cslee-llm-server.internal:8080/v1
SLLM_MODEL_NAME=<CSLEE-LLM-모델명>
```

`docker-compose.cslee.yml`에서 `sllm:` 서비스 주석 해제 (자체 GPU 서버 보유 시)
