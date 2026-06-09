> ## ⚠️ DEPRECATED — V4.0 통합본 사용 권장
>
> 이 문서는 **CCOP 온톨로지 V3.4** 명세입니다. **2026-05-21부로 V4.0으로 통합되어 deprecated** 되었습니다.
>
> **현행 SSOT**: [`docs/CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
> **코드 SSOT**: `app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`
>
> V4.0은 V3.7 카탈로그(25 노드 / 53 엣지)를 그대로 유지하면서, 도메인 사용 매트릭스 / 식별자 형식 / 추론 규칙을 표준 메타로 격상한 통합본입니다. 본 문서는 **역사적 참고용**으로만 보존됩니다.
>
> ---
>

# CCOP 온톨로지 v3.4 설계 문서

> 8대 사이버 범죄 시뮬레이션 기반 최적화 설계  
> 기준일: 2026-04-17  
> 이전 버전: v3.3 (55종 엣지) → v3.4 (45종 엣지)

---

## 1. 시뮬레이션 결과 요약

### 신규 후보 엣지 검증 결과

| 후보 엣지 | 커버 사건 수 | 해당 사건 | 판정 |
|-----------|------------|-----------|------|
| `operates` | **5/8** | 몸캠·투자사기·도박·마약·텔레그램 | ✅ **등재** |
| `recruits` | **4/8** | 투자사기·도박·대포통장·마약 | ✅ **등재** |
| `contains_file` | **2/8** | 몸캠·텔레그램 | ✅ **등재** (증거물 관계 핵심) |
| `hosts` | **2/8** | 투자사기·도박사이트 | ✅ **등재** (인프라 추적 필수) |
| `blackmails` | **1/8** | 몸캠피싱 | ✅ **등재** (협박 = 죄명 구성요건) |
| `located_at` | **0/8** | (시뮬레이션 미사용) | ✅ **등재** (ATM 위치 필수, 별도 확인) |

### 핵심 엣지 커버리지 (상위 5종)

| 엣지 | 커버 수 | 의미 |
|------|---------|------|
| `suspect_in` | 8/8 | 모든 사건의 피의자 연결 |
| `controls` | 6/8 | 대포통장 실질 지배 |
| `operates` | 5/8 | 플랫폼/채널 운영자 식별 |
| `owns` / `recruits` / `sent_msg` | 4/8 | 자산·모집·통신 |

---

## 2. v3.4 최적화 온톨로지 — 45종 엣지

### 제거 (16종): 중복·유령·반정규화

| 제거 엣지 | 이유 | 대체 |
|-----------|------|------|
| `impersonates` | V3.3에서 deprecated | `used_for` + `targets` |
| `involves` | deprecated | `suspect_in` / `victim_in` |
| `involves_device` | deprecated | `owns_device` |
| `involves_org` | deprecated | `works_at` / `member_of` |
| `accessed` | `accessed_from`과 중복 | `accessed_from` |
| `accessed_to` | `accessed_from`과 중복 | `accessed_from` |
| `performed` | `operates`/`recorded_in`으로 커버 | `operates` |
| `performed_by` | `performed` 역방향 중복 | — |
| `eg_used_account` | Case→Object 반정규화 | 추론 쿼리 |
| `eg_used_ip` | Case→Object 반정규화 | 추론 쿼리 |
| `eg_used_phone` | Case→Object 반정규화 | 추론 쿼리 |
| `communicated_with` | IP간 직접 연결, 실 수사 미사용 | `used_ip` + `accessed_from` |
| `same_organization` | `member_of`로 커버 | `member_of` |
| `contacted` | `caller`/`callee`로 커버 | `caller` / `callee` |
| `received_by` | `received_msg`와 중복 | `received_msg` |
| `shared_resource` | `related_case`로 커버 | `related_case` |

### 추가 (6종): 시뮬레이션 검증 완료

| 신규 엣지 | Domain → Range | 검증 사건 |
|-----------|---------------|----------|
| `operates` | Person/Org → Site/DigitalID | 몸캠·투자사기·도박·마약·텔레그램 |
| `recruits` | Person → Person | 투자사기·도박·대포통장·마약 |
| `blackmails` | Person → Person | 몸캠피싱·랜섬웨어 |
| `hosts` | NetworkTrace → WebTrace | 투자사기·도박사이트 |
| `contains_file` | WebTrace/Message/DigitalID → FileTrace | 몸캠·텔레그램 |
| `located_at` | ATM/Device/Org → Location | ATM위치·기기위치 |

---

## 3. v3.4 전체 엣지 카탈로그 (45종)

### Category 1 — 사건 연결 (6종)
```
suspect_in    Person → Case        피의자로 사건과 연결
victim_in     Person → Case        피해자로 사건과 연결
witness_in    Person → Case        참고인으로 사건과 연결
filed_as      Petition → Case      진정서 → 수사 사건 전환
clusters_with Petition → Petition  유사 진정서 군집
related_case  Case → Case          공유 증거 기반 사건 연계
```

### Category 2 — 신원/소유 (10종)
```
has_account   Person → BankAccount   계좌 명의 보유
controls      Person → BankAccount   계좌 실질 지배 (명의 무관)
owns_phone    Person → Phone         전화번호 보유
owns_device   Person → Device        기기 소유/사용
owns_vehicle  Person → Vehicle       차량 법적 소유
drives        Person → Vehicle       차량 실제 운행 (owns_vehicle과 구분)
owns          Person → Any           범용 소유 (crypto 등)
uses_id       Person → DigitalID     플랫폼 ID/닉네임 사용
uses_email    Person → Email         이메일 사용
registered_to Phone → Person         전화번호 등록 명의자 (역방향)
```

### Category 3 — 인물 관계 (7종)
```
member_of     Person → Organization  조직/채널 소속 (role: admin|member)
works_at      Person → Organization  합법적 소속 (수배자 파악 등)
accomplice_of Person → Person        공범 관계
recruits      Person → Person        ★NEW 모집 (대포통장·판매원·투자자 유인)
sameAs        Person → Person        동일 인물 해소 (엔티티 해소)
contradicts   Person → Person        정보 모순 (명의도용·계정탈취)
blackmails    Person → Person        ★NEW 협박 (몸캠·랜섬웨어)
```

### Category 4 — 운영/인프라 (6종)
```
operates      Person/Org → Site/DigitalID  ★NEW 플랫폼/채널/사이트 운영
hosts         NetworkTrace → WebTrace      ★NEW 서버 IP → 사이트 호스팅
resolves_to   WebTrace → NetworkTrace      도메인 → IP (DNS 조회)
contains_file Site/Msg/DigitalID → File    ★NEW 파일 내장/배포
located_at    ATM/Device/Org → Location    ★NEW 장치 고정 위치
belongs_to    BankAccount → Organization   계좌 소속 금융기관
```

### Category 5 — 자금 흐름 (3종)
```
from_account  BankAccount → Transfer       이체 출금 계좌
to_account    Transfer → BankAccount/Crypto 이체 입금 계좌/지갑
transferred_to BankAccount → BankAccount   다단계 세탁 추론 (직접생성 금지)
```

### Category 6 — 사칭 패턴 (2종)
```
used_for   Any → Impersonation            사칭 수단 (전화/이메일/ID)
targets    Impersonation → Person/Org     사칭 대상 (기관 또는 개인)
```

### Category 7 — 통신 (4종)
```
caller      Phone → Call               통화 발신
callee      Call → Phone               통화 수신
sent_msg    Phone/DigitalID → Message  메시지 발신
received_msg Message → Phone/Person   메시지 수신
```

### Category 8 — 디지털 접속 (3종)
```
used_ip       Device/Person → NetworkTrace  IP 사용
accessed_from Access → NetworkTrace         접속 이벤트 출발 IP
linked_to     Any → Any                     범용 연결 (최후 수단)
```

### Category 9 — 위치/이동 (3종)
```
recorded_in  Vehicle/Phone/Person → Movement  이동 이벤트 기록
occurred_at  Event → Location                 이벤트 발생 위치
mentions_account Message → BankAccount        메시지 내 계좌번호 언급
```

### Category 10 — 메타/출처 (1종)
```
sourced_from  Any → Source   데이터 출처 (vt_src 참조, 모든 노드 적용)
```

---

## 4. 8대 사건 유형별 커버리지 검증

| 엣지 | 몸캠 | 보이스피싱 | 사칭 | 투자사기 | 도박 | 대포통장 | 마약 | 텔레그램 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| suspect_in | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| controls | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | | |
| **operates** | ✅ | | | ✅ | ✅ | | ✅ | ✅ |
| **recruits** | | | | ✅ | ✅ | ✅ | ✅ | |
| **blackmails** | ✅ | | | | | | | |
| **contains_file** | ✅ | | | | | | | ✅ |
| **hosts** | | | | ✅ | ✅ | | | |
| **located_at** | | ✅ | | | ✅ | | ✅ | |
| used_for / targets | | ✅ | ✅ | | | | | |
| transferred_to | | | | | ✅ | ✅ | ✅ | |
| from/to_account | ✅ | ✅ | | ✅ | | | | |
| sent_msg | ✅ | | ✅ | | | | ✅ | ✅ |
| owns | | | | ✅ | ✅ | | ✅ | ✅ |
| recruits | | | | ✅ | ✅ | ✅ | ✅ | |

---

## 5. 설계 원칙 (v3.4)

### 원칙 1 — 수사 언어 1:1 대응
엣지 레이블은 수사관이 즉각 읽을 수 있어야 함
- `operates` → "이 사람이 이 사이트를 운영했다"
- `blackmails` → "이 사람이 저 사람을 협박했다"
- `recruits` → "이 사람이 저 사람을 모집했다"

### 원칙 2 — 3개 사건 이상 공통 → 반드시 등재
시뮬레이션에서 3개 이상 사건에 나타난 엣지는 온톨로지 1급 시민

### 원칙 3 — 중복 제거 기준
- 의미가 같고 방향만 다른 쌍 → 하나 제거
- 특수화가 범용으로 커버 가능 → 범용 사용
- 반정규화(Case→Object 직접 연결) → 추론 쿼리로 대체

### 원칙 4 — `linked_to` 사용 제한
마지막 수단으로만 사용. linked_to 사용 시 주석 필수:
```cypher
CREATE (a)-[:linked_to {reason:'현행 온톨로지 미분류', pending_edge:'TBD'}]->(b)
```

### 원칙 5 — 엣지 메타 속성 표준화
모든 엣지 공통 필수 속성:
```
source_id    : vt_src 참조 (데이터 출처)
rec_created  : ISO8601 (DB 기록 시점)
verified     : bool (수사관 확인 여부)
```

---

## 6. 마이그레이션 경로 (v3.3 → v3.4)

```
Step 1. 제거 16종 — DB elabel 삭제 (데이터 없는 경우)
         데이터 있는 경우 → linked_to로 이관 후 삭제

Step 2. 추가 6종 — CREATE ELABEL 등록
         operates / recruits / blackmails / hosts / contains_file / located_at

Step 3. 온톨로지 서비스 코드 업데이트
         app/middleware/services/ontology_service.py

Step 4. AI 프롬프트 업데이트
         app/services/ai_service.py — 신규 엣지 예시 추가

Step 5. Cytoscape 스타일 등록
         app/templates/index.html — 신규 엣지 색상/레이블 추가
```
