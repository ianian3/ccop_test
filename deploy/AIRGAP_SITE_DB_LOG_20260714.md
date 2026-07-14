# 폐쇄망 현장 DB 선설치 작업일지 정리 (2026-07-14 접수)

> 고객사 측(DB 벤더 엔지니어)이 폐쇄망 VM에 **AgensGraph를 네이티브(베어메탈)로 선설치**한 작업일지를 접수·정리한 문서.
> **⚠️ 이 정보는 설치 계획을 변경한다** — DB 컨테이너 반입 불필요, 앱은 네이티브 DB에 접속. 반영 내역은 `AIRGAP_PREFLIGHT_20260714.md` §5 참조.
> 🔒 비밀번호는 본 문서에 기록하지 않는다(작업일지 원본 별도 보관). 기본 비밀번호 사용 중 → **즉시 변경 권고** (아래 보안 지적).

## 1. 접수 내용 (원본 작업일지 요약)

| 항목 | 값 |
|---|---|
| 고객사 | 경찰청 · 한림대 · CSLEE |
| 제품/등급 | AgensGraph **16.9** (Single) + AgensSQL |
| 설치 플랫폼 | **Rocky Linux 10.1** (서버 64 Core / 128 GB — 런북 대상 VM 사양과 일치) |
| Extensions | **(비어 있음 — 별도 확장 미설치)** |
| 접속 | `psql -U hlucyber -d postgres -p 5333` |
| 기동 | `pg_ctl start` (systemd 유닛 여부 미기재) |
| 계정 | 일반: `agens` / 슈퍼유저: `hlucyber` (비밀번호: 원본 참조) |
| 기본 DB | `agens` · CHARACTERSET UTF-8 · **PORT 5333** |
| 설치 경로 | `/home/hlucyber/agsgraph-16` |
| 데이터 경로 | `/data/agsdata` (WAL: `/agslog/agsgraph-16` → `/data/agsdata/pg_wal`) |
| Archive Mode | No |
| 메모리 튜닝 | shared_buffers **32GB** · work_mem 31,536kB · max_connections **1000** |

## 2. 설치 계획에 미치는 영향

| # | 변경 | 내용 |
|---|---|---|
| C1 | **DB 컨테이너 불필요** | 1차 번들에서 `agensgraph_2.13.2.tar` 제외 가능(용량↓). compose는 **네이티브 DB 접속 전용 파일**(`docker-compose.airgap.nativedb.yml`) 사용 |
| C2 | **앱 접속 정보 변경** | `DB_HOST=host.docker.internal`(host-gateway) · `DB_PORT=5333` · DB/계정은 §3 결정 필요 |
| C3 | **DB 복원 대상 변경** | pg_restore 를 컨테이너가 아닌 **네이티브 16.9**에 수행 |
| C4 | **기동 의존 변경** | 앱 기동 전 네이티브 DB 가동 확인(`pg_isready -p 5333`). DB 재기동 절차는 DBA(`pg_ctl`) 소관 |

## 3. 신규 확인·결정 필요 항목 (현장 전 필수)

| # | 항목 | 리스크 | 확인 방법 |
|---|---|---|---|
| V1 | **문법 호환** — 앱의 Cypher 실행 계층(`SET graph_path` + `cypher()` SQL 래핑)이 AgensGraph 16.9에서 동작하는가 | 高 — 전 기능 영향 | staging에서 AG16 계열로 앱 연동 스모크 테스트, 불가 시 현장 1차에서 최우선 검증 |
| V2 | **Extensions 공란** — 운영 스택이 쓰는 그래프 확장/카탈로그(`ag_graph` 등)와 `uuid-ossp`(init.sql)가 16.9 기본 제공인지, 별도 CREATE EXTENSION 필요한지 | 高 | 현장에서 `\dx`, `SELECT * FROM ag_graph` 계열 확인. 필요 시 DBA에 확장 설치 요청 |
| V3 | **덤프 호환** — 운영 덤프(AgensGraph 2.13/PG13 기반) → 16.9(PG16 기반) 복원 시 그래프 카탈로그 호환 여부 | 高 | staging에서 복원 리허설. 실패 시 **그래프 재적재 경로**(CSV/RDB→ETL 파이프라인, 앱 내장)로 전환 — 데이터 반입을 덤프 대신 원천 CSV로 준비하는 플랜 B |
| V4 | **DB·계정 정책** — 복원/운영 DB명(`agens` 재사용 vs `tccopdb` 신설), 앱 전용 계정(`ccop`) 신설 및 최소 권한 | 中 | DBA와 협의: `CREATE DATABASE tccopdb OWNER ccop;` 권장 (슈퍼유저 hlucyber 를 앱에 쓰지 말 것) |
| V5 | **방화벽/바인딩** — 컨테이너(app)→호스트 5333 접근 허용 (`listen_addresses`, `pg_hba.conf`에 docker 브리지 대역 허용) | 中 | DBA 협의: pg_hba에 `172.17.0.0/16`(또는 compose 브리지 대역) md5 추가 |

## 4. 🔒 보안 지적 (고객사 전달 권고)

1. **기본 비밀번호 사용 중** — 일반/슈퍼유저 모두 벤더 기본값으로 설정되어 있음. 폐쇄망이라도 **초기 접속 후 즉시 변경** 권고 (특히 슈퍼유저).
2. 앱 연결에는 슈퍼유저가 아닌 **최소 권한 앱 계정 신설** 권고 (V4).
3. Archive Mode=No — 운영 전환 시 백업 정책(주기 덤프 등) 별도 수립 필요 (`scripts/backup_db.sh` 이식 검토).
