# EP5-030 기업은행 건별 거래내역 적재 — 위치·IP·자금흐름 (2026-09-08)

> 발단: "V4.8에 기지국 위치가 포함되는데 통합 그래프 어디 있나?" → 조사 결과 **설계만 있고
> 적재는 없었다**. EP3 기지국(85건·시군·상대방 위치)은 가치가 낮아 보류. 대신 사용자가 짚은
> **EP5-030 기업은행 수신거래내역의 거래점**을 확인하는 과정에서 훨씬 큰 소스가 열렸다.

## 1. 발견 — 암호화로 미적재였던 파일이 열린다

`수신거래내역자료_비식별화.xls` 2본은 크로스워크(20260828)에 **"비밀번호 암호화 → 복호화 필요"**
로 미적재 기록(P1-4 백로그). 2026-08-28 비식별화 재배포(v3) 이후 **암호 없이 열림을 실측 확인**.

내용: **3차집금 계좌 2본의 건별 거래명세 1,593건**(2017-03~04, 출금취소 1 스킵)

| 계좌 | 명의 | 거래 | 유입 | 유출 |
|---|---|---:|---|---|
| 02541269877431 (기업) | 조지영 | 954건 | 85쌍 · 4.02억 | 43쌍 · 3.96억 |
| 53987421033554 (기업) | **오민양(신규 명의자)** | 639건 | 61쌍 · 1.97억 | 74쌍 · 1.86억 |

유입≈유출 = 집금 통과 계좌 특성 그대로. 합계 약 **6억 원 규모 자금흐름**이 그래프에 신규 반영.

## 2. 적재 (`scripts/ingest_030_ibk_txn.py`, source_id=EP5-030-ibk)

| 축 | 매핑 | 결과 |
|---|---|---|
| 이체 | (송금측)-[transferred_to {first/last_dlng_dt, **total_amount·txn_count(숫자)**}]->(수취측) | 263쌍 신규 (통합 354→**617**) |
| 거래 IP | (계좌)-[used_ip {creation_method:'etl', tx_count, first/last_dt}]->(vt_ip) | 103엣지 (계좌측 used_ip는 기존 5뿐이었음) |
| 거래점 | (계좌)-[**located_at** {tx_count, wd_count, dep_count, first/last_dt}]->(**vt_loc** {loc_id:'기업은행 <지점>', loc_type:'atm_loc'}) | vt_loc 27 · 엣지 27 |

### 설계 결정
- **located_at 재사용**(V4.8 정의: domain=Any, range=Location). 원 의미는 '고정 객체의 정적 위치'
  이나, 이벤트 노드 없이 건별 거래 위치를 남기는 최소 표현으로 '계좌 거래 발생 지점(집계)'에
  확장 사용. 감사는 Any 와일드카드로 통과. (엄밀한 대안 = 거래 이벤트 노드 + occurred_at — V4.9 후보)
- `'제휴영업점'`·`'SPEED4'` 등 **채널명은 위치가 아니므로 vt_loc 제외**(blocklist + 대문자영숫자 패턴).
- 적요(거래내용)의 사람이름은 **노드로 만들지 않음** — EP5 크로스워크의 명의 오추출 전례.
- 계좌번호 정규화 = 숫자만(하이픈 제거), 기존 관례 일치. 병합 셀 함정: 메타(계좌번호·예금주)가
  라벨 셀 +1 이 아니라 **+3 위치** → 오른쪽 첫 비공백 셀 스캔으로 해결.

### build_integrated_graph.py 확장
- KP += `vt_loc:loc_id` · EDGES += `located_at` (누락 시 통합 재구축 때 신규 데이터가 **소실**됨)
- **엣지 속성 숫자 화이트리스트** 신설: `total_amount·txn_count·tx_count·wd_count·dep_count·
  msg_count·call_count·total_dur_sec` — 기존엔 전부 문자열로 저장돼 `>= / ORDER BY` 가 조용히
  깨졌다(P1-B ep_count 와 동일 계열 결함). 재구축 후 실측: **"총액 1억↑ 이체" 숫자 비교 11건**
  (문자열 시절 0건).

## 3. 교차 실증 — 이 적재의 백미

**`59.21.209.237`**: 기존 그래프에서 **송현주**(EP5-033 구글 계정)가 쓰던 IP인데, 같은 IP로
**오민양 명의 계좌의 뱅킹 거래 14건**이 처리됨.
→ 명의(오민양) 뒤의 **실사용자 후보(송현주)** 가 자금 축으로 특정 — EP7 'IP 역조회로 위장 뚫기'
패턴의 금융판. `ep_count>=3` 노드도 66→**69**(신규 거래 IP가 타 EP 기존 IP와 합류).

**거래점 분포(인출 위치)**: 상동 **443건(전부 출금)** · 구월동 139 · 강일동 54 · 중곡동 49 ·
부산병무청 23 · 강서중앙 21 — 인출책 활동 거점이 동·지점 단위로 그래프에 올라옴.

## 4. EP3 기지국 검토 결론 (보류)

전수 실측: 기지국 값 **85건/395행**(음성·VOLTE 착신만), 시·군 단위 34지역, 전부 **상대방(발신자)
위치**(피의자 회선의 착신 기록이므로). EP4의 013은 EP3와 동일 사본. 복수 지역 발신자 3명뿐이라
동선 가치 없음. 남는 가치는 발신자(피해자 추정) 전국 분포 정도 → **적재 보류**,
EP5-030-ibk(1,601건·동 단위·집금계좌 거래 위치)와 급이 다름.
※ 검토 중 정정 2건: '포천→서울→구리 동선' 예시는 서로 다른 발신자를 이어붙인 오류였음 ·
`used_loc` 엣지는 V4.8에 없음(located_at 이 정경).

## 5. 재현

```bash
# 적재 (로컬 5434 — .env 는 운영 읽기전용이므로 env 오버라이드 필수)
DB_HOST=localhost DB_PORT=5434 DB_USER=ccop DB_PASSWORD=... \
  python3 scripts/ingest_030_ibk_txn.py --graph ep5_graph
# 통합 재구축 + 지표 + 감사
DB_HOST=... python3 scripts/build_integrated_graph.py && python3 scripts/refine_integrated_graph.py \
  && python3 scripts/graph_analytics.py --graph ccop_ep_integrated --set && python3 scripts/audit_ep_v48.py
# 운영 복제
DB_HOST=localhost DB_PORT=5434 ... DST_HOST=49.50.128.28 DST_PORT=5333 \
  python3 scripts/replicate_graph.py ep5_graph ccop_ep_integrated
```

결과(로컬 재구축): 통합 **24,613노드(+306) · 26,981엣지(+1,384)** · V4.8 감사 위반 0 ·
인물중심 Louvain 1,849 군집 · 지표 10종 재계산.

---

## 6. 🔴 운영 DB 엔진 크래시 발견 (적재 후 벤치 중)

### 증상과 격리
복제 후 벤치에서 M05류 질의가 0행 → 직접 재현 결과 **운영 DB 백엔드 크래시**
(`server closed the connection unexpectedly` → 전 연결 `FATAL: the database system is in
recovery mode`). 격리 실측:

| 형태 | 결과 |
|---|---|
| count · 스칼라 · 엔티티 반환 · 단독 노드 맵리터럴 · 앵커(첫 노드) 조건 · 엣지 변수 조건 | 정상 |
| **경로 순회 + 비앵커(대상) 노드 속성 조건** — 맵리터럴이든 WHERE든 | **크래시** |

같은 쿼리가 **로컬(PG13.9 기반)에서는 정상 1행**. 운영은 **AgensGraph 2.16-devel /
PostgreSQL 16beta2** — 개발·베타 빌드가 운영에 올라가 있는 상태로, 엔진 결함으로 판단.
공유 DB(타 기관 접속 중)라 **재현 3회 후 중단**.

### 시도한 것
- 복제 잔재 `_src_id` property index 85개 제거(`DROP PROPERTY INDEX` — 일반 DROP INDEX 는
  WrongObjectType) + ANALYZE → **크래시 지속** (인덱스 원인 아님)
- 맵리터럴 → WHERE 이동 결정론 재작성(`_maps_to_where`) → **크래시 지속** (형태 무관, 조합이 원인)

### 적용한 보호 — `AGENS_TRAVERSAL_COND_GUARD=1`
앱이 크래시 형태를 운영에 보내지 않도록 실행 직전 차단(`_crashy_traversal_cond`):
경로 절의 **비앵커 노드 변수에 속성 조건**이 있으면 실행하지 않고 경고 반환
("조건을 앵커 노드로 옮겨 질문" 안내). 앵커 조건·엣지 조건은 통과. 로컬 검증:
차단 시 DB 무사, 정상 질의(조지영 5행·1억↑ 21행) 영향 없음.
플래그는 **운영 DB를 바라보는 배포에만** 설정(미설정 시 기존 동작 — 로컬 PG13.9 는 불필요).

### DB 관리자 요청 사항 (재발 방지의 본질)
1. **안정판 AgensGraph 로 교체** — 2.16-devel/PG16beta2 는 운영 부적합
2. 서버 로그의 segfault 스택 확보(원인 리포트용). 최소 재현:
   `MATCH (p:vt_psn {name:'조정모'})-[:uses_id]->(id:vt_id {platform:'kakao'}) RETURN id`
3. 엔진 교체 전까지 가드 유지 · 교체 후 가드 해제하고 재검증

### 부수 수정
- `replicate_graph.py`: 복제 후 `_src_id` property index 자동 정리 추가(잔재 방지)
- tier 값 공백 변형(`'3차 집금'`) → 실값 치환 완화 추가
