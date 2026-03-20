import os
import sys
import logging
from dotenv import load_dotenv

# 애플리케이션 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.vector_rag_service import VectorRAGService

# 로그 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    load_dotenv()
    
    # Flask 앱 컨텍스트 생성 (config 및 OpenAI API 키 로드용)
    app = create_app()
    
    graph_path = "tccop_graph_v6"
    
    with app.app_context():
        logger.info(f"🚀 '{graph_path}' 에 대한 벡터 DB 빌드 작업을 시작합니다...")
        
        success = VectorRAGService.build_entity_vectors(graph_path)
        
        if success:
            logger.info(f"✅ 벡터 DB 빌드 성공! 이제 RAG 기반의 정교한 엔티티 매칭이 가능합니다.")
        else:
            logger.error(f"❌ 벡터 DB 빌드 실패. 로그를 확인해 주세요.")

if __name__ == "__main__":
    main()
