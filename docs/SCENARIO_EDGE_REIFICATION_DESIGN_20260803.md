# 시나리오 엣지 이벤트 Reification 확장 설계 (🟠 11개)

> **작성일**: 2026-08-03
> **대상**: `SCENARIO_EDGE_ONTOLOGY_REVIEW_20260803.md`의 🟠 우선순위 11개 엣지
> **원칙**: 직접 엣지 추가가 아니라 **기존 이벤트 노드(vt_access/vt_transfer/vt_call/vt_msg) reification 확장** — 앞선 온톨로지 검토(`CCOP_ONTOLOGY_V4.1_REVIEW.md` 렌즈 A·B)에서 CASE·Participation Pattern 국제 표준으로 확인
> **SoT**: `app/middleware/services/ontology_service.py`

---

## 0. 핵심 발견 — 현재 온톨로지가 이미 다형(Any) 이벤트 엣지를 보유

설계에 착수하며 SoT를 정밀 조회한 결과, **직접 엣지를 새로 만들 필요가 없는 엣지가 이미 존재**합니다:

| 기존 엣지 | 정의 | 함의 |
|---|---|---|
| **`occurred_at`** | **Any** → Location | 어떤 이벤트든 위치 연결 가능 — **No.1(발신위치)은 스키마 변경 0** |
| **`performed_by`** | **Any** → Person | 어떤 이벤트든 사람 주체 연결 |
| **`recorded_in`** | **Any** → Movement | 이동 이벤트 다형 참여 |
| **`used_for`** | **Any** → Impersonation | 사칭 이벤트 다형 수단 |

→ CCOP는 이미 **이벤트 reification을 다형 엣지로 설계**해 두었습니다. 이 위에 최소한만 얹으면 됩니다. 이것이 "직접 엣지 11개(60→71)"가 아니라 **"신규 3개(60→63)"**로 끝나는 이유입니다.

## 1. 설계 요약 — 11개를 신규 3 + 다형화 3 + 기존 1로 커버

| 방식 | 엣지 | 커버하는 시나리오 No |
|---|---|---|
| **기존 재사용** | `occurred_at` (Any→Location) | No.1 (통화 발신위치) |
| **신규 ①** | `access_via` (vt_access → vt_telno/vt_id/vt_bacnt) | No.4, 21, 22, 23 (접속 주체) |
| **신규 ②** | `via_ip` (vt_transfer → vt_ip) | No.5 (이체 접속 IP) |
| **신규 ③** | `mentions_location` (vt_msg → vt_loc) | No.10 (메시지 언급 위치) |
| **다형화 ④** | `from_account`/`to_account` range를 **금융노드**(bacnt→+crypto/atm)로 확장 | No.6, 9, 19 |
| **다형화 ⑤** | `sent_msg`/`received_msg` domain을 **Phone/DigitalID**로 확장 | No.13 (계정 간 대화) |
| **다형화 ⑥** | `transferred_to` range를 crypto까지 확장 | No.19 (지갑 간 세탁) |

**엣지 총수: 60 → 63** (신규 3개만, 다형화는 기존 엣지 range 확장이라 수 불변)

## 2. 패턴별 상세 설계

### 패턴 A — 접속 이벤트(vt_access) 주체 확장

**현재**: `(vt_access)-[:accessed_from]->(vt_ip)` + `(vt_access)-[:performed_by]->(vt_psn)`
**문제**: 시나리오는 `vt_telno`·`vt_id`가 IP 접속 주체(수단)인데, `performed_by`는 range가 Person(사람)뿐.
**설계**: 신규 `access_via` (vt_access → vt_telno | vt_id | vt_bacnt) — "접속에 사용된 통신수단/계정/모바일뱅킹 계좌"

```cypher
-- No.4 "특정 IP에 접속한 전화번호"
MATCH (ip:vt_ip {ip_addr:'1.2.3.4'})<-[:accessed_from]-(a:vt_access)-[:access_via]->(t:vt_telno)
RETURN t
-- No.21/22 "포털 역조회 — IP에 접속한 계정"
MATCH (ip:vt_ip)<-[:accessed_from]-(a:vt_access)-[:access_via]->(id:vt_id)
RETURN id, a.lgn_dt ORDER BY a.lgn_dt DESC   -- No.23 '최종접속'은 lgn_dt 정렬로 표현(속성)
```

> "최종 접속"(No.22·23)은 신규 엣지가 아니라 `vt_access.lgn_dt` **정렬 속성**으로 해결 — 엣지 남발 방지.

### 패턴 B — 금융 이벤트(vt_transfer) 다형 확장

**현재**: `(vt_bacnt)-[:from_account]->(vt_transfer)-[:to_account]->(vt_bacnt)` (계좌만)
**설계**: `from_account`/`to_account`의 domain/range를 **금융노드 = {vt_bacnt, vt_crypto, vt_atm}**로 다형화 + 신규 `via_ip`

```cypher
-- No.6 "계좌에서 가상자산으로 전송"
MATCH (b:vt_bacnt)-[:from_account]->(tr:vt_transfer)-[:to_account]->(w:vt_crypto) RETURN tr
-- No.19 "지갑 간 세탁"
MATCH (w1:vt_crypto)-[:from_account]->(tr:vt_transfer)-[:to_account]->(w2:vt_crypto) RETURN *
-- No.9 "ATM 현금 인출"
MATCH (b:vt_bacnt)-[:from_account]->(tr:vt_transfer)-[:to_account]->(atm:vt_atm) RETURN tr
-- No.5 "이체 접속 IP (모바일뱅킹)"
MATCH (b:vt_bacnt)-[:from_account]->(tr:vt_transfer)-[:via_ip]->(ip:vt_ip) RETURN ip
```

> **부수 효과**: No.9로 `vt_atm` **고아노드가 해소**됩니다(현재 vt_atm에 연결 엣지 0). `transferred_to`(자금세탁 추론)도 crypto까지 확장하면 계좌↔가상자산 세탁 경로 추적 가능.

### 패턴 E — 위치·컨텐츠

- **No.1 통화 발신위치**: `(t:vt_telno)-[:caller]->(c:vt_call)-[:occurred_at]->(l:vt_loc)` — **`occurred_at`이 이미 Any→Location이라 스키마 변경 0**, ETL만 추가.
- **No.10 메시지 언급 위치**: 신규 `mentions_location` (vt_msg → vt_loc) — "발생 위치(occurred_at)"와 의미가 다른 "내용상 언급 장소"라 별도 엣지.
- **No.13 계정 간 대화**: `sent_msg`/`received_msg`의 domain을 **Phone/DigitalID** 다형화 → `(id1:vt_id)-[:sent_msg]->(m:vt_msg)-[:received_msg]->(id2:vt_id)`.

## 3. 신규/변경 엣지 카탈로그 (SoT 반영안)

**신규 3종** (RELATIONSHIPS + EDGE_STYLE_V40 + NODE_ID_STANDARD 무관):

| 엣지 | domain | range | 의미 | 주요 속성 |
|---|---|---|---|---|
| `access_via` | Event(Access) | Object(Phone/DigitalID/BankAccount) | 접속에 사용된 수단 | valid_from, confidence, source_id |
| `via_ip` | Event(Transfer) | Object(NetworkTrace) | 이체 접속 IP | source_id |
| `mentions_location` | Event(Message) | Location | 메시지 언급 위치 | confidence, source_id |

**다형화 3종** (기존 엣지 domain/range 완화, 신규 아님):

| 엣지 | 변경 | 비고 |
|---|---|---|
| `from_account`/`to_account` | range: BankAccount → **FinancialNode**(bacnt/crypto/atm) | 금융 이벤트 다형 |
| `sent_msg`/`received_msg` | domain: Phone → **Phone∪DigitalID** | 계정 메시지 |
| `transferred_to` | range: BankAccount → **+CryptoWallet** | 세탁 경로 |

## 4. ETL 매핑

| 데이터 소스 | 생성 이벤트 노드 | 참여 엣지 |
|---|---|---|
| 시스템로그·포털 역조회(2차년 EP6) | `vt_access` | `access_via`(telno/id) + `accessed_from`(ip) + `occurred_at`(loc) |
| 계좌내역(IP 포함 시) | `vt_transfer` | `from_account`/`to_account` + `via_ip` |
| 가상자산 거래(사이버마약 3.가상자산) | `vt_transfer` | `from_account`/`to_account`(crypto) |
| ATM 인출 기록 | `vt_transfer` | `from_account`(bacnt) + `to_account`(atm) |
| 통화내역(기지국, 1-1/1-2) | `vt_call` | `caller`/`callee` + `occurred_at`(loc) |
| 텔레그램 대화 | `vt_msg` | `sent_msg`/`received_msg`(id) + `mentions_location` |

> ⚠️ **데이터 선행 검증**: 1차년 계좌내역 샘플엔 IP 컬럼이 없음 → `via_ip`(No.5)는 모바일뱅킹 로그 확보가 전제. 없는 데이터로 엣지만 만들면 공엣지.

## 5. Text2Cypher 영향 평가 (핵심 리스크)

| 항목 | 영향 | 대응 |
|---|---|---|
| **스키마 크기** | 60→63 (+5%) | 방금 도입한 **질문별 스키마 pruning**이 vt_access/transfer 관련 질문에만 신규 엣지 주입 → 무관 질문 영향 0 (reification·pruning 시너지) |
| **2-hop 쿼리 난이도** | 🔴 직접 엣지 1-hop 대비 reification은 2-hop(`telno<-access_via-access-accessed_from->ip`) — sLLM 생성 난이도↑ | **few-shot 예제 6~9개 추가** 필수 (기존 caller/callee·from/to_account 2-hop 패턴 재활용 학습) |
| **다형 range 혼동** | LLM이 `from_account`에 crypto/atm 허용을 모름 | 프롬프트에 "from_account/to_account는 계좌·지갑·ATM 가능" 명시 + `_validate_cypher_schema` 다형 range 반영 |
| **LABEL_ALIASES(노드)** | 무영향 (노드 25개 불변) | — |
| **추론 규칙** | `transferred_to` 다형화 → MoneyLaundering 규칙이 crypto 경유 세탁 포함 | 추론 규칙 trigger 재검토 |

**핵심 트레이드오프**: reification은 온톨로지 철학상 옳고 엣지 수를 억제(63 vs 71)하지만, **2-hop 쿼리가 v42 sLLM에 더 어렵습니다**. 직접 엣지의 유혹은 "쉬운 Cypher"이지만 온톨로지 팽창·n-ary 손실을 부릅니다. → few-shot 보강으로 2-hop 난이도를 흡수하는 것이 정답.

## 6. 권고 및 단계적 도입

**권고**: reification 확장 채택. 근거 — ① 엣지 63 vs 71(직접엣지)로 팽창 억제, ② occurred_at 등 기존 다형 엣지 재사용으로 No.1은 변경 0, ③ n-ary(언제/성공여부/금액) 보존, ④ 국제 표준(CASE) 정합.

**단계**:
1. **스키마 정의** — 신규 3엣지 + 다형화 3종을 RELATIONSHIPS/EDGE_STYLE_V40에 반영 + 회귀 테스트(`test_ontology_catalog_sync.py`) 갱신 → **V4.3**
2. **few-shot 보강** — `data/few_shot_examples.json`에 2-hop reification 예제 6~9개 추가
3. **ETL 매핑** — 이벤트 노드 생성 로직(§4)
4. **Text2Cypher 검증** — `_validate_cypher_schema` 다형 range 반영 + 프롬프트 명시
5. **A/B 평가** — reification 쿼리 정확도를 `scripts/ab_schema_augment.py` 프레임 확장해 측정 (직접엣지 대비 2-hop 정확도)

**리스크 요약**: 2-hop 정확도 하락(→ few-shot + A/B로 선제 검증), ETL 복잡도↑, 데이터 근거(IP 등) 선행 확보.

---

## 부록 — 11개 엣지 최종 매핑표

| No | 요구(노드1-노드2/엣지) | 처리 방식 | reification 경로 |
|---|---|---|---|
| 1 | vt_telno-vt_loc / 발신위치 | **기존 occurred_at** (변경0) | telno-caller→call-occurred_at→loc |
| 4 | vt_telno-vt_ip / 접속 | 신규 access_via | telno←access_via-access-accessed_from→ip |
| 5 | vt_bacnt-vt_ip / 이체접속 | 신규 via_ip | bacnt-from_account→transfer-via_ip→ip |
| 6 | vt_bacnt-vt_crypto / 연결 | from/to 다형화 | bacnt-from_account→transfer-to_account→crypto |
| 9 | vt_bacnt-vt_atm / 출금 | from/to 다형화 | bacnt-from_account→transfer-to_account→atm |
| 10 | vt_msg-vt_loc / 기재됨 | 신규 mentions_location | msg-mentions_location→loc |
| 13 | vt_id-vt_id / 문자대화 | sent/received_msg 다형화 | id-sent_msg→msg-received_msg→id |
| 19 | vt_crypto-vt_crypto / 금융거래 | from/to 다형화 + transferred_to | crypto-from_account→transfer-to_account→crypto |
| 21 | vt_id-vt_ip / 접속 | 신규 access_via | id←access_via-access-accessed_from→ip |
| 22 | vt_id-vt_ip / 최종접속 | access_via + lgn_dt 정렬 | id←access_via-access(ORDER BY lgn_dt)-accessed_from→ip |
| 23 | vt_telno-vt_ip / 최종접속 | access_via + lgn_dt 정렬 | telno←access_via-access(ORDER BY lgn_dt)-accessed_from→ip |
