"""
logger = logging.getLogger(__name__)

KICS 그래프 분석 서비스 (analysis_service.py)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enhancement Areas 2 & 4:
- 추론 엔진 (INFERENCE_RULES 실행)
- 이상 점수 (Anomaly Score) 시스템
- 중심성 분석 (Centrality Analysis)
- 연쇄사건 탐지
"""

from app.services.graph_service import get_db_connection, GraphService
from app.database import safe_set_graph_path
import logging


class AnalysisService:
    """KICS 그래프 분석 엔진"""

    # ═══════════════════════════════════════════
    # 이상 점수 규칙 (Anomaly Scoring Rules)
    # ═══════════════════════════════════════════
    ANOMALY_RULES = [
        {'name': '다수사건_전화', 'score': 30, 'description': '동일 번호 3건+ 사건 연루',
         'cypher': """
            MATCH (t:vt_telno)<-[:eg_used_phone]-(c:vt_case)
            WITH t.telno as telno, count(c) as case_cnt
            WHERE case_cnt >= 3
            RETURN telno, case_cnt, '다수사건_전화' as rule
         """},
        {'name': '다수사건_계좌', 'score': 30, 'description': '동일 계좌 3건+ 사건 연루',
         'cypher': """
            MATCH (a:vt_bacnt)<-[:eg_used_account]-(c:vt_case)
            WITH a.actno as actno, count(c) as case_cnt
            WHERE case_cnt >= 3
            RETURN actno, case_cnt, '다수사건_계좌' as rule
         """},
        {'name': '다단계이체', 'score': 20, 'description': '3단계+ 자금이동 경로',
         'cypher': """
            MATCH (t1:vt_transfer)-[:to_account]->(a:vt_bacnt)<-[:from_account]-(t2:vt_transfer)-[:to_account]->(b:vt_bacnt)<-[:from_account]-(t3:vt_transfer)
            RETURN a.actno, b.actno, '다단계이체' as rule
         """},
        {'name': '대량통화', 'score': 15, 'description': '동일 번호 50건+ 통화',
         'cypher': """
            MATCH (c:vt_call)-[:caller]->(t:vt_telno)
            WITH t.telno as telno, count(c) as call_cnt
            WHERE call_cnt >= 50
            RETURN telno, call_cnt, '대량통화' as rule
         """},
    ]

    @staticmethod
    def run_anomaly_scoring(graph_name='test_local_data'):
        """이상 점수 분석 실행"""
        conn, cur = get_db_connection()
        if not conn:
            return {'error': 'DB 연결 실패'}

        results = {'graph': graph_name, 'alerts': [], 'summary': {}}
        
        try:
            conn.autocommit = False
            safe_set_graph_path(cur, graph_name)
            
            for rule in AnalysisService.ANOMALY_RULES:
                try:
                    cur.execute(rule['cypher'])
                    rows = cur.fetchall()
                    for r in rows:
                        results['alerts'].append({
                            'rule': rule['name'],
                            'score': rule['score'],
                            'description': rule['description'],
                            'data': [str(x) for x in r]
                        })
                except Exception as e:
                    logger.error(f"[Anomaly Rule Error: {rule['name']}] {e}")
            
            # 요약 통계
            total_score = sum(a['score'] for a in results['alerts'])
            results['summary'] = {
                'total_alerts': len(results['alerts']),
                'total_score': total_score,
                'risk_level': '🔴 고위험' if total_score >= 80 else '🟡 주의' if total_score >= 50 else '🟢 정상',
                'top_rules': {}
            }
            for a in results['alerts']:
                r = a['rule']
                results['summary']['top_rules'][r] = results['summary']['top_rules'].get(r, 0) + 1
            
            return results
        except Exception as e:
            return {'error': str(e)}
        finally:
            conn.close()

    @staticmethod
    def run_centrality_analysis(graph_name='test_local_data'):
        """중심성 분석 — 가장 많은 연결을 가진 노드 식별"""
        conn, cur = get_db_connection()
        if not conn:
            return {'error': 'DB 연결 실패'}
        
        results = {'accounts': [], 'phones': [], 'persons': []}
        
        try:
            conn.autocommit = False
            safe_set_graph_path(cur, graph_name)
            
            # 계좌 중심성 (연결된 이체 수)
            cur.execute("""
                MATCH (a:vt_bacnt)<-[r]-(n)
                RETURN a.actno, count(r) as degree
                ORDER BY degree DESC LIMIT 10
            """)
            for r in cur.fetchall():
                results['accounts'].append({'id': str(r[0]), 'degree': int(r[1])})
            
            # 전화번호 중심성 (연결된 통화 수)
            cur.execute("""
                MATCH (t:vt_telno)<-[r]-(n)
                RETURN t.telno, count(r) as degree
                ORDER BY degree DESC LIMIT 10
            """)
            for r in cur.fetchall():
                results['phones'].append({'id': str(r[0]), 'degree': int(r[1])})
            
            # 인물 중심성
            cur.execute("""
                MATCH (p:vt_psn)-[r]-(n)
                RETURN p.id, p.name, count(r) as degree
                ORDER BY degree DESC LIMIT 10
            """)
            for r in cur.fetchall():
                results['persons'].append({'id': str(r[0]), 'name': str(r[1]), 'degree': int(r[2])})
            
            return results
        except Exception as e:
            return {'error': str(e)}
        finally:
            conn.close()

    @staticmethod
    def run_inference_engine(graph_name='test_local_data'):
        """추론 엔진 — INFERENCE_RULES 기반 패턴 탐지"""
        from app.services.ontology_service import KICSCrimeDomainOntology
        
        conn, cur = get_db_connection()
        if not conn:
            return {'error': 'DB 연결 실패'}
        
        results = {'patterns': [], 'new_edges': 0}
        
        try:
            conn.autocommit = False
            safe_set_graph_path(cur, graph_name)
            
            for rule in KICSCrimeDomainOntology.INFERENCE_RULES:
                pattern = rule.get('pattern', '')
                threshold = rule.get('threshold', 3)
                
                if pattern == 'shared_resource_usage':
                    # 동일 자원 다수 사건 사용 → 조직범죄
                    cur.execute(f"""
                        MATCH (t:vt_telno)<-[:eg_used_phone]-(c:vt_case)
                        WITH t, collect(c.flnm) as cases
                        WHERE size(cases) >= {threshold}
                        RETURN t.telno, cases
                    """)
                    for r in cur.fetchall():
                        results['patterns'].append({
                            'rule': rule['name'],
                            'confidence': rule['confidence'],
                            'evidence': str(r[0]),
                            'cases': [str(x) for x in r[1]] if isinstance(r[1], list) else [str(r[1])]
                        })
                
                elif pattern == 'multi_hop_transfer':
                    # 다단계 이체 → 자금세탁
                    cur.execute(f"""
                        MATCH (t1:vt_transfer)-[:to_account]->(a:vt_bacnt)<-[:from_account]-(t2:vt_transfer)
                        WITH a, count(*) as hops
                        WHERE hops >= {threshold}
                        RETURN a.actno, hops
                    """)
                    for r in cur.fetchall():
                        results['patterns'].append({
                            'rule': rule['name'],
                            'confidence': rule['confidence'],
                            'evidence': str(r[0]),
                            'hop_count': int(r[1])
                        })
            
            return results
        except Exception as e:
            return {'error': str(e)}
        finally:
            conn.close()

    @staticmethod
    def get_case_summary(graph_name='test_local_data'):
        """사건 종합 요약 — AI 브리핑용"""
        conn, cur = get_db_connection()
        if not conn:
            return {'error': 'DB 연결 실패'}
        
        summary = {'cases': [], 'total_nodes': 0, 'total_edges': 0, 'node_types': {}, 'edge_types': {}}
        
        try:
            conn.autocommit = False
            safe_set_graph_path(cur, graph_name)
            
            # 전체 노드/엣지 수
            cur.execute("MATCH (n) RETURN count(n)")
            summary['total_nodes'] = int(cur.fetchone()[0])
            
            cur.execute("MATCH ()-[r]->() RETURN count(r)")
            summary['total_edges'] = int(cur.fetchone()[0])
            
            # 노드 타입별 수
            for label in ['vt_case', 'vt_psn', 'vt_bacnt', 'vt_telno', 'vt_transfer', 'vt_call', 
                          'vt_ip', 'vt_org', 'vt_msg', 'vt_vhcl', 'vt_loc_evt', 'vt_lpr_evt', 'vt_site', 'vt_file']:
                try:
                    cur.execute(f"MATCH (n:{label}) RETURN count(n)")
                    cnt = int(cur.fetchone()[0])
                    if cnt > 0:
                        summary['node_types'][label] = cnt
                except: pass
            
            # 사건별 요약
            cur.execute("MATCH (c:vt_case) RETURN c.flnm, c.crime, c.date LIMIT 20")
            for r in cur.fetchall():
                summary['cases'].append({
                    'case_no': str(r[0]),
                    'crime': str(r[1]),
                    'date': str(r[2])
                })
            
            return summary
        except Exception as e:
            return {'error': str(e)}
        finally:
            conn.close()
