import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services.langgraph_agent import LangGraphAgent

def test_q7():
    app = create_app()
    with app.app_context():
        agent = LangGraphAgent()
        question = "특정 ATM 기기(ATM-001)에서 돈을 입금(to_account) 시킨 사람들의 이름."
        print(f"질문: {question}")
        
        result = agent.run(question, graph_path="tccop_graph_v6")
        
        print("\n최종 사이퍼:")
        print(result.get('cypher', '없음'))
        
        if result.get('error'):
            print(f"에러: {result.get('error')}")

if __name__ == "__main__":
    test_q7()
