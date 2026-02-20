"""
RDB → GDB 온톨로지 기반 변환 서비스

KICS 4-Layer 온톨로지 모델에 따라 RDB 데이터를 그래프로 변환합니다:
  Layer 1 (Case)     → vt_case
  Layer 2 (Actor)    → vt_psn  
  Layer 3 (Action)   → vt_transfer, vt_call
  Layer 4 (Evidence) → vt_bacnt, vt_telno, vt_ip
"""
import psycopg2
import json
import traceback
from flask import current_app
from app.services.ontology_service import KICSCrimeDomainOntology, OntologyEnricher


class RdbToGraphService:
    """RDB 데이터를 KICS 온톨로지 기반으로 GDB(AgensGraph)에 변환 적재"""

    # ─────────────────────────────────────────────
    # RDB 테이블 → 온톨로지 매핑 정의
    # ─────────────────────────────────────────────
    RDB_TO_ONTOLOGY = {
        # RDB 테이블명 → (온톨로지 엔티티키, GDB vertex 라벨, 고유키 컬럼, 속성 컬럼 매핑)
        'rdb_cases': {
            'entity': 'Case',
            'label': 'vt_case',
            'unique_key': 'flnm',
            'columns': {
                'case_no': 'flnm',
                'crime_name': 'crime',
                'reg_date': 'date',
            },
            'layer': 'Case'
        },
        'rdb_suspects': {
            'entity': 'Person',
            'label': 'vt_psn',
            'unique_key': 'id',
            'columns': {
                'user_id': 'id',
                'name': 'name',
            },
            'layer': 'Actor'
        },
        'rdb_accounts': {
            'entity': 'BankAccount',
            'label': 'vt_bacnt',
            'unique_key': 'actno',
            'columns': {
                'actno': 'actno',
                'bank_name': 'bank',
                'holder_name': 'holder',
            },
            'layer': 'Evidence'
        },
        'rdb_phones': {
            'entity': 'Phone',
            'label': 'vt_telno',
            'unique_key': 'telno',
            'columns': {
                'telno': 'telno',
                'carrier': 'telecom',
            },
            'layer': 'Evidence'
        },
        'rdb_ips': {
            'entity': 'IP',
            'label': 'vt_ip',
            'unique_key': 'ip_addr',
            'columns': {
                'ip_addr': 'ip_addr',
                'isp': 'isp',
                'country': 'country',
            },
            'layer': 'Evidence'
        },
    }

    # RDB 관계 타입 → 온톨로지 엣지 라벨 매핑
    RELATION_TO_EDGE = {
        # (source_type, target_type, rdb_rel_type) → ontology edge label
        ('case', 'suspect', 'involves'): 'involves',
        # 사건 ↔ 증거 (계좌/전화/IP)
        ('case', 'account', 'evidence'): 'eg_used_account',
        ('case', 'account', 'related_to'): 'eg_used_account',
        ('case', 'phone', 'evidence'): 'eg_used_phone',
        ('case', 'phone', 'related_to'): 'eg_used_phone',
        ('case', 'ip', 'evidence'): 'eg_used_ip',
        ('case', 'ip', 'related_to'): 'eg_used_ip',
        # 닉네임/피의자 ↔ 소유 자산 (핵심 수사단서)
        ('suspect', 'account', 'owns'): 'has_account',
        ('suspect', 'account', 'related_to'): 'has_account',
        ('suspect', 'phone', 'owns'): 'owns_phone',
        ('suspect', 'phone', 'related_to'): 'owns_phone',
        ('suspect', 'ip', 'owns'): 'used_ip',
        ('suspect', 'ip', 'related_to'): 'used_ip',
        # 기타
        ('account', 'phone', 'related_to'): 'linked_to',
    }

    # RDB 타입명 → GDB 라벨/키 매핑
    TYPE_LABEL_MAP = {
        'case': ('vt_case', 'flnm'),
        'suspect': ('vt_psn', 'id'),
        'account': ('vt_bacnt', 'actno'),
        'phone': ('vt_telno', 'telno'),
        'ip': ('vt_ip', 'ip_addr'),
    }

    @staticmethod
    def get_db_connection():
        """DB 연결"""
        try:
            conn = psycopg2.connect(
                dbname=current_app.config['DB_CONFIG']['dbname'],
                user=current_app.config['DB_CONFIG']['user'],
                password=current_app.config['DB_CONFIG']['password'],
                host=current_app.config['DB_CONFIG']['host'],
                port=current_app.config['DB_CONFIG']['port']
            )
            return conn, conn.cursor()
        except Exception as e:
            print(f"❌ DB 연결 실패: {e}")
            return None, None

    @staticmethod
    def transfer_data(graph_name="test_ai01"):
        """
        RDB 데이터를 KICS 온톨로지 기반으로 GDB에 변환 적재

        변환 순서:
        1. Layer 1 (Case)     → 사건 노드
        2. Layer 2 (Actor)    → 피의자 노드
        3. Layer 4 (Evidence) → 계좌, 전화번호 노드
        4. Layer 3 (Action)   → 이체, 통화 이벤트 노드
        5. 관계 (Edges)       → 온톨로지 기반 엣지
        """
        print(f"\n{'='*60}")
        print(f"🚀 [RDB → GDB] 온톨로지 기반 변환 시작")
        print(f"   Graph: {graph_name}")
        print(f"   Ontology: KICS 4-Layer Model")
        print(f"{'='*60}")

        conn, cur = RdbToGraphService.get_db_connection()
        if not conn:
            return False, "DB 연결 실패"

        stats = {
            "nodes": 0, "edges": 0,
            "cases": 0, "persons": 0, "accounts": 0, "phones": 0,
            "transfers": 0, "calls": 0, "relations": 0,
            "errors": []
        }

        def safe_str(val):
            """SQL 인젝션 방지용 문자열 처리"""
            if val is None:
                return ''
            return str(val).replace("'", "").replace("\\", "").replace('"', '').strip()

        def run_cypher(query):
            """Cypher 쿼리 실행 (에러 무시)"""
            try:
                cur.execute(query)
                conn.commit()
                return True
            except Exception as e:
                conn.rollback()
                err_msg = str(e).lower()
                if 'already exists' not in err_msg and 'duplicate' not in err_msg:
                    print(f"   ⚠ Cypher: {str(e)[:100]}")
                return False

        try:
            # ── 그래프 경로 설정 ──
            try:
                cur.execute(f"SET graph_path = {graph_name}")
                conn.commit()
            except:
                conn.rollback()
                try:
                    cur.execute(f"CREATE GRAPH IF NOT EXISTS {graph_name}")
                    conn.commit()
                    cur.execute(f"SET graph_path = {graph_name}")
                    conn.commit()
                    print(f"  ✓ 새 그래프 '{graph_name}' 생성됨")
                except Exception as ge:
                    conn.rollback()
                    raise Exception(f"그래프 '{graph_name}' 설정 실패: {ge}")

            # ── 필요한 vertex/edge 라벨 미리 생성 ──
            vertex_labels = ['vt_case', 'vt_psn', 'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_event', 'vt_persona']
            edge_labels = ['involves', 'eg_digital_trace', 'eg_used_account', 'eg_used_phone', 'eg_used_ip',
                           'has_account', 'owns', 'owns_phone', 'used_ip', 'linked_to',
                           'participated_in', 'event_involved', 'supported_by',
                           'from_account', 'to_account', 'caller', 'callee', 'contacted',
                           'shared_resource', 'related_to', 'accomplice_of']
            
            for vl in vertex_labels:
                try:
                    cur.execute(f"CREATE VLABEL IF NOT EXISTS {vl}")
                    conn.commit()
                except:
                    conn.rollback()
                    cur.execute(f"SET graph_path = {graph_name}")
            
            for el in edge_labels:
                try:
                    cur.execute(f"CREATE ELABEL IF NOT EXISTS {el}")
                    conn.commit()
                except:
                    conn.rollback()
                    cur.execute(f"SET graph_path = {graph_name}")

            # ══════════════════════════════════════════
            # PHASE 0: RDB 데이터 감지
            # ══════════════════════════════════════════
            print(f"\n🔍 Phase 0: RDB 데이터 감지")
            rdb_counts = {}
            for table in ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones', 'rdb_ips', 'rdb_transfers', 'rdb_calls', 'rdb_relations']:
                try:
                    cur.execute(f"SELECT count(*) FROM {table}")
                    rdb_counts[table] = cur.fetchone()[0]
                except:
                    rdb_counts[table] = 0
                    conn.rollback()
                    cur.execute(f"SET graph_path = {graph_name}")
            
            detected_types = [t for t, c in rdb_counts.items() if c > 0]
            print(f"  감지된 테이블: {', '.join(detected_types) if detected_types else '없음'}")
            for t, c in rdb_counts.items():
                status = '✅' if c > 0 else '⬜'
                print(f"    {status} {t}: {c}건")

            # ══════════════════════════════════════════
            # PHASE 1: 노드 변환 (감지된 타입만)
            # ══════════════════════════════════════════
            print(f"\n📦 Phase 1: 노드 변환 (감지 기반)")

            # ── Layer 1: Case (사건) ──
            if rdb_counts.get('rdb_cases', 0) > 0:
                print(f"  [Layer 1] Case 노드 생성...")
                try:
                    cur.execute("SELECT case_no, crime_name, reg_date FROM rdb_cases")
                    cases = cur.fetchall()
                    for r in cases:
                        flnm = safe_str(r[0])
                        crime = safe_str(r[1])
                        date = safe_str(r[2])
                        if not flnm:
                            continue

                        props = OntologyEnricher.enrich_node('vt_case', {
                            'flnm': flnm, 'crime': crime, 'date': date
                        })
                        query = (
                            f"MERGE (n:vt_case {{flnm: '{flnm}'}}) "
                            f"SET n.crime = '{crime}', n.date = '{date}', "
                            f"n.source = 'rdb_import', n.layer = 'Case', "
                            f"n.ontology = 'KICS', n.legal_category = '수사사건'"
                        )
                        if run_cypher(query):
                            stats['cases'] += 1
                            stats['nodes'] += 1
                    print(f"    ✓ 사건: {stats['cases']}건")
                except Exception as e:
                    stats['errors'].append(f"Case: {e}")
                    print(f"    ✗ Case 오류: {e}")
            else:
                print(f"  [Layer 1] Case: SKIP (데이터 없음)")

            # ── Layer 2: Actor (피의자/인물) ──
            if rdb_counts.get('rdb_suspects', 0) > 0:
                print(f"  [Layer 2] Person 노드 생성...")
                try:
                    cur.execute("SELECT user_id, name, nickname FROM rdb_suspects")
                    suspects = cur.fetchall()
                    for r in suspects:
                        uid = safe_str(r[0])
                        name = safe_str(r[1])
                        nickname = safe_str(r[2]) if len(r) > 2 else ''
                        if not uid:
                            continue

                        query = (
                            f"MERGE (n:vt_psn {{id: '{uid}'}}) "
                            f"SET n.name = '{name}', n.nickname = '{nickname}', "
                            f"n.source = 'rdb_import', "
                            f"n.layer = 'Actor', n.ontology = 'KICS', "
                            f"n.legal_category = '피의자정보'"
                        )
                        if run_cypher(query):
                            stats['persons'] += 1
                            stats['nodes'] += 1
                    print(f"    ✓ 인물: {stats['persons']}명")
                except Exception as e:
                    stats['errors'].append(f"Person: {e}")
                    print(f"    ✗ Person 오류: {e}")
            else:
                print(f"  [Layer 2] Person: SKIP (데이터 없음)")

            # ── Layer 4: Evidence - 계좌 (BankAccount) ──
            if rdb_counts.get('rdb_accounts', 0) > 0:
                print(f"  [Layer 4] BankAccount 노드 생성...")
                try:
                    cur.execute("SELECT actno, bank_name, holder_name FROM rdb_accounts")
                    accounts = cur.fetchall()
                    for r in accounts:
                        actno = safe_str(r[0])
                        bank = safe_str(r[1])
                        holder = safe_str(r[2])
                        if not actno:
                            continue

                        query = (
                            f"MERGE (n:vt_bacnt {{actno: '{actno}'}}) "
                            f"SET n.bank = '{bank}', n.holder = '{holder}', "
                            f"n.source = 'rdb_import', n.layer = 'Evidence', "
                            f"n.sublayer = 'Financial', n.ontology = 'KICS', "
                            f"n.legal_category = '금융거래정보'"
                        )
                        if run_cypher(query):
                            stats['accounts'] += 1
                            stats['nodes'] += 1
                    print(f"    ✓ 계좌: {stats['accounts']}건")
                except Exception as e:
                    stats['errors'].append(f"Account: {e}")
                    print(f"    ✗ Account 오류: {e}")
            else:
                print(f"  [Layer 4] Account: SKIP (데이터 없음)")

            # ── Layer 4: Evidence - 전화번호 (Phone) ──
            if rdb_counts.get('rdb_phones', 0) > 0:
                print(f"  [Layer 4] Phone 노드 생성...")
                try:
                    cur.execute("SELECT telno, carrier FROM rdb_phones")
                    phones = cur.fetchall()
                    for r in phones:
                        telno = safe_str(r[0])
                        carrier = safe_str(r[1])
                        if not telno:
                            continue

                        query = (
                            f"MERGE (n:vt_telno {{telno: '{telno}'}}) "
                            f"SET n.telecom = '{carrier}', "
                            f"n.source = 'rdb_import', n.layer = 'Evidence', "
                            f"n.sublayer = 'Communication', n.ontology = 'KICS', "
                            f"n.legal_category = '통신사실확인자료'"
                        )
                        if run_cypher(query):
                            stats['phones'] += 1
                            stats['nodes'] += 1
                    print(f"    ✓ 전화번호: {stats['phones']}건")
                except Exception as e:
                    stats['errors'].append(f"Phone: {e}")
                    print(f"    ✗ Phone 오류: {e}")
            else:
                print(f"  [Layer 4] Phone: SKIP (데이터 없음)")

            # ── Layer 4: Evidence - IP 주소 ──
            if rdb_counts.get('rdb_ips', 0) > 0:
                print(f"  [Layer 4] IP 노드 생성...")
                stats.setdefault('ips', 0)
                try:
                    cur.execute("SELECT ip_addr, isp, country FROM rdb_ips")
                    ips = cur.fetchall()
                    for r in ips:
                        ip_addr = safe_str(r[0])
                        isp = safe_str(r[1])
                        country = safe_str(r[2])
                        if not ip_addr:
                            continue

                        query = (
                            f"MERGE (n:vt_ip {{ip_addr: '{ip_addr}'}}) "
                            f"SET n.isp = '{isp}', n.country = '{country}', "
                            f"n.source = 'rdb_import', n.layer = 'Evidence', "
                            f"n.sublayer = 'Digital', n.ontology = 'KICS', "
                            f"n.legal_category = '디지털증거'"
                        )
                        if run_cypher(query):
                            stats['ips'] += 1
                            stats['nodes'] += 1
                    print(f"    ✓ IP: {stats['ips']}건")
                except Exception as e:
                    stats['errors'].append(f"IP: {e}")
                    print(f"    ✗ IP 오류: {e}")
            else:
                print(f"  [Layer 4] IP: SKIP (데이터 없음)")

            # ══════════════════════════════════════════
            # PHASE 2: Action Layer (이벤트 노드 + 엣지)
            # ══════════════════════════════════════════
            print(f"\n📦 Phase 2: Action Layer (이벤트 노드 + 연결)")

            # ── Layer 3: Transfer (이체 이벤트) ──
            if rdb_counts.get('rdb_transfers', 0) > 0:
                print(f"  [Layer 3] Transfer 이벤트 변환...")
                try:
                    cur.execute("""
                        SELECT trx_id, amount, trx_date, sender_actno, receiver_actno 
                        FROM rdb_transfers
                    """)
                    transfers = cur.fetchall()
                    for r in transfers:
                        trx_id = safe_str(r[0])
                        amount = r[1] if r[1] else 0
                        trx_date = safe_str(r[2])
                        sender = safe_str(r[3])
                        receiver = safe_str(r[4])

                        if not trx_id:
                            continue

                        # 이체 이벤트 노드 생성 (vt_event)
                        query = (
                            f"MERGE (n:vt_event {{event_id: '{trx_id}'}}) "
                            f"SET n.event_type = 'transfer', n.amount = {amount}, n.timestamp = '{trx_date}', "
                            f"n.status = 'completed', "
                            f"n.source = 'rdb_import', n.layer = 'Event', "
                            f"n.ontology = 'KICS', n.legal_category = '금융거래정보'"
                        )
                        if run_cypher(query):
                            stats['transfers'] += 1
                            stats['nodes'] += 1

                        # Sender → Event (participated_in: sender)
                        if sender:
                            query = (
                                f"MATCH (e:vt_event {{event_id: '{trx_id}'}}), "
                                f"(a:vt_bacnt {{actno: '{sender}'}}) "
                                f"MERGE (a)-[r:participated_in]->(e) "
                                f"SET r.role = 'sender', r.ontology = 'KICS'"
                            )
                            if run_cypher(query):
                                stats['edges'] += 1

                        # Receiver → Event (participated_in: receiver)
                        if receiver:
                            query = (
                                f"MATCH (e:vt_event {{event_id: '{trx_id}'}}), "
                                f"(a:vt_bacnt {{actno: '{receiver}'}}) "
                                f"MERGE (a)-[r:participated_in]->(e) "
                                f"SET r.role = 'receiver', r.ontology = 'KICS'"
                            )
                            if run_cypher(query):
                                stats['edges'] += 1

                    print(f"    ✓ 이체: {stats['transfers']}건")
                except Exception as e:
                    conn.rollback()
                    try: cur.execute(f"SET graph_path = {graph_name}")
                    except: conn.rollback()
                    stats['errors'].append(f"Transfer: {e}")
                    print(f"    ✗ Transfer 오류: {e}")
            else:
                print(f"  [Layer 3] Transfer: SKIP (데이터 없음)")

            # ── Layer 3: Call (통화 이벤트) ──
            if rdb_counts.get('rdb_calls', 0) > 0:
                print(f"  [Layer 3] Call 이벤트 변환...")
                try:
                    cur.execute("""
                        SELECT call_id, duration, call_date, caller_no, callee_no 
                        FROM rdb_calls
                    """)
                    calls = cur.fetchall()
                    for r in calls:
                        call_id = safe_str(r[0])
                        duration = r[1] if r[1] else 0
                        call_date = safe_str(r[2])
                        caller = safe_str(r[3])
                        callee = safe_str(r[4])

                        if not call_id:
                            continue

                        # 통화 이벤트 노드 생성 (vt_event)
                        query = (
                            f"MERGE (n:vt_event {{event_id: '{call_id}'}}) "
                            f"SET n.event_type = 'call', n.duration = {duration}, n.timestamp = '{call_date}', "
                            f"n.status = 'completed', "
                            f"n.source = 'rdb_import', n.layer = 'Event', "
                            f"n.ontology = 'KICS', n.legal_category = '통신사실확인자료'"
                        )
                        if run_cypher(query):
                            stats['calls'] += 1
                            stats['nodes'] += 1

                        # Caller → Event (participated_in: caller)
                        if caller:
                            query = (
                                f"MATCH (e:vt_event {{event_id: '{call_id}'}}), "
                                f"(p:vt_telno {{telno: '{caller}'}}) "
                                f"MERGE (p)-[r:participated_in]->(e) "
                                f"SET r.role = 'caller', r.ontology = 'KICS'"
                            )
                            if run_cypher(query):
                                stats['edges'] += 1

                        # Callee → Event (participated_in: callee)
                        if callee:
                            query = (
                                f"MATCH (e:vt_event {{event_id: '{call_id}'}}), "
                                f"(p:vt_telno {{telno: '{callee}'}}) "
                                f"MERGE (p)-[r:participated_in]->(e) "
                                f"SET r.role = 'callee', r.ontology = 'KICS'"
                            )
                            if run_cypher(query):
                                stats['edges'] += 1

                    print(f"    ✓ 통화: {stats['calls']}건")
                except Exception as e:
                    conn.rollback()
                    try: cur.execute(f"SET graph_path = {graph_name}")
                    except: conn.rollback()
                    stats['errors'].append(f"Call: {e}")
                    print(f"    ✗ Call 오류: {e}")
            else:
                print(f"  [Layer 3] Call: SKIP (데이터 없음)")

            # ══════════════════════════════════════════
            # PHASE 3: 관계 변환 (Ontology-based Edges)
            # ══════════════════════════════════════════
            print(f"\n📦 Phase 3: 온톨로지 기반 관계 변환")
            try:
                cur.execute("""
                    SELECT source_type, source_value, target_type, target_value, 
                           rel_type, weight 
                    FROM rdb_relations
                """)
                relations = cur.fetchall()

                for r in relations:
                    src_type, src_val, tgt_type, tgt_val, rdb_rel, weight = r
                    src_val = safe_str(src_val)
                    tgt_val = safe_str(tgt_val)

                    if not src_val or not tgt_val:
                        continue

                    # RDB 타입 → GDB 라벨/키 매핑
                    if src_type not in RdbToGraphService.TYPE_LABEL_MAP:
                        continue
                    if tgt_type not in RdbToGraphService.TYPE_LABEL_MAP:
                        continue

                    src_label, src_key = RdbToGraphService.TYPE_LABEL_MAP[src_type]
                    tgt_label, tgt_key = RdbToGraphService.TYPE_LABEL_MAP[tgt_type]

                    # 온톨로지 기반 엣지 라벨 결정
                    mapping_key = (src_type, tgt_type, rdb_rel)
                    edge_label = RdbToGraphService.RELATION_TO_EDGE.get(
                        mapping_key, rdb_rel
                    )

                    # 온톨로지 메타데이터 조회
                    ont_rel = KICSCrimeDomainOntology.RELATIONSHIPS.get(edge_label, {})
                    legal_cat = ont_rel.get('legal_significance', '')
                    meaning = ont_rel.get('meaning', '')

                    query = (
                        f"MATCH (s:{src_label} {{{src_key}: '{src_val}'}}), "
                        f"(t:{tgt_label} {{{tgt_key}: '{tgt_val}'}}) "
                        f"MERGE (s)-[e:{edge_label}]->(t) "
                        f"SET e.weight = {weight or 1}, "
                        f"e.source = 'rdb_import', e.ontology = 'KICS'"
                    )
                    if legal_cat:
                        query += f", e.legal_category = '{safe_str(legal_cat)}'"

                    if run_cypher(query):
                        stats['relations'] += 1
                        stats['edges'] += 1

                print(f"    ✓ 관계: {stats['relations']}건")
            except Exception as e:
                conn.rollback()
                try: cur.execute(f"SET graph_path = {graph_name}")
                except: conn.rollback()
                stats['errors'].append(f"Relations: {e}")
                print(f"    ✗ Relations 오류: {e}")

            # ══════════════════════════════════════════
            # PHASE 4: 추론 관계 생성 (Inferred Edges)
            # ══════════════════════════════════════════
            print(f"\n📦 Phase 4: 추론 관계 생성")
            inference_stats = {'shared_account': 0, 'shared_phone': 0, 'shared_ip': 0,
                              'has_account': 0, 'owns_phone': 0, 'used_ip': 0, 'accomplice': 0}

            # ── Phase 4-1: shared_resource (사건 간 공유 자원) ──
            print(f"  [4-1] 사건 간 공유 자원 추론...")

            # (1) 계좌 기반 사건 공유
            try:
                query = """
                    MATCH (c1:vt_case)-[:eg_used_account]->(a:vt_bacnt)<-[:eg_used_account]-(c2:vt_case)
                    WHERE id(c1) < id(c2)
                    MERGE (c1)-[e:shared_resource]->(c2)
                    SET e.shared_type = 'account', e.ontology = 'KICS', 
                        e.inferred = true, e.source = 'rdb_inference'
                """
                run_cypher(query)
                print(f"    ✓ 계좌 공유 사건 연결")
            except Exception as e:
                print(f"    ⚠ 계좌 공유 건너뜀: {e}")

            # (2) 전화번호 기반 사건 공유
            try:
                query = """
                    MATCH (c1:vt_case)-[:eg_used_phone]->(t:vt_telno)<-[:eg_used_phone]-(c2:vt_case)
                    WHERE id(c1) < id(c2)
                    MERGE (c1)-[e:shared_resource]->(c2)
                    SET e.shared_type = 'phone', e.ontology = 'KICS',
                        e.inferred = true, e.source = 'rdb_inference'
                """
                run_cypher(query)
                print(f"    ✓ 전화번호 공유 사건 연결")
            except Exception as e:
                print(f"    ⚠ 전화번호 공유 건너뜀: {e}")

            # (3) IP 기반 사건 공유
            try:
                query = """
                    MATCH (c1:vt_case)-[:eg_used_ip]->(i:vt_ip)<-[:eg_used_ip]-(c2:vt_case)
                    WHERE id(c1) < id(c2)
                    MERGE (c1)-[e:shared_resource]->(c2)
                    SET e.shared_type = 'ip', e.ontology = 'KICS',
                        e.inferred = true, e.source = 'rdb_inference'
                """
                run_cypher(query)
                print(f"    ✓ IP 공유 사건 연결")
            except Exception as e:
                print(f"    ⚠ IP 공유 건너뜀: {e}")

            # ── Phase 4-2: Actor-Evidence 소유관계 (역추론) ──
            print(f"  [4-2] Actor-Evidence 소유관계 추론...")

            # (4) Person → has_account → Account (같은 사건 기반 추론)
            try:
                query = """
                    MATCH (c:vt_case)-[:involves]->(p:vt_psn),
                          (c)-[:eg_used_account]->(a:vt_bacnt)
                    MERGE (p)-[e:has_account]->(a)
                    SET e.inferred = true, e.source = 'case_co_occurrence',
                        e.ontology = 'KICS', e.legal_category = '금융거래정보',
                        e.confidence = 0.7
                """
                run_cypher(query)
                print(f"    ✓ Person→Account 소유관계 추론")
            except Exception as e:
                print(f"    ⚠ has_account 건너뜀: {e}")

            # (5) Person → owns_phone → Phone (같은 사건 기반 추론)
            try:
                query = """
                    MATCH (c:vt_case)-[:involves]->(p:vt_psn),
                          (c)-[:eg_used_phone]->(t:vt_telno)
                    MERGE (p)-[e:owns_phone]->(t)
                    SET e.inferred = true, e.source = 'case_co_occurrence',
                        e.ontology = 'KICS', e.legal_category = '통신사실확인자료',
                        e.confidence = 0.7
                """
                run_cypher(query)
                print(f"    ✓ Person→Phone 소유관계 추론")
            except Exception as e:
                print(f"    ⚠ owns_phone 건너뜀: {e}")

            # (6) Person → used_ip → IP (같은 사건 기반 추론)
            try:
                query = """
                    MATCH (c:vt_case)-[:involves]->(p:vt_psn),
                          (c)-[:eg_used_ip]->(i:vt_ip)
                    MERGE (p)-[e:used_ip]->(i)
                    SET e.inferred = true, e.source = 'case_co_occurrence',
                        e.ontology = 'KICS', e.legal_category = '디지털증거',
                        e.confidence = 0.7
                """
                run_cypher(query)
                print(f"    ✓ Person→IP 사용관계 추론")
            except Exception as e:
                print(f"    ⚠ used_ip 건너뜀: {e}")

            # ── Phase 4-3: 공범 관계 추론 ──
            print(f"  [4-3] 공범 관계 추론...")

            # (7) 같은 계좌를 사용한 다른 사건의 인물 → 공범 추정
            try:
                query = """
                    MATCH (p1:vt_psn)<-[:involves]-(c1:vt_case)-[:eg_used_account]->(a:vt_bacnt)
                          <-[:eg_used_account]-(c2:vt_case)-[:involves]->(p2:vt_psn)
                    WHERE id(p1) < id(p2)
                    MERGE (p1)-[e:accomplice_of]->(p2)
                    SET e.confidence = 0.7, e.inferred = true,
                        e.source = 'shared_account_inference',
                        e.ontology = 'KICS', e.legal_category = '피의자정보'
                """
                run_cypher(query)
                print(f"    ✓ 공범 관계 추론 (계좌 기반)")
            except Exception as e:
                print(f"    ⚠ 공범 추론 건너뜀: {e}")

            # (8) 같은 전화번호를 사용한 다른 사건의 인물 → 공범 추정
            try:
                query = """
                    MATCH (p1:vt_psn)<-[:involves]-(c1:vt_case)-[:eg_used_phone]->(t:vt_telno)
                          <-[:eg_used_phone]-(c2:vt_case)-[:involves]->(p2:vt_psn)
                    WHERE id(p1) < id(p2)
                    MERGE (p1)-[e:accomplice_of]->(p2)
                    SET e.confidence = 0.6, e.inferred = true,
                        e.source = 'shared_phone_inference',
                        e.ontology = 'KICS', e.legal_category = '피의자정보'
                """
                run_cypher(query)
                print(f"    ✓ 공범 관계 추론 (전화번호 기반)")
            except Exception as e:
                print(f"    ⚠ 전화 공범 추론 건너뜀: {e}")

            conn.commit()

            # ── 결과 요약 ──
            print(f"\n{'='*60}")
            print(f"✅ [RDB → GDB] 온톨로지 기반 변환 완료!")
            print(f"   📊 노드 합계: {stats['nodes']}개")
            print(f"      ├─ 사건(Case):     {stats['cases']}건")
            print(f"      ├─ 인물(Person):   {stats['persons']}명")
            print(f"      ├─ 계좌(Account):  {stats['accounts']}건")
            print(f"      ├─ 전화(Phone):    {stats['phones']}건")
            print(f"      ├─ 이체(Transfer): {stats['transfers']}건")
            print(f"      └─ 통화(Call):     {stats['calls']}건")
            print(f"   🔗 엣지 합계: {stats['edges']}개")
            print(f"      └─ 관계(Relations): {stats['relations']}건")
            if stats['errors']:
                print(f"   ⚠ 오류: {len(stats['errors'])}건")
            print(f"{'='*60}\n")

            return True, stats

        except Exception as e:
            conn.rollback()
            print(f"❌ 변환 중 치명적 오류: {e}")
            traceback.print_exc()
            return False, str(e)
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def get_conversion_preview():
        """변환 전 미리보기 (각 테이블의 레코드 수 + 예상 노드/엣지)"""
        conn, cur = RdbToGraphService.get_db_connection()
        if not conn:
            return None

        preview = {
            "rdb_tables": {},
            "expected_nodes": 0,
            "expected_edges": 0,
            "ontology_mapping": []
        }

        try:
            tables = ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones',
                       'rdb_transfers', 'rdb_calls', 'rdb_relations']

            for table in tables:
                try:
                    cur.execute(f"SELECT count(*) FROM {table}")
                    count = cur.fetchone()[0]
                    preview['rdb_tables'][table] = count

                    # 노드 예상치
                    if table in RdbToGraphService.RDB_TO_ONTOLOGY:
                        mapping = RdbToGraphService.RDB_TO_ONTOLOGY[table]
                        preview['expected_nodes'] += count
                        preview['ontology_mapping'].append({
                            'rdb_table': table,
                            'gdb_label': mapping['label'],
                            'entity': mapping['entity'],
                            'layer': mapping['layer'],
                            'count': count
                        })
                    elif table == 'rdb_transfers':
                        preview['expected_nodes'] += count
                        preview['expected_edges'] += count * 3  # from, to, transferred_to
                        preview['ontology_mapping'].append({
                            'rdb_table': table,
                            'gdb_label': 'vt_transfer',
                            'entity': 'Transfer',
                            'layer': 'Action',
                            'count': count
                        })
                    elif table == 'rdb_calls':
                        preview['expected_nodes'] += count
                        preview['expected_edges'] += count * 3  # caller, callee, contacted
                        preview['ontology_mapping'].append({
                            'rdb_table': table,
                            'gdb_label': 'vt_call',
                            'entity': 'Call',
                            'layer': 'Action',
                            'count': count
                        })
                    elif table == 'rdb_relations':
                        preview['expected_edges'] += count
                except:
                    preview['rdb_tables'][table] = 0

            conn.close()
            return preview

        except Exception as e:
            conn.close()
            return None
