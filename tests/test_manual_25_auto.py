import sys
import os
import re

# 프로젝트 루트(app 접근용) 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.ai_service import AIService

def extract_queries_from_md(file_path):
    queries = []
    if not os.path.exists(file_path):
        return queries
        
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            # "1. 질문내용" 형태의 정규식 추출
            match = re.match(r'^\d+\.\s+(.+)', line)
            if match:
                queries.append(match.group(1).strip())
    return queries

def run_manual_25_test():
    doc_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../docs/Test_Queries_30.md'))
    queries = extract_queries_from_md(doc_path)
    
    if not queries:
        print("❌ 마크다운 문서에서 파싱할 문항을 찾지 못했습니다.")
        return

    app = create_app()
    with app.app_context():
        success = 0
        total = len(queries)
        
        print("\n" + "="*70)
        print(f"🚀 [맞춤형 테스트] 수사관 에디팅 25문항 자동화 벤치마크")
        print("="*70)
        
        for i, q in enumerate(queries, 1):
            print(f"\n[{i}/{total}] 질의: {q}")
            
            # AI 서비스 단의 자동 엔티티 교정 로직 검증 
            aug_q = AIService.augment_entities(q)
            if aug_q != q:
                # 변경된 부분만 대략적으로 추려내기보단 원본과 다른 경우 알림
                print(f"   [💡 AI 자동 교정 적용]")
                
            try:
                # vLLM Generate
                cypher = AIService.generate_cypher(aug_q, graph_path="tccop_graph_v6")
                
                # 쿼리 평가 로직
                if "SELECT * FROM cypher(" in cypher:
                    clean_cypher = cypher.replace("\n", " ").replace("  ", " ")
                    print(f"   [✨ 생성 성공]\n     {clean_cypher}")
                    success += 1
                else:
                    print(f"   [❌ 문법 치명적 오류] AgensGraph 문법 실패: {cypher}")
                    
            except Exception as e:
                print(f"   [❌ 시스템/연결 에러] {e}")

        print("\n" + "="*70)
        print(f"🎯 25문항 평가 완료: 통과율 {(success/total)*100}% ({success}/{total}건 성공)")
        print("="*70)

if __name__ == "__main__":
    run_manual_25_test()
