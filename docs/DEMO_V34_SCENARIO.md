# CCOP v3.4 데모 시나리오 가이드

> **온톨로지 버전**: v3.4 (45종 엣지)  
> **기준일**: 2026-04-20  
> **데모 그래프**: 4종 (복합사건 1 + 단일범죄유형 3)

---

## 데모 그래프 목록

| 그래프명 | 시나리오 | 노드 | 엣지 | v3.4 신규 엣지 |
|---------|---------|------|------|--------------|
| `ccop_demo_v34` | 복합 조직 사건 (몸캠+투자+대포통장) | 60 | 84 | 6종 전체 |
| `ccop_demo_moccam` | 텔레그램 조직형 몸캠피싱 | 41 | 58 | operates, recruits, blackmails, hosts, contains_file, located_at |
| `ccop_demo_invest` | 수익보장형 가상투자 사기 | 47 | 59 | operates, recruits, hosts, contains_file, located_at |
| `ccop_demo_voice` | 검찰/금감원 사칭 보이스피싱 | 51 | 70 | operates, recruits, hosts, contains_file, located_at |

> **생성 스크립트**: `scripts/create_demo_v34.py`, `create_demo_moccam.py`, `create_demo_invest.py`, `create_demo_voice.py`

---

## 1. `ccop_demo_moccam` — 텔레그램 조직형 몸캠피싱

### 1-1. 사건 개요

| 항목 | 내용 |
|------|------|
| 사건번호 | CASE-2026-MC001 |
| 죄명 | 성착취물 제작·협박 (형법 제350조, 성폭력처벌법) |
| 범행 유형 | 텔레그램 여성 위장 접근 → 영상통화 녹화 → 협박금 대포통장 송금 |
| 피해 규모 | 26,000,000원 (피해자 2명) |
| 피해자 | 최피해(20백만), 정피해(6백만) |
| 총책 거점 | 해외 (베트남 추정) |

### 1-2. 등장인물

| ID | 이름 | 역할 | 상태 |
|----|------|------|------|
| PSN-A001 | 김총책 | 총책 | 수배중 (해외) |
| PSN-A002 | 이협박 | 협박 담당 | 체포 |
| PSN-A003 | 박현금 | 현금 수거책 | 체포 |
| PSN-V001 | 최피해 | 피해자 | — |
| PSN-V002 | 정피해 | 피해자 | — |

### 1-3. v3.4 신규 엣지 활용 포인트

```
★ operates   : 김총책 → 텔레그램채널(@moc_official) 운영
★ recruits   : 김총책 → 이협박 모집 (협박담당)
               김총책 → 박현금 모집 (수거책)
★ blackmails : 이협박 → 최피해 협박 (몸캠영상유포협박)
               이협박 → 정피해 협박
★ hosts      : IP-001(베트남) → SITE-001(영상저장서버)
★ contains_file : SITE-001 → FILE-001(협박영상)
                  MSG-001  → FILE-001(영상 전달)
★ located_at : ATM-001 → LOC-001(강남 GS25)
               ATM-002 → LOC-002(서초 CU)
```

### 1-4. 핵심 수사 쿼리

```cypher
-- 협박 관계망 조회
MATCH (a:vt_psn)-[:blackmails]->(v:vt_psn)
RETURN a.name AS 협박자, v.name AS 피해자

-- 조직 모집 계층 조회
MATCH (boss:vt_psn)-[:recruits]->(member:vt_psn)
RETURN boss.name AS 총책, member.name AS 조직원, member.role AS 역할

-- 협박 도구 추적 (영상 → 업로드 서버 → IP)
MATCH (f:vt_file)<-[:contains_file]-(s:vt_site)<-[:hosts]-(ip:vt_ip)
RETURN f.filename, s.url, ip.address, ip.country
```

---

## 2. `ccop_demo_invest` — 수익보장형 가상투자 사기

### 2-1. 사건 개요

| 항목 | 내용 |
|------|------|
| 사건번호 | CASE-2026-IV001 |
| 죄명 | 사기죄 (형법 제347조), 전기통신금융사기 |
| 범행 유형 | 미래에셋증권 사칭 + 가짜 투자플랫폼 + 악성APK 배포 |
| 피해 규모 | 51,000,000원 (피해자 3명) |
| 피해자 | 한피해(24백만), 유피해(18백만), 강피해(9백만) |
| 위장회사 | 스마트인베스트(주) |

### 2-2. 등장인물

| ID | 이름 | 역할 | 상태 |
|----|------|------|------|
| PSN-A001 | 오총괄 | 총괄책 | 추적중 |
| PSN-A002 | 나영업 | 영업·유인책 | 체포 |
| PSN-A003 | 최기술 | 기술·사이트 운영 | 체포 |
| PSN-V001 | 한피해 | 피해자 | — |
| PSN-V002 | 유피해 | 피해자 | — |
| PSN-V003 | 강피해 | 피해자 | — |

### 2-3. v3.4 신규 엣지 활용 포인트

```
★ operates   : 오총괄 → 투자사이트(smartinvest-kr.com) 운영
               오총괄 → 텔레그램채널(@smart_invest_official) 운영
               ORG-001(스마트인베스트) → 투자사이트 운영
★ recruits   : 오총괄 → 나영업 모집 (영업책)
               오총괄 → 최기술 모집 (기술책)
★ hosts      : IP-001 → SITE-001(투자플랫폼) 호스팅
               IP-002 → SITE-002(APK배포사이트) 호스팅
★ contains_file : SITE-002 → FILE-001(악성APK)
                  MSG-001  → FILE-001(APK 배포 메시지)
★ located_at : ATM-001 → LOC-001
               DEV-001 → LOC-002(기술책 사무소)
★ used_for + targets : 사칭이벤트 → 미래에셋증권 (IMP-001)
```

### 2-4. 핵심 수사 쿼리

```cypher
-- 사칭 인프라 전체 조회 (used_for → targets)
MATCH (tool)-[:used_for]->(imp:vt_impersonation)-[:targets]->(org:vt_org)
RETURN labels(tool)[0] AS 수단유형, imp.method AS 수법, org.org_name AS 사칭대상

-- 악성APK 배포 경로
MATCH (msg)-[:contains_file]->(f:vt_file {filetype:'APK'})
      <-[:contains_file]-(site:vt_site)<-[:hosts]-(ip:vt_ip)
RETURN msg, f.filename, site.url, ip.address

-- 피해금 흐름 (3명 피해자 → 대포통장 → 세탁)
MATCH path = (v:vt_psn)-[:victim_in]->(c:vt_flnm),
             (v)-[:owns_account]->(acnt:vt_bacnt)
             -[:transferred_to*1..3]->(dest:vt_bacnt)
RETURN v.name, acnt.acnt_id, dest.acnt_id
```

---

## 3. `ccop_demo_voice` — 검찰/금감원 사칭 보이스피싱

### 3-1. 사건 개요

| 항목 | 내용 |
|------|------|
| 사건번호 | CASE-2026-VC001 |
| 죄명 | 전기통신금융사기 (전기통신금융사기법 제3조) |
| 범행 유형 | 검찰청 사칭 → ATM 출금 유도 → 현금 수거 → 3단계 세탁 |
| 피해 규모 | 82,000,000원 (피해자 3명) |
| 콜센터 거점 | 필리핀 마닐라 |

### 3-2. 등장인물

| ID | 이름 | 역할 | 상태 |
|----|------|------|------|
| PSN-A001 | 강총책 | 총책 | 수배중 (필리핀) |
| PSN-A002 | 박발신 | 발신책 (사칭전화) | 체포 |
| PSN-A003 | 윤수거 | 현금 수거책 | 체포 |
| PSN-A004 | 임세탁 | 자금세탁책 | 추적중 |
| PSN-V001 | 이피해 | 피해자 (3,500만) | — |
| PSN-V002 | 최피해 | 피해자 (2,700만) | — |
| PSN-V003 | 정피해 | 피해자 (2,000만) | — |

### 3-3. v3.4 신규 엣지 활용 포인트

```
★ recruits   : 강총책 → 박발신 모집 (발신책, 건당5만원)
               강총책 → 윤수거 모집 (현금수거책, 건당10만원)
               강총책 → 임세탁 모집 (자금세탁, 5%커미션)
★ operates   : 강총책 → 검찰사칭사이트(prosecution-kr-secure.com)
               강총책 → 금감원사칭사이트(fss-safe-account.net)
               강총책 → 텔레그램채널(@prosecution_official_kr)
★ hosts      : IP-001(필리핀VoIP) → SITE-001(검찰사칭사이트)
               IP-002(미국) → SITE-002(금감원사칭사이트)
★ contains_file : SITE-001 → FILE-001(위조수사통보서.hwp)
                  SITE-002 → FILE-002(악성APK)
                  MSG-002  → FILE-001(카카오톡 전달)
★ located_at : ATM-001 → LOC-001(강남 GS25)
               ATM-002 → LOC-002(서초 CU)
               ATM-003 → LOC-003(분당 서현역)
               ORG-001(마닐라콜센터) → LOC-004
```

### 3-4. 자금세탁 3단계 구조

```
이피해(3,500만) ─┐
                  ├─→ [TRF-001·002] → ACNT-D001(1차대포) ─→ [TRF-004] → ACNT-D002(2차세탁)
최피해(2,700만) ─┘                                                         ─→ [TRF-005] → ACNT-D003(최종인출)
정피해(2,000만) ──────────────────→ [TRF-003] → ACNT-D001
```

### 3-5. 핵심 수사 쿼리

```cypher
-- 전화번호 스푸핑 탐지 (070 VoIP + 필리핀 IP)
MATCH (ip:vt_ip {country:'PH'})-[:linked_to]->(call:vt_evt_call)
      <-[:caller]-(tel:vt_telno {tel_type:'070인터넷전화'})
RETURN ip.address, tel.number, call.call_dt, call.duration_sec

-- 자금세탁 체인 전체 조회
MATCH path = (victim:vt_psn)-[:victim_in]->(c:vt_flnm),
             (victim)-[:owns_account]->(a1:vt_bacnt)
             -[:transferred_to*1..3]->(final:vt_bacnt)
WHERE NOT (final)-[:transferred_to]->()
RETURN victim.name, a1.acnt_id, final.acnt_id, length(path) AS hop_cnt
ORDER BY hop_cnt DESC

-- 조직 모집 계층 (recruits)
MATCH (boss:vt_psn)-[r:recruits]->(member:vt_psn)
RETURN boss.name AS 총책, member.name AS 조직원, r.recruit_type AS 역할, r.payment AS 보수
```

---

## 4. `ccop_demo_v34` — 복합 조직 사건

### 4-1. 사건 개요

| 항목 | 내용 |
|------|------|
| 사건번호 | CASE-2026-DEMO-001 |
| 죄명 | 전기통신금융사기 · 성착취물제작 · 자금세탁 |
| 범행 유형 | 텔레그램 기반 몸캠피싱 + 투자사기 + 대포통장 조직 복합 |
| 피해 규모 | 다수 피해자 |
| 특징 | v3.4 신규 엣지 6종 **전부** 포함 |

### 4-2. v3.4 신규 엣지 6종 전체 검증

| 엣지 | 포함 여부 | 활용 패턴 |
|------|----------|---------|
| `operates` | ✅ | 총책 → 피싱사이트/텔레그램채널 |
| `recruits` | ✅ | 조직 계층 구조 (총책→모집책→말단) |
| `blackmails` | ✅ | 몸캠 협박 (Person→Person) |
| `hosts` | ✅ | 서버IP → 피싱사이트 |
| `contains_file` | ✅ | 사이트/메시지 → 악성파일 |
| `located_at` | ✅ | ATM → 위치 (CCTV 교차분석) |

---

## 5. v3.4 공통 조회 패턴

### 5-1. 조직 계층 전체 시각화

```cypher
-- 총책 중심 조직 구조 (recruits 체인)
MATCH path = (boss:vt_psn)-[:recruits*1..3]->(member:vt_psn)
RETURN path

-- 공범 네트워크 (accomplice_of + recruits 복합)
MATCH (p:vt_psn)-[:suspect_in]->(c:vt_flnm)
OPTIONAL MATCH (p)-[:recruits|accomplice_of]-(other:vt_psn)
RETURN p.name, collect(other.name) AS 연결된_공범
```

### 5-2. 인프라 역추적 (hosts + operates)

```cypher
-- 피싱 인프라 전체 (IP → 사이트 → 운영자)
MATCH (ip:vt_ip)-[:hosts]->(site:vt_site)<-[:operates]-(person:vt_psn)
RETURN ip.address, ip.country, site.url, person.name AS 운영자
```

### 5-3. ATM 위치 기반 현장 대조

```cypher
-- ATM + 위치 + 인근 이체 이벤트 (located_at)
MATCH (atm:vt_atm)-[:located_at]->(loc:vt_loc)
OPTIONAL MATCH (atm)-[:linked_to]->(trf:vt_evt_transfer)
RETURN atm.atm_id, loc.address, loc.cctv_available,
       count(trf) AS 관련_이체건수
ORDER BY 관련_이체건수 DESC
```

### 5-4. 협박 피해자 연결망 (blackmails)

```cypher
-- 협박자 → 피해자 전체 (몸캠피싱)
MATCH (suspect:vt_psn)-[b:blackmails]->(victim:vt_psn)
RETURN suspect.name AS 협박자, victim.name AS 피해자,
       b.method AS 협박수법, b.date AS 협박일
```

---

## 6. v3.3 → v3.4 변경 대비표

| 항목 | v3.3 (구) | v3.4 (현행) |
|------|-----------|------------|
| 엣지 수 | 55종 | 45종 |
| Case→Object 직접 연결 | `eg_used_account`, `eg_used_phone` (존재) | **제거** — 추론 쿼리로 대체 |
| 사칭 표현 | `impersonates` (deprecated) | `used_for` + `targets` (vt_impersonation 노드) |
| 인물 역할 | `vt_psn.role = 'suspect'` | `suspect_in` / `victim_in` / `witness_in` 엣지 |
| 플랫폼 운영 | 없음 | `operates` (Person/Org → Site/ID) |
| 조직 모집 | 없음 | `recruits` (Person → Person) |
| 협박 | 없음 | `blackmails` (Person → Person) |
| 인프라 호스팅 | 없음 | `hosts` (IP → Site) |
| 파일 배포 | 없음 | `contains_file` (Site/Msg/ID → File) |
| 고정 위치 | 없음 | `located_at` (ATM/Device/Org → Location) |
| involves | `(case)-[:involves]->(person)` | **제거** |
| performed | `(person)-[:performed]->(event)` | **제거** |
| contacted | `(phone)-[:contacted]->(phone)` | **제거** → `caller` / `callee` |
| communicated_with | `(ip)-[:communicated_with]->(ip)` | **제거** |

---

## 7. 데모 실행 방법

```bash
# 전체 데모 그래프 재생성
python scripts/create_demo_v34.py
python scripts/create_demo_moccam.py
python scripts/create_demo_invest.py
python scripts/create_demo_voice.py

# UI 접속 후 그래프 선택
open http://localhost:5002
```

> **그래프 선택**: UI 상단 드롭다운 → `ccop_demo_moccam` / `ccop_demo_invest` / `ccop_demo_voice` / `ccop_demo_v34`
