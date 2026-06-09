import sys
import os
import json
from unittest.mock import patch, MagicMock

# 프로젝트 루트 경로 확보
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.ai_service import AIService
from app.services.langgraph_agent import LangGraphAgent

# ---------------------------------------------------------
# [추천 2] 50개(예시형 10개) 극악 난이도 자연어 모의 테스트 셋
# ---------------------------------------------------------
COMPLEX_QUERIES = [
    "국민은행 110-222-333 계좌에서 돈을 빼서 SKT 알뜰폰 사용자인 김철수에게 보낸 모든 송금 내역",
    "이태원 살인사건(CASE-001) 용의자들이 접속한 IP 대역과 동일한 위치에서 로그인한 다른 피의자들",
    "최근 3일간 새벽 2시에 특정 ATM 기기에서 500만원 이상 연속 인출된 모든 계좌의 소유주 이름",
    "보이스피싱 주범(010-9999-8888)과 5분 이상 통화한 피해자들이 돈을 입금한 최종 종착지 대포통장",
    "서로 다른 3개의 사건에 동시에 연루된 인물들이 공통으로 사용하는 이메일이나 전화번호",
    "토스뱅크 계좌 999-888-777에서 시작된 자금이 3단계를 거쳐 하나은행으로 들어간 경로",
    "특정 의심 IP(192.168.0.1)를 통해 관리자 페이지에 접근한 이력이 있는 모든 사내 직원",
    "사기꾼 집단 내에서 가장 많이 전화를 주고받은 핵심 연락책(허브 노드) 상위 3명",
    "어제 오후 5시부터 6시 사이에 농협은행(NH) 계좌로 100만원씩 쪼개기 입금된 패턴 분석",
    "특정 피의자가 본인 명의가 아닌 다른 사람의 기기를 사용하여 접속한 접속 기록 전체"
]

def run_offline_cypher_benchmark():
    """DB 없이 vLLM만 사용하여 Cypher 생성 퀄리티 단순 눈으로 검증"""
    print("\n" + "="*60)
    print("🚀 [추천 2] 오프라인 Text-to-Cypher 벤치마크 (AI 능력 테스트)")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        for i, q in enumerate(COMPLEX_QUERIES, 1):
            print(f"\n[{i}/10] 질의: {q}")
            
            # 1. 라우터 전처리 (엔티티 치환 등)
            augmented_q = AIService.augment_entities(q)
            if augmented_q != q:
                print(f"   [!] 자동 변환 힌트 삽입됨: {augmented_q}")
                
            # 2. Cypher 생성 (vLLM 연결)
            try:
                cypher_query = AIService.generate_cypher(augmented_q, graph_path="tccop_graph_v6")
                print(f"   [✨생성된 Cypher]\n     {cypher_query}")
            except Exception as e:
                print(f"   [❌ 생성 실패] {e}")


def run_mock_db_pipeline():
    """LangGraph 전체 파이프라인 (Router -> Synthesis -> Execution) Mocking 테스트"""
    print("\n\n" + "="*60)
    print("🛠️ [추천 3] LangGraph + Mock(가짜) DB 파이프라인 연동 테스트")
    print("="*60)
    
    app = create_app()
    with app.app_context():
        agent = LangGraphAgent()
        
        # 테스트용 질문
        test_q = "국민은행 110-222-333 계좌의 소유주를 찾아줘"
        
        # ===== [핵심] GraphService 함수 가짜 덮어쓰기 (Mocking) =====
        with patch('app.services.graph_service.GraphService.execute_cypher') as mock_db, \
             patch('app.services.graph_service.GraphService.get_current_schema') as mock_schema:
            
            # 1. DB 조회 시 반환할 가짜 데이터 정의
            mock_db.return_value = [
                {
                    "group": "nodes",
                    "data": {"id": "1", "label": "vt_psn", "properties": {"name": "김수사", "id": "900101-1xxxxxx"}}
                }
            ]
            
            # 2. 스키마 조회 시 반환할 가짜 스키마 정의
            mock_schema.return_value = {
                "nodes": ["vt_psn", "vt_bacnt", "vt_telno", "vt_ip", "vt_transfer", "vt_case"],
                "edges": ["has_account", "owns_phone", "involves", "from_account", "to_account"]
            }
            
            print(f"▶ 사용자 질문: {test_q}")
            print(f"▶ DB 상태: [OFFLINE] -> Mock 데이터로 우회 설정됨\n")
            
            # LangGraph 파이프라인 실행
            try:
                results = agent.app.invoke(
                    {
                        "question": test_q,
                        "graph_path": "tccop_graph_v6",
                        "reflection_steps": 0,
                        "error_count": 0  # 초기값 세팅 필수
                    },
                    config={"recursion_limit": 10}
                )
                
                print("▶ [파이프라인 통과 완료] 최종 상태 요약:")
                print(f"  - 인텐트: {results.get('intent')}")
                print(f"  - 키워드: {results.get('keyword')}")
                print(f"  - 생성된 쿼리: {results.get('cypher_query')}")
                
                # Mock DB에서 꺼내온 결과를 확인
                db_results = results.get('results', [])
                if db_results:
                    print(f"  - DB 실행 결과(Mock): {db_results[0]['data']['properties']['name']} (정상 수신됨!)")
                else:
                    print("  - DB 실행 결과: 없음")
                    
                # Mock DB가 실제로 호출되었는지 검증
                mock_db.assert_called_once()
                print("\n✅ LangGraph 파이프라인이 (DB 없이도) 처음부터 끝까지 무결성 있게 동작합니다.")
                
            except Exception as e:
                print(f"\n❌ 파이프라인 에러 발생: {e}")

if __name__ == "__main__":
    # 두 가지 테스트를 순서대로 실행
    run_offline_cypher_benchmark()
    run_mock_db_pipeline()
