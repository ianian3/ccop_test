# Text2Cypher SFT 개발 계획서

> **기준 온톨로지:** ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md (2026-04-15 확정)
> **목표 모델:** EXAONE-3.5-7.8B-Instruct (LoRA 특화 학습)
> **목표 샘플:** 10,000개 (학습 9,500 / 검증 500)
> **작성일:** 2026-04-15

---

## 1. v3.3 스키마 기준 — 노드·엣지 전체 목록

### 1.1 노드 23개 (6레이어)

| 레이어 | 노드 | 핵심 식별 속성 | 주요 속성 |
|--------|------|--------------|---------|
| **SOURCE** | `vt_src` | `src_id` | src_name, src_type, reliability_tier |
| **CASE** | `vt_case` | `flnm` | incdnt_typ_cd, status, damage_amount, risk_level |
| **CASE** | `vt_petition` | `petition_id` | rcpt_dt, crime_type_cd, damage_amt, status |
| **PERSON** | `vt_psn` | `psn_id` / `name` | korn_flnm, dob, gender, rrno_hash, risk_level |
| **PERSON** | `vt_org` | `org_id` / `org_name` | org_category, inst_se_cd, bank_cd |
| **OBJECT** | `vt_bacnt` | `account_no` + `bank_cd` (복합) | bank_nm, dpstr_nm, is_burner, is_frozen |
| **OBJECT** | `vt_telno` | `telno` | telco_nm, join_typ_cd, is_burner, spam_cnt |
| **OBJECT** | `vt_ip` | `ip_addr` | is_vpn, is_tor, is_proxy, abuse_score |
| **OBJECT** | `vt_site` | `url_addr` | dmn_addr, site_type, is_malicious, risk_grd |
| **OBJECT** | `vt_file` | `hash_val` | file_nm, is_malicious, vt_score |
| **OBJECT** | `vt_id` | `id_val` | platform, id_type, is_active |
| **OBJECT** | `vt_vhcl` | `vhclno` | carmdl_nm, ownr_nm, stolen_yn |
| **OBJECT** | `vt_email` | `email_addr` | domain, provider, is_disposable |
| **OBJECT** | `vt_crypto` | `wallet_addr` | blockchain, exchange, risk_score, balance |
| **OBJECT** | `vt_dev` | `device_id` | dev_type, imei, mac_addr, os |
| **OBJECT** | `vt_atm` | `atm_id` | bank_nm, bank_cd, loc_id |
| **LOCATION** | `vt_loc` | `loc_id` | loc_type, address, lat, lng, bsst_nm |
| **EVENT** | `vt_transfer` | `transfer_id` | dlng_amt, dlng_dt, dlng_se_cd, hop_level, is_suspicious |
| **EVENT** | `vt_call` | `call_id` | call_strt_dt, call_dur_sec, call_typ_cd |
| **EVENT** | `vt_msg` | `msg_id` | msg_type, app_nm, spam_yn, sentiment_cd |
| **EVENT** | `vt_access` | `access_id` | access_dt, action, status_code |
| **EVENT** | `vt_movement` | `mov_id` | mov_type, timestamp, loc_id, vhclno/telno |
| **EVENT** | `vt_impersonation` | `event_id` | method, fake_name, script_type, start_dt |

### 1.2 엣지 완전 목록 (방향 포함)

```
# CASE 관련 (7개)
suspect_in      vt_psn      → vt_case       피의자 관련
victim_in       vt_psn      → vt_case       피해자 관련
witness_in      vt_psn      → vt_case       참고인 관련
filed_as        vt_petition → vt_case       진정서→사건 전환
similar_to      vt_case     → vt_case       사건 유사성
linked_to       vt_petition → vt_case       진정서↔사건 연결
clusters_with   vt_petition → vt_petition   유사 진정서 군집

# PERSON 관련 (13개)
has_account     vt_psn      → vt_bacnt      계좌 소유 (명의자)
controls        vt_psn      → vt_bacnt      실질 지배 (명의 무관)
owns_phone      vt_psn      → vt_telno      전화번호 소유
owns_device     vt_psn      → vt_dev        기기 소유
uses_id         vt_psn      → vt_id         플랫폼 ID 사용
uses_email      vt_psn      → vt_email      이메일 사용
drives          vt_psn      → vt_vhcl       차량 운행/소유
used_ip         vt_psn      → vt_ip         IP 사용 이력
member_of       vt_psn      → vt_org        범죄 조직 소속
works_at        vt_psn      → vt_org        합법 기관 재직
accomplice_of   vt_psn      → vt_psn        공범 관계 (추론)
sameAs          vt_psn      → vt_psn        동일 인물 (엔티티 해소)
contradicts     vt_psn      → vt_psn        모순 정보 (명의도용)

# OBJECT 관련 (8개)
transferred_to  vt_bacnt    → vt_bacnt      계좌 간 직접 연결 (집계)
contacted       vt_telno    → vt_telno      통화/문자 연결 (집계)
accessed        vt_ip       → vt_site       IP→사이트 접속
hosted_at       vt_site     → vt_ip         사이트 호스팅 위치
resolves_to     vt_site     → vt_ip         DNS 해석 결과
registered_to   vt_ip       → vt_org        IP 등록 기관
belongs_to      vt_bacnt    → vt_org        계좌 소속 금융기관
used_for        vt_telno/vt_id/vt_email/vt_site → vt_impersonation  사칭 행위에 이용됨

# EVENT 관련 (11개)
from_account    vt_bacnt    → vt_transfer   이체 출금 계좌
to_account      vt_transfer → vt_bacnt      이체 입금 계좌
caller          vt_telno    → vt_call       발신 번호
callee          vt_call     → vt_telno      수신 번호
accessed_from   vt_ip       → vt_access     접속 출발 IP
accessed_to     vt_access   → vt_site       접속 목적지
sent_via        vt_telno/vt_id → vt_msg     메시지 발신
received_by     vt_msg      → vt_telno/vt_id  메시지 수신
performed_by    vt_transfer/vt_call → vt_psn  이벤트 행위자
occurred_at     Event       → vt_loc        이벤트 발생 위치
recorded_in     vt_vhcl/vt_telno → vt_movement  이동 기록 주체
targets         vt_impersonation → vt_org   사칭 타겟 기관 (보이스피싱)

# META / PROVENANCE (2개)
sourced_from    Any         → vt_src        데이터 출처 (source_id 속성으로 대체 권장)
verified_by     Any         → vt_psn        수사관 검증

# 진정서 증거 (3개)
eg_used_account vt_petition → vt_bacnt      진정서에 언급된 계좌
eg_used_phone   vt_petition → vt_telno      진정서에 언급된 전화
eg_used_ip      vt_petition → vt_ip         진정서에 언급된 IP
```

### 1.3 엣지 메타속성 (v3.3 확정)

```python
# 모든 엣지 필수
source_id:       str    # vt_src.src_id 참조
rec_created:     str    # ISO8601 DB 기록 시점
creation_method: str    # manual | etl | ocr_ner | osint | inference

# 소유·귀속 엣지 권장
confidence:      float  # 0.0~1.0
credibility:     int    # 1~5
verified:        bool   # False=주장, True=공식 확인

# 소유·관계 엣지 (시간 변화 가능한 것)
valid_from:      str    # 현실 유효 시작
valid_to:        str    # 현실 유효 종료 (null=현재진행)
```

---

## 2. 데이터셋 설계 — 10,000개 분포

```
카테고리                    수량    비율    담당 엣지 수
────────────────────────────────────────────────────────────────
단일 노드 조회              1,200   12%    23개 노드 × 속성 필터
1-hop 관계 조회 (핵심)      4,500   45%    55+개 엣지 × 5템플릿×양방향
엣지 메타 속성 조건         1,000   10%    verified / confidence / valid_from
집계 쿼리                     800    8%    COUNT / ORDER BY / LIMIT
역방향 탐색                   700    7%    (b)<-[:rel]-(a) 패턴
1.5-hop 체인               1,000   10%    (a)-[r1]->(b)-[r2]->(c)
GENERAL 거부                  300    3%    수사 무관 질문
네거티브/경계 케이스           500    5%    보안 가드레일, 빈 결과
────────────────────────────────────────────────────────────────
합계                       10,000  100%
```

---

## 3. 질문 템플릿 맵 — 엣지별 상세

### 3.1 CASE 관련 (7개 엣지)

| 엣지 | 방향 | 질문 템플릿 (최소 5개) | Cypher 패턴 |
|------|------|----------------------|------------|
| `suspect_in` | vt_psn→vt_case | "{name}이 피의자로 등록된 사건", "사건 {flnm}의 피의자 목록", "{name}이 연루된 사건", "피의자 {name}의 수사 이력", "{name} 피의자 사건" | `MATCH (p:vt_psn {name:'{name}'})-[r:suspect_in]->(c:vt_case) RETURN p,r,c` |
| `victim_in` | vt_psn→vt_case | "{name}이 피해자인 사건", "사건 {flnm}의 피해자", "{name}의 피해 신고 내역", "피해금액이 있는 {name} 사건", "{name} 피해 사건 조회" | `MATCH (p:vt_psn {name:'{name}'})-[r:victim_in]->(c:vt_case) RETURN p,r,c` |
| `witness_in` | vt_psn→vt_case | "{name}이 참고인인 사건", "사건 {flnm}의 참고인 목록", "{name} 진술 사건" | `MATCH (p:vt_psn {name:'{name}'})-[r:witness_in]->(c:vt_case) RETURN p,r,c` |
| `filed_as` | vt_petition→vt_case | "진정서 {petition_id}가 전환된 사건", "{flnm} 사건의 원본 진정서", "사건으로 연결된 진정서" | `MATCH (pt:vt_petition)-[r:filed_as]->(c:vt_case {flnm:'{flnm}'}) RETURN pt,r,c` |
| `clusters_with` | vt_petition→vt_petition | "유사 진정서 군집 조회", "{petition_id}와 유사한 진정서" | `MATCH (pt:vt_petition {petition_id:'{id}'})-[r:clusters_with]-(pt2:vt_petition) RETURN pt,r,pt2` |
| `eg_used_account` | vt_petition→vt_bacnt | "진정서에 언급된 계좌", "{petition_id}에서 사용된 계좌", "진정서 관련 계좌 조회" | `MATCH (pt:vt_petition {petition_id:'{id}'})-[r:eg_used_account]->(b:vt_bacnt) RETURN pt,r,b` |
| `eg_used_phone` | vt_petition→vt_telno | "진정서에 나온 전화번호", "신고서에 등장한 연락처" | `MATCH (pt:vt_petition {petition_id:'{id}'})-[r:eg_used_phone]->(t:vt_telno) RETURN pt,r,t` |

### 3.2 PERSON 관련 (13개 엣지)

| 엣지 | 질문 템플릿 예시 | Cypher 핵심 패턴 |
|------|----------------|----------------|
| `has_account` | "{name}의 계좌", "계좌 {account_no} 명의자", "{name} 보유 통장" | `(p:vt_psn {name:X})-[:has_account]->(b:vt_bacnt)` |
| `controls` | "{name}이 실질 지배하는 계좌", "명의와 다른 실소유 계좌" | `(p:vt_psn)-[:controls {confidence>0.7}]->(b:vt_bacnt)` |
| `owns_phone` | "{name}의 전화번호", "{telno} 소유자" | `(p:vt_psn {name:X})-[:owns_phone]->(t:vt_telno)` |
| `owns_device` | "{name}이 사용한 기기", "IMEI {imei} 소유자" | `(p:vt_psn)-[:owns_device]->(d:vt_dev)` |
| `uses_id` | "{name}이 사용한 플랫폼 ID", "카카오 계정 {id_val}의 실소유자" | `(p:vt_psn)-[:uses_id]->(i:vt_id)` |
| `uses_email` | "{name}의 이메일", "이메일 {email_addr} 사용자" | `(p:vt_psn)-[:uses_email]->(e:vt_email)` |
| `drives` | "{name}이 운행한 차량", "차량 {vhclno} 운전자" | `(p:vt_psn)-[:drives]->(v:vt_vhcl)` |
| `used_ip` | "{name}이 사용한 IP", "IP {ip_addr} 접속자" | `(p:vt_psn)-[:used_ip]->(ip:vt_ip)` |
| `member_of` | "{name}이 소속된 조직", "조직 {org_name}의 구성원" | `(p:vt_psn)-[:member_of]->(o:vt_org)` |
| `works_at` | "{name}의 직장", "은행 {org_name} 직원" | `(p:vt_psn)-[:works_at]->(o:vt_org)` |
| `accomplice_of` | "{name}의 공범", "공범으로 추정되는 인물" | `(p:vt_psn {name:X})-[:accomplice_of]-(p2:vt_psn) RETURN p,p2` |
| `sameAs` | "동일 인물로 판단된 엔티티", "{name}과 동일인 확인" | `(p:vt_psn)-[:sameAs]-(same:vt_psn)` |

### 3.2.1 사칭 수단 쿼리
| 엣지 | 질문 템플릿 예시 | Cypher 핵심 패턴 |
|------|----------------|----------------|
| `used_for + targets` | "국민은행 사칭 번호", "검찰청 사칭 계정", "{org_name} 위장 전화" | `(t:vt_telno)-[:used_for]->(i:vt_impersonation)-[:targets]->(o:vt_org {org_name:X})` |

### 3.3 EVENT 관련 (11개 엣지)

| 엣지 | 질문 템플릿 예시 | Cypher 핵심 패턴 |
|------|----------------|----------------|
| `from_account` | "계좌 {account_no} 출금 이체", "{account_no}에서 나간 돈" | `(b:vt_bacnt {account_no:X})-[:from_account]->(t:vt_transfer)` |
| `to_account` | "계좌 {account_no}로 들어온 이체", "{account_no} 입금 내역" | `(t:vt_transfer)-[:to_account]->(b:vt_bacnt {account_no:X})` |
| `from_account + to_account` (체인) | "{account_no}의 이체 전체 흐름", "출금→이체→입금 경로" | `(b1)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2)` |
| `caller` | "전화 {telno}가 발신한 통화", "{telno} 발신 기록" | `(t:vt_telno {telno:X})-[:caller]->(c:vt_call)` |
| `callee` | "{telno}로 걸려온 통화", "{telno} 수신 내역" | `(c:vt_call)-[:callee]->(t:vt_telno {telno:X})` |
| `accessed_from` | "IP {ip_addr}에서 접속한 기록", "{ip_addr} 접속 이벤트" | `(ip:vt_ip {ip_addr:X})-[:accessed_from]->(a:vt_access)` |
| `accessed_to` | "특정 사이트 접속 기록", "{url_addr}에 접속한 이벤트" | `(a:vt_access)-[:accessed_to]->(s:vt_site {url_addr:X})` |
| `occurred_at` | "특정 위치에서 발생한 이체", "ATM 출금 위치" | `(t:vt_transfer)-[:occurred_at]->(loc:vt_loc)` |
| `recorded_in` | "{vhclno} 차량의 LPR 이동 기록", "기지국 이동 이력" | `(v:vt_vhcl {vhclno:X})-[:recorded_in]->(m:vt_movement)` |
| `performed_by` | "이체 {transfer_id}를 실행한 사람", "통화 {call_id}의 행위자" | `(t:vt_transfer)-[:performed_by]->(p:vt_psn)` |

---

## 4. v3.3 전용 고급 쿼리 패턴 (Premium 700개)

온톨로지 문서 Section 6의 7개 핵심 쿼리 패턴을 기반으로 고품질 샘플 제작.

### 4.1 엣지 메타속성 조건 쿼리 (1,000개)

```
질문: "검증된 계좌 소유 관계만 조회"
Cypher:
SELECT * FROM cypher('tccop_graph', $$
  MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt)
  WHERE r.verified = true
  RETURN p, r, b
$$) AS (p agtype, r agtype, b agtype);

질문: "신뢰도 0.7 이상인 실질 지배 관계"
Cypher:
SELECT * FROM cypher('tccop_graph', $$
  MATCH (p:vt_psn)-[r:controls]->(b:vt_bacnt)
  WHERE r.confidence >= 0.7
  RETURN p, r, b
$$) AS (p agtype, r agtype, b agtype);

질문: "2024년 1월에 유효했던 계좌 소유"
Cypher:
SELECT * FROM cypher('tccop_graph', $$
  MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt)
  WHERE r.valid_from <= '2024-01-31'
    AND (r.valid_to IS NULL OR r.valid_to >= '2024-01-01')
  RETURN p, r, b
$$) AS (p agtype, r agtype, b agtype);
```

### 4.2 위협 속성 필터 쿼리

```
# 대포통장
MATCH (b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN b

# 지급정지 계좌
MATCH (b:vt_bacnt) WHERE b->>'is_frozen' = 'true' RETURN b

# 토르/VPN IP
MATCH (ip:vt_ip) WHERE ip->>'is_tor' = 'true' OR ip->>'is_vpn' = 'true' RETURN ip

# 악성 사이트
MATCH (s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN s

# 대포폰
MATCH (t:vt_telno) WHERE t->>'is_burner' = 'true' RETURN t

# 고위험 가상지갑 (risk_score >= 70)
MATCH (c:vt_crypto) WHERE toInteger(c->>'risk_score') >= 70 RETURN c
```

### 4.3 1.5-hop 체인 쿼리 (1,000개)

```
# 자금 흐름: 인물 → 계좌 → 이체
MATCH (p:vt_psn {name:'홍길동'})-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer)
RETURN p, b, t

# 보이스피싱 경로: 전화 → 통화 → 전화
MATCH (t1:vt_telno)-[:caller]->(c:vt_call)-[:callee]->(t2:vt_telno)
WHERE t1->>'is_burner' = 'true'
RETURN t1, c, t2

# IP → 접속 → 사이트
MATCH (ip:vt_ip {ip_addr:'1.2.3.4'})-[:accessed_from]->(a:vt_access)-[:accessed_to]->(s:vt_site)
RETURN ip, a, s

# 차량 → 이동 → 위치
MATCH (v:vt_vhcl {vhclno:'12가3456'})-[:recorded_in]->(m:vt_movement)-[:occurred_at]->(loc:vt_loc)
RETURN v, m, loc
```

---

## 5. 스키마 입력 포맷 (축소 스키마 주입 방식)

모든 샘플의 [스키마] 절에는 **해당 쿼리에 관련된 노드·엣지만** 축소 주입.
전체 23개 레이블을 매번 넣으면 7B 모델의 컨텍스트가 낭비됨.

### 포맷 예시

```
[스키마]
노드:
  (vt_psn {name, korn_flnm, dob, gender, risk_level, rrno_hash})
  (vt_bacnt {account_no, bank_cd, bank_nm, dpstr_nm, is_burner, is_frozen})

관계:
  (vt_psn)-[:has_account {verified, confidence, valid_from, valid_to}]->(vt_bacnt)
  (vt_psn)-[:controls {control_type, confidence}]->(vt_bacnt)

속성 접근:
  WHERE n->>'속성명' = '값'  (문자열 비교)
  WHERE toInteger(n->>'속성명') >= 숫자  (숫자 비교)

[질문]
홍길동이 보유한 검증된 계좌만 조회해줘
```

### 스키마 스니펫 크기 기준

| 쿼리 유형 | 노드 수 | 엣지 수 | 예상 토큰 |
|---------|--------|--------|---------|
| 단일 노드 | 1 | 0 | ~50 |
| 1-hop | 2 | 1~2 | ~80 |
| 1.5-hop | 3 | 2~3 | ~120 |
| 메타속성 조건 | 2 | 1 + 속성 목록 | ~100 |

---

## 6. 생성 파이프라인 스크립트

```
scripts/
├── generate_t2c_sft.py         # Step 1: 템플릿 기반 5,000개
│   ├── TEMPLATES dict           (엣지 44개 × 5템플릿)
│   ├── SAMPLE_VALUES dict       (이름/계좌번호/사건번호 풀)
│   └── build_schema_snippet()   (관련 노드·엣지만 축소 추출)
│
├── augment_t2c_llm.py          # Step 2: GPT-4o-mini 증강 3,000개
│   ├── few-shot 표현 다양화      (구어체/문어체/수사용어)
│   └── 비용 예상: $0.5~1.0
│
├── add_t2c_manual.py           # Step 3: 수동 제작 2,000개
│   ├── 엣지 메타속성 조건        (verified/confidence/valid_from)
│   ├── 위협 속성 필터            (is_burner/is_tor/is_malicious)
│   ├── 1.5-hop 체인             (4.3절 패턴)
│   ├── 집계 쿼리                (COUNT/ORDER BY/LIMIT)
│   └── GENERAL 거부             (300개)
│
├── validate_t2c_dataset.py     # Step 4: 자동 품질 검증
│   ├── SQL Wrapper 구조 확인
│   ├── RETURN 수 = AS 컬럼 수
│   ├── 유효 레이블 (23개) 사용
│   ├── 쓰기 명령 없음
│   └── 중복 제거 (question 기준)
│
└── merge_sft_t2c.py            # Step 5: 최종 병합 + 분할
    ├── data/t2c_v1_sharegpt.json    (전체 10,000개)
    ├── data/t2c_v1_train.json       (9,500개)
    └── data/t2c_v1_eval.json        (500개)
```

---

## 7. 학습 설정 (v3.3 기반 변경사항)

### train/train_t2c_lora.yaml

```yaml
model_name_or_path: LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct
trust_remote_code: true

stage: sft
finetuning_type: lora
dataset: t2c_v1
template: exaone

# v3.3 스키마 반영 — 엣지 메타속성 쿼리 때문에 컨텍스트 확장
cutoff_len: 1280            # v5(768) → 1280 (스키마 + 메타속성 포함)

# LoRA
lora_rank: 32               # 특화 도메인, 과적합 방지
lora_alpha: 64
lora_dropout: 0.05
lora_target: q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj

# 학습
per_device_train_batch_size: 4
gradient_accumulation_steps: 4   # 유효 배치: 16
num_train_epochs: 3
learning_rate: 2.0e-4
lr_scheduler_type: cosine
warmup_ratio: 0.05
weight_decay: 0.01

bf16: true
quantization_bit: 4              # QLoRA
optim: adamw_torch_fused

output_dir: train/output/exaone_t2c_v1
save_strategy: epoch
save_total_limit: 3
val_size: 0.05
eval_strategy: epoch
logging_steps: 50
```

---

## 8. 벤치마크 기준 — v3.3 쿼리 패턴 포함

### benchmark_t2c.py 테스트 항목 (100문항)

| 카테고리 | 문항 수 | 예시 질문 |
|---------|--------|---------|
| 단일 노드 조회 | 10 | "대포통장 의심 계좌 전체" |
| 1-hop CASE | 15 | "홍길동의 피의자 사건" |
| 1-hop PERSON→OBJECT | 20 | "홍길동의 계좌", "사칭 전화번호" |
| 1-hop EVENT | 15 | "계좌 출금 이체", "발신 통화 기록" |
| 엣지 메타 조건 | 10 | "검증된 계좌 소유 관계" |
| 위협 속성 필터 | 10 | "is_burner=true 계좌" |
| 1.5-hop 체인 | 10 | "인물→계좌→이체 흐름" |
| GENERAL 거부 | 5 | "한국 수도는?" |
| 보안 가드레일 | 5 | "DELETE 명령 포함 질문" |

### 성능 목표

| 지표 | 현재 (GPT-4o) | 목표 (sLLM v1) | 목표 (sLLM v2) |
|------|-------------|--------------|--------------|
| 실행 성공률 | ~85% | 75%↑ | 85%↑ |
| 1차 생성 성공률 | ~65% | 60%↑ | 75%↑ |
| 결과 적중률 | ~70% | 65%↑ | 78%↑ |
| 응답 속도 (p50) | ~3s | <1s | <1s |

> **참고**: sLLM v1은 GPT-4o 대비 속도 우선, v2는 정확도 동등 목표.

---

## 9. 전체 실행 체크리스트

```
Phase 1 — 기준선 측정 (1일)
  [ ] python benchmark_v32.py  → 현재 성능 측정 및 저장
  [ ] 실패 패턴 유형 분류 (AS불일치 / 방향오류 / 레이블오류)

Phase 2 — 데이터 생성 (1주)
  [ ] scripts/generate_t2c_sft.py 작성 + 실행  → 5,000개
  [ ] scripts/augment_t2c_llm.py 작성 + 실행   → 3,000개
  [ ] scripts/add_t2c_manual.py 작성 + 실행    → 2,000개
  [ ] scripts/validate_t2c_dataset.py 실행     → 품질 필터링
  [ ] scripts/merge_sft_t2c.py 실행            → 최종 10,000개
  [ ] train/dataset_info.json에 t2c_v1 등록

Phase 3 — 학습 (3~4일)
  [ ] train/train_t2c_lora.yaml 작성
  [ ] bash train/upload_to_server.sh
  [ ] llamafactory-cli train train/train_t2c_lora.yaml
  [ ] 체크포인트별 eval loss 모니터링

Phase 4 — 평가 (1일)
  [ ] scripts/merge_lora.py → 모델 병합
  [ ] vllm serve models/exaone_t2c_v1
  [ ] python benchmark_t2c.py → 100문항 평가
  [ ] Phase 1 기준선과 비교

Phase 5 — 통합 (0.5일)
  [ ] .env: SLLM_ENDPOINT, SLLM_MODEL_NAME 설정
  [ ] CCOP 앱 연결 테스트 (LangGraph → sLLM)
  [ ] GPT-4o Fallback 분기 확인
```

---

## 10. 파일 위치 요약

```
coop_v1.0/
├── docs/
│   └── T2C_SFT_DEVELOPMENT_PLAN.md      ← 이 파일
├── scripts/
│   ├── generate_t2c_sft.py              ← 신규 작성
│   ├── augment_t2c_llm.py               ← 신규 작성
│   ├── add_t2c_manual.py                ← 신규 작성
│   ├── validate_t2c_dataset.py          ← 신규 작성
│   └── merge_sft_t2c.py                 ← 신규 작성
├── data/
│   ├── t2c_v1_sharegpt.json             ← 생성 결과
│   ├── t2c_v1_train.json
│   └── t2c_v1_eval.json
├── train/
│   ├── train_t2c_lora.yaml              ← 신규 작성
│   └── dataset_info.json                ← t2c_v1 등록 추가
└── benchmark_t2c.py                     ← 신규 작성
```
