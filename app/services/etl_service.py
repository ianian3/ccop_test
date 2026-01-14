import pandas as pd
import psycopg2
import json
import re
from flask import current_app
from app.services.subgraph_service import SubGraphService

class ETLService:
    
    @staticmethod
    def get_db_connection():
        """DB 연결"""
        try:
            conn = psycopg2.connect(
                dbname=current_app.config['DB_CONFIG']['dbname'],
                user=current_app.config['DB_CONFIG']['user'],
                password=current_app.config['DB_CONFIG']['password'],
                host=current_app.config['DB_CONFIG']['host'],
                port=current_app.config['DB_CONFIG']['port'],
                connect_timeout=3
            )
            conn.autocommit = True
            return conn, conn.cursor()
        except Exception as e:
            print(f"!!! DB 접속 오류: {e}")
            return None, None

    @staticmethod
    def _sanitize_label(label):
        """라벨명 안전 처리 (특수문자 제거)"""
        return re.sub(r'[^a-zA-Z0-9_]', '', label)

    @staticmethod
    def _create_gin_index(cur, graph_name, label_name):
        """
        [핵심] MERGE 속도 향상을 위한 GIN 인덱스 자동 생성
        설명: AGE의 properties 컬럼에 인덱스를 걸어 데이터 중복 체크 속도를 비약적으로 높임
        """
        try:
            # 인덱스 이름 (중복 방지용 식별자)
            idx_name = f"idx_{label_name}_properties"
            
            # GIN 인덱스 생성 쿼리 (이미 있으면 IF NOT EXISTS로 패스)
            # 주의: 테이블명은 "그래프명"."라벨명" 형태임
            query = f"""
                CREATE INDEX IF NOT EXISTS "{idx_name}"
                ON "{graph_name}"."{label_name}" USING GIN (properties);
            """
            cur.execute(query)
            print(f"   [Index] '{label_name}' 라벨에 GIN 인덱스 적용 완료")
        except Exception as e:
            # 인덱스 생성 실패가 전체 로직을 멈추게 하지는 않음 (로그만 출력)
            print(f"   ⚠️ 인덱스 생성 중 경고 (무시 가능): {e}")

    @staticmethod
    def import_csv(file, mapping, target_graph):
        print("▶ [ETL] 고속 적재(Batch) + 인덱싱 모드 시작...")

        conn, cur = ETLService.get_db_connection()
        if not conn: return False, 0, 0, "DB 연결 실패"

        try:
            # 1. 트랜잭션 정리
            try: cur.execute("ROLLBACK")
            except: pass

            # 2. CSV 파싱
            # chunksize를 사용하여 메모리 효율성을 높일 수 있으나, 현재는 편의상 전체 로드
            df = pd.read_csv(file)
            df = df.fillna('')
            df.columns = df.columns.str.strip() 

            # 4. 매핑 정보 및 변수 설정
            src_col = mapping['sourceCol'].strip()
            tgt_col = mapping['targetCol'].strip()
            src_key = mapping.get('srcKey', 'flnm').strip()  # Source 속성 키 (예: flnm, telno, actno)
            tgt_key = mapping.get('tgtKey', 'flnm').strip()  # Target 속성 키
            src_label = mapping.get('srcLabel', 'auto').strip()  # Source 노드 라벨 (수동 지정)
            tgt_label = mapping.get('tgtLabel', 'auto').strip()  # Target 노드 라벨 (수동 지정)
            edge_type = ETLService._sanitize_label(mapping.get('edgeType', 'RELATION'))
            
            node_label = ETLService._sanitize_label(mapping.get('nodeLabel', 'vt_psn'))

            extra_props = mapping.get('properties', [])
            
            # 헤더 검증
            print(f"   [CSV 헤더] {list(df.columns)}")
            print(f"   [매핑 정보] Source: {src_col} → {src_key} (라벨: {src_label})")
            print(f"   [매핑 정보] Target: {tgt_col} → {tgt_key} (라벨: {tgt_label})")
            if src_col not in df.columns: return False, 0, 0, f"❌ '{src_col}' 컬럼 없음"
            if tgt_col not in df.columns: return False, 0, 0, f"❌ '{tgt_col}' 컬럼 없음"

            # 그래프 경로 설정
            cur.execute(f"SET graph_path = {target_graph};")

            # 5. 데이터 전처리 (메모리 구조화)
            print("▶ [ETL] 데이터 구조화 중...")
            node_data_map = {} 
            edge_data_list = []

            for i, row in df.iterrows():
                src_val = str(row[src_col]).strip()
                tgt_val = str(row[tgt_col]).strip()

                if not src_val or not tgt_val: continue

                # 이번 row의 추가 속성만 먼저 수집
                row_src_props = {}
                row_tgt_props = {}
                edge_props = {"source": "csv_import"}
                
                # 속성 이름 정제 함수
                def sanitize_key(k):
                    import re
                    return re.sub(r'[() ]', '_', k)

                for p in extra_props:
                    col_name = p['col'].strip()
                    if col_name not in df.columns: continue
                    val = str(row[col_name]).strip()
                    
                    # 속성 키 정제 (괄호 제거)
                    sanitized_key = sanitize_key(p['key'])
                    
                    if p['target'] == 'source': row_src_props[sanitized_key] = val
                    elif p['target'] == 'target': row_tgt_props[sanitized_key] = val
                    elif p['target'] == 'edge': edge_props[sanitized_key] = val

                # Source 노드 처리 (중복 제거 - 속성 병합)
                src_node_key = f"{src_key}_{src_val}"
                if src_node_key not in node_data_map:
                    # 새 노드 생성 시만 기본 속성 초기화
                    node_data_map[src_node_key] = {
                        "props": {src_key: src_val, "updated": "true"},
                        "manual_label": src_label
                    }
                # 이번 row의 추가 속성 병합
                node_data_map[src_node_key]["props"].update(row_src_props)
                
                # Target 노드 처리 (중복 제거 - 속성 병합)
                tgt_node_key = f"{tgt_key}_{tgt_val}"
                if tgt_node_key not in node_data_map:
                    # 새 노드 생성 시만 기본 속성 초기화
                    node_data_map[tgt_node_key] = {
                        "props": {tgt_key: tgt_val, "updated": "true"},
                        "manual_label": tgt_label
                    }
                # 이번 row의 추가 속성 병합
                node_data_map[tgt_node_key]["props"].update(row_tgt_props)
                
                # 엣지는 실제 값 기반으로 연결
                edge_data_list.append({
                    "src": src_val, 
                    "tgt": tgt_val, 
                    "src_key": src_key,  # 엣지에도 키 정보 저장
                    "tgt_key": tgt_key,
                    "props": edge_props
                })

            # ============================
            # 3. 중복 제거 (메모리 레벨)
            # ============================
            print(f"▶ [ETL] 중복 제거 중... (총 {len(node_data_map)}개 노드)")
            unique_nodes = list(node_data_map.values())
            
            # ============================
            # 3.5 인덱스 생성 (성능 최적화)
            # ============================
            print("▶ [ETL] 데이터베이스 인덱스 생성 중...")
            # KICS 전체 노드 타입에 대한 인덱스 생성
            kics_labels = ['vt_flnm', 'vt_bacnt', 'vt_telno', 'vt_site', 
                          'vt_ip', 'vt_file', 'vt_atm', 'vt_id', 'vt_psn']
            for label in kics_labels:
                ETLService._create_gin_index(cur, target_graph, label)
            
            print(f"  [ETL] 인덱스 생성 완료 ({len(kics_labels)}개 라벨)")
            
            # ============================
            # 4. 노드 처리 (MERGE 로직)
            # ============================
            total_nodes = len(unique_nodes)
            total_edges = len(edge_data_list)

            if total_nodes == 0: return True, 0, 0, "유효 데이터 0건"

            print(f"▶ [ETL] 적재 시작 (Node: {total_nodes}, Edge: {total_edges})")

            # 6. DB 적재 실행 (Batch Processing)
            
            # [Step A] 노드 적재 - AgensGraph CREATE 사용 (동적 라벨 결정)
            print(f"  [ETL] 노드 {total_nodes}개 CREATE 시작...")
            
            # GraphService import (동적 라벨 결정용)
            from app.services.graph_service import GraphService
            
            # (1) SET graph_path
            cur.execute(f"SET graph_path = {target_graph};")
            
            nodes_created_count = 0
            nodes_updated_count = 0
            label_stats = {}  # 라벨별 통계
            
            for node_data in unique_nodes:
                try:
                    node_props = node_data['props']
                    manual_label = node_data['manual_label']
                    
                    # 라벨 결정: 수동 지정 우선, 아니면 자동 결정
                    if manual_label and manual_label != 'auto':
                        dynamic_label = manual_label  # 사용자 지정 라벨 사용
                    else:
                        dynamic_label = GraphService.determine_node_label(node_props)  # 자동 결정
                    
                    # 온톨로지 메타데이터 추가
                    from app.services.ontology_service import OntologyEnricher
                    enriched_props = OntologyEnricher.enrich_node(dynamic_label, node_props)
                    
                    label_stats[dynamic_label] = label_stats.get(dynamic_label, 0) + 1
                    
                    # MERGE 로직: 노드 존재 확인 후 CREATE 또는 UPDATE
                    # 1. 식별 키 찾기 (첫 번째 속성)
                    id_key = list(enriched_props.keys())[0] if enriched_props else None
                    if not id_key:
                        continue
                    
                    id_value = str(enriched_props[id_key]).replace("'", "''")  # SQL escape
                    
                    # 2. 노드 존재 확인
                    check_query = f"""
                    MATCH (n:{dynamic_label} {{{id_key}: '{id_value}'}})
                    RETURN id(n)
                    """
                    cur.execute(check_query)
                    existing = cur.fetchone()
                    
                    if existing:
                        # 3-A. 기존 노드 업데이트
                        set_clauses = [f"n.{k} = '{str(v).replace(chr(39), chr(39)+chr(39))}'" 
                                      for k, v in enriched_props.items()]
                        set_str = ", ".join(set_clauses)
                        
                        update_query = f"""
                        MATCH (n:{dynamic_label} {{{id_key}: '{id_value}'}})
                        SET {set_str}
                        """
                        cur.execute(update_query)
                        nodes_updated_count += 1
                    else:
                        # 3-B. 새 노드 생성
                        props_list = [f"{k}: '{str(v).replace(chr(39), chr(39)+chr(39))}'" 
                                     for k, v in enriched_props.items()]
                        props_str = ", ".join(props_list)
                        
                        create_query = f"CREATE (n:{dynamic_label} {{{props_str}}})"
                        cur.execute(create_query)
                        nodes_created_count += 1
                        
                except Exception as e:
                    print(f"    노드 처리 실패: {e}")
                    continue

            conn.commit()
            print(f"  [ETL] 노드 처리 완료: 생성 {nodes_created_count}개, 업데이트 {nodes_updated_count}개")
            print(f"  [ETL] 라벨별 분포: {label_stats}")

            # [Step B] 엣지 적재 - MATCH + CREATE 패턴 (동적 라벨 매칭)
            print(f"  [ETL] 엣지 {total_edges}개 CREATE 시작...")
            
            edges_created_count = 0
            for edge_data in edge_data_list:
                src_val = edge_data['src']
                tgt_val = edge_data['tgt']
                src_prop_key = edge_data['src_key']  # Source 노드의 속성 키
                tgt_prop_key = edge_data['tgt_key']  # Target 노드의 속성 키
                edge_props = edge_data['props']
                
                try:
                    # SQL escape
                    src_val_escaped = str(src_val).replace("'", "''")
                    tgt_val_escaped = str(tgt_val).replace("'", "''")
                    
                    # 온톨로지 메타데이터 추가 (엣지)
                    from app.services.ontology_service import OntologyEnricher
                    enriched_edge_props = OntologyEnricher.enrich_edge(edge_type, edge_props)
                    
                    # 엣지 속성 문자열 생성
                    props_list = [f"{k}: '{str(v).replace(chr(39), chr(39)+chr(39))}'" for k, v in enriched_edge_props.items()]
                    edge_props_str = ", ".join(props_list) if props_list else ""
                    
                    # 1. Source 노드 찾기 (ag_vertex 사용 - 모든 라벨 검색)
                    find_src_query = f"""
                    SELECT id FROM "{target_graph}"."ag_vertex"
                    WHERE properties @> '{{"{src_prop_key}": "{src_val_escaped}"}}'::jsonb
                    LIMIT 1
                    """
                    cur.execute(find_src_query)
                    src_result = cur.fetchone()
                    if not src_result:
                        continue
                    
                    # 2. Target 노드 찾기
                    find_tgt_query = f"""
                    SELECT id FROM "{target_graph}"."ag_vertex"
                    WHERE properties @> '{{"{tgt_prop_key}": "{tgt_val_escaped}"}}'::jsonb
                    LIMIT 1
                    """
                    cur.execute(find_tgt_query)
                    tgt_result = cur.fetchone()
                    if not tgt_result:
                        continue
                    
                    src_id = str(src_result[0])
                    tgt_id = str(tgt_result[0])
                    
                    # 3. Cypher로 엣지 생성 (ID 사용)
                    edge_create_query = f"""
                    MATCH (v1), (v2)
                    WHERE id(v1) = {src_id} AND id(v2) = {tgt_id}
                    CREATE (v1)-[r:{edge_type} {{{edge_props_str}}}]->(v2)
                    """
                    cur.execute(edge_create_query)
                    edges_created_count += 1
                except Exception as e:
                    # 노드가 없거나 에러 발생 시 스킵
                    print(f"    엣지 생성 실패: {e}")
                    continue
            
            conn.commit()
            print(f"  [ETL] 엣지 {edges_created_count}개 CREATE 완료")

            # 커밋을 해야 다른 서비스에서 테이블을 볼 수 있음
            conn.commit() 
            print(f"▶ [ETL] 모든 작업 완료! (Node: {nodes_created_count}, Edge: {edges_created_count})")
            
            return True, nodes_created_count, edges_created_count, "적재 완료"

        except Exception as e:
            print(f"!!! [ETL Error] {e}")
            import traceback
            traceback.print_exc()
            return False, 0, 0, str(e)
        finally:
            if 'conn' in locals():
                conn.close()