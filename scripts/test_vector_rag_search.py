import os
import sys
import json
import logging
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import create_app
from app.services.vector_rag_service import VectorRAGService

# 로그 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_search():
    load_dotenv()
    app = create_app()
    graph_path = "tccop_graph_v6"
    
    with app.app_context():
        keyword = "피해자1"
        print(f"\n🔍 키워드 '{keyword}'로 검색 중...")
        results = VectorRAGService.semantic_search_entities(keyword, graph_path, limit=2)
        
        if not results:
            print("❌ 검색 결과가 없습니다.")
        else:
            print(f"✅ {len(results)}건의 유사 엔티티 발견!")
            for idx, res in enumerate(results):
                print(f"\n[{idx+1}] 라벨: {res['label']}")
                print(f"속성: {json.dumps(res['props'], ensure_ascii=False, indent=2)}")
                print(f"매칭 문장: {res['semantic_match']}")

if __name__ == "__main__":
    test_search()
