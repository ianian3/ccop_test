
import os
import psycopg2
from flask import current_app
from app.services.legal_rag_service import LegalRAGService

try:
    import psutil
except ImportError:
    psutil = None

class MonitoringService:
    """
    Hybrid DB Monitoring Service
    - RDB (PostgreSQL)
    - GDB (AgensGraph)
    - Vector DB (ChromaDB)
    """

    @staticmethod
    def get_system_stats():
        """시스템 리소스 사용량"""
        if not psutil: return {"error": "psutil module not installed"}
        try:
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_percent": disk.percent
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def get_rdb_stats():
        """RDB 상태 및 통계"""
        conn = None
        try:
            cfg = current_app.config['DB_CONFIG']
            conn = psycopg2.connect(**cfg)
            cur = conn.cursor()
            
            # 1. DB 기본 정보
            cur.execute("SELECT current_database(), pg_size_pretty(pg_database_size(current_database()))")
            db_name, db_size = cur.fetchone()
            
            # 2. 활성 연결 수
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            active_conn = cur.fetchone()[0]
            
            # 3. 주요 테이블 건수 (Row Count)
            tables = []
            target_tables = ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones', 'rdb_calls']
            for t in target_tables:
                try:
                    cur.execute(f"SELECT count(*) FROM {t}")
                    cnt = cur.fetchone()[0]
                    tables.append({"name": t, "count": cnt})
                except:
                    pass
                    
            return {
                "status": "online",
                "db_name": db_name,
                "size": db_size,
                "active_connections": active_conn,
                "tables": tables
            }
        except Exception as e:
            return {"status": "offline", "error": str(e)}
        finally:
            if conn: conn.close()

    @staticmethod
    def get_gdb_stats():
        """AgensGraph 상태 및 통계"""
        conn = None
        try:
            cfg = current_app.config['DB_CONFIG']
            conn = psycopg2.connect(**cfg)
            conn.autocommit = True
            cur = conn.cursor()
            
            # 그래프 목록 조회
            cur.execute("SELECT graphname FROM pg_catalog.ag_graph ORDER BY graphname")
            graphs = [r[0] for r in cur.fetchall()]
            
            graph_stats = []
            for g in graphs:
                # 각 그래프별 노드/엣지 수 (대략적)
                try:
                    cur.execute(f"SET graph_path = {g}")
                    
                    # 노드 수 (information_schema 활용 - vt_ 테이블)
                    # 실제 count(*)는 느릴 수 있으므로, 여기서는 테이블 개수로 대체하거나
                    # 꼭 필요하면 count(*) 수행. (모니터링이므로 성능 주의)
                    
                    # 1. Vertex Label 수 (테이블명 vt_로 시작)
                    cur.execute(f"""
                        SELECT count(*) FROM information_schema.tables 
                        WHERE table_schema = '{g}' AND table_name LIKE 'vt_%'
                    """)
                    v_labels = cur.fetchone()[0]
                    
                    # 2. Edge Label 수 (나머지, 제외: ag_label, ag_vertex, ag_edge)
                    cur.execute(f"""
                        SELECT count(*) FROM information_schema.tables 
                        WHERE table_schema = '{g}' 
                        AND table_name NOT LIKE 'vt_%' 
                        AND table_name NOT IN ('ag_label', 'ag_vertex', 'ag_edge')
                    """)
                    e_labels = cur.fetchone()[0]
                    
                    graph_stats.append({
                        "name": g,
                        "vertex_labels": v_labels,
                        "edge_labels": e_labels,
                        "status": "active"
                    })
                except Exception as e:
                    graph_stats.append({"name": g, "status": "error", "message": str(e)})
            
            return {
                "status": "online",
                "total_graphs": len(graphs),
                "graphs": graph_stats
            }
        except Exception as e:
            return {"status": "offline", "error": str(e)}
        finally:
            if conn: conn.close()

    @staticmethod
    def get_vector_db_stats():
        """ChromaDB 상태 및 통계"""
        try:
            client = LegalRAGService.get_chroma_client()
            cols = client.list_collections()
            
            collections = []
            total_docs = 0
            
            for c in cols:
                # c는 Collection 객체 또는 이름일 수 있음 (버전따라 다름)
                # 최신 chromadb는 Collection 객체 반환
                name = c.name if hasattr(c, 'name') else str(c)
                cnt = c.count()
                total_docs += cnt
                collections.append({
                    "name": name,
                    "count": cnt,
                    "model": c.metadata.get("embedding_model", "unknown") if c.metadata else "unknown"
                })
                
            return {
                "status": "online",
                "type": "ChromaDB",
                "collections": collections,
                "total_documents": total_docs
            }
        except Exception as e:
            return {"status": "offline", "error": str(e)}

    @staticmethod
    def get_all_stats():
        """전체 통합 모니터링 데이터"""
        return {
            "system": MonitoringService.get_system_stats(),
            "rdb": MonitoringService.get_rdb_stats(),
            "gdb": MonitoringService.get_gdb_stats(),
            "vector_db": MonitoringService.get_vector_db_stats()
        }
