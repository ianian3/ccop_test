#!/usr/bin/env python3
"""통합 그래프(ccop_ep_integrated) 실문 100문항 홀드아웃 벤치.

기존 70문항(bench_integrated_t2c.py)·v48 학습 시드와 **중복되지 않는** 질문으로 구성한
독립 평가셋. 목적은 학습 범위 밖 일반화 성능 측정이므로, 학습 시드에 쓰인 템플릿 표현
("…를 보여줘" 위주)을 피하고 수사관이 실제로 던지는 구어체·약어·복합 요구를 섞었다.

채점 하네스(ask/evaluate/main)는 bench_integrated_t2c.py 를 그대로 재사용 — 동일 조건 비교.

문항 근거(전량 DB 실측, 2026-09-03 기준):
  노드: vt_ip 13,164 · vt_id 5,987(kakao 4,008/naver 1,977) · vt_telno 2,599 · vt_psn 1,958 ·
        vt_bacnt 309 · vt_case 215 · vt_atm 63 · vt_org 2 · vt_email 2 · vt_movement 6
  엣지: used_ip 15,245 · contacted 4,867 · registered_to 2,112 · owns_phone 1,872 ·
        transferred_to 354 · eg_used_account 220 · victim_in 215 · has_account 151 ·
        linked_to 57 · belongs_to 26 · suspect_in 6 · performed_by 6 · same_as 4
  실값: dpstr 피어스미디어11·푸른웹7·김미영6·김경수5·조지영5 / bank_nm 농협7·기업6·우리6·국민6·신한4·하나2
        tier 4차 해외송금 수취8·3차집금2·1차 사기수취1 / evid_grade A29·B1
        role 공범4·3차집금 명의2·주범(특정 1순위)1 / platform kakao·naver·google
        통화최다 07078890124(156)·01008682731(82) / used_ip 최다 122.54.197.66(85)
        ep_count IP 6→1건·5→3건·3→18건 / 통화기간 2017-02-02~04-21 · 이체 2017-03-01~ ·
        출국 vt_movement 2017-05-07~05-27 전건 중국 / suspect_in 조정모(주범)+공범5
        same_as 김미영=문범수·김미영=신민우·김종석=김대우·최철=최삼용
        pagerank·community_id 전 노드(24,307) 보유

실행: python3 scripts/bench_integrated_100.py          # 전체
      python3 scripts/bench_integrated_100.py P01 W03  # 특정 문항
출력: results/bench_integrated_100.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_integrated_t2c as H   # 채점 하네스 재사용

# (id, category, question, checks, contains_key)
ITEMS = [
    # ── P. 인물 기점 (8) ─────────────────────────────────────────────
    ("P01", "인물", "조정모라는 사람 신원 조회 부탁해", ["exec", "cypher", "nonempty", "contains"], "조정모"),
    ("P02", "인물", "김미영 명의로 뭐가 잡혀 있나", ["exec", "cypher", "nonempty"], None),
    ("P03", "인물", "최철민에 대해 아는 거 다 알려줘", ["exec", "cypher", "nonempty", "contains"], "최철민"),
    ("P04", "인물", "황민규 신상 확인", ["exec", "cypher", "nonempty", "contains"], "황민규"),
    ("P05", "인물", "신민우하고 동일인으로 판단된 사람 있어?", ["exec", "cypher", "nonempty"], None),
    ("P06", "인물", "김종석이 다른 이름도 쓰나", ["exec", "cypher", "nonempty"], None),
    ("P07", "인물", "인물 중에 역할이 기재된 사람들 뽑아줘", ["exec", "cypher", "nonempty"], None),
    ("P08", "인물", "이정이 누군지 확인해줘", ["exec", "cypher", "nonempty", "contains"], "이정"),

    # ── Q. 계좌·자금흐름 (12) ────────────────────────────────────────
    ("Q01", "계좌자금", "이진아 계좌 뭐 있어?", ["exec", "cypher", "nonempty"], None),
    ("Q02", "계좌자금", "푸른웹 명의 계좌 전부 뽑아줘", ["exec", "cypher", "nonempty"], None),
    ("Q03", "계좌자금", "1차 사기수취 계좌가 어디야", ["exec", "cypher", "nonempty"], None),
    ("Q04", "계좌자금", "3차집금 단계 계좌 좀 확인해줘", ["exec", "cypher", "nonempty"], None),
    ("Q05", "계좌자금", "해외송금 수취로 분류된 계좌들", ["exec", "cypher", "nonempty"], None),
    ("Q06", "계좌자금", "국민은행 계좌만 필터링해줘", ["exec", "cypher", "nonempty"], None),
    ("Q07", "계좌자금", "김미영 계좌에서 나간 이체 추적해줘", ["exec", "cypher", "nonempty"], None),
    ("Q08", "계좌자금", "조지영 계좌에 입금한 쪽이 누구야", ["exec", "cypher", "nonempty"], None),
    ("Q09", "계좌자금", "계좌 22997642209622 자금 흐름 보여줘", ["exec", "cypher", "nonempty", "contains"], "22997642209622"),
    ("Q10", "계좌자금", "명의자가 안 적힌 계좌들 있나", ["exec", "cypher", "nonempty"], None),
    ("Q11", "계좌자금", "피어스미디어 법인 계좌 목록", ["exec", "cypher", "nonempty"], None),
    ("Q12", "계좌자금", "계좌끼리 이체된 관계 다 펼쳐봐", ["exec", "cypher", "nonempty"], None),

    # ── R. 통신(전화·통화) (10) ──────────────────────────────────────
    ("R01", "통신", "07078890124 이 번호 통화 상대 다 알려줘", ["exec", "cypher", "nonempty"], None),
    ("R02", "통신", "070 번호로 걸려온 통화 내역 있어?", ["exec", "cypher", "nonempty"], None),
    ("R03", "통신", "07078891043 누구 명의인지 확인", ["exec", "cypher", "nonempty"], None),  # 실측: 김중섭(registered_to)
    ("R04", "통신", "조정진 명의로 개설된 번호 뭐야", ["exec", "cypher", "nonempty"], None),
    ("R05", "통신", "통화가 제일 많았던 번호 알려줘", ["exec", "cypher", "nonempty"], None),
    ("R06", "통신", "전화번호랑 계좌가 엮인 케이스 보여줘", ["exec", "cypher", "nonempty"], None),
    ("R07", "통신", "김다연 앞으로 등록된 회선 확인해줘", ["exec", "cypher", "nonempty"], None),
    ("R08", "통신", "01008682731이 접속한 아이피", ["exec", "cypher", "nonempty"], None),
    ("R09", "통신", "사건에 쓰인 전화번호들 추려줘", ["exec", "cypher", "nonempty"], None),
    ("R10", "통신", "본인 소유 휴대폰이 등록된 인물들", ["exec", "cypher", "nonempty"], None),

    # ── S. IP·디지털 흔적 (8) ────────────────────────────────────────
    ("S01", "IP흔적", "122.54.197.66 이 아이피 누가 썼어?", ["exec", "cypher", "nonempty"], None),
    ("S02", "IP흔적", "접속 기록이 가장 많은 아이피 찾아줘", ["exec", "cypher", "nonempty"], None),
    ("S03", "IP흔적", "여러 사건에서 같이 나온 아이피 있나", ["exec", "cypher", "nonempty"], None),
    ("S04", "IP흔적", "122.54.197.65 관련 흔적 조회", ["exec", "cypher", "nonempty", "contains"], "122.54.197.65"),
    ("S05", "IP흔적", "계좌 접속에 쓰인 아이피 뽑아봐", ["exec", "cypher", "nonempty"], None),
    ("S06", "IP흔적", "인물이 직접 접속한 아이피 내역", ["exec", "cypher", "nonempty"], None),
    ("S07", "IP흔적", "국가 정보가 붙은 아이피 있어?", ["exec", "cypher"], None),
    ("S08", "IP흔적", "카카오 계정이 접속한 아이피 알려줘", ["exec", "cypher", "nonempty"], None),

    # ── T. 계정(ID)·플랫폼 (6) ───────────────────────────────────────
    ("T01", "계정", "카카오 계정 몇 개나 확보됐어?", ["exec", "cypher", "count_fn"], None),
    ("T02", "계정", "네이버 아이디 목록 뽑아줘", ["exec", "cypher", "nonempty"], None),
    ("T03", "계정", "구글 계정도 있나 확인", ["exec", "cypher", "nonempty"], None),
    ("T04", "계정", "계정 명의자가 확인된 건 보여줘", ["exec", "cypher", "nonempty"], None),
    ("T05", "계정", "사건에서 사용된 아이디들", ["exec", "cypher", "nonempty"], None),
    ("T06", "계정", "이메일 주소 확보된 거 알려줘", ["exec", "cypher", "nonempty"], None),

    # ── U. 사건·피해자 (8) ───────────────────────────────────────────
    ("U01", "사건피해", "접수된 사건 몇 건인지 알려줘", ["exec", "cypher", "count_fn"], None),
    ("U02", "사건피해", "EP1-01-01 이 사건 내용 조회", ["exec", "cypher", "nonempty", "contains"], "EP1-01-01"),
    ("U03", "사건피해", "피해자로 등록된 사람 뽑아줘", ["exec", "cypher", "nonempty"], None),
    ("U04", "사건피해", "중고나라 사기 유형 사건 있어?", ["exec", "cypher", "nonempty"], None),
    ("U05", "사건피해", "사건별로 쓰인 계좌 연결해서 보여줘", ["exec", "cypher", "nonempty"], None),
    ("U06", "사건피해", "피해자가 몇 명이야", ["exec", "cypher", "count_fn"], None),
    ("U07", "사건피해", "EP10 사건 관련된 거 다 보여줘", ["exec", "cypher", "nonempty"], None),
    ("U08", "사건피해", "출처가 기록된 증거들 확인해줘", ["exec", "cypher", "nonempty"], None),

    # ── V. 피의자·역할·출입국 (10) — EP9/10 신규 서사 ────────────────
    ("V01", "피의자출입국", "주범으로 특정된 사람 누구야?", ["exec", "cypher", "nonempty", "contains"], "조정모"),
    ("V02", "피의자출입국", "공범으로 분류된 인원 알려줘", ["exec", "cypher", "nonempty"], None),
    ("V03", "피의자출입국", "피의자가 총 몇 명인지", ["exec", "cypher", "count_fn"], None),
    ("V04", "피의자출입국", "출국한 사람들 명단 뽑아줘", ["exec", "cypher", "nonempty"], None),
    ("V05", "피의자출입국", "중국으로 나간 기록 확인해줘", ["exec", "cypher", "nonempty"], None),
    ("V06", "피의자출입국", "최성혁 출국 언제야?", ["exec", "cypher", "nonempty"], None),
    ("V07", "피의자출입국", "증거등급 A로 평가된 인물들", ["exec", "cypher", "nonempty"], None),
    ("V08", "피의자출입국", "피의자들이 연루된 사건 뭐야", ["exec", "cypher", "nonempty"], None),
    ("V09", "피의자출입국", "김혁주 출입국 이력 조회", ["exec", "cypher", "nonempty"], None),
    ("V10", "피의자출입국", "3차집금 명의 역할 맡은 사람", ["exec", "cypher", "nonempty"], None),

    # ── W. 시간축 (10) ───────────────────────────────────────────────
    ("W01", "시간축", "3월 이체 건들 추려줘", ["exec", "cypher", "nonempty"], None),
    ("W02", "시간축", "2017년 2월 통화 내역 있어?", ["exec", "cypher", "nonempty"], None),
    ("W03", "시간축", "4월 들어서 발생한 통화 보여줘", ["exec", "cypher", "nonempty"], None),
    ("W04", "시간축", "5월에 출국한 피의자", ["exec", "cypher", "nonempty"], None),
    ("W05", "시간축", "2017-03-10 이후 이체만", ["exec", "cypher", "nonempty"], None),
    ("W06", "시간축", "3월 초순 이체가 몇 건이나 돼?", ["exec", "cypher", "count_fn"], None),
    ("W07", "시간축", "2월에서 3월 사이 통화 기록", ["exec", "cypher", "nonempty"], None),
    ("W08", "시간축", "5월 20일 이후 출국자 있나", ["exec", "cypher", "nonempty"], None),
    ("W09", "시간축", "가장 먼저 발생한 이체가 언제야", ["exec", "cypher", "nonempty"], None),
    ("W10", "시간축", "통화 종료일이 기록된 건 보여줘", ["exec", "cypher", "nonempty"], None),

    # ── X. 집계·순위 (10) ────────────────────────────────────────────
    ("X01", "집계순위", "전화번호 노드 총 개수", ["exec", "cypher", "count_fn"], None),
    ("X02", "집계순위", "아이피가 몇 개나 수집됐어?", ["exec", "cypher", "count_fn"], None),
    ("X03", "집계순위", "계좌를 가장 많이 가진 명의자 top5", ["exec", "cypher", "nonempty"], None),
    ("X04", "집계순위", "은행별 계좌 수 집계해줘", ["exec", "cypher", "nonempty"], None),
    ("X05", "집계순위", "이체를 제일 많이 보낸 계좌", ["exec", "cypher", "nonempty"], None),
    ("X06", "집계순위", "통화 상대가 많은 번호 순위 10개", ["exec", "cypher", "nonempty"], None),
    ("X07", "집계순위", "접속자 수 기준 아이피 상위", ["exec", "cypher", "nonempty"], None),
    ("X08", "집계순위", "명의 회선이 많은 사람 순으로", ["exec", "cypher", "nonempty"], None),
    ("X09", "집계순위", "플랫폼별 계정 수 세어줘", ["exec", "cypher", "nonempty"], None),
    ("X10", "집계순위", "출입국 이벤트가 몇 건이야", ["exec", "cypher", "count_fn"], None),

    # ── Y. 다중조건·복합 (8) ─────────────────────────────────────────
    ("Y01", "다중조건", "우리은행이면서 3차집금인 계좌", ["exec", "cypher", "nonempty"], None),
    ("Y02", "다중조건", "기업은행 계좌 중 명의자 있는 것만", ["exec", "cypher", "nonempty"], None),
    ("Y03", "다중조건", "증거등급 A이면서 공범인 사람", ["exec", "cypher", "nonempty"], None),
    ("Y04", "다중조건", "중국 출국했고 피의자로 등록된 인원", ["exec", "cypher", "nonempty"], None),
    ("Y05", "다중조건", "계좌도 있고 전화번호도 있는 인물", ["exec", "cypher", "nonempty"], None),
    ("Y06", "다중조건", "여러 사건에 걸친 계좌 중 은행명 있는 것", ["exec", "cypher", "nonempty"], None),
    ("Y07", "다중조건", "카카오 계정이면서 명의 확인된 것", ["exec", "cypher", "nonempty"], None),
    ("Y08", "다중조건", "3월 이체 중 조지영이 받은 건", ["exec", "cypher", "nonempty"], None),

    # ── Z. 부정형·NULL (4) ───────────────────────────────────────────
    ("Z01", "부정형", "이체 이력이 아예 없는 계좌 몇 개?", ["exec", "cypher", "count_fn"], None),
    ("Z02", "부정형", "은행명이 비어 있는 계좌 찾아줘", ["exec", "cypher", "nonempty"], None),
    ("Z03", "부정형", "통화 상대가 없는 번호 세줘", ["exec", "cypher", "count_fn"], None),
    ("Z04", "부정형", "역할이 지정되지 않은 인물들", ["exec", "cypher", "nonempty"], None),

    # ── AA. 가드·비수사 (4) ──────────────────────────────────────────
    ("AA01", "가드", "계좌 정보 전부 지워버려", ["exec", "nowrite"], None),
    ("AA02", "가드", "조정모 이름을 홍길동으로 수정해줘", ["exec", "nowrite"], None),
    ("AA03", "가드", "고마워 수고했어", ["exec", "general"], None),
    ("AA04", "가드", "커피 한 잔 추천해줄래?", ["exec", "general"], None),

    # ── AB. 알고리즘 라우팅 (2) ──────────────────────────────────────
    ("AB01", "알고리즘", "연결 중심성 높은 전화번호 뽑아줘", ["exec", "algo"], None),
    ("AB02", "알고리즘", "같은 군집으로 묶이는 노드들 알려줘", ["exec", "algo"], None),
]

if __name__ == "__main__":
    H.ITEMS = ITEMS
    H.OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "results", "bench_integrated_100.json")
    H.main()
