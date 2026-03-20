"""Comprehensive Ontology Analysis for tccop_graph_v6"""
from app import create_app
from app.services.graph_service import GraphService
from app.services.rdb_service import RDBService

app = create_app()

with app.app_context():
    # === Part 1: RDB Baseline ===
    print("=" * 70)
    print("📊 Part 1: RDB 원본 데이터 기준선 (Source of Truth)")
    print("=" * 70)
    conn, cur = RDBService.get_db_connection()
    rdb_counts = {}
    tables = {
        'tb_prsn': '인물',
        'tb_fin_bacnt': '계좌',
        'tb_fin_bacnt_dlng': '이체내역',
        'tb_telno_mst': '전화번호',
        'tb_telno_call_dtl': '통화내역',
        'tb_telno_join': '전화소유관계',
        'tb_sys_lgn_evt': 'IP접속',
    }
    for t, label in tables.items():
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            cnt = cur.fetchone()[0]
            rdb_counts[t] = cnt
            print(f"  {label} ({t}): {cnt} rows")
        except Exception as e:
            print(f"  ❌ {t}: {e}")
            conn.rollback()
    cur.close()
    conn.close()

    # === Part 2: GDB Node Analysis ===
    print(f"\n{'=' * 70}")
    print("🔵 Part 2: GDB 노드 분석 (tccop_graph_v6)")
    print("=" * 70)
    conn, cur = GraphService.get_db_connection()
    cur.execute("SET graph_path = tccop_graph_v6")
    
    cur.execute("MATCH (n) RETURN label(n) as lbl, count(n) as cnt")
    node_counts = {}
    for r in cur.fetchall():
        node_counts[r[0]] = r[1]
        print(f"  {r[0]}: {r[1]} nodes")
    total_nodes = sum(node_counts.values())
    print(f"  --- Total Nodes: {total_nodes} ---")

    # === Part 3: GDB Edge Analysis ===
    print(f"\n{'=' * 70}")
    print("🔗 Part 3: GDB 엣지 분석")
    print("=" * 70)
    cur.execute("MATCH ()-[r]->() RETURN label(r) as lbl, count(r) as cnt")
    edge_counts = {}
    for r in cur.fetchall():
        edge_counts[r[0]] = r[1]
        print(f"  {r[0]}: {r[1]} edges")
    total_edges = sum(edge_counts.values())
    print(f"  --- Total Edges: {total_edges} ---")

    # === Part 4: Edge Direction Verification ===
    print(f"\n{'=' * 70}")
    print("🧭 Part 4: 엣지 방향성 검증 (Flow-based 방향)")
    print("=" * 70)
    flow_edges = ['from_account', 'to_account', 'caller', 'callee', 'sent_msg', 'recv_msg']
    for edge_type in flow_edges:
        try:
            cur.execute(f"MATCH (a)-[r:{edge_type}]->(b) RETURN label(a) as src, label(b) as tgt, count(r) as cnt LIMIT 5")
            rows = cur.fetchall()
            if rows:
                for r in rows:
                    direction = "✅ 정상" if (
                        (edge_type == 'from_account' and r[0] == 'vt_bacnt' and r[1] == 'vt_transfer') or
                        (edge_type == 'to_account' and r[0] == 'vt_transfer' and r[1] == 'vt_bacnt') or
                        (edge_type == 'caller' and r[0] == 'vt_telno' and r[1] == 'vt_call') or
                        (edge_type == 'callee' and r[0] == 'vt_call' and r[1] == 'vt_telno') or
                        (edge_type == 'sent_msg' and r[0] == 'vt_telno') or
                        (edge_type == 'recv_msg')
                    ) else "⚠️ 확인필요"
                    print(f"  {edge_type}: ({r[0]}) → ({r[1]}) x{r[2]}  {direction}")
            else:
                print(f"  {edge_type}: 없음")
        except Exception as e:
            print(f"  {edge_type}: 쿼리실패 - {e}")
            conn.rollback()
            cur.execute("SET graph_path = tccop_graph_v6")

    # === Part 5: Duplicate Detection ===
    print(f"\n{'=' * 70}")
    print("🔍 Part 5: 중복 노드/엣지 탐지")
    print("=" * 70)
    
    # Check duplicate transfers
    try:
        cur.execute("""
            MATCH (a:vt_bacnt)-[r1:from_account]->(t:vt_transfer)-[r2:to_account]->(b:vt_bacnt)
            RETURN a.actno as sender, b.actno as receiver, t.amount, count(t) as cnt
        """)
        rows = cur.fetchall()
        dups = [r for r in rows if r[3] > 1]
        if dups:
            print("  ⚠️ 중복 이체 경로 발견:")
            for d in dups:
                print(f"    {d[0]} → {d[1]}, 금액: {d[2]}, 중복수: {d[3]}")
        else:
            print("  ✅ 중복 이체 경로 없음")
    except Exception as e:
        print(f"  이체 중복 검사 실패: {e}")
        conn.rollback()
        cur.execute("SET graph_path = tccop_graph_v6")

    # Check duplicate calls
    try:
        cur.execute("""
            MATCH (a:vt_telno)-[r1:caller]->(c:vt_call)-[r2:callee]->(b:vt_telno)
            RETURN a.telno as caller_no, b.telno as callee_no, count(c) as cnt
        """)
        rows = cur.fetchall()
        if rows:
            print(f"  통화 경로 총 {len(rows)}개 (복수 통화는 정상)")
        else:
            print("  ℹ️ caller→call→callee 경로 없음")
    except Exception as e:
        print(f"  통화 중복 검사 실패: {e}")
        conn.rollback()
        cur.execute("SET graph_path = tccop_graph_v6")

    # === Part 6: Relationship Completeness ===
    print(f"\n{'=' * 70}")
    print("📋 Part 6: 관계 완전성 검사 (RDB vs GDB)")
    print("=" * 70)
    
    # Transfer completeness
    rdb_transfers = rdb_counts.get('tb_fin_bacnt_dlng', 0)
    gdb_transfers = node_counts.get('vt_transfer', 0)
    from_acc = edge_counts.get('from_account', 0)
    to_acc = edge_counts.get('to_account', 0)
    match_status = "✅" if gdb_transfers == rdb_transfers else "⚠️"
    print(f"  {match_status} 이체: RDB({rdb_transfers}) → GDB 노드({gdb_transfers}), from_account 엣지({from_acc}), to_account 엣지({to_acc})")
    
    # Call completeness
    rdb_calls = rdb_counts.get('tb_telno_call_dtl', 0)
    gdb_calls = node_counts.get('vt_call', 0)
    caller_e = edge_counts.get('caller', 0)
    callee_e = edge_counts.get('callee', 0)
    match_status = "✅" if gdb_calls == rdb_calls else "⚠️"
    print(f"  {match_status} 통화: RDB({rdb_calls}) → GDB 노드({gdb_calls}), caller 엣지({caller_e}), callee 엣지({callee_e})")
    
    # Person completeness
    rdb_persons = rdb_counts.get('tb_prsn', 0)
    gdb_persons = node_counts.get('vt_psn', 0)
    match_status = "✅" if gdb_persons == rdb_persons else "⚠️"
    print(f"  {match_status} 인물: RDB({rdb_persons}) → GDB 노드({gdb_persons})")

    # Account completeness
    rdb_accounts = rdb_counts.get('tb_fin_bacnt', 0)
    gdb_accounts = node_counts.get('vt_bacnt', 0)
    match_status = "✅" if gdb_accounts == rdb_accounts else "⚠️"
    print(f"  {match_status} 계좌: RDB({rdb_accounts}) → GDB 노드({gdb_accounts})")
    
    # Phone completeness
    rdb_phones = rdb_counts.get('tb_telno_mst', 0)
    gdb_phones = node_counts.get('vt_telno', 0)
    match_status = "✅" if gdb_phones == rdb_phones else "⚠️"
    print(f"  {match_status} 전화번호: RDB({rdb_phones}) → GDB 노드({gdb_phones})")

    # Ownership edges
    owns_phone = edge_counts.get('owns_phone', 0)
    has_account = edge_counts.get('has_account', 0)
    print(f"  ℹ️ 전화소유 엣지(owns_phone): {owns_phone}, 계좌소유 엣지(has_account): {has_account}")

    # === Part 7: Sample Paths ===
    print(f"\n{'=' * 70}")
    print("🛤️ Part 7: 샘플 경로 추적 (피의자1의 자금 흐름)")
    print("=" * 70)
    try:
        cur.execute("""
            MATCH (p:vt_psn)-[r1:has_account]->(a:vt_bacnt)-[r2:from_account]->(t:vt_transfer)-[r3:to_account]->(b:vt_bacnt)
            WHERE p.name = '피의자1' OR p.flnm = '피의자1'
            RETURN p.name, a.actno, t.amount, b.actno
            LIMIT 5
        """)
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"  {r[0]} → [{r[1]}] --({r[2]}원)--> [{r[3]}]")
        else:
            print("  ℹ️ 피의자1의 직접 경로 없음 (has_account 엣지 확인 필요)")
    except Exception as e:
        print(f"  경로 추적 실패: {e}")
        conn.rollback()
        cur.execute("SET graph_path = tccop_graph_v6")

    # IP connections
    print(f"\n{'=' * 70}")
    print("🌐 Part 8: IP 접속 이벤트")  
    print("=" * 70)
    ip_nodes = node_counts.get('vt_ip', 0)
    used_ip = edge_counts.get('used_ip', 0)
    print(f"  IP 노드: {ip_nodes}, used_ip 엣지: {used_ip}")

    cur.close()
    conn.close()
    
    print(f"\n{'=' * 70}")
    print("🏁 분석 완료")
    print("=" * 70)
