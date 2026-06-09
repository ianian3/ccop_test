import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services.langgraph_agent import LangGraphAgent

def test_question_2():
    app = create_app()
    with app.app_context():
        agent = LangGraphAgent()
        question = "특정 ATM 기기 'ATM-부산001'에서 돈을 입금시킨 사람들의 이름 찾아줘.."
        print(f"질문: {question}")
        
        result = agent.run(question, graph_path="tccop_graph_v6")
        
        print("\n최종 사이퍼:")
        print(result.get('cypher', '없음'))
        
        elements = result.get('elements', [])
        print(f"\n최종 결과 건수: {len(elements)}")
        print("샘플 데이터:", elements[:2])

if __name__ == "__main__":
    test_question_2()
