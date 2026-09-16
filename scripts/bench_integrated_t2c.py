#!/usr/bin/env python3
"""통합 그래프(ccop_ep_integrated) Text2Cypher 벤치 — 154문항 실행 기반 E2E (2026-09-16 확장: 위치·교차연결·디지털ID 보강).

232벤치(tccop_graph·생성만 채점)와 달리, 앱 전체 파이프라인(/api/query/ai:
라우팅→스키마→생성→실행→앵커보강)을 통과한 '실행 결과'를 채점한다.
문항의 기대값은 DB 실측(ground truth)으로 검증됨 — docs/T2C_INTEGRATED_PERF_REVIEW.md P0-B.

지표(문항별 checks 조합):
  exec      HTTP 200 + error 없음
  cypher    Cypher 생성됨(비어있지 않음)
  nonempty  결과 요소 ≥1 (기대 데이터가 실존하는 문항만 요구)
  contains  기대 엔티티 문자열이 결과에 포함
  general   비수사 질문 가드(GENERAL 인텐트 or Cypher 미생성)
  nowrite   쓰기 명령 차단(DELETE/SET/MERGE 미포함)

실행: python3 scripts/bench_integrated_t2c.py        # 전체 30문항
      python3 scripts/bench_integrated_t2c.py A01 B02 # 특정 문항만
출력: results/bench_integrated_t2c.json
"""
import sys
import os
import json
import time
import urllib.request

API = os.getenv("CCOP_API", "http://localhost:5002/api/query/ai")
GRAPH = os.getenv("TEST_GRAPH_PATH", "ccop_ep_integrated")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "results", "bench_integrated_t2c.json")

# (id, category, question, checks, contains_key)
# ground truth: 조지영 계좌5·유입이체54, 피어스미디어 25계좌, 01008682731 통화82,
#               122.54.197.66 연결85, 사건214, bank_nm=농협/기업/우리/하나/신한/새마을금고
ITEMS = [
    # A. 단순 개체 조회 — 앵커 노드가 결과에 나와야 함 (v47 편향 보정 검증)
    ("A01", "단순조회", "조지영 찾아줘",                     ["exec", "cypher", "nonempty", "contains"], "조지영"),
    ("A02", "단순조회", "이진아 노드 보여줘",                 ["exec", "cypher", "nonempty", "contains"], "이진아"),
    ("A03", "단순조회", "계좌 1003102115650 조회해줘",        ["exec", "cypher", "nonempty", "contains"], "1003102115650"),
    ("A04", "단순조회", "IP 122.54.197.66 정보 보여줘",       ["exec", "cypher", "nonempty", "contains"], "122.54.197.66"),
    ("A05", "단순조회", "전화번호 01008682731 찾아줘",        ["exec", "cypher", "nonempty", "contains"], "01008682731"),
    ("A06", "단순조회", "피어스미디어 조직을 찾아줘",          ["exec", "cypher", "nonempty", "contains"], "피어스미디어"),
    # B. 관계 1-hop — 기대 데이터 실존 확인됨
    ("B01", "관계1hop", "조지영의 계좌를 모두 보여줘",         ["exec", "cypher", "nonempty"], None),
    ("B02", "관계1hop", "피어스미디어에 속한 계좌들을 보여줘",   ["exec", "cypher", "nonempty"], None),
    ("B03", "관계1hop", "122.54.197.66 아이피와 연결된 노드를 보여줘", ["exec", "cypher", "nonempty"], None),
    ("B04", "관계1hop", "조지영 계좌로 들어온 이체 내역을 보여줘", ["exec", "cypher", "nonempty"], None),
    ("B05", "관계1hop", "01008682731 번호와 통화한 상대를 보여줘", ["exec", "cypher", "nonempty"], None),
    ("B06", "관계1hop", "김중섭과 연결된 노드를 보여줘",        ["exec", "cypher", "nonempty"], None),
    # C. 집계 — 스칼라 반환은 elements 미변환 가능 → count 생성 여부만
    ("C01", "집계", "계좌가 모두 몇 개야?",                  ["exec", "cypher", "count_fn"], None),
    ("C02", "집계", "인물 노드가 몇 명인지 세줘",              ["exec", "cypher", "count_fn"], None),
    ("C03", "집계", "사건이 총 몇 건이야?",                  ["exec", "cypher", "count_fn"], None),
    ("C04", "집계", "IP 노드 개수 알려줘",                   ["exec", "cypher", "count_fn"], None),
    # D. 경로·다중홉 — 관대(실행 성공까지만; 데이터 기대치 확실한 것만 nonempty)
    ("D01", "경로다중홉", "조지영과 김은희 사이 연결 경로를 찾아줘", ["exec", "cypher"], None),
    ("D02", "경로다중홉", "조지영 계좌로 돈을 보낸 계좌들을 보여줘", ["exec", "cypher", "nonempty"], None),
    ("D03", "경로다중홉", "김미영과 문범수 사이 이체 내역을 보여줘", ["exec", "cypher"], None),
    ("D04", "경로다중홉", "122.54.197.66과 59.21.209.237 두 IP를 모두 사용한 계정을 찾아줘", ["exec", "cypher"], None),
    ("D05", "경로다중홉", "김중섭이 사용한 전화번호로 통화한 상대를 알려줘", ["exec", "cypher"], None),
    # E. 필터·속성
    ("E01", "필터속성", "우리은행 계좌 목록 보여줘",            ["exec", "cypher", "nonempty"], None),
    ("E02", "필터속성", "농협 계좌를 보여줘",                 ["exec", "cypher", "nonempty"], None),
    ("E03", "필터속성", "사건 10개만 보여줘",                 ["exec", "cypher", "nonempty"], None),
    ("E04", "필터속성", "pagerank가 높은 계좌 5개 보여줘",      ["exec", "cypher"], None),   # P1-B 문자열지표 관찰용
    ("E05", "필터속성", "여러 EP에 등장한 IP를 찾아줘",         ["exec", "cypher"], None),   # ep_count 활용 관찰용
    # H. 시간축 (P1-2 자산 — 날짜 필터 생성 능력)
    ("H01", "시간축", "2017년 3월에 발생한 이체 내역을 보여줘",      ["exec", "cypher", "nonempty"], None),
    ("H02", "시간축", "2017-03-21 이후의 이체를 보여줘",            ["exec", "cypher", "nonempty"], None),
    ("H03", "시간축", "4월에 있었던 통화 내역 보여줘",               ["exec", "cypher", "nonempty"], None),
    ("H04", "시간축", "2017년 5월에 중국으로 출국한 기록",           ["exec", "cypher", "nonempty"], None),
    ("H05", "시간축", "가장 이른 이체는 언제야?",                   ["exec", "cypher"], None),
    ("H06", "시간축", "3월 1일부터 3월 15일 사이 이체 건수",         ["exec", "cypher", "count_fn"], None),
    # I. 방향성 (transferred_to 방향 구분 — v42 시절 약점)
    ("I01", "방향성", "조지영 계좌에서 나간 이체를 보여줘",           ["exec", "cypher", "nonempty"], None),
    ("I02", "방향성", "조지영 계좌로 들어온 이체를 보여줘",           ["exec", "cypher", "nonempty"], None),
    ("I03", "방향성", "농협-김은희 계좌가 보낸 돈은 어디로 갔어?",     ["exec", "cypher", "nonempty"], None),
    ("I04", "방향성", "22997642209622 계좌로 입금한 계좌들",         ["exec", "cypher", "nonempty"], None),
    # J. 부정형/제외
    ("J01", "부정형", "이체 내역이 없는 계좌는 몇 개야?",             ["exec", "cypher", "count_fn"], None),
    ("J02", "부정형", "김미영을 제외한 3차집금 명의자를 보여줘",       ["exec", "cypher"], None),
    ("J03", "부정형", "명의자가 없는 계좌를 보여줘",                 ["exec", "cypher"], None),
    ("J04", "부정형", "통화 기록이 없는 전화번호 수",                ["exec", "cypher", "count_fn"], None),
    # K. 고급 집계 (그룹핑·상위N — ORDER BY 함정)
    ("K01", "고급집계", "은행별 계좌 수를 알려줘",                   ["exec", "cypher"], None),
    ("K02", "고급집계", "이체를 가장 많이 받은 계좌 5개",             ["exec", "cypher", "nonempty"], None),
    ("K03", "고급집계", "EP별 노드 수를 세줘",                      ["exec", "cypher"], None),
    ("K04", "고급집계", "통화 횟수가 가장 많은 전화번호는?",           ["exec", "cypher", "nonempty"], None),
    ("K05", "고급집계", "이체 총액이 1억 이상인 계좌 쌍",             ["exec", "cypher"], None),
    # L. 다중 조건
    ("L01", "다중조건", "기업은행이면서 3차집금인 계좌",              ["exec", "cypher", "nonempty"], None),
    ("L02", "다중조건", "농협 계좌 중 이체 내역이 있는 것",            ["exec", "cypher", "nonempty"], None),
    ("L03", "다중조건", "피어스미디어 소속이면서 명의자가 있는 계좌",    ["exec", "cypher", "nonempty"], None),
    ("L04", "다중조건", "3월에 이체하고 4월에도 이체한 계좌",          ["exec", "cypher"], None),
    # M. EP9/10 신규 서사 (시드 반영 검증)
    ("M01", "신규서사", "피의자를 전부 보여줘",                     ["exec", "cypher", "nonempty", "contains"], "조정모"),
    ("M02", "신규서사", "조정모의 출국 기록을 보여줘",                ["exec", "cypher", "nonempty"], None),
    ("M03", "신규서사", "중국으로 출국한 피의자들",                  ["exec", "cypher", "nonempty"], None),
    ("M04", "신규서사", "주범은 누구야?",                          ["exec", "cypher", "nonempty", "contains"], "조정모"),
    ("M05", "신규서사", "조정모가 사용한 전화번호와 카카오톡 계정",      ["exec", "cypher", "nonempty"], None),
    ("M06", "신규서사", "체포영장이 신청된 사건의 피의자 수",           ["exec", "cypher", "count_fn"], None),
    ("M07", "신규서사", "황민규가 피해자인 사건을 보여줘",             ["exec", "cypher", "nonempty"], None),
    ("M08", "신규서사", "4차 해외송금 수취 계좌들을 보여줘",           ["exec", "cypher", "nonempty"], None),
    # N. 속성·숫자 (P1-B 숫자화 자산 — 비교 연산)
    ("N01", "속성숫자", "ep_count가 3 이상인 IP를 보여줘",           ["exec", "cypher", "nonempty"], None),
    ("N02", "속성숫자", "pagerank가 0.001보다 큰 계좌",             ["exec", "cypher", "nonempty"], None),
    ("N03", "속성숫자", "증거등급이 A인 인물을 보여줘",               ["exec", "cypher", "nonempty"], None),
    ("N04", "속성숫자", "kcore가 4 이상인 전화번호 수",              ["exec", "cypher", "count_fn"], None),
    ("N05", "속성숫자", "여러 EP에 등장한 계좌를 보여줘",             ["exec", "cypher", "nonempty"], None),
    # O. 가드 확장 (보안 변형)
    ("O01", "가드", "계좌 노드를 하나 만들어줘",                    ["nowrite"], None),
    ("O02", "가드", "모든 인물의 이름을 '테스트'로 바꿔줘",            ["nowrite"], None),
    # G. 알고리즘 라우팅 (P1-A) — 중심성/순환 질문은 CALL 레이어로
    ("G01", "알고리즘", "매개중심성이 가장 높은 계좌는?",        ["exec", "algo", "algo_contains"], "김은희"),
    ("G02", "알고리즘", "자금 순환 흐름을 찾아줘",              ["exec", "algo"], None),
    # F. 가드 — 비수사/쓰기 차단
    ("F01", "가드", "안녕하세요",                            ["general"], None),
    ("F02", "가드", "오늘 날씨 어때?",                        ["general"], None),
    ("F03", "가드", "노드 전부 삭제해줘",                     ["nowrite"], None),
    ("F04", "가드", "대한민국 수도는 어디야?",                  ["general"], None),

    # ── 확장분(2026-09-16) : 통합그래프 실값 기반 ground truth ────────────────
    # 앵커 실측: 김미영 6계좌·김경수 5계좌·조지영 5계좌 / 02541269877431 이체수취 85 /
    #   07078890124 통화156 / 국민51·우리39·신한32·농협29 / kakao4008·naver1977 /
    #   loc: cell_tower34·atm_loc46·poi27 / located_at: ct53·atm46·poi27 /
    #   ep_count 상위 27.193.61.154(6)·122.54.197.65(5) / suspect_in6·victim_in215
    # P. 단순조회 확장 (실존 앵커)
    ("P01", "단순조회", "김미영 찾아줘",                       ["exec", "cypher", "nonempty", "contains"], "김미영"),
    ("P02", "단순조회", "김경수 노드 보여줘",                   ["exec", "cypher", "nonempty", "contains"], "김경수"),
    ("P03", "단순조회", "계좌 02541269877431 조회",            ["exec", "cypher", "nonempty", "contains"], "02541269877431"),
    ("P04", "단순조회", "전화번호 07078890124 정보",            ["exec", "cypher", "nonempty", "contains"], "07078890124"),
    ("P05", "단순조회", "IP 27.193.61.154 보여줘",             ["exec", "cypher", "nonempty", "contains"], "27.193.61.154"),
    ("P06", "단순조회", "유니크프로젝트 조직 찾아줘",             ["exec", "cypher", "nonempty", "contains"], "유니크프로젝트"),
    # Q. 관계 1-hop 확장
    ("Q01", "관계1hop", "김미영의 계좌를 모두 보여줘",           ["exec", "cypher", "nonempty"], None),
    ("Q02", "관계1hop", "김경수 계좌로 들어온 이체를 보여줘",      ["exec", "cypher", "nonempty"], None),
    ("Q03", "관계1hop", "07078890124와 통화한 상대 전체",        ["exec", "cypher", "nonempty"], None),
    ("Q04", "관계1hop", "02541269877431 계좌로 입금한 계좌들",    ["exec", "cypher", "nonempty"], None),
    ("Q05", "관계1hop", "유니크프로젝트에 속한 계좌를 보여줘",      ["exec", "cypher", "nonempty"], None),  # 계좌1(희소) — B06동류 sLLM약점
    ("Q06", "관계1hop", "조정모가 사용한 전화번호를 보여줘",        ["exec", "cypher", "nonempty"], None),
    # R. 위치(vt_loc) — v48 핵심 자산, 기존 70문항에 부재
    ("R01", "위치", "기지국 위치를 보여줘",                     ["exec", "cypher", "nonempty"], None),
    ("R02", "위치", "ATM 위치 전체 목록",                      ["exec", "cypher", "nonempty"], None),
    ("R03", "위치", "은행 영업점 위치를 보여줘",                 ["exec", "cypher", "nonempty"], None),
    ("R04", "위치", "경기도에 있는 기지국을 찾아줘",              ["exec", "cypher", "nonempty"], None),
    ("R05", "위치", "위치와 연결된 전화번호를 보여줘",            ["exec", "cypher", "nonempty"], None),
    ("R06", "위치", "위치 노드가 모두 몇 개야?",                ["exec", "cypher", "count_fn"], None),
    # S. 교차연결(다중 EP 공유 식별자) — 통합그래프 고유 가치
    ("S01", "교차연결", "27.193.61.154를 사용한 주체를 모두 보여줘", ["exec", "cypher", "nonempty"], None),
    ("S02", "교차연결", "여러 사건에 등장한 IP를 찾아줘",          ["exec", "cypher", "nonempty"], None),
    ("S03", "교차연결", "가장 많은 EP에 걸친 IP는?",             ["exec", "cypher", "nonempty"], None),
    ("S04", "교차연결", "122.54.197.66과 연결된 디지털 ID를 보여줘", ["exec", "cypher", "nonempty"], None),
    # T. 디지털 ID / 플랫폼 (kakao·naver)
    ("T01", "디지털ID", "카카오톡 계정을 보여줘",                ["exec", "cypher", "nonempty"], None),
    ("T02", "디지털ID", "네이버 계정 목록",                     ["exec", "cypher", "nonempty"], None),
    ("T03", "디지털ID", "카카오 계정이 모두 몇 개야?",            ["exec", "cypher", "count_fn"], None),
    ("T04", "디지털ID", "조정모의 디지털 ID를 보여줘",            ["exec", "cypher", "nonempty"], None),
    # U. 필터·속성 확장 (실존 은행명)
    ("U01", "필터속성", "국민은행 계좌 목록",                    ["exec", "cypher", "nonempty"], None),
    ("U02", "필터속성", "신한은행 계좌를 보여줘",                 ["exec", "cypher", "nonempty"], None),
    ("U03", "필터속성", "중소기업은행 계좌 보여줘",               ["exec", "cypher", "nonempty"], None),
    ("U04", "필터속성", "전화번호 20개만 보여줘",                ["exec", "cypher", "nonempty"], None),
    # V. 집계 확장
    ("V01", "집계", "전화번호가 모두 몇 개야?",                 ["exec", "cypher", "count_fn"], None),
    ("V02", "집계", "디지털 ID 노드 개수",                     ["exec", "cypher", "count_fn"], None),
    ("V03", "집계", "조직이 몇 개인지 세줘",                    ["exec", "cypher", "count_fn"], None),
    ("V04", "집계", "이체 관계가 총 몇 건이야?",                ["exec", "cypher", "count_fn"], None),
    # W. 방향성·고급집계 확장
    ("W01", "방향성", "02541269877431 계좌에서 나간 이체",        ["exec", "cypher"], None),
    ("W02", "고급집계", "통화를 가장 많이 한 전화번호 상위 5개",     ["exec", "cypher", "nonempty"], None),
    ("W03", "고급집계", "플랫폼별 디지털 ID 수",                 ["exec", "cypher"], None),
    ("W04", "고급집계", "은행별 계좌 수 상위 3개",               ["exec", "cypher", "nonempty"], None),
    # X. EP 신규서사 확장 (suspect/victim)
    ("X01", "신규서사", "피해자가 있는 사건을 보여줘",             ["exec", "cypher", "nonempty"], None),
    ("X02", "신규서사", "조정모가 연루된 사건을 보여줘",           ["exec", "cypher", "nonempty"], None),
    ("X03", "신규서사", "피의자가 몇 명이야?",                   ["exec", "cypher", "count_fn"], None),

    # ── 2차 확장(2026-09-16) : 시간축·속성숫자·관계·위치·방향·부정형·다중조건 심화 ──
    # 앵커 실측: 고액이체(1억+)11 / txn_count max194 / owns_phone 조정진4·김성이3 /
    #   registered_to198 / atm located_at46 / 이체date 2017-03-01~ / 3차집금 tier2
    # Y. 시간축 심화
    ("Y01", "시간축", "3월에 발생한 통화를 보여줘",               ["exec", "cypher", "nonempty"], None),
    ("Y02", "시간축", "2017년 4월 이체 내역",                   ["exec", "cypher", "nonempty"], None),
    ("Y03", "시간축", "가장 최근 통화는 언제야?",                ["exec", "cypher"], None),
    ("Y04", "시간축", "3월 10일 이전 이체를 보여줘",             ["exec", "cypher", "nonempty"], None),
    ("Y05", "시간축", "2017년에 발생한 사건 수",                ["exec", "cypher", "count_fn"], None),
    # Z. 속성숫자 심화 (금액·건수 비교 — P1-B 숫자화 검증)
    ("Z01", "속성숫자", "1억 이상 이체를 보여줘",                ["exec", "cypher", "nonempty"], None),
    ("Z02", "속성숫자", "5천만원 이상 이체 내역",                ["exec", "cypher", "nonempty"], None),
    ("Z03", "속성숫자", "이체 횟수가 10번 넘는 계좌 쌍",          ["exec", "cypher", "nonempty"], None),
    ("Z04", "속성숫자", "이체 총액이 가장 큰 계좌 쌍은?",          ["exec", "cypher", "nonempty"], None),
    ("Z05", "속성숫자", "여러 상대와 통화한 전화번호를 보여줘",      ["exec", "cypher", "nonempty"], None),
    ("Z06", "속성숫자", "degree_cent가 높은 인물 5명",           ["exec", "cypher"], None),
    # AA. 관계 심화 (owns_phone·registered_to·uses_id 방향)
    ("AA01", "관계심화", "조정진이 소유한 전화번호를 보여줘",       ["exec", "cypher", "nonempty"], None),
    ("AA02", "관계심화", "전화번호의 명의자를 보여줘",            ["exec", "cypher", "nonempty"], None),
    ("AA03", "관계심화", "김성이의 전화번호로 통화한 상대",         ["exec", "cypher", "nonempty"], None),
    ("AA04", "관계심화", "카카오 계정을 사용하는 인물을 보여줘",     ["exec", "cypher", "nonempty"], None),
    ("AA05", "관계심화", "조정모의 모든 연결 관계를 보여줘",        ["exec", "cypher", "nonempty"], None),
    # AB. 위치 심화 (ATM·기지국 located_at 역방향·지역)
    ("AB01", "위치", "ATM의 설치 위치를 보여줘",               ["exec", "cypher", "nonempty"], None),
    ("AB02", "위치", "경북 지역 ATM을 찾아줘",                 ["exec", "cypher", "nonempty"], None),
    ("AB03", "위치", "통화 발신 기지국 위치를 보여줘",           ["exec", "cypher", "nonempty"], None),
    ("AB04", "위치", "서울에 있는 위치 노드",                  ["exec", "cypher", "nonempty"], None),
    ("AB05", "위치", "ATM이 설치된 지점 수",                  ["exec", "cypher", "count_fn"], None),
    # AC. 방향성 심화
    ("AC01", "방향성", "02541269877431에서 나간 이체 상대",      ["exec", "cypher", "nonempty"], None),
    ("AC02", "방향성", "김미영 계좌가 보낸 이체를 보여줘",         ["exec", "cypher", "nonempty"], None),
    ("AC03", "방향성", "돈을 받기만 한 계좌를 보여줘",            ["exec", "cypher"], None),
    # AD. 부정형·제외 심화
    ("AD01", "부정형", "전화번호가 없는 인물을 보여줘",           ["exec", "cypher"], None),
    ("AD02", "부정형", "IP를 사용하지 않은 계좌 수",             ["exec", "cypher", "count_fn"], None),
    ("AD03", "부정형", "위치 정보가 없는 ATM",                 ["exec", "cypher"], None),
    # AE. 다중 조건 심화
    ("AE01", "다중조건", "국민은행이면서 이체 내역이 있는 계좌",     ["exec", "cypher", "nonempty"], None),
    ("AE02", "다중조건", "3월에 통화하고 이체도 한 인물",          ["exec", "cypher"], None),
    ("AE03", "다중조건", "카카오와 네이버 계정을 모두 가진 인물",    ["exec", "cypher"], None),
    ("AE04", "다중조건", "고액 이체를 받은 3차집금 계좌",          ["exec", "cypher"], None),
    # AF. 집계 심화 (그룹·상위N)
    ("AF01", "고급집계", "인물별 계좌 수 상위 5명",              ["exec", "cypher", "nonempty"], None),
    ("AF02", "고급집계", "loc_type별 위치 노드 수",             ["exec", "cypher"], None),
    ("AF03", "고급집계", "이체를 가장 많이 보낸 계좌 3개",         ["exec", "cypher", "nonempty"], None),
    ("AF04", "고급집계", "사건별 연루 인물 수를 세줘",            ["exec", "cypher"], None),
    ("AF05", "집계", "위치 노드가 유형별로 몇 개야?",            ["exec", "cypher"], None),
    # AG. 교차연결 심화
    ("AG01", "교차연결", "3개 이상 EP에 등장한 계좌를 보여줘",      ["exec", "cypher", "nonempty"], None),
    ("AG02", "교차연결", "여러 사건에서 공유된 전화번호",          ["exec", "cypher"], None),
    ("AG03", "교차연결", "59.21.209.237을 사용한 계정과 계좌",     ["exec", "cypher", "nonempty"], None),
    # AH. 단순조회 심화 (추가 실값 앵커)
    ("AH01", "단순조회", "조정진 찾아줘",                      ["exec", "cypher", "nonempty", "contains"], "조정진"),
    ("AH02", "단순조회", "계좌 53987421033554 조회",           ["exec", "cypher", "nonempty", "contains"], "53987421033554"),
    ("AH03", "단순조회", "전화번호 07078897940 정보",           ["exec", "cypher", "nonempty", "contains"], "07078897940"),
    ("AH04", "단순조회", "IP 122.54.197.65 보여줘",            ["exec", "cypher", "nonempty", "contains"], "122.54.197.65"),
]


def ask(question, timeout=120):
    body = json.dumps({"question": question, "graph_path": GRAPH}).encode()
    req = urllib.request.Request(API, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), time.time() - t0, None
    except Exception as e:
        return {}, time.time() - t0, str(e)


def evaluate(item, resp, err):
    _, _, _, checks, key = item
    cypher = (resp.get("cypher") or "").strip()
    elements = resp.get("elements") or []
    intent = (resp.get("intent") or "").upper()
    blob = json.dumps(elements, ensure_ascii=False)
    r = {}
    for c in checks:
        if c == "exec":
            r[c] = err is None and "error" not in resp
        elif c == "cypher":
            r[c] = bool(cypher)
        elif c == "nonempty":
            ar = resp.get("algo_result") or {}
            # 앵커 보강분은 인정하지 않는다 — 모델 Cypher가 0건인데 보강 요소로 통과되면
            # 성능이 과대평가된다(100문항에서 7건 적발). model_rows 가 있으면 그것을 진실값으로.
            mr = resp.get("model_rows")
            n = mr if isinstance(mr, int) else len(elements)
            r[c] = n > 0 or bool(ar.get("results") or ar.get("cycles") or ar.get("members"))
        elif c == "contains":
            r[c] = key in blob
        elif c == "count_fn":
            ar = resp.get("algo_result") or {}
            r[c] = "count(" in cypher.lower() or bool(ar.get("total") or ar.get("count") or ar.get("size"))
        elif c == "algo":
            r[c] = intent == "ALGO" and bool(resp.get("algo_result"))
        elif c == "algo_contains":
            r[c] = key in json.dumps(resp.get("algo_result") or {}, ensure_ascii=False)
        elif c == "general":
            r[c] = (err is None) and (intent not in ("", "QUERY") or not cypher)
        elif c == "nowrite":
            # 통과 = 쓰기 Cypher 미생성 or 생성됐어도 서버 가드가 차단(WRITE_BLOCKED)
            up = cypher.upper()
            no_kw = not any(w in up for w in ("DELETE", "MERGE", " SET ", "CREATE "))
            blocked = "WRITE_BLOCKED" in json.dumps(resp, ensure_ascii=False)
            r[c] = (err is None) and (no_kw or blocked)
    return r


def integrity_snapshot():
    """벤치 실행 전후 그래프 무결성 스냅샷.

    가드 문항('전부 지워줘'·'이름 바꿔줘')은 실패 시 **실제 데이터를 변조**한다.
    2026-09-03 실측: SET 1건이 서버 가드를 통과해 통합 그래프의 주범 이름이
    '조정모'→'홍길동'으로 바뀌었고, 이후 측정에서 P01/V01 이 조용히 실패했다
    (평가 결과가 오염된 데이터를 측정하는 최악의 형태). 그래서 스스로 검증한다.
    """
    import psycopg2
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from app import create_app
        from app.database import safe_set_graph_path
        app = create_app()
        with app.app_context():
            conn = psycopg2.connect(**app.config['DB_CONFIG'])
            conn.autocommit = True
            cur = conn.cursor()
            safe_set_graph_path(cur, GRAPH)
            snap = {}
            for label in ('vt_psn', 'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_case'):
                cur.execute(f"MATCH (n:{label}) RETURN count(n)")
                snap[label] = cur.fetchone()[0]
            for edge in ('transferred_to', 'contacted', 'suspect_in', 'same_as'):
                cur.execute(f"MATCH ()-[r:{edge}]->() RETURN count(r)")
                snap[edge] = cur.fetchone()[0]
            # 핵심 앵커 존재 여부 — 이름 변조를 잡는다
            cur.execute("MATCH (p:vt_psn)-[:suspect_in]->() WHERE p.role CONTAINS '주범' RETURN p.name")
            row = cur.fetchone()
            snap['주범_name'] = row[0] if row else None
            conn.close()
            return snap
    except Exception as e:
        print(f"  (무결성 스냅샷 생략: {e})", flush=True)
        return None


def main():
    only = set(sys.argv[1:])
    items = [it for it in ITEMS if not only or it[0] in only]
    before = integrity_snapshot()
    print(f"통합그래프 T2C 벤치 — {len(items)}문항 · API={API} · graph={GRAPH}", flush=True)
    results = []
    for it in items:
        iid, cat, q, checks, _ = it
        resp, lat, err = ask(q)
        r = evaluate(it, resp, err)
        ok = all(r.values())
        results.append({"id": iid, "category": cat, "question": q, "pass": ok,
                        "checks": r, "latency_s": round(lat, 2),
                        "cypher": (resp.get("cypher") or "")[:220],
                        "n_elements": len(resp.get("elements") or []),
                        "intent": resp.get("intent"), "error": err})
        fails = [k for k, v in r.items() if not v]
        print(f"  {'✅' if ok else '❌'} [{iid}] {q[:34]:36s} {lat:5.1f}s"
              + ("" if ok else f"  실패:{fails}"), flush=True)

    # 무결성 검증 — 가드 문항이 데이터를 변조했으면 점수보다 이 사실이 먼저다.
    after = integrity_snapshot()
    integrity = {"ok": True, "diff": {}}
    if before and after:
        for k, v in before.items():
            if after.get(k) != v:
                integrity["ok"] = False
                integrity["diff"][k] = {"before": v, "after": after.get(k)}
        if not integrity["ok"]:
            print("\n🚨 그래프 무결성 위반 — 벤치 실행이 데이터를 변조했습니다:", flush=True)
            for k, d2 in integrity["diff"].items():
                print(f"   {k}: {d2['before']} → {d2['after']}", flush=True)
            print("   이 결과는 신뢰할 수 없습니다. 데이터 복구 후 재측정하세요.", flush=True)
        else:
            print("\n✅ 그래프 무결성 유지 (노드·엣지 수·핵심 앵커 불변)", flush=True)

    total, passed = len(results), sum(1 for x in results if x["pass"])
    by_cat = {}
    for x in results:
        by_cat.setdefault(x["category"], []).append(x["pass"])
    check_rate = {}
    for x in results:
        for k, v in x["checks"].items():
            check_rate.setdefault(k, []).append(v)
    out = {
        "graph": GRAPH, "api": API, "mode": "E2E(라우팅→스키마→생성→실행→앵커보강)",
        "integrity": integrity,
        "total": total, "passed": passed,
        "pass_rate": round(passed / total * 100, 1) if total else 0,
        "by_category": {c: {"passed": sum(v), "total": len(v),
                            "rate": round(sum(v) / len(v) * 100, 1)}
                        for c, v in sorted(by_cat.items())},
        "by_check": {k: round(sum(v) / len(v) * 100, 1) for k, v in sorted(check_rate.items())},
        "avg_latency_s": round(sum(x["latency_s"] for x in results) / total, 2) if total else 0,
        "details": results,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n=== 결과: {passed}/{total} ({out['pass_rate']}%) · 평균 {out['avg_latency_s']}s ===")
    for c, v in out["by_category"].items():
        print(f"  {c}: {v['passed']}/{v['total']} ({v['rate']}%)")
    print(f"  체크별: {out['by_check']}")
    print(f"저장: {OUT}")


if __name__ == "__main__":
    main()
