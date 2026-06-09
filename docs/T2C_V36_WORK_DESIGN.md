# Text2Cypher SFT v2 작업 설계서 — 온톨로지 v3.6 기준

> **기준 온톨로지:** ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md (2026-04-24 확정)
> **이전 버전:** T2C_SFT_DEVELOPMENT_PLAN.md (v3.3 기준, t2c_v1 데이터셋)
> **목표 모델:** EXAONE-3.5-7.8B-Instruct (LoRA)
> **목표 데이터셋:** `t2c_v2` — 11,000개 (학습 9,900 / 검증 1,100)
> **작성일:** 2026-04-24

---

## 1. 현황 분석 — t2c_v1 (v3.3 기반)

### 1.1 기존 데이터셋 현황

| 항목 | 현황 |
|------|------|
| 총 샘플 수 | **4,132개** (QUERY 3,632 / GENERAL 300 / GUARD 200) |
| 파일 위치 | `data/t2c_v1_all_validated.json` |
| 학습/검증 | `data/t2c_v1_train.json` (3,632) / `data/t2c_v1_eval.json` (500) |
| 기준 온톨로지 | v3.3 (23노드, 구버전 엣지 목록) |
| 포맷 | ShareGPT (`from`/`value`, `intent` 필드 포함) |

### 1.2 QUERY 복잡도 분포 — 실측 (치명적 편향 발견)

| 복잡도 | 실측 수 | 실측 비율 | v2 목표 비율 | 상태 |
|--------|--------|---------|-----------|------|
| **단일 노드 (엣지 0개)** | **3,251** | **89.5%** | **~15%** | ❌ 심각한 과다 |
| 1-hop 관계 (엣지 1개) | 192 | 5.3% | ~45% | ❌ 절대 부족 |
| 체인/멀티홉 (엣지 2개+) | 189 | 5.2% | ~20% | ❌ 절대 부족 |
| 엣지 메타속성 조건 | 380 | 10.5% | ~10% | ✅ |
| 집계 쿼리 (COUNT/ORDER BY) | 13 | 0.4% | ~5% | ❌ 극단 부족 |
| 위협 속성 필터 | 62 | 1.7% | ~5% | ❌ 부족 |

> 단일 노드 쿼리가 89.5%로 관계 그래프 핵심 기능(1-hop 이상)이 거의 미학습 상태.
> 1-hop 이상 쿼리는 총 381개(10.5%)에 불과 — 근본적 재구성 필요.

### 1.3 엣지 커버리지 현황

| 엣지 | 샘플 수 | 상태 |
|------|--------|------|
| `has_account` | 134 | ✅ |
| `caller` | 74 | ✅ |
| `from_account` | 71 | ✅ |
| `to_account` | 69 | ✅ |
| `accessed_from` | 34 | ✅ |
| `accessed_to` | 34 | ✅ |
| `used_ip` | 31 | ✅ |
| `owns_phone` | 31 | ✅ |
| `contacted` | 30 | ❌ DEPRECATED → `caller`/`callee` 분리 |
| `transferred_to` | 29 | ✅ |
| `impersonates` | 15 | ❌ DEPRECATED → `used_for`/`targets` 사용 |
| `accessed` | 14 | ❌ DEPRECATED → `hosts` 방향 역전 |
| `suspect_in` | 14 | ✅ (극소) |
| `callee` | 10 | ✅ (극소) |
| `recorded_in` / `occurred_at` / `drives` / `member_of` | ≤3 | ⚠️ 극소 |
| `performed_by` | 2 | ❌ DEPRECATED → v3.4 제거 |
| **신규 엣지 15종** | **0** | ❌ 미커버 |

**수정 필요 샘플 요약**:
- DEPRECATED 엣지 포함: **61개** 삭제
- `eg_used_*` 방향 오류 (vt_petition 주체): **72개** 수정
- 단일 노드 과다: **1,751개** 제거 대상 (3,251 → 1,500)

---

## 2. v3.3 → v3.6 변경 갭 분석

### 2.1 엣지 상태 변화 전체

| 상태 | 엣지 | 처리 방향 |
|------|------|---------|
| **RENAMED** | `similar_to` → `related_case` | 기존 샘플 엣지명 교체 |
| **DEPRECATED** | `contacted` → `caller`/`callee` 분리 | 기존 샘플 삭제 후 재생성 |
| **DEPRECATED** | `accessed` → `hosts` (방향 역전) | 기존 샘플 삭제 후 재생성 |
| **DEPRECATED** | `hosted_at` → `hosts` | 삭제 |
| **DEPRECATED** | `performed_by` → v3.4 완전 제거 | 기존 샘플 삭제 |
| **DEPRECATED** | `sent_via` → `sent_msg` | 기존 샘플 엣지명 교체 |
| **DEPRECATED** | `received_by` → `received_msg` | 기존 샘플 엣지명 교체 |
| **DEPRECATED** | `impersonates` → `used_for` + `targets` | 기존 샘플 삭제 후 재생성 |
| **DIRECTION FIX** | `eg_used_*`: `vt_petition→` → `vt_case→` | 기존 샘플 수정 |
| **NEW** | `related_case` (Case↔Case 유사성) | 신규 생성 |
| **NEW** | `owns_vehicle` (Person→Vehicle, 법적 소유) | 신규 생성 |
| **NEW** | `registered_to` (Phone→Person, 명의자 역추적) | 신규 생성 |
| **NEW** | `mentions_account` (Message→BankAccount) | 신규 생성 |
| **NEW** | `communicated_with` (IP→IP 직접 통신) | 신규 생성 |
| **NEW** | `operates` (Person/Org→Site/DigitalID) | 신규 생성 |
| **NEW** | `recruits` (Person→Person) | 신규 생성 |
| **NEW** | `blackmails` (Person→Person) | 신규 생성 |
| **NEW** | `hosts` (IP→Site, 방향 역전) | 신규 생성 |
| **NEW** | `contains_file` (Site/Msg/ID→File) | 신규 생성 |
| **NEW** | `located_at` (ATM/Device/Org→Location) | 신규 생성 |
| **NEW** | `owns` (Person→Any, 범용) | 신규 생성 |
| **NEW** | `sent_msg` (Phone/ID→Message) | 신규 생성 |
| **NEW** | `received_msg` (Message→Phone) | 신규 생성 |
| **NEW** | `owns_device` | 신규 생성 (t2c_v1 미포함) |
| **NEW** | `member_of` / `works_at` | 보강 생성 (t2c_v1 저커버) |
| **NEW** | `sourced_from` (tier 기반 조회 쿼리) | 신규 생성 |

### 2.2 eg_used_* 방향 오류 현황

```
# v3.3 (잘못된 방향 — t2c_v1에 포함)
(pt:vt_petition)-[:eg_used_account]->(b:vt_bacnt)  ← petition이 주체

# v3.6 (올바른 방향)
(c:vt_case)-[:eg_used_account]->(b:vt_bacnt)        ← case가 주체
(c:vt_case)-[:eg_used_phone]->(t:vt_telno)
(c:vt_case)-[:eg_used_ip]->(i:vt_ip)
```

---

## 3. 데이터셋 목표 구성 — t2c_v2 (11,000개)

### 3.1 전체 분포

```
인텐트/복잡도               v1 실측   v2 목표   증감
────────────────────────────────────────────────────────────────
QUERY 소계                  3,632     9,500   +5,868
  └ 단일 노드 (엣지 0)       3,251     1,500   -1,751  (과다 → 정리)
  └ 1-hop 관계  (엣지 1)       192     4,500   +4,308  (핵심 확충)
  └ 체인/멀티홉 (엣지 2+)      189     2,000   +1,811
  └ 엣지 메타속성 조건          380     1,000     +620
  └ 집계 (COUNT/ORDER BY)       13       500     +487
  └ 위협 속성 필터              62       500     +438
  └ 비율: QUERY/GENERAL/GUARD  (87.9%)        (86.4%)
────────────────────────────────────────────────────────────────
GENERAL 거부                  300       500     +200
GUARD (보안 가드레일)          200       500     +300  (쓰기명령/주입 강화)
────────────────────────────────────────────────────────────────
합계                         4,132    11,000   +6,868
────────────────────────────────────────────────────────────────
train (90%)                  3,632     9,900
eval  (10%, 층화 추출)          500     1,100
```

**복잡도 목표 비율 (QUERY 9,500개 기준)**:
```
단일 노드   1,500  15.8%
1-hop      4,500  47.4%  ← 핵심
체인       2,000  21.1%
메타조건   1,000  10.5%
집계         500   5.3%
────────────────────────
합계       9,500  100%
```

### 3.2 기존 샘플 정제 처리 (Step 0)

```python
# 처리 우선순위 (00_patch_v1_dataset.py)

Step 0-A: RENAME 처리 (Cypher 본문 regex 교체 — 자동)
  - similar_to   → related_case          (0개 — v1에 없었으나 혹시 대비)
  - sent_via     → sent_msg
  - received_by  → received_msg

Step 0-B: DIRECTION FIX (vt_petition → vt_case 교체 — 자동, 72개)
  - eg_used_account / eg_used_phone / eg_used_ip 포함 샘플
  - Cypher: (pt:vt_petition … )-[:eg_used_*] → (c:vt_case … )-[:eg_used_*]
  - 스키마 스니펫도 함께 수정

Step 0-C: DEPRECATED 삭제 (61개)
  - contacted(30), impersonates(15), accessed(14), performed_by(2)
  - 해당 샘플 전체 삭제 (재생성은 Step 1에서 새 패턴으로)

Step 0-D: 단일 노드 과다 정리 (1,751개 랜덤 제거)
  - 단일 노드 QUERY 3,251개 중 1,500개만 유지
  - 속성 필터 포함(위협 속성 등) 샘플 우선 보존
  - 랜덤 시드 고정(seed=42)으로 재현 가능하게

# Step 0 결과 예상
  원본  4,132
  - DEPRECATED       -61
  - eg_used_* 수정   (72개 유지, Cypher만 교체)
  - 단일노드 정리  -1,751
  ──────────────────
  정제 결과  ~2,300개 (이 중 1,500개가 단일 노드, 800개가 관계 쿼리)
```

### 3.3 신규 샘플 생성 계획 (Step 1~3 — 8,700개)

#### 신규 생성 총량 배분 (Step 0 정제 ~2,300 + 신규 ~8,700 = 11,000)

```
Step 1 — 템플릿 기반 생성    4,500개
Step 2 — LLM 표현 다양화    2,200개  (Step 1 결과 대상, GPT-4o-mini)
Step 3 — 수동/고급 추가     2,000개  (멀티홉·집계·가드레일)
────────────────────────────────
신규 소계                   8,700개
────────────────────────────────
Step 0 정제 보존            ~2,300개
────────────────────────────────
병합 후 중복제거 목표       11,000개
```

#### 1-hop 엣지별 목표 샘플 (Step 1 핵심, 총 4,500개 중 ~3,500개)

| 엣지 | 방향 | 목표 | 질문 유형 |
|------|------|-----|---------|
| `has_account` | Person→Account | 200 | 명의 계좌, 소유 계좌 (기존 134 → 보강) |
| `owns_phone` | Person→Phone | 150 | 전화 소유자, 번호 역조회 |
| `suspect_in` | Person→Case | 200 | 피의자 목록, 사건별 피의자 |
| `victim_in` | Person→Case | 150 | 피해자, 피해 사건 |
| `witness_in` | Person→Case | 80 | 참고인 |
| `caller` / `callee` | Phone↔Call | 200 | 발신/수신 통화 기록 |
| `from_account` / `to_account` | Account↔Transfer | 200 | 출금/입금 이체 |
| `accessed_from` / `accessed_to` | Access↔IP/Site | 150 | 접속 출발·목적지 |
| `transferred_to` | Account→Account | 100 | 계좌 간 이체 집계 |
| `used_ip` | Person→IP | 100 | IP 사용 이력 |
| `member_of` | Person→Org | 150 | 조직 소속, 범죄단체 |
| `works_at` | Person→Org | 100 | 합법기관 재직 |
| `accomplice_of` | Person↔Person | 150 | 공범 관계 |
| `sameAs` | Person↔Person | 100 | 동일인물, 별명 |
| `drives` | Person→Vehicle | 100 | 운전자, LPR 기반 |
| `filed_as` | Petition→Case | 100 | 진정서→사건 전환 |
| `used_for` + `targets` | Object→Impersonation→Org | 120 | 사칭 수단 |
| `eg_used_*` | Case→Object | 150 | 사건 관련 증거 계좌/전화/IP |
| `recorded_in` | Vehicle/Phone→Movement | 80 | LPR·기지국 이동 |
| `occurred_at` | Event→Location | 80 | 이체·통화 발생 위치 |
| `belongs_to` | Account→Org | 60 | 계좌 소속 금융기관 |
| `linked_to` | Petition→Case | 60 | 진정서 기존 사건 연결 |
| **신규 엣지 15종 (§4 상세)** | | **1,370** | 아래 §4 참조 |
| **합계 (1-hop)** | | **3,500** | |

#### 체인/멀티홉 (Step 1~3, 총 2,000개)

| 체인 유형 | 목표 | 예시 패턴 |
|---------|-----|---------|
| 1.5-hop (노드 3개) | 1,000 | 인물→계좌→이체, 전화→통화→전화, IP→접속→사이트 |
| 2-hop (노드 4개) | 500 | 인물→계좌→이체→계좌, 총책→모집→조직원→계좌 |
| 신규 엣지 포함 체인 | 400 | IP→hosts→사이트→contains_file→파일 등 |
| sourced_from 포함 | 100 | 사건→출처 신뢰도 필터 + 관계 조회 |

#### 집계/역방향/고급 (Step 3, 총 500개)

| 유형 | 목표 | 예시 |
|------|-----|------|
| COUNT + GROUP BY | 150 | 사건별 피의자 수, 엣지 타입별 수 |
| ORDER BY LIMIT | 150 | 피해금액 TOP 10 사건, 최근 이체 순 |
| 역방향 탐색 | 100 | (b)<-[:has_account]-(p) 패턴 |
| 조건 복합 | 100 | WHERE 다중 조건 AND/OR |

#### 신규 엣지 15종 상세 목표

| 엣지 | 목표 | 비고 |
|------|-----|------|
| `related_case` | 120 | 공유증거 기반 유사사건 |
| `owns_vehicle` | 100 | 등록원부 소유 (drives와 구분) |
| `registered_to` | 100 | Phone→Person 역방향 명의자 |
| `mentions_account` | 150 | 보이스피싱 핵심, confidence 조건 |
| `communicated_with` | 80 | IP↔IP C2 통신 |
| `operates` | 150 | 사이트/디지털ID 운영자 |
| `recruits` | 120 | 조직 모집 체인 |
| `blackmails` | 100 | 협박·몸캠피싱 |
| `hosts` | 120 | IP→Site 인프라 역추적 |
| `contains_file` | 100 | 악성파일 배포 경로 |
| `located_at` | 100 | ATM/기기/기관 위치 |
| `owns` | 80 | 범용 소유 (구체적 엣지 없을 때) |
| `sent_msg` | 120 | 메시지 발신 |
| `received_msg` | 80 | 메시지 수신 |
| `sourced_from` | 200 | tier 기반 출처 필터 조회 |
| **합계** | **1,620** | (1-hop 1,370 + 체인 포함 250) |

---

## 4. 신규 엣지 질문 템플릿 — 상세

### 4.1 `related_case` (Case↔Case)

```
질문 템플릿:
  "사건 {flnm}과 유사한 사건", "동일 증거(계좌/전화)가 나온 다른 사건",
  "{flnm}과 연결된 관련 사건 목록", "공유 증거 기반 유사 사건"

Cypher 패턴:
  MATCH (c1:vt_case {flnm: '{flnm}'})-[r:related_case]-(c2:vt_case)
  RETURN c1, r, c2

  MATCH (c1:vt_case)-[r:related_case]->(c2:vt_case)
  WHERE toFloat(r->>'confidence') >= 0.75
  RETURN c1, r, c2
```

### 4.2 `owns_vehicle` vs `drives` (의미 구분)

```
질문 템플릿:
  owns_vehicle: "{name}이 법적으로 소유한 차량", "차량등록원부 기준 소유자",
                "차량 {vhclno}의 법적 소유주"
  drives:       "{name}이 운전한 차량 (LPR 기반)", "번호판 인식에서 발견된 차량"

Cypher 패턴:
  # 소유
  MATCH (p:vt_psn {name: '{name}'})-[r:owns_vehicle]->(v:vt_vhcl) RETURN p, r, v

  # 운행
  MATCH (p:vt_psn {name: '{name}'})-[r:drives]->(v:vt_vhcl) RETURN p, r, v

  # 소유자 역방향 조회
  MATCH (v:vt_vhcl {vhclno: '{vhclno}'})<-[r:owns_vehicle]-(p:vt_psn) RETURN v, r, p
```

### 4.3 `registered_to` (Phone→Person, 역방향)

```
질문 템플릿:
  "{telno}의 명의자", "전화번호 {telno}가 등록된 사람",
  "가입자 명의로 등록된 전화번호", "{name} 명의 전화번호 역방향 조회"

Cypher 패턴:
  MATCH (t:vt_telno {telno: '{telno}'})-[r:registered_to]->(p:vt_psn) RETURN t, r, p
  MATCH (p:vt_psn {name: '{name}'})<-[r:registered_to]-(t:vt_telno) RETURN t, r, p
```

### 4.4 `mentions_account` (Message→BankAccount, 보이스피싱 핵심)

```
질문 템플릿:
  "계좌번호 {account_no}가 언급된 문자", "보이스피싱 문자에서 계좌번호 추출",
  "{telno}로 온 메시지 중 계좌 언급", "계좌 언급 의심 메시지 필터"

Cypher 패턴:
  MATCH (m:vt_msg)-[r:mentions_account]->(b:vt_bacnt {account_no: '{actno}'})
  RETURN m, r, b

  MATCH (m:vt_msg)-[r:mentions_account]->(b:vt_bacnt)
  WHERE toFloat(r->>'confidence') >= 0.85
  RETURN m, r, b
```

### 4.5 `operates` (Person/Org→Site/DigitalID)

```
질문 템플릿:
  "{name}이 운영하는 웹사이트", "{org_name}이 관리하는 카카오 채널",
  "피의자 {name}의 플랫폼 계정", "사기 사이트 운영자"

Cypher 패턴:
  MATCH (p:vt_psn {name: '{name}'})-[r:operates]->(s:vt_site) RETURN p, r, s
  MATCH (o:vt_org)-[r:operates]->(i:vt_id) RETURN o, r, i
  MATCH (s:vt_site {url_addr: '{url}'})<-[r:operates]-(p:vt_psn) RETURN s, r, p
```

### 4.6 `recruits` / `blackmails` (Person→Person)

```
질문 템플릿:
  recruits:   "{name}이 모집한 조직원", "모집책 역할을 한 인물",
              "보이스피싱 말단 모집 경로", "조직 계층 모집 체인"
  blackmails: "{name}이 협박한 피해자", "몸캠피싱 협박 가해자",
              "협박 증거와 가해자 연결"

Cypher 패턴:
  MATCH (boss:vt_psn {name: '{name}'})-[r:recruits]->(member:vt_psn) RETURN boss, r, member
  MATCH (p:vt_psn {name: '{name}'})-[r:blackmails]->(victim:vt_psn) RETURN p, r, victim
```

### 4.7 `hosts` (IP→Site)

```
질문 템플릿:
  "IP {ip_addr}에 호스팅된 사이트", "피싱 사이트의 서버 IP",
  "악성 사이트가 올라간 서버", "{url}의 호스팅 인프라"

Cypher 패턴:
  MATCH (ip:vt_ip {ip_addr: '{ip}'})-[r:hosts]->(s:vt_site) RETURN ip, r, s
  MATCH (s:vt_site {url_addr: '{url}'})<-[r:hosts]-(ip:vt_ip) RETURN s, r, ip

  -- 악성 사이트 호스팅 IP 역추적
  MATCH (ip:vt_ip)-[r:hosts]->(s:vt_site)
  WHERE s->>'is_malicious' = 'true'
  RETURN ip, r, s
```

### 4.8 `contains_file` (Site/Msg/ID→File)

```
질문 템플릿:
  "사이트 {url}에 있는 악성 파일", "메시지 첨부 파일 조회",
  "해시 {hash_val} 파일이 포함된 사이트", "악성 파일 배포 경로"

Cypher 패턴:
  MATCH (s:vt_site {url_addr: '{url}'})-[r:contains_file]->(f:vt_file) RETURN s, r, f
  MATCH (m:vt_msg)-[r:contains_file]->(f:vt_file) WHERE f->>'is_malicious' = 'true' RETURN m, r, f
```

### 4.9 `located_at` (ATM/Device/Org→Location)

```
질문 템플릿:
  "ATM {atm_id}의 설치 위치", "기기 {device_id}가 있는 위치",
  "특정 좌표 반경의 ATM", "은행 {org_name}의 주소"

Cypher 패턴:
  MATCH (a:vt_atm {atm_id: '{atm_id}'})-[r:located_at]->(loc:vt_loc) RETURN a, r, loc
  MATCH (d:vt_dev {device_id: '{dev_id}'})-[r:located_at]->(loc:vt_loc) RETURN d, r, loc
```

### 4.10 `sourced_from` (Provenance 조회)

```
질문 템플릿:
  "공식 수사자료에서 수집된 계좌", "KICS 기관연계 데이터만 조회",
  "tier 1~2 신뢰 출처의 인물 정보", "출처별 데이터 현황"

Cypher 패턴:
  -- Tier 1 출처 계좌만 조회
  MATCH (b:vt_bacnt)-[:sourced_from]->(s:vt_src)
  WHERE toInteger(s->>'reliability_tier') <= 2
  RETURN b, s

  -- 출처별 노드 수 집계
  MATCH (n)-[:sourced_from]->(s:vt_src)
  RETURN labels(n)[0] AS node_type, s.src_name, count(*) AS cnt
  ORDER BY cnt DESC

  -- OSINT 제외하고 피의자 조회
  MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case)-[:sourced_from]->(s:vt_src)
  WHERE toInteger(s->>'reliability_tier') <= 3
  RETURN p, c, s
```

---

## 5. 멀티홉 체인 쿼리 (v3.6 신규 엣지 포함)

### 5.1 핵심 수사 시나리오 체인 (500개)

```cypher
-- [보이스피싱] 사칭 체인: 전화 → 사칭이벤트 → 피해기관
MATCH (t:vt_telno)-[:used_for]->(i:vt_impersonation)-[:targets]->(o:vt_org)
WHERE t->>'is_burner' = 'true'
RETURN t, i, o

-- [자금세탁] 인물 → 계좌 → 이체 → 계좌 (2hop)
MATCH (p:vt_psn {name:'{name}'})-[:has_account]->(b1:vt_bacnt)
      -[:from_account]->(tr:vt_transfer)-[:to_account]->(b2:vt_bacnt)
RETURN p, b1, tr, b2

-- [조직망] 모집 체인: 총책 → 모집책 → 말단
MATCH path = (boss:vt_psn)-[:recruits*2..3]->(foot:vt_psn)
RETURN path

-- [인프라 추적] IP → 사이트 → 파일
MATCH (ip:vt_ip)-[:hosts]->(s:vt_site)-[:contains_file]->(f:vt_file)
WHERE f->>'is_malicious' = 'true'
RETURN ip, s, f

-- [이동 추적] 차량 → 이동이벤트 → 위치
MATCH (v:vt_vhcl {vhclno:'{vhclno}'})-[:recorded_in]->(m:vt_movement)-[:occurred_at]->(loc:vt_loc)
RETURN v, m, loc

-- [동일인물] sameAs 통합 뷰
MATCH (p:vt_psn {name:'{name}'})-[:sameAs*1..2]-(same:vt_psn)
WITH collect(p) + collect(same) AS all_psn
UNWIND all_psn AS person
MATCH (person)-[r:has_account|owns_phone|used_ip]-(obj)
RETURN person.name, type(r), obj

-- [출처 신뢰도 필터] 검증 데이터만 공범 분석
MATCH (p1:vt_psn)-[r:accomplice_of]-(p2:vt_psn)
WHERE r->>'confidence' >= '0.75'
  AND EXISTS {
    MATCH (p1)-[:suspect_in]->(:vt_case)-[:sourced_from]->(s:vt_src)
    WHERE toInteger(s->>'reliability_tier') <= 2
  }
RETURN p1, r, p2
```

---

## 6. 스키마 스니펫 업데이트 — v3.6 기준

### 6.1 신규 노드 스니펫 (추가)

```
# vt_msg (보강)
(vt_msg {msg_id, msg_type, app_nm, dsptch_dt, content_hash, spam_yn,
          mentions_account, mentions_url, sentiment_cd})

# vt_impersonation (기존 유지, 연결 방식 명확화)
(vt_impersonation {event_id, method, fake_name, script_type, start_dt})

# vt_src (출처 조회 쿼리용)
(vt_src {src_id, src_name, src_type, reliability_tier})
```

### 6.2 신규 엣지 스니펫 (추가)

```
관계 (v3.6 신규):
  (vt_case)-[:related_case {confidence, inference}]->(vt_case)
  (vt_psn)-[:owns_vehicle {valid_from, valid_to}]->(vt_vhcl)
  (vt_telno)-[:registered_to]->(vt_psn)
  (vt_msg)-[:mentions_account {confidence}]->(vt_bacnt)
  (vt_ip)-[:communicated_with]->(vt_ip)
  (vt_psn)-[:operates {valid_from, role}]->(vt_site)
  (vt_org)-[:operates]->(vt_id)
  (vt_psn)-[:recruits {recruit_type, date}]->(vt_psn)
  (vt_psn)-[:blackmails {method, date}]->(vt_psn)
  (vt_ip)-[:hosts {port, detected_at}]->(vt_site)
  (vt_site)-[:contains_file {file_role}]->(vt_file)
  (vt_msg)-[:contains_file]->(vt_file)
  (vt_atm)-[:located_at]->(vt_loc)
  (vt_dev)-[:located_at]->(vt_loc)
  (vt_psn)-[:sent_msg]->(vt_msg)
  (vt_msg)-[:received_msg]->(vt_telno)
  (Any)-[:sourced_from {src_tier, rec_created}]->(vt_src)

관계 (방향 수정):
  (vt_case)-[:eg_used_account]->(vt_bacnt)   ← vt_petition이 아닌 vt_case
  (vt_case)-[:eg_used_phone]->(vt_telno)
  (vt_case)-[:eg_used_ip]->(vt_ip)
```

### 6.3 AgensGraph 속성 접근 문법 (모든 샘플 필수)

```sql
-- 표준 SQL Wrapper 래핑
SELECT * FROM cypher('tccop_graph', $$
  [Cypher 쿼리 본문]
$$) AS ([컬럼명] agtype [, ...]);

-- 속성 접근 문법
WHERE n->>'속성명' = '문자열값'       -- 문자열 비교
WHERE toInteger(n->>'속성명') >= 숫자  -- 정수 비교
WHERE toFloat(n->>'속성명') >= 0.7    -- 부동소수점 비교
WHERE n->>'boolean속성' = 'true'      -- boolean 비교

-- RETURN 수 = AS 컬럼 수 (필수)
RETURN p, r, b  →  AS (p agtype, r agtype, b agtype)
```

---

## 7. 생성 파이프라인

### 7.1 파일 구조

```
coop_v1.0/
├── scripts/
│   ├── t2c_v2/
│   │   ├── 00_patch_v1_dataset.py      # Step 0: 기존 t2c_v1 정제
│   │   ├── 01_generate_templates.py    # Step 1: 템플릿 기반 생성
│   │   ├── 02_augment_llm.py           # Step 2: GPT-4o-mini 표현 다양화
│   │   ├── 03_add_manual.py            # Step 3: 수동/고급 쿼리 추가
│   │   ├── 04_validate.py              # Step 4: 자동 품질 검증
│   │   └── 05_merge_split.py           # Step 5: 병합 + 분할
│
├── data/
│   ├── t2c_v1_patched.json             # Step 0 결과 (~4,000개)
│   ├── t2c_v2_templates.json           # Step 1 결과 (~4,000개)
│   ├── t2c_v2_augmented.json           # Step 2 결과 (~5,000개)
│   ├── t2c_v2_all.json                 # 병합 (중복 제거 전)
│   ├── t2c_v2_sharegpt.json            # 최종 10,000개
│   ├── t2c_v2_train.json               # 9,500개
│   └── t2c_v2_eval.json                # 500개
│
└── train/
    ├── train_t2c_lora_v2.yaml          # v2 학습 설정
    └── dataset_info.json               # t2c_v2 등록 추가
```

### 7.2 Step 0 — 기존 데이터 정제 (`00_patch_v1_dataset.py`)

```python
# 자동 처리 규칙
RENAME_MAP = {
    'similar_to':   'related_case',
    'sent_via':     'sent_msg',
    'received_by':  'received_msg',
}

# 삭제 대상 (61개 — 재생성)
DELETE_EDGES = ['contacted', 'impersonates', 'accessed', 'performed_by']

# eg_used_* 방향 수정
# vt_petition.petition_id → vt_case.flnm
EG_USED_FIX = True

# 검증 항목
VALID_LABELS = [
    'vt_src', 'vt_case', 'vt_petition', 'vt_psn', 'vt_org',
    'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_site', 'vt_file',
    'vt_id', 'vt_vhcl', 'vt_email', 'vt_crypto', 'vt_dev',
    'vt_atm', 'vt_loc', 'vt_transfer', 'vt_call', 'vt_msg',
    'vt_access', 'vt_movement', 'vt_impersonation'
]

VALID_EDGES = [
    # Case
    'suspect_in', 'victim_in', 'witness_in', 'filed_as',
    'related_case', 'linked_to', 'clusters_with',
    # Case→Object
    'eg_used_account', 'eg_used_phone', 'eg_used_ip',
    # Person
    'has_account', 'controls', 'owns_phone', 'owns_device',
    'uses_id', 'uses_email', 'drives', 'owns_vehicle', 'used_ip',
    'member_of', 'works_at', 'accomplice_of', 'sameAs', 'contradicts', 'owns',
    # Person v3.4
    'operates', 'recruits', 'blackmails',
    # Object→Person
    'registered_to',
    # Object
    'transferred_to', 'resolves_to', 'linked_to', 'belongs_to',
    'hosts', 'contains_file', 'located_at', 'communicated_with', 'mentions_account',
    # Event
    'from_account', 'to_account', 'caller', 'callee',
    'accessed_from', 'accessed_to', 'sent_msg', 'received_msg',
    'occurred_at', 'recorded_in',
    # 사칭
    'used_for', 'targets',
    # Meta
    'sourced_from', 'verified_by',
]
```

### 7.3 Step 4 — 자동 품질 검증 (`04_validate.py`)

```python
# 검증 항목
def validate(sample: dict) -> list[str]:
    errors = []
    cypher = get_cypher(sample)

    # 1. SQL Wrapper 구조 확인
    if 'SELECT * FROM cypher(' not in cypher:
        errors.append('SQL_WRAPPER_MISSING')

    # 2. RETURN 수 = AS 컬럼 수
    returns = count_return_items(cypher)
    as_cols = count_as_columns(cypher)
    if returns != as_cols:
        errors.append(f'RETURN_AS_MISMATCH: {returns} vs {as_cols}')

    # 3. 유효 레이블 사용
    labels = extract_labels(cypher)
    invalid = [l for l in labels if l not in VALID_LABELS]
    if invalid:
        errors.append(f'INVALID_LABEL: {invalid}')

    # 4. 유효 엣지 사용
    edges = extract_edges(cypher)
    invalid_e = [e for e in edges if e not in VALID_EDGES]
    if invalid_e:
        errors.append(f'INVALID_EDGE: {invalid_e}')

    # 5. 쓰기 명령 없음
    write_cmds = ['CREATE', 'MERGE', 'DELETE', 'SET', 'REMOVE']
    for cmd in write_cmds:
        if f'\n  {cmd} ' in cypher or f'\n{cmd} ' in cypher:
            errors.append(f'WRITE_CMD: {cmd}')

    # 6. DEPRECATED 엣지 없음
    deprecated = ['similar_to', 'contacted', 'accessed', 'hosted_at',
                  'performed_by', 'sent_via', 'received_by', 'impersonates']
    for e in deprecated:
        if f':{e}' in cypher:
            errors.append(f'DEPRECATED_EDGE: {e}')

    return errors
```

---

## 8. 학습 설정 — `train_t2c_lora_v2.yaml`

```yaml
### CCOP Text2Cypher v2 SFT — EXAONE-3.5-7.8B LoRA
### 학습 데이터: t2c_v2 (10,000개, 학습 9,500 / 검증 500)
### 기준: ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md (23노드, 52종 엣지)

model_name_or_path: LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct
trust_remote_code: true

stage: sft
do_train: true
finetuning_type: lora

lora_rank: 32
lora_alpha: 64
lora_dropout: 0.05
lora_target: q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj

dataset: t2c_v2
dataset_dir: /home/ai-kyw-dev/ccop_train/train
template: exaone

# v3.6: 멀티홉 체인 + sourced_from 조인 쿼리 → 컨텍스트 확장
cutoff_len: 1536            # v1(1280) → 1536 (복잡 체인 커버)
overwrite_cache: true
preprocessing_num_workers: 4

output_dir: /home/ai-kyw-dev/ccop_train/train/output/exaone_t2c_v2
per_device_train_batch_size: 4
gradient_accumulation_steps: 4    # 유효 배치: 16
num_train_epochs: 3
learning_rate: 2.0e-4
lr_scheduler_type: cosine
warmup_ratio: 0.05
weight_decay: 0.01

bf16: true
quantization_bit: 4
optim: adamw_torch_fused

save_strategy: epoch
save_total_limit: 3
val_size: 0.05
eval_strategy: epoch
logging_steps: 50
report_to: tensorboard
```

---

## 9. 벤치마크 업데이트 — `benchmark_t2c_v2.py` (150문항)

| 카테고리 | v1 문항 | v2 문항 | 신규 추가 이유 |
|---------|--------|--------|------------|
| 단일 노드 조회 | 10 | 12 | vt_msg, vt_src 추가 |
| 1-hop CASE | 15 | 15 | 유지 |
| 1-hop PERSON→OBJECT | 20 | 25 | owns_vehicle, registered_to, operates |
| 1-hop PERSON↔PERSON | — | 10 | recruits, blackmails, accomplice_of |
| 1-hop EVENT | 15 | 15 | sent_msg, received_msg, mentions_account |
| 1-hop OBJECT | — | 10 | hosts, contains_file, located_at |
| 엣지 메타 조건 | 10 | 15 | sourced_from tier 조건 포함 |
| 위협 속성 필터 | 10 | 12 | communicated_with, mentions_account 추가 |
| 1.5-hop 체인 | 10 | 15 | 신규 엣지 포함 체인 |
| GENERAL 거부 | 5 | 5 | 유지 |
| 보안 가드레일 | 5 | 8 | 쓰기 명령 가드레일 강화 |
| **합계** | **100** | **142** | |

### 성능 목표

| 지표 | t2c_v1 목표 | t2c_v2 목표 |
|------|-----------|-----------|
| 실행 성공률 | 75%↑ | **85%↑** |
| 1차 생성 성공률 | 60%↑ | **72%↑** |
| 신규 엣지 정확도 | — | **65%↑** |
| 응답 속도 (p50) | <1s | <1s |

---

## 10. 실행 체크리스트

```
Phase 0 — 기존 데이터 정제 (0.5일)
  [ ] scripts/t2c_v2/00_patch_v1_dataset.py 작성 + 실행
      - RENAME: similar_to→related_case, sent_via→sent_msg, received_by→received_msg
      - DELETE: contacted(30), impersonates(15), accessed(14), performed_by(2) = 61개
      - FIX: eg_used_* 방향 (vt_petition → vt_case)
      - 결과: data/t2c_v1_patched.json (~4,000개)

Phase 1 — 템플릿 기반 신규 생성 (1일)
  [ ] scripts/t2c_v2/01_generate_templates.py 작성 + 실행
      - §4 신규 엣지 14종 + 체인 500개 포함
      - SAMPLE_VALUES: 한국형 이름/계좌/사건번호/전화번호 풀 (각 50+개)
      - build_schema_snippet(): v3.6 스니펫 업데이트 반영
      - 결과: data/t2c_v2_templates.json (~4,000개)

Phase 2 — LLM 표현 다양화 (1일, 비용 $0.5~1.0)
  [ ] scripts/t2c_v2/02_augment_llm.py 작성 + 실행
      - GPT-4o-mini few-shot 다양화 (구어체/문어체/수사용어)
      - Phase 0 + Phase 1 결과 대상
      - 결과: data/t2c_v2_augmented.json (~2,000개 신규)

Phase 3 — 수동 제작 (1일)
  [ ] scripts/t2c_v2/03_add_manual.py 작성
      - sourced_from tier 조건 조회 (200개)
      - 멀티홉 복합 체인 (300개)
      - 집계 쿼리 (COUNT/ORDER BY/LIMIT) (200개)
  [ ] 고품질 수동 제작 샘플 직접 작성 (목표: 300개)

Phase 4 — 품질 검증 (0.5일)
  [ ] scripts/t2c_v2/04_validate.py 실행
      - SQL Wrapper 구조, RETURN=AS, 유효 레이블/엣지, DEPRECATED 없음
      - 합격률 목표: 95%+
      - 불합격 샘플 수동 수정 또는 삭제

Phase 5 — 병합 + 분할 (0.5일)
  [ ] scripts/t2c_v2/05_merge_split.py 실행
      - 중복 제거 (question 기준)
      - 균형 확인: QUERY/GENERAL/GUARD 비율
      - 결과: data/t2c_v2_sharegpt.json (10,000개)
      -        data/t2c_v2_train.json (9,500개)
      -        data/t2c_v2_eval.json (500개)
  [ ] train/dataset_info.json에 t2c_v2 등록

Phase 6 — 학습 (3~4일, 서버 작업)
  [ ] train/train_t2c_lora_v2.yaml 작성
  [ ] bash train/upload_to_server.sh (데이터 + yaml 업로드)
  [ ] llamafactory-cli train train/train_t2c_lora_v2.yaml
  [ ] 체크포인트별 eval_loss 모니터링

Phase 7 — 평가 (1일)
  [ ] scripts/merge_lora.py → 모델 병합
  [ ] vllm serve models/exaone_t2c_v2
  [ ] python benchmark_t2c_v2.py → 142문항 평가
  [ ] t2c_v1 기준선과 지표 비교

Phase 8 — 통합 (0.5일)
  [ ] .env: SLLM_ENDPOINT, SLLM_MODEL_NAME 설정
  [ ] CCOP 앱 연결 테스트 (LangGraph → sLLM)
  [ ] GPT-4o Fallback 분기 확인
  [ ] 프로덕션 배포
```

---

## 11. 리스크 및 완화 방안

| 리스크 | 가능성 | 완화 방안 |
|--------|--------|---------|
| 신규 엣지 14종 → 모델 과적합 | 중간 | 각 엣지 100개+ 샘플 확보, lora_rank 유지 |
| `registered_to` 역방향 혼동 | 높음 | 스키마 스니펫에 방향 화살표 명시 |
| `sourced_from` 복합 쿼리 컨텍스트 초과 | 중간 | cutoff_len 1536 설정, 스니펫 축소 |
| `owns_vehicle` vs `drives` 혼동 | 높음 | 질문 키워드 명확 분리 (등록원부/LPR) |
| eg_used_* 방향 오류 미수정 | 낮음 | Step 0 자동 패치 + 검증 스크립트 |
| GPT-4o-mini 증강 품질 저하 | 중간 | few-shot 5개 이상, 검증 통과율 모니터링 |

---

*이 문서는 T2C_SFT_DEVELOPMENT_PLAN.md (v3.3)를 v3.6 온톨로지 기준으로 업데이트한 실행 설계서입니다.*
*온톨로지 변경 시 §2(갭 분석)와 §4(템플릿) 우선 갱신 후 데이터 재생성.*
