import os
import sys
import logging
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from app import create_app
from app.services.langgraph_agent import LangGraphAgent

# 로그 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_specific_query():
    load_dotenv()
    app = create_app()
    graph_name = "tccop_graph_v6"
    
    test_questions = [
        "피해자1 이라는 사람을 찾아줘",
        "피해자1 연결 계좌 보여줘",
        "피의자1 이 보유한 계좌번호 찾아줘",
        "계좌 '110-1111-1111' 에서 발생한 이체(vt_transfer) 내역",
        "전화번호 '1000000001' 을 사용하는 사람",
    ]
    
    with app.app_context():
        agent = LangGraphAgent()
        
        for question in test_questions:
            print(f"\n🚀 질문 테스트: '{question}'")
            result = agent.run(question, graph_name)
            
            print(f"   - Status: {result.get('status')}")
            print(f"   - Generated Cypher: {result.get('cypher')}")
            print(f"   - Results Count: {result.get('results_count')}")
            if result.get('error'):
                print(f"   - Error: {result.get('error')}")

if __name__ == "__main__":
    test_specific_query()
