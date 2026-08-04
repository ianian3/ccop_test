import pandas as pd
import psycopg2
import json
import re
from flask import current_app
from app.database import safe_set_graph_path
from app.services.subgraph_service import SubGraphService
import logging


logger = logging.getLogger(__name__)

class StandardCodeMapper:
    """
    표준 코드 자동 매핑 클래스
    - 은행 약어 → 금결원 코드
    - 통신사 약어 → 표준 코드
    - 해시 알고리즘 정규화
    """
    
    # 은행 약어 → 금결원 코드 매핑
    BANK_CODES = {
        'KB': '004', '국민': '004', '국민은행': '004',
        'SH': '088', '신한': '088', '신한은행': '088',
        'WR': '020', '우리': '020', '우리은행': '020',
        'HN': '081', '하나': '081', '하나은행': '081',
        'NH': '011', '농협': '011', '농협은행': '011',
        'IBK': '003', '기업': '003', '기업은행': '003',
        'SC': '023', 'SC제일': '023', 'SC제일은행': '023',
        'CITI': '027', '씨티': '027', '씨티은행': '027',
        'KDB': '002', '산업': '002', '산업은행': '002',
        'Sh': '007', '수협': '007', '수협은행': '007',
        'DGB': '031', '대구': '031', '대구은행': '031',
        'BNK': '032', '부산': '032', '부산은행': '032',
        'KJB': '034', '광주': '034', '광주은행': '034',
        'JJB': '035', '제주': '035', '제주은행': '035',
        'JBB': '037', '전북': '037', '전북은행': '037',
        'MG': '045', '새마을': '045', '새마을금고': '045',
        'CU': '048', '신협': '048',
        'POST': '071', '우체국': '071',
        'KBANK': '089', '케이뱅크': '089', 'K뱅크': '089',
        'KAKAO': '090', '카카오': '090', '카카오뱅크': '090',
        'TOSS': '092', '토스': '092', '토스뱅크': '092',
    }
    
    # 통신사 약어 → 표준 코드 매핑
    CARRIER_CODES = {
        'SKT': '01', 'SK텔레콤': '01', 'SK': '01',
        'KT': '02', '케이티': '02',
        'LGU': '03', 'LGU+': '03', 'LG유플러스': '03', 'LG': '03',
        'MVNO': '04', '알뜰폰': '04', '가상이동통신': '04',
    }
    
    # 해시 알고리즘 정규화
    HASH_ALGORITHMS = {
        'md5': 'MD5', 'MD5': 'MD5',
        'sha1': 'SHA1', 'SHA1': 'SHA1', 'SHA-1': 'SHA1',
        'sha256': 'SHA256', 'SHA256': 'SHA256', 'SHA-256': 'SHA256',
        'sha384': 'SHA384', 'SHA384': 'SHA384', 'SHA-384': 'SHA384',
        'sha512': 'SHA512', 'SHA512': 'SHA512', 'SHA-512': 'SHA512',
    }
    
    @classmethod
    def map_bank_code(cls, value: str) -> str:
        """은행 약어/이름을 금결원 코드로 변환"""
        if not value:
            return None
        value = str(value).strip()
        # 이미 3자리 숫자 코드면 그대로 반환
        if re.match(r'^\d{3}$', value):
            return value
        return cls.BANK_CODES.get(value)
    
    @classmethod
    def map_carrier_code(cls, value: str) -> str:
        """통신사 약어/이름을 표준 코드로 변환"""
        if not value:
            return None
        value = str(value).strip()
        # 이미 2자리 숫자 코드면 그대로 반환
        if re.match(r'^\d{2}$', value):
            return value
        return cls.CARRIER_CODES.get(value)
    
    @classmethod
    def normalize_hash_algorithm(cls, value: str) -> str:
        """해시 알고리즘 이름 정규화"""
        if not value:
            return 'SHA256'  # 기본값
        value = str(value).strip()
        return cls.HASH_ALGORITHMS.get(value, 'SHA256')
    
    @classmethod
    def enrich_account_node(cls, props: dict) -> dict:
        """계좌 노드에 표준 은행코드 추가"""
        # bank_cd, bank, bank_nm 등의 컬럼에서 은행 정보 추출
        bank_value = props.get('bank_cd') or props.get('bank') or props.get('bank_nm') or props.get('은행')
        if bank_value:
            bnk_cd = cls.map_bank_code(bank_value)
            if bnk_cd:
                props['bnk_cd'] = bnk_cd
        return props
    
    @classmethod
    def enrich_phone_node(cls, props: dict) -> dict:
        """전화 노드에 표준 통신사코드 추가"""
        carrier_value = props.get('carrier') or props.get('carr') or props.get('통신사')
        if carrier_value:
            carr_cd = cls.map_carrier_code(carrier_value)
            if carr_cd:
                props['carr_cd'] = carr_cd
        return props
    
    @classmethod
    def enrich_file_node(cls, props: dict) -> dict:
        """파일 노드에 해시 속성 정규화"""
        # 해시 알고리즘 정규화
        hash_alg = props.get('hash_alg') or props.get('hash_algorithm')
        if hash_alg:
            props['hash_alg'] = cls.normalize_hash_algorithm(hash_alg)
        else:
            props['hash_alg'] = 'SHA256'  # 기본값
        
        # 해시값이 없으면 evd_cd 추가
        if not props.get('hash_val'):
            props['evd_cd'] = 'E09'  # 디지털파일
        
        return props
    
    @classmethod
    def auto_enrich(cls, label: str, props: dict) -> dict:
        """라벨에 따라 자동으로 표준 코드 추가"""
        if label == 'vt_bacnt':
            return cls.enrich_account_node(props)
        elif label == 'vt_telno':
            return cls.enrich_phone_node(props)
        elif label == 'vt_file':
            return cls.enrich_file_node(props)
        return props


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
            logger.error(f"!!! DB 접속 오류: {e}")
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
            logger.info(f"   [Index] '{label_name}' 라벨에 GIN 인덱스 적용 완료")
        except Exception as e:
            # 인덱스 생성 실패가 전체 로직을 멈추게 하지는 않음 (로그만 출력)
            logger.warning(f"   ⚠️ 인덱스 생성 중 경고 (무시 가능): {e}")

    @staticmethod
    def import_csv(file, mapping, target_graph):
        logger.info("▶ [ETL] 고속 적재(Batch) + 인덱싱 모드 시작...")

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
            logger.info(f"   [CSV 헤더] {list(df.columns)}")
            logger.info(f"   [매핑 정보] Source: {src_col} → {src_key} (라벨: {src_label})")
            logger.info(f"   [매핑 정보] Target: {tgt_col} → {tgt_key} (라벨: {tgt_label})")
            if src_col not in df.columns: return False, 0, 0, f"❌ '{src_col}' 컬럼 없음"
            if tgt_col not in df.columns: return False, 0, 0, f"❌ '{tgt_col}' 컬럼 없음"

            # 그래프 경로 설정
            safe_set_graph_path(cur, target_graph)

            # 5. 데이터 전처리 (메모리 구조화)
            logger.info("▶ [ETL] 데이터 구조화 중...")
            node_data_map = {} 
            edge_data_list = []

            for i, row in df.iterrows():
                src_val = str(row[src_col]).strip()
                tgt_val = str(row[tgt_col]).strip()

                if not src_val or not tgt_val: continue

                # 이번 row의 추가 속성만 먼저 수집
                row_src_props = {}
                row_tgt_props = {}
                
                # 시간축(Temporal) & 출처(Provenance) 속성 자동 추가
                from datetime import datetime
                current_time = datetime.now().isoformat()
                edge_props = {
                    "source": "csv_import",
                    "timestamp": current_time,
                    "seq": i + 1,  # 행 순서 번호
                    "created_at": current_time
                }
                
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
                    # 새 노드 생성 시만 기본 속성 초기화 (created_at 포함)
                    node_data_map[src_node_key] = {
                        "props": {src_key: src_val, "updated": "true", "created_at": current_time},
                        "manual_label": src_label
                    }
                # 이번 row의 추가 속성 병합
                node_data_map[src_node_key]["props"].update(row_src_props)
                
                # Target 노드 처리 (중복 제거 - 속성 병합)
                tgt_node_key = f"{tgt_key}_{tgt_val}"
                if tgt_node_key not in node_data_map:
                    # 새 노드 생성 시만 기본 속성 초기화 (created_at 포함)
                    node_data_map[tgt_node_key] = {
                        "props": {tgt_key: tgt_val, "updated": "true", "created_at": current_time},
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
            logger.info(f"▶ [ETL] 중복 제거 중... (총 {len(node_data_map)}개 노드)")
            unique_nodes = list(node_data_map.values())
            
            # ============================
            # 3.5 인덱스 생성 (성능 최적화)
            # ============================
            logger.info("▶ [ETL] 데이터베이스 인덱스 생성 중...")
            # KICS 전체 노드 타입에 대한 인덱스 생성
            kics_labels = ['vt_flnm', 'vt_bacnt', 'vt_telno', 'vt_site', 
                          'vt_ip', 'vt_file', 'vt_atm', 'vt_id', 'vt_psn']
            for label in kics_labels:
                ETLService._create_gin_index(cur, target_graph, label)
            
            logger.info(f"  [ETL] 인덱스 생성 완료 ({len(kics_labels)}개 라벨)")
            
            # ============================
            # 4. 노드 처리 (MERGE 로직)
            # ============================
            total_nodes = len(unique_nodes)
            total_edges = len(edge_data_list)

            if total_nodes == 0: return True, 0, 0, "유효 데이터 0건"

            logger.info(f"▶ [ETL] 적재 시작 (Node: {total_nodes}, Edge: {total_edges})")

            # 6. DB 적재 실행 (Batch Processing)
            
            # [Step A] 노드 적재 - AgensGraph CREATE 사용 (동적 라벨 결정)
            logger.info(f"  [ETL] 노드 {total_nodes}개 CREATE 시작...")
            
            # GraphService import (동적 라벨 결정용)
            from app.services.graph_service import GraphService
            
            # (1) SET graph_path
            safe_set_graph_path(cur, target_graph)
            
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

                    # 표준 코드 자동 매핑 (StandardCodeMapper)
                    enriched_props = StandardCodeMapper.auto_enrich(dynamic_label, enriched_props)

                    # V4.0 메타 6 컬럼 주입 (Phase 2.1)
                    # source_domain 우선순위: node_data 명시 > ETL 컨텍스트 > 기본 'KICS'(investigation)
                    from app.services.rdb_to_graph_service import RdbToGraphService
                    enriched_props = RdbToGraphService.make_node_props_v40(
                        dynamic_label,
                        enriched_props,
                        source_domain=node_data.get('source_domain', 'KICS'),
                        source_id=node_data.get('source_id'),
                    )

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
                    logger.error(f"    노드 처리 실패: {e}")
                    continue

            conn.commit()
            logger.info(f"  [ETL] 노드 처리 완료: 생성 {nodes_created_count}개, 업데이트 {nodes_updated_count}개")
            logger.info(f"  [ETL] 라벨별 분포: {label_stats}")

            # [Step B] 엣지 적재 - MATCH + CREATE 패턴 (동적 라벨 매칭)
            logger.info(f"  [ETL] 엣지 {total_edges}개 CREATE 시작...")
            
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

                    # V4.0 엣지 메타 4 컬럼 주입 (Phase 2.1.D)
                    from app.services.rdb_to_graph_service import RdbToGraphService
                    enriched_edge_props = RdbToGraphService.make_edge_props_v40(
                        edge_type,
                        enriched_edge_props,
                        source_domain=edge_data.get('source_domain', 'KICS'),
                        source_id=edge_data.get('source_id'),
                    )

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
                    # MERGE로 멱등성 확보 (재실행 시 엣지 중복 방지) + 속성은 SET으로 갱신
                    edge_create_query = f"""
                    MATCH (v1), (v2)
                    WHERE id(v1) = '{src_id}' AND id(v2) = '{tgt_id}'
                    MERGE (v1)-[r:{edge_type}]->(v2)
                    """
                    if edge_props_str:
                        edge_create_query += f"                    SET r += {{{edge_props_str}}}\n"
                    cur.execute(edge_create_query)
                    edges_created_count += 1
                except Exception as e:
                    # 노드가 없거나 에러 발생 시 스킵
                    logger.error(f"    엣지 생성 실패: {e}")
                    continue
            
            conn.commit()
            logger.info(f"  [ETL] 기본 엣지 {edges_created_count}개 CREATE 완료")

            # ============================
            # [Step C] 추가 관계 처리 (additionalRelations)
            # ============================
            additional_rels = mapping.get('additionalRelations', [])
            if additional_rels:
                logger.info(f"  [ETL] 추가 관계 {len(additional_rels)}개 처리 중...")
                additional_edges_count = 0
                
                for add_rel in additional_rels:
                    add_src_col = add_rel.get('sourceCol', '').strip()
                    add_tgt_col = add_rel.get('targetCol', '').strip()
                    add_src_key = add_rel.get('srcKey', 'id').strip()
                    add_tgt_key = add_rel.get('tgtKey', 'id').strip()
                    add_edge_type = ETLService._sanitize_label(add_rel.get('edgeType', 'RELATION'))
                    
                    if add_src_col not in df.columns or add_tgt_col not in df.columns:
                        logger.warning(f"    ⚠️ 컬럼 누락: {add_src_col} 또는 {add_tgt_col}")
                        continue
                    
                    for i, row in df.iterrows():
                        add_src_val = str(row[add_src_col]).strip()
                        add_tgt_val = str(row[add_tgt_col]).strip()
                        
                        if not add_src_val or not add_tgt_val:
                            continue
                        
                        try:
                            # 기존 노드 ID 조회 + 엣지 생성
                            edge_create_query = f"""
                            SELECT v1.id, v2.id 
                            FROM "{target_graph}"."ag_vertex" v1,
                                 "{target_graph}"."ag_vertex" v2
                            WHERE v1.properties ->> '{add_src_key}' = '{add_src_val}'
                              AND v2.properties ->> '{add_tgt_key}' = '{add_tgt_val}'
                            LIMIT 1
                            """
                            cur.execute(edge_create_query)
                            result = cur.fetchone()
                            
                            if result:
                                src_id, tgt_id = result
                                # V4.0 provenance 메타 주입 (source_domain/source_id/collected_at) — 엣지 출처 추적
                                from app.services.rdb_to_graph_service import RdbToGraphService
                                add_edge_props = RdbToGraphService.make_edge_props_v40(
                                    add_edge_type, {},
                                    source_domain=add_rel.get('source_domain', 'KICS'),
                                    source_id=add_rel.get('source_id'),
                                )
                                add_props_list = [f"{k}: '{str(v).replace(chr(39), chr(39)+chr(39))}'"
                                                  for k, v in add_edge_props.items()]
                                add_props_str = ", ".join(add_props_list)
                                # MERGE로 멱등성 확보 (재실행 시 중복 방지) + provenance는 SET으로 갱신
                                create_edge_q = f"""
                                MATCH (v1), (v2)
                                WHERE id(v1) = '{src_id}' AND id(v2) = '{tgt_id}'
                                MERGE (v1)-[r:{add_edge_type}]->(v2)
                                """
                                if add_props_str:
                                    create_edge_q += f"                                SET r += {{{add_props_str}}}\n"
                                cur.execute(create_edge_q)
                                additional_edges_count += 1
                        except Exception as e:
                            # 엣지 생성 실패 시 스킵
                            continue
                    
                    logger.info(f"    [{add_edge_type}] 엣지 처리 완료")
                
                edges_created_count += additional_edges_count
                logger.info(f"  [ETL] 추가 엣지 {additional_edges_count}개 CREATE 완료")
            
            conn.commit()
            logger.info(f"▶ [ETL] 모든 작업 완료! (Node: {nodes_created_count}, Edge: {edges_created_count})")
            
            return True, nodes_created_count, edges_created_count, "적재 완료"

        except Exception as e:
            logger.error(f"!!! [ETL Error] {e}")
            import traceback
            traceback.print_exc()
            return False, 0, 0, str(e)
        finally:
            if 'conn' in locals():
                conn.close()
    
