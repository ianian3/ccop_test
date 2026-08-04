# CCOP 5단계 파이프라인 이음새(Seam) 정합성 검토

> **작성일**: 2026-08-04
> **범위**: `Raw data → CSV → RDB 적재 → GDB(온톨로지 변환) → 시각화` 전 구간의 단계 간 이음새 정합.
> **초점**: 데이터가 5단계를 지나며 식별자·컬럼·타입·방향·provenance가 일관 보존되는가.

---

## 0. 파이프라인 맵 — **두 경로로 분기, `tbl_*` 경로만 온전**

| 단계 | 코드 | 대상 스키마 | provenance | 정규화 |
|---|---|---|---|---|
| Raw→CSV | `docs/samples/*.csv`(한글 헤더), `scripts/osint_ingest.py`, 업로드 `routes_api.py:1620-1662` | — | **CSV에 source_id 컬럼 없음**(라우트 파라미터로 주입) | — |
| CSV→RDB **(A)** 고정스키마 | `rdb_service.py:52-316` `import_predefined_schema_to_rdb` (파일명 `tbl_*`) | **test_v40** | source_domain/source_id/reliability_tier 기록(`:110-113`) | norm_telno+norm_account 적용 |
| CSV→RDB **(B)** 자동추론 | `rdb_service.py:318-691` `import_csv_to_rdb` (비-`tbl_`) | **public** | **미기록**(DDL 대기 주석 `:322`) | norm_account만, **전화 미정규화** |
| RDB→GDB | `rdb_to_graph_service.py:134+` `transfer_data` | **test_v40** 읽음(`:141`) | — | `_norm_telno` 재적용, 계좌 재정규화 없음 |
| GDB→Viz | `graph_service.py`(`{id,label,props}`), `routes_api.py:1397,1411`, `index.html:2235-2419` | — | — | — |

경로 분기점: `routes_api.py:1646-1655`. **온전한 경로 = `tbl_*` CSV → (A) test_v40 → transfer_data(test_v40).** 경로 (B)는 구버전 발산 서브파이프라인(§P0-1).

---

## P0 — 엔드투엔드 무결성 파괴

### P0-1 컬럼 매핑 체인 단절 (loader B ↔ 그래프 reader) — **Silent Data Loss**
`import_csv_to_rdb`는 public V2 대문자 스키마에 쓰고, `transfer_data`는 test_v40 소문자를 읽는다. 구체 발산:
- **이체**: (B)가 `TB_FIN_BACNT_DLNG(BACNT_NO, BANK_CD, DLNG_SE_CD, TRRC_BACNT_NO)` 기록(`rdb_service.py:518`) vs reader `SELECT src_bacnt_no, tgt_bacnt_no FROM tb_fin_bacnt_dlng`(`rdb_to_graph_service.py:582`) — `src_bacnt_no`/`tgt_bacnt_no`가 (B) 테이블에 **부재**.
- **계좌**: reader `bacnt_no, bnk_cd, bank_nm`(`:497`) vs (B) `BANK_CD`.
- **통화**: reader `caller_telno/callee_telno`(`:613`) vs (B) `DSPTCH_TELNO/RCPTN_TELNO`.
- 게다가 (B)는 **public**에 쓰고 transfer_data는 **test_v40**을 읽음.

**결과**: 비-`tbl_` CSV(배포 샘플 `docs/samples/금융기관_계좌이체_샘플.csv` 포함)는 RDB엔 적재되나 **그래프에 영원히 도달 안 함 — 사용자에게 에러도 안 뜸**. `tbl_*` 고정스키마 경로만 엔드투엔드 온전.

---

## P1 — 살아있는 경로의 정확성/정보 손실

### P1-1 provenance가 RDB→GDB 이음새에서 전량 소실
`transfer_data`의 전체 코어 노드/이벤트 빌드(`:469-923`)에 `source_id`/`source_domain`/`reliability_tier` 참조 **0건**. test_v40엔 loader (A)가 기록(`:110-113`)하지만 그래프 노드로 SELECT·기록 안 함 → 모든 인물/계좌/전화/이체/통화/이동 노드가 **출처 소실**. 그래프까지 살아남는 provenance는 OSINT 서브경로 `vt_src`+`sourced_from`(`:1011-1056`)뿐(표준 CSV 로더가 안 채우는 테이블). 엣지 `evid_grade`/`src_tier`(`:596`)는 provenance 유래가 아닌 **하드코딩 상수**. → 프론트에 표시할 출처 정보 없음.

### P1-2 그래프 속성 ↔ 시각화 라벨 불일치 → 핵심 엔티티 빈칸 렌더 (사용자 직접 체감)
`graph_service`는 raw 그래프 속성을 `data.props`로 반환(`:496,541,595`). 프론트 하드코딩 라벨 함수는 `transfer_data`가 안 쓴 RDB식 키를 읽는다:

| 노드 | transfer_data 기록 | index.html 라벨 읽기 | 결과 |
|---|---|---|---|
| vt_bacnt | `account_no,bank_cd,bank_name`(`:516`) | `p.actno,p.bnk_cd,p.bank_nm`(`:2261`) | **계좌번호 빈칸** |
| vt_access | `access_id,timestamp`(`:567`) | `p.src_ip`(`:2291`) | 빈 IP |
| vt_msg | `event_type,summary`(`:718`) | `p.platform,p.msg_type`(`:2292`) | 빈칸 |
| vt_movement | `mov_type,telno,lat,lng`(`:856`) | `p.from_loc`(`:2293`) | 빈칸 |

작동하는 매칭: vt_case `flnm`, vt_psn `name`, vt_ip `ip_addr`, vt_site `url_addr`, vt_transfer `amount`, vt_call `duration`, vt_atm `atm_id`. (레거시 fallback 계좌경로는 `actno` 기록(`:345`) — 프론트가 `actno`를 기대하는 이유, KICS 경로가 여기서 발산.)

### P1-3 loader (A) 부분적재
`import_predefined_schema_to_rdb`가 `conn.autocommit=True`(`:69`) → `except`의 `conn.rollback()`(`:312`)이 **autocommit 하에서 no-op** → 실패 행 이전 삽입분 잔존. 중간 오류 시 부분 적재 RDB가 그래프로 흐름. (loader (B) `:678`은 상대적으로 원자적.)

---

## P2 — 화장/잠재/방어

- **노드 스타일 SSoT 무력화**: `applyV40NodeStyles`(`index.html:2387`)가 `st.border_color`를 읽으나 `VISUAL_STYLE_V40`에 `border_color` 키 없음 → 테두리 미적용. `shape:'roundrectangle'`(`ontology_service.py:386`)은 Cytoscape가 `round-rectangle`을 요구해 무시. `label_property`(vt_call→`call_dt` 등 `:409`)는 **죽은 메타**(프론트가 자체 하드코딩). → **온톨로지가 노드 라벨/색의 런타임 SoT가 아님**(엣지 스타일은 SoT 정상 반영).
- **`transfer_data`에 norm_account 읽기 방어 없음**: `_norm_telno`는 재적용(`:533,617`)하나 계좌는 저장형 그대로 MATCH(`:598,676`) → 비정규화 계좌값은 MATCH 실패로 **이체 엣지 드롭**.
- **loader (B) 내부 정규화 분열**: 계좌 마스터는 정규화(`:498`)하나 DLNG 참조(`:513`)·전화(`:525`)는 raw. (P0-1로 dead-end라 잠재.)
- **온톨로지 라벨 하드코딩**: `vertex_labels`/`edge_labels`(`:191-228`)가 SoT 미참조 병렬 리스트 → 드리프트 위험(대조 테스트로 일부 방어됨).
- **고아노드 시각화 도달**: per-row MERGE 노드는 후속 엣지 MATCH 실패해도 생성 → 고립 노드 미필터 렌더.
- **경미 라벨 저하**: vt_org `org_name`vs`p.org_nm`, vt_file `filename`vs`p.file_nm`, vt_telno `carrier_cd`vs`p.carr_cd`.

---

## ✅ 해소 확인 (기존 수정 통합)

- **엣지 방향(accessed_from/performed_by)**: 엔드투엔드 일관 검증. `transfer_data`가 `vt_access→vt_ip`(`:573`)·`vt_access→vt_psn`(`:812`) 생성, `RELATIONSHIPS` domain/range와 일치, `graph_service`가 `source=startNode/target=endNode`(`:615`)+`target-arrow-shape:triangle`로 **시각화 화살표에 올바로 반영**.
- `safe_str` 이스케이프, 엣지 MERGE 멱등, `norm_account`, SoT 대조 테스트, `STANDARD_TABLE_MAP` 크로스워크 — 모두 확인.

---

## 종합 (카테고리별) 및 권장 우선순위

| 축 | 현황 | 등급 |
|---|---|---|
| (b) 컬럼 매핑 단절 | loader B↔reader = silent loss / KICS 속성↔프론트 라벨 = 빈칸 렌더 | **P0 / P1** |
| (c) provenance 소실 | RDB→GDB 이음새에서 전량 소실(경로 B는 RDB 진입도 안 함) | **P1** |
| (a) 정규화→매칭 | `tbl_*` 경로 내 온전(전화 이중방어). 갭=transfer_data 계좌 읽기방어·loader B 분열 | P2 |
| (d) 시각화-온톨로지 스타일 | 엣지는 SoT 정상, 노드 라벨/색 SSoT 우회 | P2 |

**권장 순서**:
1. **P1-2 시각화 빈칸**(계좌/IP/msg/movement 속성명 정합) — 즉시 체감·저리스크. `transfer_data` 속성명 ↔ `index.html` 라벨 읽기 통일.
2. **P1-1 provenance 소실** — `PROVENANCE_NORMALIZATION_DESIGN` 설계대로 transfer_data가 source_id/domain/tier를 노드에 기록.
3. **P0-1 silent loss** — 경로 (B) 정리: transfer_data 스키마/컬럼 정합 or 경로 통합(STANDARD_TABLE_MAP 활용).
4. P1-3 부분적재(autocommit 트랜잭션화), P2들.

---

## 부록 — 근거 파일
- 분기: `routes_api.py:1646-1655` · 로더 A/B: `rdb_service.py:52-316`/`318-691`
- 변환: `rdb_to_graph_service.py:134-923` · 시각화: `graph_service.py`, `index.html:2235-2419`
- 관련 설계: `docs/PROVENANCE_NORMALIZATION_DESIGN_20260804.md`, `docs/STANDARD_DDL_ALIGNMENT_REVIEW_20260804.md`
