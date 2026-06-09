from app.database import get_db_connection

class SubGraphService:
    @staticmethod
    def get_schema(graph_path):
        """DB에서 현재 스키마(테이블 목록)를 직접 조회"""
        conn, cur = get_db_connection()
        if not conn: return [], []
        
        nodes = []
        edges = []
        try:
            # 설정 테이블 조회 시도 (없으면 Fallback)
            try:
                cur.execute(f"SELECT table_name, table_type FROM public.sys_graph_config WHERE graph_name = '{graph_path}'")
                rows = cur.fetchall()
                if rows:
                    for r in rows:
                        if r[1] == 'NODE': nodes.append(r[0])
                        elif r[1] == 'EDGE': edges.append(r[0])
                    return nodes, edges
            except: pass

            # Fallback: information_schema 직접 조회
            cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{graph_path}'")
            tables = [r[0] for r in cur.fetchall()]
            for tbl in tables:
                if tbl.startswith("eg_") or "rel" in tbl: edges.append(tbl)
                else: nodes.append(tbl)
                
            return nodes, edges
        finally:
            conn.close()