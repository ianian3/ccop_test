import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services.langgraph_agent import LangGraphAgent

def test():
    app = create_app()
    with app.app_context():
        agent = LangGraphAgent()
        question = "특정 ATM 번호(atm_no)가 '001'인 기기에서 돈을 입금시킨 사람들의 이름 찾아줘."
        print(f"질문: {question}")
        
        result = agent.run(question, graph_path="tccop_graph_v6")
        
        print("\n최종 사이퍼:")
        print(result.get('cypher', '없음'))
        print(f"결과 건수: {len(result.get('elements', []))}")

if __name__ == "__main__":
    test()
