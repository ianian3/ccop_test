
import os
import sys
import time
import json
from flask import Flask
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from app.services.ai_service import AIService

def run_performance_test_v6():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    graph_path = "tccop_graph_v6"
    
    test_queries = [
        # [1-10] 기본 엔티티 검색 및 1-Hop 탐색
        "특정 계좌(123-456)의 소유자가 누구인지 찾아줘",
        "인물 '홍길동'이 보유한 모든 전화번호 리스트를 보여줘",
        "사건번호 'CASE-2025-001'에 연루된 모든 피의자 리스트",
        "전화번호 '010-1111-2222'를 사용하는 사람이 접속한 IP 주소 목록",
        "특정 ATM(ATM-01)에서 돈을 인출한 계좌 정보를 모두 찾아줘",
        "피의자 '김철수'와 연관된 모든 사건 리스트",
        "이체 내역 중 금액이 1,000만원 이상인 건들과 연결된 계좌들",
        "특정 IP(1.2.3.4)를 통해 접속한 모든 사용자 ID",
        "계좌 '333-444-555'로 입금한 모든 송금인 계좌번호",
        "특정 전화번호와 통화한 모든 수신자 리스트",
        
        # [11-20] 다층 추적 및 경로 분석 (Multi-Hop)
        "홍길동의 계좌에서 나간 돈이 최종적으로 도달한 계좌들을 추적해줘",
        "김철수와 이영희 사이의 모든 통화 및 이체 연결 고리(3단계 이내)",
        "특정 전화번호로 통화한 사람이 사용한 모든 은행 계좌들",
        "동일한 IP를 공유하는 인물들 간의 자금 흐름 분석",
        "사건 A와 사건 B에 동시에 등장하는 공통 피의자 검색",
        "대포통장 의심 계좌(A)에서 세 단계를 거쳐 세탁된 자금의 행방",
        "특정 사이트에 접속한 사람들이 사용한 공통된 전화번호 추출",
        "피의자 그룹 내에서 가장 빈번하게 통화가 일어나는 핵심 인물 찾기",
        "인물 A의 계좌에서 인물 B의 계좌로 직접 송금이 없어도 연결된 경로가 있는지",
        "특정 계좌와 연결된 모든 증거물(전화, IP, 차량) 통합 조회",
        
        # [21-30] 복잡한 조건 필터링 및 수사 시나리오
        "어제 오후 2시부터 4시 사이에 발생한 100만원 이상의 모든 이체 내역",
        "최근 3일간 5회 이상 빈번하게 송금이 일어난 계좌 간의 관계도",
        "통화 시간이 10분 이상인 긴밀한 관계의 인물들 네트워크",
        "특정 사건과 연관된 인물들이 사용한 모든 가상 자산 정보",
        "보이스피싱 의심 번호와 연관된 모든 인출책 계좌 추적",
        "이동 경로상 동일한 위치(ATM)를 공유하는 피의자들의 접점 분석",
        "특정 IP 대역을 사용하는 조직적인 접속 시도와 연관된 사건들",
        "피의자 한 명을 중심으로 뻗어나가는 3-Hop 이내의 모든 범죄 네트워크",
        "자금 세탁 패턴(순환 송금 등)이 의심되는 계좌 세트 탐지",
        "전체 그래프에서 가장 많은 연결을 가진 상위 10개 허브 노드 정보"
    ]
    
    results = []
    
    print(f"🚀 [Performance Test for {graph_path}] Starting...")
    print(f"📍 Endpoint: {Config.SLLM_ENDPOINT}")
    print(f"📍 Model: {Config.SLLM_MODEL_NAME}")
    print(f"📍 Total Queries: {len(test_queries)}")
    print("-" * 70)
    
    with app.app_context():
        # Schema cache to speed up (optional, but good for testing)
        for i, q in enumerate(test_queries):
            print(f"[{i+1}/{len(test_queries)}] Q: {q}")
            
            start_time = time.time()
            try:
                # generate_cypher now takes graph_path to inject schema correctly
                cypher = AIService.generate_cypher(q, graph_path=graph_path)
                end_time = time.time()
                
                duration = end_time - start_time
                success = len(cypher) > 10 and "MATCH" in cypher
                
                results.append({
                    "query": q,
                    "duration": duration,
                    "success": success,
                    "cypher": cypher
                })
                
                status_emoji = "✅" if success else "⚠️"
                print(f"   {status_emoji} Latency: {duration:.2f}s")
                if success:
                    print(f"   📝 Generated Cypher: {cypher[:100]}...")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                results.append({"query": q, "duration": 0, "success": False, "error": str(e)})

    # Summary
    print("-" * 70)
    valid_results = [r for r in results if r['success']]
    total_time = sum(r['duration'] for r in valid_results)
    avg_time = total_time / len(valid_results) if valid_results else 0
    max_time = max([r['duration'] for r in valid_results]) if valid_results else 0
    min_time = min([r['duration'] for r in valid_results]) if valid_results else 0
    
    print(f"📊 Test Results Summary for {graph_path}:")
    print(f"- Total Test Cases: {len(test_queries)}")
    print(f"- Successful Generations: {len(valid_results)}")
    print(f"- Failures/Empty: {len(test_queries) - len(valid_results)}")
    print(f"- Average Latency: {avg_time:.2f}s")
    print(f"- Max Latency: {max_time:.2f}s")
    print(f"- Min Latency: {min_time:.2f}s")
    print("-" * 70)
    
    # Save results to JSON for later analysis
    output_file = f"perf_results_{graph_path}_{int(time.time())}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "graph": graph_path,
            "model": Config.SLLM_MODEL_NAME,
            "summary": {
                "total": len(test_queries),
                "success": len(valid_results),
                "avg_latency": avg_time
            },
            "details": results
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Detailed results saved to {output_file}")

if __name__ == "__main__":
    run_performance_test_v6()
