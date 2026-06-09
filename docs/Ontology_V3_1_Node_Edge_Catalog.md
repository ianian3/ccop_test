> ## ⚠️ DEPRECATED — V4.0 통합본 사용 권장
>
> 이 문서는 **CCOP 온톨로지 V3.1** 명세입니다. **2026-05-21부로 V4.0으로 통합되어 deprecated** 되었습니다.
>
> **현행 SSOT**: [`docs/CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
> **코드 SSOT**: `app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`
>
> V4.0은 V3.7 카탈로그(25 노드 / 53 엣지)를 그대로 유지하면서, 도메인 사용 매트릭스 / 식별자 형식 / 추론 규칙을 표준 메타로 격상한 통합본입니다. 본 문서는 **역사적 참고용**으로만 보존됩니다.
>
> ---
>

# CCOP 지식 그래프 V3.1 — 노드·엣지 완전 카탈로그

**기준 버전**: V3.1 (2026-04-06 확정)
**참조 구현**: `app/middleware/services/ontology_service.py`
**노드**: 22개 / **활성 엣지**: 50개 / **Deprecated 엣지**: 3개

---

## 목차

1. [노드 카탈로그 (22개) — 속성 설명 포함](#1-노드-카탈로그)
   - N-01 vt_src / N-02 vt_case / N-03 vt_petition
   - N-04 vt_psn / N-05 vt_org
   - N-06 vt_bacnt / N-07 vt_crypto / N-08 vt_ip / N-09 vt_site / N-10 vt_file
   - N-11 vt_id / N-12 vt_email / N-13 vt_dev / N-14 vt_telno / N-15 vt_vhcl / N-16 vt_atm
   - N-17 vt_loc
   - N-18 vt_transfer / N-19 vt_call / N-20 vt_access / N-21 vt_msg / N-22 vt_movement
2. [엣지 공통 메타속성 (EDGE_META_SCHEMA)](#2-엣지-공통-메타속성)
3. [엣지 카탈로그 (53개)](#3-엣지-카탈로그)
4. [레이어 간 허용 관계 매트릭스](#4-관계-매트릭스)
5. [주요 수사 패턴 그래프 다이어그램](#5-수사-패턴-다이어그램)

---

## 1. 노드 카탈로그

> **PK**: 그래프 MERGE 기준 식별자 / **Attributes**: 검색·분석용 부가 속성
> 각 노드 하단의 속성 설명 표를 함께 참조하세요.

---

### SOURCE LAYER (1종)

#### N-01. `vt_src` — 소스 (데이터 출처)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `src_id` | string | 소스 고유 식별자 (예: `src-kics`, `src-dutcheat`) |
| **PK** | `src_name` | string | 소스 명칭 (예: 경찰청 KICS, 더치트) |
| **PK** | `src_type` | string | `official` \| `osint` \| `petition` \| `internal` |
| **PK** | `reliability_tier` | int | 신뢰도 등급 1~5 (1=최고) |
| Attr | `collector` | string | 수집 담당자/시스템 |
| Attr | `collected_at` | string | 수집 일시 ISO8601 |
| Attr | `update_cycle` | string | 갱신 주기 (예: `daily`, `realtime`) |
| Attr | `contact` | string | 소스 담당 연락처 |

**reliability_tier**: `1`=공식수사자료 / `2`=기관연계 / `3`=전처리진정서 / `4`=OSINT / `5`=미확인제보

---

### CASE LAYER (2종)

#### N-02. `vt_case` — 사건

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `flnm` | string | 사건번호 (경찰청 표준 — 예: `2024-강남-12345`) |
| **PK** | `incdnt_no` | string | 관리번호 (KICS 내부 시퀀스) |
| Attr | `incdnt_nm` | string | 사건명 |
| Attr | `incdnt_typ_cd` | string | 사건유형코드 (경찰청 공식 분류 코드) |
| Attr | `crime_type` | string | 범죄유형 자유문자열 (예: 보이스피싱, 랜섬웨어) |
| Attr | `occrn_dt` | string | 범죄 발생일 ISO8601 |
| Attr | `damage_amount` | float | 피해금액 (원) |
| Attr | `case_summary` | string | 사건 요약 텍스트 |
| Attr | `status` | string | `수사중` \| `송치` \| `불기소` \| `종결` |
| Attr | `chrgdp_nm` | string | 담당 부서명 |
| Attr | `chrg_plcmn_nm` | string | 담당 경찰관 성명 |
| Attr | `police_station` | string | 접수 경찰서 |

#### N-03. `vt_petition` — 진정서

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `petition_id` | string | 진정서 고유 ID (예: `pet-2024-00001`) |
| Attr | `rcpt_dt` | string | 접수일 ISO8601 |
| Attr | `rcpt_channel` | string | 접수 채널 (`web` \| `fax` \| `visit` \| `112`) |
| Attr | `rcpt_station` | string | 접수 경찰서 |
| Attr | `crime_type_cd` | string | 진정서 기재 범죄유형 코드 |
| Attr | `damage_amt` | float | 진술 피해금액 (원, 미확인) |
| Attr | `incdt_dt` | string | 피해 발생일 (진술 기준) |
| Attr | `status` | string | `접수` \| `검토중` \| `사건전환` \| `기각` |
| Attr | `linked_case_id` | string | 전환된 사건 flnm (filed_as 엣지와 함께 사용) |
| Attr | `ocr_confidence` | float | OCR 추출 신뢰도 0.0~1.0 |
| Attr | `schema_version` | string | 전처리 스키마 버전 |

---

### PERSON LAYER (2종)

#### N-04. `vt_psn` — 인물

> ⚠️ `role` 속성 없음 — 역할은 반드시 엣지로 표현 (`suspect_in` / `victim_in` / `witness_in`)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `psn_id` | string | 인물 고유 ID (예: `psn-20240001`) |
| Attr | `korn_flnm` | string | 한글 성명 (경찰청 표준 필드명) |
| Attr | `name` | string | 영문명 또는 별칭 |
| Attr | `dob` | string | 생년월일 (YYYYMMDD) |
| Attr | `gender` | string | `M` \| `F` \| `U` |
| Attr | `nationality` | string | 국적 코드 (ISO 3166-1 alpha-2) |
| Attr | `rrno_hash` | string | 주민등록번호 SHA-256 해시 (원본 비저장) |
| Attr | `passport_no` | string | 여권번호 |
| Attr | `contact` | string | 연락처 |
| Attr | `aliases` | list | 별명·닉네임 목록 |
| Attr | `risk_level` | int | 위험도 점수 1~5 (수사관 수동 부여) |

#### N-05. `vt_org` — 조직

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `org_id` | string | 조직 고유 ID (예: `org-kookmin-bank`) |
| Attr | `org_name` | string | 조직명 (검색 키워드용, PK 아님) |
| Attr | `org_category` | string | `criminal` \| `financial` \| `government` \| `company` \| `telecom` |
| Attr | `inst_se_cd` | string | 기관구분코드 (경찰청 표준) |
| Attr | `brno` | string | 사업자등록번호 |
| Attr | `bank_cd` | string | 금융기관코드 (금융결제원 기준) |
| Attr | `addr` | string | 소재지 주소 |
| Attr | `member_count` | int | 구성원 수 (추정) |
| Attr | `activity_type` | string | 활동 유형 (예: 보이스피싱조직, 해킹팀) |
| Attr | `hierarchy_level` | int | 조직 계층 깊이 (1=최상위) |

---

### OBJECT LAYER (11종)

#### N-06. `vt_bacnt` — 계좌 (BankAccount)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `account_no` | string | 계좌번호 |
| **PK** | `bank_cd` | string | 금융기관코드 (금융결제원 기준 — 복합 PK) |
| Attr | `bank_nm` | string | 금융기관명 |
| Attr | `dpstr_nm` | string | 예금주 성명 |
| Attr | `account_type` | string | `일반` \| `사업자` \| `가상계좌` |
| Attr | `bacnt_opn_dt` | string | 개설일 |
| Attr | `is_burner` | bool | 대포통장 여부 |
| Attr | `is_frozen` | bool | 지급정지 여부 (금융감독원 등록) |
| Attr | `total_received` | float | 수신 총액 (원) |
| Attr | `total_sent` | float | 송금 총액 (원) |
| Attr | `transaction_cnt` | int | 거래 건수 |

#### N-07. `vt_crypto` — 가상자산 지갑 (CryptoWallet)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `wallet_addr` | string | 지갑 주소 |
| **PK** | `blockchain` | string | 블록체인 네트워크 (`BTC` \| `ETH` \| `TRX` \| `MATIC` 등) |
| Attr | `asset_type` | string | 주요 자산 유형 (예: `BTC`, `USDT`) |
| Attr | `exchange` | string | 연계 거래소명 (예: 업비트, 바이낸스) |
| Attr | `balance` | float | 잔액 (해당 자산 단위) |
| Attr | `risk_score` | float | 위험도 0.0~1.0 (체인분석 스코어) |
| Attr | `kyc_verified` | bool | 거래소 KYC 완료 여부 |
| Attr | `tx_cnt` | int | 총 트랜잭션 건수 |

#### N-08. `vt_ip` — IP 주소 (NetworkTrace)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `ip_addr` | string | IP 주소 (IPv4/IPv6) |
| Attr | `version` | string | `IPv4` \| `IPv6` |
| Attr | `isp` | string | 인터넷 서비스 제공자 |
| Attr | `asn` | string | AS 번호 (예: AS4766) |
| Attr | `country` | string | 국가 코드 ISO 3166-1 |
| Attr | `geo_region` | string | 지역 (시/도) |
| Attr | `city` | string | 도시 |
| Attr | `is_vpn` | bool | VPN 사용 여부 |
| Attr | `is_tor` | bool | Tor 노드 여부 |
| Attr | `is_proxy` | bool | 프록시 여부 |
| Attr | `is_hosting` | bool | 클라우드/호스팅 IP 여부 |
| Attr | `abuse_score` | int | 악용 신고 점수 0~100 (AbuseIPDB 기준) |

#### N-09. `vt_site` — 사이트/도메인 (WebTrace)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `url_addr` | string | 전체 URL (정규화된 형태) |
| Attr | `dmn_addr` | string | 도메인 주소 (서브도메인 포함) |
| Attr | `site_type` | string | `phishing` \| `c2` \| `scam` \| `normal` |
| Attr | `is_malicious` | bool | 악성 여부 |
| Attr | `risk_grd` | string | 위험 등급 (`HIGH` \| `MED` \| `LOW`) |
| Attr | `sign_kwrd` | string | 탐지 키워드 (예: "금융감독원", "대출") |
| Attr | `detct_dt` | string | 최초 탐지일 |
| Attr | `registrar` | string | 도메인 등록 기관 |
| Attr | `whois_org` | string | WHOIS 등록 조직 |
| Attr | `reg_dt` | string | 도메인 등록일 |
| Attr | `exp_dt` | string | 도메인 만료일 |
| Attr | `page_title` | string | 웹페이지 제목 |
| Attr | `page_hash` | string | 페이지 콘텐츠 해시 (변조 탐지용) |

#### N-10. `vt_file` — 파일 (FileTrace)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `hash_val` | string | SHA-256 해시 (유일 식별자) |
| Attr | `file_nm` | string | 파일명 |
| Attr | `file_extsn_nm` | string | 확장자 (예: `.exe`, `.hwp`) |
| Attr | `file_sz` | int | 파일 크기 (bytes) |
| Attr | `file_path` | string | 발견 경로 |
| Attr | `creat_dt` | string | 파일 생성일 |
| Attr | `mdfr_dt` | string | 파일 수정일 |
| Attr | `is_malicious` | bool | 악성코드 여부 |
| Attr | `vt_score` | string | VirusTotal 탐지율 (예: `45/72`) |

#### N-11. `vt_id` — 디지털 ID (DigitalID)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `id_val` | string | ID 값 (닉네임·계정명) |
| **PK** | `platform` | string | 플랫폼명 (`Telegram` \| `KakaoTalk` \| `Instagram` \| `Naver` 등) |
| Attr | `id_type` | string | `nickname` \| `username` \| `handle` \| `email_prefix` |
| Attr | `profile_url` | string | 프로필 URL |
| Attr | `is_active` | bool | 계정 활성 여부 |
| Attr | `real_name` | string | 계정 등록 실명 (확인된 경우) |

#### N-12. `vt_email` — 이메일 (Email)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `email_addr` | string | 이메일 주소 전체 |
| Attr | `domain` | string | 이메일 도메인 (예: `gmail.com`) |
| Attr | `provider` | string | 제공사 분류 (예: Google, Naver, 자체) |
| Attr | `is_disposable` | bool | 일회용 이메일 여부 (스팸 탐지) |

#### N-13. `vt_dev` — 기기 (Device)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `device_id` | string | 기기 고유 ID |
| Attr | `dev_type` | string | `smartphone` \| `pc` \| `tablet` \| `iot` |
| Attr | `imei` | string | IMEI 번호 (15자리, 이동통신 단말) |
| Attr | `mac_addr` | string | MAC 주소 |
| Attr | `model` | string | 기기 모델명 (예: Galaxy S24) |
| Attr | `os` | string | 운영체제 (`Android` \| `iOS` \| `Windows`) |
| Attr | `os_version` | string | OS 버전 |

#### N-14. `vt_telno` — 전화번호 (Phone)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `telno` | string | 전화번호 (숫자만, 예: `01012345678`) |
| Attr | `country_code` | string | 국가코드 (예: `+82`) |
| Attr | `telco_nm` | string | 통신사명 (SKT \| KT \| LGU+) |
| Attr | `join_typ_cd` | string | 가입 유형 (`선불` \| `후불` \| `알뜰폰`) |
| Attr | `is_registered` | bool | 정식 등록 여부 |
| Attr | `is_burner` | bool | 대포폰 의심 여부 |
| Attr | `subs_holder` | string | 명의자 성명 |
| Attr | `imsi` | string | IMSI 번호 (가입자 식별) |
| Attr | `spam_cnt` | int | 스팸 신고 건수 |

#### N-15. `vt_vhcl` — 차량 (Vehicle)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `vhclno` | string | 차량번호판 (예: `12가3456`) |
| Attr | `carmdl_nm` | string | 차종명 (예: 소나타) |
| Attr | `carmdl_dtl_nm` | string | 세부 모델명 |
| Attr | `color` | string | 차량 색상 |
| Attr | `ownr_nm` | string | 등록 소유자 성명 |
| Attr | `rgst_dt` | string | 등록일 |
| Attr | `stolen_yn` | bool | 도난 신고 여부 |

#### N-16. `vt_atm` — ATM

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `atm_id` | string | ATM 고유 관리번호 |
| Attr | `bank_nm` | string | 운영 금융기관명 |
| Attr | `bank_cd` | string | 금융기관코드 |
| Attr | `loc_id` | string | 위치 ID (`vt_loc.loc_id` 참조) |
| Attr | `address` | string | 설치 주소 |
| Attr | `is_outdoor` | bool | 실외 설치 여부 |

---

### LOCATION LAYER (1종)

#### N-17. `vt_loc` — 위치 (Location)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `loc_id` | string | 위치 고유 ID |
| Attr | `loc_type` | string | `address` \| `cell_tower` \| `cctv` \| `atm_loc` \| `transit` \| `poi` |
| Attr | `address` | string | 도로명 주소 |
| Attr | `lat` | float | 위도 (WGS84) |
| Attr | `lng` | float | 경도 (WGS84) |
| Attr | `place_name` | string | 장소명 |
| Attr | `sido_nm` | string | 시/도 명 |
| Attr | `sigungu_nm` | string | 시/군/구 명 |
| Attr | `bsst_nm` | string | 기지국명 (loc_type=cell_tower 시) |
| Attr | `bsst_addr` | string | 기지국 주소 (cell_tower 시) |
| Attr | `telecom` | string | 통신사 (cell_tower 시) |
| Attr | `cctv_id` | string | CCTV 관리번호 (loc_type=cctv 시) |
| Attr | `cctv_operator` | string | CCTV 운영기관 (cctv 시) |

---

### EVENT LAYER (5종)

> 모든 이벤트 노드: PK = `event_id` (단일화, V3.1 수정)
> RDB Bridge Key로 실제 원본 테이블 참조

#### N-18. `vt_transfer` — 이체 (Transfer)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `event_id` | string | 이체 이벤트 ID (ETL: `dlng-{dlng_sn}`) |
| BridgeKey | `dlng_sn` | string | RDB 원본 키 → TB_FIN_BACNT_DLNG |
| Attr | `dlng_amt` | float | 이체 금액 (원) |
| Attr | `blnc_amt` | float | 이체 후 잔액 |
| Attr | `dlng_se_cd` | string | 거래 구분 코드 (입금/출금/이체) |
| Attr | `dlng_dt` | string | 거래 일시 ISO8601 |
| Attr | `dlng_memo_cn` | string | 거래 메모 (보이스피싱 키워드 포함 가능) |
| Attr | `trrc_psnnm` | string | 거래 상대방 성명 |
| Attr | `atm_mng_no` | string | ATM 번호 (ATM 출금 시) |
| Attr | `hop_level` | int | 자금세탁 홉 단계 (0=원거래) |
| Attr | `is_suspicious` | bool | 의심 거래 플래그 |

#### N-19. `vt_call` — 통화 (Call)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `event_id` | string | 통화 이벤트 ID (ETL: `call-{call_sn}`) |
| BridgeKey | `call_sn` | string | RDB 원본 키 → TB_TELNO_CALL_DTL |
| Attr | `call_strt_dt` | string | 통화 시작 일시 ISO8601 |
| Attr | `call_dur_sec` | int | 통화 시간 (초) |
| Attr | `call_typ_cd` | string | `음성` \| `영상` \| `국제` |
| Attr | `dsptch_telno` | string | 발신 번호 |
| Attr | `rcptn_telno` | string | 수신 번호 |
| Attr | `bsst_loc_id` | string | 발신 기지국 위치 ID (`vt_loc.loc_id`) |

#### N-20. `vt_access` — 접속 (Access)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `access_id` | string | 접속 이벤트 ID (ETL: `lgn-{lgn_sn}`) |
| BridgeKey | `lgn_sn` | string | RDB 원본 키 → TB_SYS_LGN_EVT |
| Attr | `user_id` | string | 로그인 계정 ID |
| Attr | `result_cd` | string | 접속 결과 (`SUCCESS` \| `FAIL` \| `LOCKOUT`) |
| Attr | `service_nm` | string | 접속 서비스명 (예: 인터넷뱅킹, KICS) |
| Attr | `access_dt` | string | 접속 일시 ISO8601 |
| Attr | `action` | string | 수행 행위 (예: `login`, `transfer`, `withdraw`) |
| Attr | `user_agent` | string | 브라우저/앱 User-Agent |
| Attr | `status_code` | int | HTTP 상태 코드 |
| Attr | `bytes_sent` | int | 송신 바이트 |
| Attr | `bytes_recv` | int | 수신 바이트 |

#### N-21. `vt_msg` — 메시지 (Message)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `event_id` | string | 메시지 이벤트 ID (ETL: `msg-{msg_sn}`) |
| BridgeKey | `msg_sn` | string | RDB 원본 키 → TB_TELNO_SMS_MSG |
| Attr | `msg_type` | string | `SMS` \| `MMS` \| `카카오톡` \| `텔레그램` |
| Attr | `app_nm` | string | 메신저 앱명 |
| Attr | `room_id` | string | 채팅방 ID |
| Attr | `dsptch_dt` | string | 발송 일시 ISO8601 |
| Attr | `content_hash` | string | 내용 해시 (원문 비저장, 개인정보 보호) |
| Attr | `spam_yn` | bool | 스팸 메시지 여부 |
| Attr | `mentions_account` | string | 메시지 내 언급된 계좌번호 (NER 추출) |
| Attr | `mentions_url` | string | 메시지 내 포함된 URL (피싱 링크) |
| Attr | `sentiment_cd` | string | 감성 분류 (`위협` \| `유인` \| `일반`) |

#### N-22. `vt_movement` — 이동이벤트 (Movement)

| 구분 | 속성명 | 타입 | 설명 |
|------|--------|------|------|
| **PK** | `mov_id` | string | 이동이벤트 ID |
| Attr | `mov_type` | string | `lpr` (LPR차량) \| `cell_tower` (기지국) \| `transit` (교통카드) |
| Attr | `timestamp` | string | 이동 감지 일시 ISO8601 |
| Attr | `loc_id` | string | 감지 위치 ID (`vt_loc.loc_id`) |
| **lpr 전용** | `vhclno` | string | 감지된 차량번호 |
| **lpr 전용** | `cctv_id` | string | 촬영 CCTV ID |
| **lpr 전용** | `rcgn_sn` | string | 번호판 인식 시퀀스 |
| **cell 전용** | `telno` | string | 감지된 전화번호 |
| **cell 전용** | `evt_typ_nm` | string | 이벤트 유형 (발신/수신/위치등록) |
| **transit 전용** | `card_no` | string | 교통카드 번호 |
| **transit 전용** | `tk_pnm` | string | 승차 역/정류장 |
| **transit 전용** | `gf_pnm` | string | 하차 역/정류장 |

---

## 2. 엣지 공통 메타속성

모든 엣지에 아래 속성 체계가 적용됩니다.

```
[필수 — 모든 엣지]
  source_id       : str    — vt_src.src_id 참조 (MANDATORY)
  rec_created     : str    — ISO8601, DB 기록 시점 (MANDATORY)
  creation_method : str    — 'manual' | 'etl' | 'ocr_ner' | 'osint' | 'inference'

[신뢰도 — 소유·귀속 엣지]
  confidence      : float  — 0.0~1.0 (1.0 = 공식 문서)
  credibility     : int    — 1~5 (GraphAware 기준)
  verified        : bool   — False=추정, True=수사관·공식문서 확인

[이중시간 — 소유·관계 엣지]
  valid_from      : str    — 현실에서 유효 시작 (ISO8601)
  valid_to        : str    — 현실에서 유효 종료 (null = 현재진행)

[검증 정보 — verified=True 시 필수]
  verified_by     : str    — 수사관 ID
  verified_at     : str    — 검증 일시
```

---

## 3. 엣지 카탈로그

### 3.1 역할 엣지 — Case (3종)

> V3.0 핵심 변경: `vt_psn.role` 속성 → 엣지 타입으로 완전 이동

| 엣지명 | 방향 | 한국어 | 의미 | 법적 분류 |
|--------|------|--------|------|----------|
| `suspect_in` | Person → Case | 피의자 | 인물이 사건의 피의자로 관련 | 피의자정보 |
| `victim_in` | Person → Case | 피해자 | 인물이 사건의 피해자로 관련 | 피해자정보 |
| `witness_in` | Person → Case | 참고인 | 인물이 사건의 참고인으로 관련 | 참고인진술 |

---

### 3.2 엔티티 해소 엣지 (2종)

| 엣지명 | 방향 | 한국어 | 의미 | 생성 방식 |
|--------|------|--------|------|----------|
| `sameAs` | Person → Person | 동일인물 | 두 vt_psn이 동일 인물로 해소 | 추론 전용 |
| `contradicts` | Person → Person | 모순정보 | 두 vt_psn 정보가 모순 (명의도용 등) | 추론 전용 |

---

### 3.3 진정서 엣지 (2종)

| 엣지명 | 방향 | 한국어 | 의미 | 법적 분류 |
|--------|------|--------|------|----------|
| `filed_as` | Petition → Case | 사건전환 | 진정서가 수사 사건으로 전환됨 | 수사개시 |
| `clusters_with` | Petition → Petition | 유사진정서 | 유사 진정서 군집 연결 | — (추론) |

---

### 3.4 시간적 관계 엣지 (5종)

| 엣지명 | 방향 | 한국어 | 의미 | 법적 분류 |
|--------|------|--------|------|----------|
| `uses_id` | Person → DigitalID | ID사용 | 인물이 플랫폼 ID/닉네임 사용 | 신원확인 |
| `uses_email` | Person → Email | 이메일사용 | 인물이 이메일 주소 사용 | 신원확인 |
| `drives` | Person → Vehicle | 차량운행 | 인물이 차량 운행 (운행권) | 차량정보 |
| `recorded_in` | Vehicle\|Phone → Movement | 이동기록 | 차량/전화번호가 이동이벤트에 기록 | 위치정보 |
| `occurred_at` | Event → Location | 발생위치 | 이벤트의 발생 위치 | 위치정보 |

---

### 3.5 소유·귀속 엣지 (5종)

> Person → Object 방향. 소유권·사용권 표현.

| 엣지명 | 방향 | 한국어 | 의미 | 법적 분류 |
|--------|------|--------|------|----------|
| `owns` | Person → Any | 소유 | 범용 소유 (구체 엣지 우선 사용) | 피의자정보 |
| `owns_phone` | Person → Phone | 전화소유 | 인물이 전화번호를 소유 | 통신사실확인자료 |
| `has_account` | Person → BankAccount | 계좌소유 | 인물이 계좌를 소유 | 금융거래정보 |
| `used_ip` | Person → NetworkTrace | IP사용 | 인물이 IP 주소를 사용 | 디지털증거 |
| `owns_device` | Person → Device | 기기소유 | 인물이 기기를 소유/사용 | 디지털증거 |
| `owns_vehicle` | Person → Vehicle | 차량소유 | 인물이 차량을 법적 소유 (drives는 운행) | 차량정보 |

---

### 3.6 사건-증거 연결 엣지 (3종)

> Case → Object. 사건에 사용된 증거 직접 연결.

| 엣지명 | 방향 | 한국어 | 의미 | 법적 분류 |
|--------|------|--------|------|----------|
| `eg_used_account` | Case → BankAccount | 사건계좌 | 사건에 사용된 계좌 | 금융거래정보 |
| `eg_used_phone` | Case → Phone | 사건전화 | 사건에 사용된 전화번호 | 통신사실확인자료 |
| `eg_used_ip` | Case → NetworkTrace | 사건IP | 사건에 사용된 IP | 디지털증거 |

---

### 3.7 Actor-Organization 관계 엣지 (4종)

| 엣지명 | 방향 | 한국어 | 의미 | 법적 분류 |
|--------|------|--------|------|----------|
| `member_of` | Person → Organization | 조직소속 | 인물이 조직(범죄단체 포함)에 소속 | 피의자정보 |
| `works_at` | Person → Organization | 소속 | 인물의 합법적 소속 조직 | 내부자 식별 |
| `belongs_to` | BankAccount → Organization | 소속기관 | 계좌 소속 금융기관 | 금융거래정보 |
| `controls` | Person → BankAccount | 실지배 | 인물이 계좌를 실질적으로 지배 (명의와 무관) | 금융거래정보 |

---

### 3.8 행위 수행 엣지 (2종)

| 엣지명 | 방향 | 한국어 | 의미 |
|--------|------|--------|------|
| `performed` | Person → Event(Any) | 수행 | 인물이 이체/통화/접속 등 행위를 수행 |
| `performed_by` | Event → Person | 행위자 | 이벤트를 수행한 인물 (역방향) |

---

### 3.9 Fan-out 이벤트 패턴 엣지 (9종)

> 이벤트 노드를 중간에 두는 Fan-out 패턴. 동일 이체·통화의 다중 속성 표현.

#### 이체 (Transfer Fan-out)

| 엣지명 | 방향 | 한국어 | 의미 |
|--------|------|--------|------|
| `from_account` | BankAccount → Transfer | 출금계좌 | 이체의 출금 계좌 |
| `to_account` | Transfer → BankAccount | 입금계좌 | 이체의 입금 계좌 |

#### 통화 (Call Fan-out)

| 엣지명 | 방향 | 한국어 | 의미 |
|--------|------|--------|------|
| `caller` | Phone → Call | 발신 | 통화의 발신 번호 |
| `callee` | Call → Phone | 수신 | 통화의 수신 번호 |

#### 접속 (Access Fan-out)

| 엣지명 | 방향 | 한국어 | 의미 |
|--------|------|--------|------|
| `accessed_from` | Access → NetworkTrace | 접속IP | 접속의 출발 IP |
| `accessed_to` | Access → WebTrace | 접속대상 | 접속의 목적지 사이트 |

#### 메시지 (Message Fan-out)

| 엣지명 | 방향 | 한국어 | 의미 |
|--------|------|--------|------|
| `sent_msg` | Phone → Message | 발신 | 메시지 발신 번호 |
| `received_by` | Message → Person | 수신자 | 메시지 수신자 (인물) |
| `received_msg` | Message → Phone | 수신번호 | 메시지 수신 전화번호 |

---

### 3.10 증거 간 연결 엣지 (4종)

| 엣지명 | 방향 | 한국어 | 의미 | 생성 방식 |
|--------|------|--------|------|----------|
| `linked_to` | Any → Any | 연결됨 | 두 증거가 연결됨 (범용) | ETL |
| `accessed` | NetworkTrace → WebTrace | 접속 | IP에서 사이트에 접속 | ETL |
| `communicated_with` | NetworkTrace → NetworkTrace | 통신 | IP 간 통신 | ETL |
| `resolves_to` | WebTrace → NetworkTrace | DNS조회 | 도메인 → IP 조회 (DNS 표준 방향) | 추론 |

---

### 3.11 추론·집계 엣지 (5종)

| 엣지명 | 방향 | 한국어 | 의미 | 특이사항 |
|--------|------|--------|------|---------|
| `transferred_to` | BankAccount → BankAccount | 이체(다단계) | 다단계 자금세탁 추론 — **ETL 직접 생성 금지** | inferred=True, transitive |
| `related_case` | Case → Case | 관련사건 | 공유 증거 기반 사건 연결 | inference=True |
| `shared_resource` | Case → Case | 공유증거 | 두 사건이 동일 증거 공유 | 추론 전용 |
| `same_organization` | Person → Person | 동일조직 | 동일 범죄 조직 소속 추정 | 추론 전용 |
| `accomplice_of` | Person → Person | 공범 | 공범 관계 | 추론 전용 |

---

### 3.12 출처·연락처 엣지 (3종)

| 엣지명 | 방향 | 한국어 | 의미 |
|--------|------|--------|------|
| `sourced_from` | Any → Source | 출처 | 노드/엣지의 데이터 출처 (vt_src 참조) |
| `registered_to` | Phone → Person | 명의자 | 전화번호의 등록 명의자 |
| `contacted` | Phone → Phone | 통화 | 전화번호 간 통화 기록 (집계) |

---

### 3.13 메시지 분석 엣지 (1종)

| 엣지명 | 방향 | 한국어 | 의미 | 법적 분류 |
|--------|------|--------|------|----------|
| `mentions_account` | Message → BankAccount | 계좌언급 | 메시지 내 계좌번호 언급 | 보이스피싱 핵심증거 |

---

### 3.14 사칭 엣지 — V3.1 신설 (1종)

| 엣지명 | 방향 | 한국어 | 의미 | 법적 분류 |
|--------|------|--------|------|----------|
| `impersonates` | Phone\|DigitalID\|Email → Organization | 사칭 | 전화번호/계정/이메일이 특정 기관을 사칭 | 전기통신금융사기법 제3조 |

**`impersonates` 전용 속성**:

| 속성명 | 타입 | 설명 |
|--------|------|------|
| `impersonation_method` | string | `caller_id_spoofing` \| `fake_site` \| `fake_account` \| `email_spoofing` |
| `valid_from` | string | 사칭 활동 시작일 |
| `valid_to` | string | 사칭 활동 종료일 (null=현재진행) |

---

### 3.15 DEPRECATED 엣지 (3종) — 신규 생성 금지

| 엣지명 | 방향 | 대체 엣지 | 비고 |
|--------|------|----------|------|
| `involves` | Case → Person | `suspect_in` / `victim_in` / `witness_in` | 기존 데이터 읽기 호환용만 유지 |
| `involves_org` | Case → Organization | `member_of` / `works_at` | 동일 |
| `involves_device` | Case → Device | `owns_device` | 동일 |

---

## 4. 관계 매트릭스

> 행(From) → 열(To) 방향의 허용 엣지 목록

```
           │ vt_src │ vt_case │ vt_petition │ vt_psn │ vt_org │ vt_bacnt │ vt_crypto │ vt_ip │ vt_site │ vt_file │ vt_id │ vt_email │ vt_telno │ vt_vhcl │ vt_dev │ vt_atm │ vt_loc │ 이벤트류
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_psn     │        │ suspect_ │             │sameAs  │member_ │has_accnt │           │used_ip│         │         │uses_id│uses_email│owns_phone│owns_vhcl│owns_dev│        │        │performed
           │        │ victim_  │             │contrdct│works_at│controls  │           │       │         │         │       │          │          │drives   │        │        │        │
           │        │ witness_ │             │        │        │          │           │       │         │         │       │          │          │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_org     │        │         │             │        │        │          │           │       │         │         │       │          │          │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_case    │        │related_ │             │        │        │eg_used_  │           │eg_used│         │         │       │          │eg_used_  │         │        │        │        │
           │        │ shared_ │             │        │        │ account  │           │ _ip   │         │         │       │          │ phone    │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_petition│        │filed_as │clusters_    │        │        │          │           │       │         │         │       │          │          │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_bacnt   │        │         │             │        │belongs_│transferrd│           │       │         │         │       │          │          │         │        │        │        │from_acc
           │        │         │             │        │ to     │          │           │       │         │         │       │          │          │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_ip      │        │         │             │        │        │          │           │commun │accessed │         │       │          │          │         │        │        │        │
           │        │         │             │        │        │          │           │ _with │         │         │       │          │          │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_site    │        │         │             │        │        │          │           │resolv │         │         │       │          │          │         │        │        │        │
           │        │         │             │        │        │          │           │ es_to │         │         │       │          │          │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_telno   │        │         │             │regstrd │imprsnt │          │           │       │         │         │       │          │contacted │         │        │        │        │caller
           │        │         │             │ _to    │ ates   │          │           │       │         │         │       │          │          │         │        │        │        │sent_msg
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_id      │        │         │             │        │imprsnt │          │           │       │         │         │       │          │          │         │        │        │        │
           │        │         │             │        │  ates  │          │           │       │         │         │       │          │          │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_email   │        │         │             │        │imprsnt │          │           │       │         │         │       │          │          │         │        │        │        │
           │        │         │             │        │  ates  │          │           │       │         │         │       │          │          │         │        │        │        │
───────────┼────────┼─────────┼─────────────┼────────┼────────┼──────────┼───────────┼───────┼─────────┼─────────┼───────┼──────────┼──────────┼─────────┼────────┼────────┼────────┼──────────
vt_transfer│        │         │             │        │        │to_account│           │       │         │         │       │          │          │         │        │        │        │
vt_call    │        │         │             │        │        │          │           │       │         │         │       │          │callee    │         │        │        │        │
vt_access  │        │         │             │        │        │          │           │accsd_ │accessed_│         │       │          │          │         │        │        │        │
           │        │         │             │        │        │          │           │ from  │ to      │         │       │          │          │         │        │        │        │
vt_msg     │        │         │             │rcvd_by │        │mntns_acc │           │       │         │         │       │          │rcvd_msg  │         │        │        │        │
```

---

## 5. 수사 패턴 다이어그램

### 패턴 A — 자금세탁 N-Hop 추적

```
[vt_psn: 홍길동]
    │ suspect_in
    ▼
[vt_case: 2024-1234]
    │ eg_used_account
    ▼
[vt_bacnt: 계좌A]
    │ from_account          ← Fan-out 시작
    ▼
[vt_transfer: T-001]
    │ to_account            ← Fan-out 종료
    ▼
[vt_bacnt: 계좌B]          ← 세탁 1홉
    │ from_account
    ▼
[vt_transfer: T-002]
    │ to_account
    ▼
[vt_bacnt: 계좌C]          ← 세탁 2홉

※ transferred_to (inferred) : 계좌A ──→ 계좌C  [추론 엣지, hop_level=2]
```

---

### 패턴 B — 사칭 보이스피싱 (V3.1 신설)

```
[vt_psn: 피의자]
    │ suspect_in
    ▼
[vt_case: 2024-5678]
    │ eg_used_phone
    ▼
[vt_telno: 1588-9999]     ← 사칭 번호
    │ impersonates ────────────────────────→ [vt_org: 국민은행]
    │ caller                                        ↑
    ▼                                     사칭 대상 기관
[vt_call: CALL-001]
    │ callee
    ▼
[vt_telno: 010-1234-5678] ← 피해자 번호
    │ registered_to
    ▼
[vt_psn: 피해자]
    │ victim_in
    ▼
[vt_case: 2024-5678]
```

---

### 패턴 C — 디지털 신원 추적

```
[vt_psn: 용의자]
    ├─ uses_id ──────→ [vt_id: @hacker123 / Telegram]
    │                       │ impersonates ──→ [vt_org: 금융감독원]
    ├─ used_ip ──────→ [vt_ip: 1.2.3.4]
    │                       │ accessed ──────→ [vt_site: fake-fss.kr]
    │                       │                      │ resolves_to ──→ [vt_ip: 5.6.7.8]
    └─ has_account ──→ [vt_bacnt: 계좌A]
                            │ belongs_to ────→ [vt_org: 토스뱅크]
```

---

### 패턴 D — 위치 기반 공범 추론

```
[vt_movement: MOV-001 {mov_type: 'lpr'}]
    │ recorded_in ←── [vt_vhcl: 12가3456]
    │                       │ owns_vehicle
    │                       ▼
    │                  [vt_psn: 피의자A]
    │ occurred_at
    ▼
[vt_loc: 서울 강남구 ATM 앞]

[vt_movement: MOV-002 {mov_type: 'cell_tower'}]
    │ recorded_in ←── [vt_telno: 010-9999-8888]
    │ occurred_at
    ▼
[vt_loc: 서울 강남구 ATM 앞]   ← 동일 위치·시간대

※ 추론: 두 인물이 동일 시공간 → same_organization 엣지 후보
```

---

## 부록. 엣지 수 집계

| 구분 | 수량 | 엣지명 |
|------|------|--------|
| 역할 엣지 | 3 | suspect_in, victim_in, witness_in |
| 엔티티 해소 | 2 | sameAs, contradicts |
| 진정서 | 2 | filed_as, clusters_with |
| 시간적 관계 | 5 | uses_id, uses_email, drives, recorded_in, occurred_at |
| 소유·귀속 | 6 | owns, owns_phone, has_account, used_ip, owns_device, owns_vehicle |
| 사건-증거 | 3 | eg_used_account, eg_used_phone, eg_used_ip |
| Actor-Org | 4 | member_of, works_at, belongs_to, controls |
| 행위 수행 | 2 | performed, performed_by |
| Fan-out 이벤트 | 9 | from_account, to_account, caller, callee, accessed_from, accessed_to, sent_msg, received_by, received_msg |
| 증거 간 연결 | 4 | linked_to, accessed, communicated_with, resolves_to |
| 추론·집계 | 5 | transferred_to, related_case, shared_resource, same_organization, accomplice_of |
| 출처·연락처 | 3 | sourced_from, registered_to, contacted |
| 메시지 분석 | 1 | mentions_account |
| **사칭 (V3.1 신설)** | **1** | **impersonates** |
| **활성 합계** | **50** | |
| DEPRECATED | 3 | involves, involves_org, involves_device |
| **전체 합계** | **53** | |
