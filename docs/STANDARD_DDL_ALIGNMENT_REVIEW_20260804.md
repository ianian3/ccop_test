# CyberCOP 표준 DDL ↔ 온톨로지 ↔ 적재코드 3자 정합 검토

> **작성일**: 2026-08-04
> **대상**: `docs/CYBERCOP_STANDARD_TABLE_DDL_20260804.sql`(DA팀 V3.7 표준 DDL, 51테이블) · `docs/6. CCOP-DE53-테이블명세서...xlsx`(컬럼정의서 근거문서)
> **기준**: 온톨로지 SoT(`ontology_service.py` 25노드) · 적재코드(`rdb_service.py` INSERT, `rdb_to_graph_service.py` SELECT)
> **목적**: 표준 DDL의 CCOP 적용 갭 진단 + **마이그레이션 SoT 크로스워크** 확정

---

## 0. 핵심 결론

**명세서↔DDL은 완벽 정합(51테이블/전컬럼 일치)이나, 적재코드는 표준 DDL과 테이블명 교집합이 0건** — 코드는 완전히 다른 레거시 스키마(public V2 / test_v40)로 동작 중이다. 온톨로지 개념 매핑은 대체로 성립하나 4개 도메인(마약·OSINT평판·엔티티해소·범죄캠페인)이 노드 미반영, provenance는 개념 호환되나 컬럼명·값어휘·정규화수준이 상이하다.

| 정합 축 | 상태 | 조치 |
|---|---|---|
| 명세서 ↔ DDL | ✅ 완전 일치(51테이블/전컬럼/타입/PK) | **불요** — SoT 신뢰 |
| DDL ↔ 온톨로지 | △ 핵심 1:1 성립, 4도메인 미반영 | P1/P2 |
| DDL ↔ 적재코드 | ❌ 테이블명 0% 정합 | **P0** |

---

## 1. 크로스워크 매핑표 — 테이블 (마이그레이션 SoT)

온톨로지 노드 기준. 적재는 2종 레거시 스키마(public V2 대문자 / test_v40 소문자) 병존.

| 온톨로지 노드 | 표준 DDL (목표) | 적재 public V2 | 적재 test_v40 | 명명 갭 |
|---|---|---|---|---|
| vt_src | `TB_DATA_SOU_A` | TB_DATA_SRC | — | SOU_A/SRC |
| vt_case | `TB_INCDNT_M` | TB_INCDNT_MST | tb_incdnt_mst | _M/_MST |
| vt_petition | `TB_PETTN_M` | TB_PETTN_MST | — | _M/_MST |
| vt_psn | `TB_PSN_M` | TB_PRSN | tb_prsn | **PSN/PRSN** |
| vt_org | `TB_INST_M` | TB_INST | — | _M |
| vt_bacnt | `TB_FNNC_BACNT_M` | TB_FIN_BACNT | tb_fin_bacnt | **FNNC/FIN** |
| vt_telno | `TB_TELNO_M` | TB_TELNO_MST | tb_telno_mst | _M/_MST |
| vt_ip | `TB_IP_ADDR_M` | ⚠ 부재(파생) | — | 적재 IP마스터 없음(접속/도메인서 파생) |
| vt_site | `TB_WEB_DMN_M` | TB_WEB_DMN | — | _M |
| vt_file | `TB_DGTL_FILE_LIST_M` | TB_DGTL_FILE_INVNT | — | LIST/INVNT |
| vt_vhcl | `TB_VHCL_M` | TB_VHCL_MST | — | _M/_MST |
| vt_id | `TB_DGTL_ID_M` | TB_DGTL_ID_MST | — | _M/_MST |
| vt_email | `TB_EML_ADDR_M` | TB_EMAIL_MST | — | **EML/EMAIL** |
| vt_crypto | ⚠ **부재** | TB_CRYPTO_WALLET_MST | — | 표준 마스터 없음 |
| vt_dev | `TB_ISTR_M` | TB_DEV_MST | — | **ISTR/DEV** |
| vt_atm | `TB_ATM_M` | TB_ATM_MST | — | _M/_MST |
| vt_loc | `TB_PSTN_M` | TB_LOC_MST | — | **PSTN/LOC** |
| vt_transfer | `TB_FNNC_BACNT_DLNG_T` | TB_FIN_BACNT_DLNG | tb_fin_bacnt_dlng | 명명 상이 |
| vt_call | `TB_TELNO_CALL_D` | TB_TELNO_CALL_DTL | tb_telno_call_dtl | _D/_DTL |
| vt_msg | `TB_TELNO_SMS_MSG_T` + `TB_CTT_MSG_T` | TB_TELNO_SMS_MSG + TB_CHAT_MSG | — | **N:1** |
| vt_access | `TB_SYS_LGN_EVT_T` | TB_SYS_LGN_EVT | — | _T |
| vt_movement | `TB_MOBL_PSTN_EVT_T` + `TB_TRFC_CARD_MVMN_T` + `TB_VHCL_NOPLT_RECG_EVT_T` | TB_GEO_MBL_LOC_EVT + TB_VHCL_LPR_EVT | — | **N:1** |
| vt_impersonation | `TB_FAAS_EVT_T` | TB_IMPRSN_REL | — | 명명 상이 |
| pt_cluster | `TB_PETTN_CLSTR_T` | TB_PETTN_CLSTR | — | _T |
| site_cluster | `TB_OSINT_SITE_CLSTR_M` | (미적재) | — | — |

**완전일치 0건** — 가장 가까운 `TB_SYS_LGN_EVT`조차 표준은 `_T` 접미사 차이.

## 2. 크로스워크 매핑표 — 주요 식별 컬럼

**정합 방향이 테이블마다 다름** (일괄 규칙 불가):

| 개념 | 온톨로지 canonical | 표준 DDL | 적재(public/test_v40) | 비고 |
|---|---|---|---|---|
| 계좌번호 | `account_no` | `ACTNO` | BACNT_NO / bacnt_no | **4자 전부 상이** |
| 은행코드 | — | `BANK_CD` | bnk_cd | |
| 예금주 | — | `DPSTR_NM` | dpstr | |
| 전화번호 | `telno` | `DSPTCH_TELNO` | telno | **표준만 이질**(발신번호=PK) |
| 사람ID | `psn_id` | `PSN_ID` ✓ | prsn_id / id | **적재가 이질** |
| 통화지속 | — | `CALL_HR`(char6, 시:분:초) | CALL_DUR_SEC(int 초) / duration | 타입·의미 불일치 |
| 이체 상대계좌 | — | `ADDRSE_ACTNO` | TRRC_BACNT_NO | |

## 3. 크로스워크 매핑표 — Provenance

CCOP는 **inline 비정규화**(전 테이블 6컬럼, `scripts/v40_meta_patch.sql`), 표준은 **SRC_ID FK + 마스터 정규화**(핵심 30테이블 FK-only, 17테이블 inline, 4테이블 없음).

| CCOP inline | 표준 DDL | 매핑 | 마찰 |
|---|---|---|---|
| `source_id`(64) | `SRC_ID`(200) | ✓ | 길이 |
| `source_domain` | `SRC_TYP_CD`(마스터)/`SRC_DMN_ADDR`(inline) | △ | **값어휘**: 계보(investigation/osint/partner/inference) vs 시스템태그(KICS/OSINT/DIGITAL) |
| `reliability_tier`(1~4) | `CFRT_GRD_CD`(1~5) | △ | **척도** 1~4 vs 1~5 |
| `collected_at` | `CLCT_DT` | ✓ | |
| vt_src 노드 | `TB_DATA_SOU_A` | ✓ | |

**전환 영향**: 핵심 30테이블이 inline 컬럼이 없어, 노드에 source_domain/reliability_tier를 채우려면 **`TB_DATA_SOU_A` JOIN 필수**(현 코드는 inline 전제). 값어휘·척도 리매핑 로직 신설. 현재 tier가 코드에 `1` 하드코딩(`rdb_service.py:111,124,135`)이라 표준 등급 다양성 미반영.

## 4. 온톨로지 미반영 도메인 (확장 후보)

| 도메인 | 표준 DDL | 온톨로지 현황 | 판정 |
|---|---|---|---|
| **마약** | TB_NCTC_SLANG_M, TB_NCTC_DLNG_T | **완전 미반영** (히트 0) | **P1 노드·엣지 신설** |
| OSINT 평판 7종 | TB_OSINT_*_RPUTTN_T | 노드 없음(속성/vt_src로 흡수 설계) | P2 속성 매핑 문서화 |
| 엔티티해소 | TB_SAME_PRSN_RSLV_T, TB_CRSH_INFO_T | `sameAs`/conflict **엣지로 존재** | P2 RDB테이블→엣지 변환 정의 |
| 범죄캠페인 | TB_CRIM_CMPGN_CLSTR_M | `belongs_to_campaign` 엣지만, 전용노드 없음 | P2 |
| 운영/참조 | TB_DATA_CLCT_L, TB_DATA_QC_L, TB_COM_C, TB_BANK_C | (노드 대상 아님) | 조치 불요 |

---

## 5. 마이그레이션 로드맵·리스크

### P0 — 명명 정합 (최대 작업·리스크)
- 적재코드↔표준 테이블명 **0% 정합**. `rdb_service.py` 전 INSERT(2스키마) + `rdb_to_graph_service.py` 매핑표(`:57-92`)+전 SELECT를 표준 `TB_*_M/_T/_D`로 재작성.
- **선행조건**: 위 §1·§2 크로스워크를 코드가 참조하는 **단일 매핑 상수(SoT)로 확정** — 하드코딩 산재 방지.
- 식별 컬럼은 방향이 테이블마다 달라 **컬럼 단위 매핑표 필수**.

### P1
- **Provenance 정규화 전환**: `TB_DATA_SOU_A` JOIN 도입 + 값어휘/척도 리매핑 + source_id 길이(64→200).
- **vt_crypto 마스터 부재**: 표준에 지갑 마스터 없음 → 적재원천 재설계(평판/위험 테이블 대체 여부 결정).
- **마약 도메인**: 노드·엣지 신설.

### P2
- 엔티티해소(2테이블)·범죄캠페인(1) → 그래프 엣지 변환 규칙(온톨로지에 엣지 이미 존재, 저리스크).
- OSINT 평판 7종 → 노드 속성 흡수 매핑 문서화.

### 조치 불요
- 명세서↔DDL (완전 일치, 검증 종결).

---

## 부록 — 검증 근거
- 적재 매핑표 실측: `rdb_to_graph_service.py:57-92` (public V2 23매핑)
- test_v40 스키마: `rdb_service.py:105-257`
- provenance inline 패치: `scripts/v40_meta_patch.sql`
- 표준 DDL·명세서: 51테이블 완전 일치(컬럼정의서 662행 대조)
