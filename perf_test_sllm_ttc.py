
import os
import sys
import time
import json
import statistics
from flask import Flask
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from app.services.ai_service import AIService

def run_performance_test():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    test_queries = [
        "특정 계좌(123-456)의 모든 거래 내역 조회해줘",
        "홍길동과 김철수 사이의 최단 연결 경로가 뭐야?",
        "500만원 이상 이체된 건수와 연관된 인물들을 모두 찾아줘",
        "피의자 이영희가 소유한 전화번호와 최근 통화한 상대방 리스트",
        "이 사건과 연관된 모든 IP 주소와 접속 사이트 정보를 추출해줘"
    ]
    
    results = []
    
    print(f"🚀 [On-premise sLLM TTC Performance Test] Starting...")
    print(f"📍 Endpoint: {Config.SLLM_ENDPOINT}")
    print(f"📍 Model: {Config.SLLM_MODEL_NAME}")
    print("-" * 60)
    
    with app.app_context():
        for i, q in enumerate(test_queries):
            print(f"[{i+1}/{len(test_queries)}] Query: {q}")
            
            start_time = time.time()
            try:
                cypher = AIService.generate_cypher(q)
                end_time = time.time()
                
                duration = end_time - start_time
                success = len(cypher) > 20 and "MATCH" in cypher
                
                results.append({
                    "query": q,
                    "duration": duration,
                    "success": success,
                    "cypher_preview": cypher[:80] + "..." if len(cypher) > 80 else cypher
                })
                
                status_emoji = "✅" if success else "⚠️"
                print(f"   {status_emoji} Time: {duration:.2f}s")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                results.append({"query": q, "duration": 0, "success": False, "error": str(e)})

    # Summary
    print("-" * 60)
    total_time = sum(r['duration'] for r in results if r['success'])
    avg_time = total_time / len([r for r in results if r['success']]) if results else 0
    
    print(f"📊 Test Summary:")
    print(f"- Total Queries: {len(test_queries)}")
    print(f"- Successful: {len([r for r in results if r['success'] or (not r.get('error') and r.get('duration') > 0)])}")
    print(f"- Average Latency: {avg_time:.2f}s")
    print("-" * 60)
    
    # Detailed Table-like output
    print(f"{'No':<3} | {'Latency':<8} | {'Status':<7} | {'Query'}")
    for idx, r in enumerate(results):
        status = "PASS" if r['success'] else "FAIL"
        print(f"{idx+1:<3} | {r['duration']:>6.2f}s | {status:<7} | {r['query']}")

if __name__ == "__main__":
    run_performance_test()
