# CCOP GDB 온톨로지 매핑 가이드 v2 (RDB 표준화 v2 연동)

> **Version**: 2.0  
> **Date**: 2026-02-23  
> **기반 문서**: `RDB_DATA_STANDARDIZATION_v2.md`

본 문서는 새롭게 정의된 **27개의 RDB 표준 테이블(v2)**을 KICS 기반 4-Layer 그래프 데이터베이스(GDB) 온톨로지로 변환하기 위한 **노드(Node) 및 엣지(Edge) 매핑 표준**을 정의합니다.

---

## 1. 노드(Node) 매핑 표준 (KICS 4-Layer)

RDB의 각 마스터/상세 테이블은 GDB의 특정 노드(Entity) 레이블로 변환됩니다.

### 1-1. Case Layer (사건 중심)
| RDB 테이블 (Source) | GDB 노드 라벨 (Target) | 식별키 (Key) | 주요 속성 (Properties) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| `TB_INCDNT_MST` | `vt_case` (사건) | `INCDNT_NO` | 사건명(`INCDNT_NM`), 발생일시, 담당자 | 수사의 중심 앵커 노드 |

### 1-2. Actor Layer (행위자)
| RDB 테이블 (Source) | GDB 노드 라벨 (Target) | 식별키 (Key) | 주요 속성 (Properties) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| `TB_PRSN` | `vt_psn` (인물) | `PRSN_ID` | 성명(`KORN_FLNM`), 구분코드(`PRSN_SE_CD`) | 용의자, 피해자 등 자연인 |
| `TB_INST` | `vt_org` (조직) | `INST_ID` | 기관명(`INST_NM`), 사업자번호 | 법인, 은행, 통신사 등 |
| `TB_CHAT_MSG` (발신자) | `vt_persona` (페르소나)| `DSPTCH_USER_ID`| 앱명(`APP_NM`) | 디지털 채팅 ID, 닉네임 |

### 1-3. Evidence Layer (증거/객체)
| RDB 테이블 (Source) | GDB 노드 라벨 (Target) | 식별키 (Key) | 주요 속성 (Properties) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| `TB_FIN_BACNT` | `vt_bacnt` (계좌) | `BACNT_NO` | 은행코드(`BANK_CD`), 예금주명 | 금융 계좌 |
| `TB_TELNO_MST` | `vt_telno` (전화번호) | `TELNO` | 통신사명, 가입유형 | 전화번호 마스터 |
| `TB_VHCL_MST` | `vt_vhcl` (차량) | `VHCLNO` | 차종명, 소유자명 | 이동 수단 (차량) |
| `TB_WEB_DMN` / `URL`| `vt_site` (웹사이트) | `DMN_ADDR` / `URL`| 설명, 악성여부 | 웹 도메인 및 URL |
| `TB_SYS_LGN_EVT` | `vt_ip` (IP주소) | `CNNT_IP_ADDR` | 접속IP | 접속 출발 IP |
| `TB_DGTL_FILE_INVNT`| `vt_file` (파일) | `HASH_VAL` | 파일명, 확장자, 크기 | 디지털 압수물/첨부파일 |

### 1-4. Action/Event Layer (행위/이벤트 - Dynamic)
| RDB 테이블 (Source) | GDB 노드 라벨 (Target) | 식별키 (Key) | 주요 속성 (Properties) | 설명 |
| :--- | :--- | :--- | :--- | :--- |
| `TB_FIN_BACNT_DLNG` | `vt_transfer` (이체) | `DLNG_SN` | 거래일시, 거래금액, 구분 | 자금 이체/결제 행위 |
| `TB_TELNO_CALL_DTL` | `vt_call` (통화) | `CALL_SN` | 통화시작일시, 지속시간 | 통신 내역 |
| `TB_TELNO_SMS_MSG` | `vt_msg` (메시지) | `SMS_SN` | 발신일시, 내용, 스팸여부 | SMS 문자 송수신 |
| `TB_CHAT_MSG` | `vt_msg` (메신저) | `CHAT_SN` | 채팅방ID, 발신일시, 내용 | 카카오/텔레그램 대화 |
| `TB_GEO_MBL_LOC_EVT`| `vt_loc_evt` (위치이벤트)| `LOC_EVT_SN` | 기지국위경도, 발생일시 | 기지국 접속 위치 기록 |
| `TB_VHCL_LPR_EVT` | `vt_lpr_evt` (LPR인식) | `RCGN_SN` | 인식일시, 위치 위경도 | 차량 방범CCTV 인식 이벤트 |

---

## 2. 엣지(Edge) 생성 및 매핑 (Relationships)

테이블 간의 외래키(FK) 및 조인 논리를 통해 그래프의 **동적 엣지**를 자동 생성합니다.

### 2-1. 사건 구조 (Case $\leftrightarrow$ Entity)
*   `[vt_case]` $\xrightarrow{involves}$ `[vt_psn]` : 사건 마스터와 사람 테이블 연결 (피해자/피의자)
*   `[vt_case]` $\xrightarrow{used\_evidence}$ `[vt_bacnt]` : 사기 피해 신고(`TB_FRD_VCTM_RPT`)의 용의계좌 참조
*   `[vt_case]` $\xrightarrow{used\_evidence}$ `[vt_telno]` : 사기 피해 신고의 용의전화번호 참조

### 2-2. 인물 및 자산 소유 (Actor $\leftrightarrow$ Evidence)
*   `[vt_psn]` $\xrightarrow{has\_account}$ `[vt_bacnt]` : `TB_FIN_BACNT.DPSTR_NM` (예금주)와 사람 일치 시
*   `[vt_psn]` $\xrightarrow{owns\_phone}$ `[vt_telno]` : `TB_TELNO_JOIN.JOIN_PSNNM` (가입자)와 사람 일치 시
*   `[vt_psn]` $\xrightarrow{owns\_vehicle}$ `[vt_vhcl]` : `TB_VHCL_MST.OWNR_NM` (차량소유자) 연동
*   `[vt_psn]` $\xrightarrow{uses\_id}$ `[vt_persona]` : 채팅/시스템 로그인 시 사용하는 ID 귀속

### 2-3. 이벤트 및 이력 (Event 연관성)
*   **자금 이체 (`TB_FIN_BACNT_DLNG`)**
    *   `[vt_transfer]` $\xrightarrow{from\_account}$ `[vt_bacnt]` (출금계좌)
    *   `[vt_transfer]` $\xrightarrow{to\_account}$ `[vt_bacnt]` (입금계좌)
*   **통화 기록 (`TB_TELNO_CALL_DTL`)**
    *   `[vt_call]` $\xrightarrow{caller}$ `[vt_telno]` (발신번호)
    *   `[vt_call]` $\xrightarrow{callee}$ `[vt_telno]` (수신번호)
*   **위치 및 이동 (`TB_GEO_MBL_LOC_EVT`, `TB_VHCL_LPR_EVT`)**
    *   `[vt_telno]` $\xrightarrow{located\_at}$ `[vt_loc_evt]` (시간대별 기지국 위치)
    *   `[vt_vhcl]` $\xrightarrow{detected\_at}$ `[vt_lpr_evt]` (시간대별 차량 인식 위치)
*   **디지털 접속 (`TB_SYS_LGN_EVT`, `TB_WEB_ATCH`)**
    *   `[vt_persona]` $\xrightarrow{accessed\_from}$ `[vt_ip]` (로그인 IP 기록)
    *   `[vt_site]` $\xrightarrow{contains\_file}$ `[vt_file]` (웹 첨부파일/해시 연동)

---

## 3. 고급 그래프 추론 규칙 (AI Inference)

RDB에 직접적인 관계 테이블이 없어도 GDB 특성을 살려 아래 관계를 자동 추론(Infer)하여 엣지로 추가합니다.

1.  **자금 세탁 경로 추론 (`transitive_transfer`)**
    *   `[vt_bacnt] -[to_account]- [vt_transfer] -[from_account]- [vt_bacnt]` 패턴이 3-hop 이상 지속될 경우, 첫 계좌와 마지막 계좌를 직접 잇는 은닉 엣지 생성
2.  **공범/동일조직 추론 (`accomplice_of`)**
    *   서로 다른 `vt_psn`(인물)이 동일한 `vt_ip`(접속IP) 혹은 동일한 `vt_loc_evt`(기지국 위치)를 비슷한 시간대에 자주 점유하는 경우 신뢰도(weight)를 부여하여 공범 엣지 생성
3.  **대포폰/대포차 판별 (`mismatch_owner`)**
    *   `vt_telno`의 명의자(`has_owner`)와 실제 통화 빈도가 높은 인물 그룹이 상이할 경우 '대포폰 의심' 속성을 노드에 부여

## 4. 백엔드 코드 수정 적용 방안
이러한 v2 모델로 시스템을 전면 개편할 경우 다음 파일들이 중점적으로 리팩토링 되어야 합니다.
*   `app/services/ontology_service.py`: `ENTITIES` 딕셔너리에 `vt_vhcl`, `vt_loc_evt` 등 신규 노드 추가. `RELATIONSHIPS` 룰셋 업데이트.
*   `app/services/rdb_service.py`: `tb_` 접두어가 붙은 27개 구조를 위한 쿼리 생성로직 전면 개편, ON CONFLICT (UPSERT) 로직 복원.
*   `app/services/rdb_to_graph_service.py`: 복잡해진 조인 조건(예: 계좌 이동시 `TB_FIN_BACNT_DLNG` 파싱)을 노드-엣지 배열로 변환하는 Cypher 빌더 교체.
