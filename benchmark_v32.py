#!/usr/bin/env python3
"""
CCOP Text-to-Cypher V3.2 벤치마크 테스트 (32문항)
LangGraph 에이전트 전체 파이프라인을 통해 실행합니다.

Usage:
  python benchmark_v32.py
"""
import os
import sys
import time
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from dotenv import load_dotenv
load_dotenv()

from config import Config

def run_benchmark():
    app = Flask(__name__)
    app.config.from_object(Config)

    graph_path = os.getenv("DEFAULT_GRAPH_PATH", "tccop_graph_v6")

    # === 32문항 V3.2 벤치마크 수트 ===
    test_queries = [
        # [1단계] 기초 단일 노드 및 속성 검색 (Basic)
        "이름이 '피의자1'인 사람(vt_psn) 노드를 모두 찾아줘.",
        "계좌번호가 '110-1111-1111'인 계좌(vt_bacnt)의 주인을 보여줘.",
        "전화번호가 '1000000001'인 통신 기기(vt_telno) 소유자 목록을 뽑아.",
        "사건번호가 'CASE-2023-001'인 사건(vt_case)에 연루된 사람들을 찾아줘.",
        "IP 주소가 '203.108.1.223'인 IP를 통해 접속한 인물 리스트.",

        # [2단계] 방향성 및 단일 이력 추적 (Direction)
        "피의자1 명의의 계좌에서 다른 사람 계좌로 출금(from_account)된 거래 이력 전체.",
        "특정 ATM 기기(ATM-001)에서 돈을 입금(to_account) 시킨 사람들의 이름.",
        "'0100000001' 번호에서 전화를 발신(caller)하여 통화한 기록 전체.",
        "피해자1이 돈을 송금해서 최종적으로 돈을 받은 수신 계좌(to_account) 목록.",
        "불법 도박 집단이 사용한 의심 IP 세트와 연관된 접속 이벤트 내역.",

        # [3단계] 연산자 필터링 (Numeric/Date)
        "이체 금액(amount)이 500만원(5000000) 이상인 거액 송금 거래 내역.",
        "통화 시간(duration)이 600초(10분)를 초과하는 통화 내역 중에 발신자 번호.",
        "이체 금액이 딱 10만원(100000)인 의심스러운 쪼개기 입금 거래들.",
        "등록일시가 '2023-05-01' 이후에 만들어진 모든 대포통장 리스트.",
        "거래 금액이 문자열 '50000'보다 작은(<=) 소액 이체내역을 찾아줘.",

        # [4단계] 네트워크 간접 경로 추적 (Path / Multi-hop)
        "피해자1의 계좌에서 출발해 3단계 거쳐 피의자1에게 도달하는 자금 이동의 경로.",
        "피해자1과 피의자1 사이에 엮여 있는 공통된 관계망(전화, 이체 등)을 그려줘.",
        "서로 다른 3개의 금융 사기 사건에 동시에 공통으로 등장하는 핵심 피의자.",
        "범죄계좌 '110-1111-1111'에서 5단계를 거쳐 세탁된 자금의 최종 종착지 계좌들.",
        "수사 대상자 '피의자1'에서 시작해서 '피의자2'로 향하는 연결망 최단 경로를 추출해.",

        # [5단계] 일반 사용자 / 비격식 언어 테스트 (B2C & Entity)
        "내 국민은행 통장('110-1111-1111')에서 무단으로 돈 빼간 사기꾼들 다 찾아줘.",
        "SKT 폰 쓰는 애들 중에 금융 사기(CASE-99) 저지른 놈들만 솎아내봐.",
        "저 계좌(국민 010-1111-1111)가 토스뱅크에서 우리은행으로 돈 보낸 내역 싹 다 가져와.",
        "새벽에 IP 이상한데서 로그인한 놈들 누구야 찾아봐 줘.",
        "농협은행(NH)에 계좌 튼 사람 명단 싹 뽑아줘.",

        # [6단계] V3.2 신규 엣지 검증
        "국민은행을 사칭한 전화번호 목록을 보여줘.",                  # impersonates
        "진정서 PTN-001이 연결된 정식 수사 사건을 찾아줘.",           # filed_as
        "진정서 PTN-001과 유사한 다른 진정서들을 군집으로 보여줘.",    # clusters_with
        "계좌 '110-1111-1111'이 소속된 은행 조직을 알려줘.",          # belongs_to
        "서울 지역에서 발생한 이동 이벤트 목록.",                       # occurred_at
        "피의자1과 동일인으로 확인된 인물들.",                           # sameAs
        "더치트에서 수집된 데이터의 출처 확인.",                         # sourced_from
    ]

    results = []
    timestamp = int(time.time())

    print("=" * 70)
    print(f"🚀 CCOP Text-to-Cypher V3.2 Benchmark ({len(test_queries)}Q)")
    print(f"📍 Graph: {graph_path}")
    print(f"📍 Endpoint: {Config.SLLM_ENDPOINT or 'OpenAI API'}")
    print(f"📍 Model: {Config.SLLM_MODEL_NAME}")
    print("=" * 70)

    with app.app_context():
        from app.services.langgraph_agent import LangGraphAgent
        agent = LangGraphAgent()

        for i, q in enumerate(test_queries):
            stage = ""
            if i < 5:    stage = "Basic"
            elif i < 10: stage = "Direction"
            elif i < 15: stage = "Numeric"
            elif i < 20: stage = "Path"
            elif i < 25: stage = "B2C"
            else:        stage = "V3.2-Edge"

            print(f"\n[{i+1:02d}/{len(test_queries)}] [{stage}] {q}")

            start = time.time()
            try:
                resp = agent.run(question=q, graph_path=graph_path)
                elapsed = time.time() - start

                status = resp.get("status", "error")
                cypher = resp.get("cypher", "")
                count  = resp.get("results_count", 0)
                intent = resp.get("intent", "")
                error  = resp.get("error")

                # 판정 기준
                has_select = "SELECT" in (cypher or "").upper()
                has_match  = "MATCH" in (cypher or "").upper()
                is_general = resp.get("type") == "general"
                is_guardrail = resp.get("type") == "guardrail"

                if is_general:
                    grade = "GENERAL"
                elif is_guardrail:
                    grade = "BLOCKED"
                elif status == "success" and has_select and has_match:
                    grade = "PASS" if count > 0 else "PASS_0"
                elif status == "partial_success" and has_select:
                    grade = "PARTIAL"
                else:
                    grade = "FAIL"

                emoji = {"PASS": "✅", "PASS_0": "🟡", "PARTIAL": "⚠️",
                         "FAIL": "❌", "GENERAL": "💬", "BLOCKED": "🛡️"}

                print(f"   {emoji.get(grade,'?')} {grade} | {elapsed:.2f}s | rows={count} | intent={intent}")
                if cypher and len(cypher) > 10:
                    print(f"   📝 {cypher[:120]}...")
                if error:
                    print(f"   ⚡ {str(error)[:100]}")

                results.append({
                    "idx": i + 1,
                    "stage": stage,
                    "query": q,
                    "grade": grade,
                    "status": status,
                    "latency": round(elapsed, 3),
                    "results_count": count,
                    "intent": intent,
                    "cypher": cypher,
                    "error": str(error) if error else None
                })
            except Exception as e:
                elapsed = time.time() - start
                print(f"   ❌ EXCEPTION: {e}")
                results.append({
                    "idx": i + 1, "stage": stage, "query": q,
                    "grade": "ERROR", "latency": round(elapsed, 3),
                    "error": str(e)
                })

    # === Summary ===
    print("\n" + "=" * 70)
    print("📊 BENCHMARK RESULTS SUMMARY")
    print("=" * 70)

    grade_counts = {}
    latencies = []
    for r in results:
        g = r.get("grade", "ERROR")
        grade_counts[g] = grade_counts.get(g, 0) + 1
        if r.get("latency"):
            latencies.append(r["latency"])

    pass_total = grade_counts.get("PASS", 0) + grade_counts.get("PASS_0", 0)
    total = len(results)

    print(f"Total: {total} | PASS: {grade_counts.get('PASS',0)} | PASS(0rows): {grade_counts.get('PASS_0',0)} | PARTIAL: {grade_counts.get('PARTIAL',0)} | FAIL: {grade_counts.get('FAIL',0)} | GENERAL: {grade_counts.get('GENERAL',0)} | ERROR: {grade_counts.get('ERROR',0)}")
    print(f"Pass Rate (Syntax): {pass_total}/{total} = {pass_total/total*100:.1f}%")
    if latencies:
        print(f"Avg Latency: {sum(latencies)/len(latencies):.2f}s | Min: {min(latencies):.2f}s | Max: {max(latencies):.2f}s")

    # Stage breakdown
    print("\n📋 Stage Breakdown:")
    stages = ["Basic", "Direction", "Numeric", "Path", "B2C", "V3.2-Edge"]
    for s in stages:
        stage_results = [r for r in results if r.get("stage") == s]
        stage_pass = sum(1 for r in stage_results if r.get("grade") in ("PASS", "PASS_0"))
        stage_total = len(stage_results)
        print(f"  {s:12s}: {stage_pass}/{stage_total}")

    # Save
    output_file = f"benchmark_v32_{timestamp}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "version": "V3.2",
            "graph": graph_path,
            "model": Config.SLLM_MODEL_NAME,
            "endpoint": Config.SLLM_ENDPOINT,
            "timestamp": timestamp,
            "summary": {
                "total": total,
                "pass": grade_counts.get("PASS", 0),
                "pass_0": grade_counts.get("PASS_0", 0),
                "partial": grade_counts.get("PARTIAL", 0),
                "fail": grade_counts.get("FAIL", 0),
                "general": grade_counts.get("GENERAL", 0),
                "error": grade_counts.get("ERROR", 0),
                "pass_rate_pct": round(pass_total / total * 100, 1),
                "avg_latency": round(sum(latencies) / len(latencies), 3) if latencies else 0,
            },
            "details": results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Results saved: {output_file}")
    print("=" * 70)

if __name__ == "__main__":
    run_benchmark()
