# CCOP RDB→GDB→표준화 파이프라인 현황·갭 설계서 — **엘리스 운영 기준** (2026-08-13)

> **기준**: 엘리스 앱서버 `elicer@…:~/ccop_app`, 커밋 **`52866b3`** (feat/legal-rag-chroma), **온톨로지 V4.0**.
> ⚠️ 로컬(개발) 저장소는 `baa2c16`에서 분기해 V4.5/V4.6·`STANDARD_TABLE_MAP`을 도입했으나 **엘리스 미배포**. 본 설계서는 **운영본(엘리스) 실측** 기준이며, 로컬-엘리스 배포 갭을 §0에 명시.
> 조사: 엘리스 코드 sha256 대조본(scp) + `git show 52866b3` + 원격 grep. line 번호는 엘리스 파일 기준.

---

## 0. 로컬 ↔ 엘리스 분기 (배포 갭) — **가장 중요**

`baa2c16` 이후 두 갈래로 분기, 서로의 작업이 미반영:

| 항목 | **엘리스 운영 (52866b3)** | 로컬 개발 (v4.6 계열) |
|---|---|---|
| 온톨로지 버전 | **V4.0** (최고 표기 `V4.0`) | V4.5 + V4.6 항목 |
| `STANDARD_TABLE_MAP` | **없음** (0건) | 있음 (단 미연결) |
| ip_role bitemporal / used_ip valid_from·to | **없음** | 있음 |
| transferred_to 이체시각(first/last_dlng_dt) | **없음** | (문서·수동 적재만) |
| vt_access access_type/subtype, G5 유효구간 | **없음** | 있음(정의) |
| **fresh 스테이징 + `norm_telno`(선행0 보존)** | **있음** (52866b3) | **없음** |
| viz 축약/부분펼침 (d358053·5da2672) | 있음 | 없음 |

→ 운영본은 **온톨로지 V4.0 세대**. 로컬의 V4.5/V4.6 개선이 배포 안 됨. 반대로 엘리스의 52866b3 표준화·viz가 로컬에 역병합 안 됨. **양방향 미동기**.

---

## 1. 파이프라인 개요 (엘리스)

| 경로 | 진입 API | 서비스 메서드 | 기본 소스 |
|---|---|---|---|
| RDB→GDB 전량 | `POST /api/rdb/to-graph` | `RdbToGraphService.transfer_data()` (`:147`) | **test_v40** |
| CSV→RDB(L2 표준화) | `routes_api` (52866b3) | `rdb_service` INSERT + **fresh 스테이징** | test_v40 소문자 `tb_*` |
| CSV→GDB | `ETLService.import_csv()` | 노드/엣지 MERGE |

- 버전 스탬프: 로더 헤더 **v3.5·V3.2 POLE**(`:2,4,144`), 온톨로지 **V4.0**.

---

## 2. 3단계 현황 (엘리스 V4.0)

### 2.1 RDB 적재 (transfer_data, Phase 1–6)
- POLE 6계층 vt_* 라벨, Phase 1(노드) ~ 6(v3.0 src/petition/OSINT) + `_postprocess_v37/v40`(4건 확인).
- 소스 테이블: test_v40 소문자 + public V2 대문자 **혼용**.
- fallback: `rdb_*` 레거시 축약 매핑.

### 2.2 GDB 변환 (POLE)
- Role-as-Edge(`suspect_in/victim_in/witness_in`), 추론엣지(`related_case`·`resolves_to`·`belongs_to`), `_postprocess_v37`(pt_cluster·relay).
- INFERENCE_RULES 카탈로그는 SoT에만, 탐지엣지 적재는 미구현(로컬과 동일).

### 2.3 표준화 — **52866b3로 개선됨 (엘리스 고유)**
- **`norm_telno`** (52866b3 신규): 온톨로지 SoT(vt_telno) 기준 **no_hyphen_e164, 숫자만 남김(선행 0 보존)**. ⚠️ 주석: "CSV 숫자추론으로 선행0 소실된 값은 복원 불가".
- **fresh 스테이징 옵션** (52866b3): `fresh=1`(기본) 첫 파일 적재 전 test_v40 초기화 → 업로드분만으로 그래프 구성. 여러 파일이면 첫 파일만 clear, 이후 누적. `fresh=0` 누적.
- **L2 표준화 레이어**: `layer_results['L2']='L2 표준화 (test_v40 RDB)'`.
- `StandardCodeMapper.map_bank_code` 은행명→금결원 표준코드.
- ⚠️ `STANDARD_TABLE_MAP`(표준 DDL 크로스워크)은 **엘리스에 아직 없음** — 표 기반 표준화는 로컬 전용.

---

## 3. 갭 (엘리스 운영 기준)

### 🔴 P0-1 · 표준 DDL 정합 (미착수)
- 적재코드는 레거시 test_v40/public V2만 사용, 표준 DDL 테이블명(`TB_PSN_M`…) 0건.
- **`STANDARD_TABLE_MAP` 자체가 엘리스에 없음** → 로컬은 "정의만·미연결", 엘리스는 "미도입". 즉 **로컬보다 한 단계 이전**.
- 근거: `docs/STANDARD_DDL_ALIGNMENT_REVIEW_20260804.md:12` "교집합 0건 = P0".

### 🔴 P0-2 · Silent loss (미존재시 skip 무음)
- `try/except: rollback` + "미존재시 skip" 가드 **94건**(엘리스 실측). public V2 대문자 테이블(TB_SYS_LGN_EVT·TB_INST·TB_TELNO_SMS_MSG·TB_VHCL_MST·TB_WEB_DMN·TB_DATA_SRC·TB_PETTN_MST·TB_OSINT_*·TB_INCDNT_EVID)이 소스에 없으면 stats 미반영 무음 누락.
- ※ 단, 52866b3 fresh 스테이징으로 "이 업로드분만" 구성 시 결측 범위가 명확해지는 부분 완화.

### 🟠 P1-1 · Provenance(source_id) 소실
- source_id 수집 SELECT **14건**(엘리스). **vt_msg 미수집 확인**: `SELECT SMS_SN, DSPTCH_TELNO, RCPTN_TELNO, DSPTCH_DT, MSG_CN FROM TB_TELNO_SMS_MSG` (`:705`) — source_id 없음. vt_access·vt_ip·vt_org·vt_vhcl·vt_movement·vt_site·vt_file 동일 패턴.
- tier 획일화: RDB 경로 `tier=1` 고정.

### 🟠 P1-2 · 온톨로지 배포 갭 (V4.0 → V4.6 미반영)
- 엘리스는 V4.0이라 **로컬의 v4.5/v4.6 개선(ip_role bitemporal·시간순 연속성·이체시각·access subtype·유효구간)이 전혀 없음**. 로컬 설계서의 "v4.6 로더 미반영"은 엘리스엔 애초에 대상 없음 = **버전 세대 차**.

### 🟡 P2 · 속성명 불일치
- fallback `actno` vs canonical `account_no` (로컬과 동일 구조).

---

## 4. 로드맵 (운영 기준 권장 순서)

1. **양방향 동기화 결정 (선결)**: 로컬 V4.6 vs 엘리스 52866b3를 **어느 브랜치로 통합**할지. 현재 양쪽이 서로의 개선을 잃고 있음 — 병합 전략 없이는 어떤 갭 수정도 재분기 위험.
2. **P0-2 silent-loss 가시화**: skip → stats `skipped_tables` 기록 (52866b3 스테이징과 궁합 좋음).
3. **P1-1 provenance**: vt_msg 등 8라벨 SELECT에 source_id 추가.
4. **P0-1 표준 DDL 정합**: (V4.6 통합 후) `STANDARD_TABLE_MAP` 이식 + 로더 연결.
5. **P1-2 V4.6 배포**: 로컬 v4.5/v4.6을 엘리스에 배포(통합 후).

---

## 5. 확인 vs 추측
- **확인(엘리스 실측)**: 온톨로지 V4.0·`STANDARD_TABLE_MAP` 0건·v4.6 항목 0건; 52866b3=norm_telno(선행0)+fresh 스테이징+L2; silent-loss 가드 94건; source_id SELECT 14건·vt_msg 미수집(`:705`); `_postprocess_v37/v40` 4건.
- **추측(런타임 검증 필요)**: test_v40 기본구성 실제 스킵 도메인 범위; fallback `actno` 노드 시각화 빈칸 실발생.

**참조(엘리스)**: `~/ccop_app/app/services/rdb_to_graph_service.py`(52866b3), `~/ccop_app/app/middleware/services/ontology_service.py`(V4.0), `~/ccop_app/app/services/rdb_service.py`, `docs/STANDARD_DDL_ALIGNMENT_REVIEW_20260804.md`.
