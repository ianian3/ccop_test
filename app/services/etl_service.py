import pandas as pd
import psycopg2
import json
import re
from flask import current_app
from app.database import safe_set_graph_path, cypher_str, safe_ident
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
            bank_cd = cls.map_bank_code(bank_value)
            if bank_cd:
                props['bank_cd'] = bank_cd     # 2026-10-01 원천 정합: 사전 속성명(구 bnk_cd)
        return props
    
    @classmethod
    def enrich_phone_node(cls, props: dict) -> dict:
        """전화 노드에 표준 통신사코드 추가"""
        carrier_value = props.get('carrier') or props.get('carr') or props.get('통신사')
        if carrier_value:
            # 2026-10-01 원천 정합: 사전 속성은 통신사명 telco_nm (구 carr_cd 코드 — 사전에 없는 이름)
            props.setdefault('telco_nm', str(carrier_value).strip())
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
    def _csv_scope(file, mapping):
        """vt_psn 합성 키 범위(A안: 출처가 다르면 다른 사람) — 지정값 > CSV 파일명 > 'csv'."""
        import os
        import re
        sc = mapping.get('scope') or os.path.splitext(os.path.basename(getattr(file, 'filename', '') or ''))[0]
        sc = re.sub(r'[^0-9A-Za-z가-힣_.-]', '_', sc or '')[:60]
        return f'csv:{sc}' if sc else 'csv'

    @staticmethod
    def _to_canonical_key(label, props, key_col):
        """사용자가 고른 키 열을 SoT 정경 키로 옮긴다 (SoT 라벨만).
        vt_psn 은 이름 열이면 합성 키(psn:{scope}:{name})에 맡기고, vt_id 는 platform 이 없으면 'unknown'."""
        from app.services.ontology_service import KICSCrimeDomainOntology as O
        std = O.NODE_ID_STANDARD.get(label) or {}
        canon = std.get('canonical_field')
        if not canon:
            return dict(props)
        fields = [f.strip() for f in canon.strip('()').split(',')]
        out = dict(props)
        if key_col in fields:
            pass
        elif (std.get('synthesize') or {}).get('from') == key_col:
            pass
        else:
            target = 'id_val' if label == 'vt_id' else fields[0]
            out[target] = out.pop(key_col)
        if label == 'vt_id':
            out.setdefault('platform', 'unknown')
        return out

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
                src_node_key = f"{src_label}|{src_key}_{src_val}"
                if src_node_key not in node_data_map:
                    # 새 노드 생성 시만 기본 속성 초기화 (created_at 포함)
                    node_data_map[src_node_key] = {
                        "props": {src_key: src_val, "updated": "true", "created_at": current_time},
                        "manual_label": src_label, "key_col": src_key
                    }
                # 이번 row의 추가 속성 병합
                node_data_map[src_node_key]["props"].update(row_src_props)
                
                # Target 노드 처리 (중복 제거 - 속성 병합)
                tgt_node_key = f"{tgt_label}|{tgt_key}_{tgt_val}"
                if tgt_node_key not in node_data_map:
                    # 새 노드 생성 시만 기본 속성 초기화 (created_at 포함)
                    node_data_map[tgt_node_key] = {
                        "props": {tgt_key: tgt_val, "updated": "true", "created_at": current_time},
                        "manual_label": tgt_label, "key_col": tgt_key
                    }
                # 이번 row의 추가 속성 병합
                node_data_map[tgt_node_key]["props"].update(row_tgt_props)
                
                # 엣지는 실제 값 기반으로 연결
                edge_data_list.append({"src_nk": src_node_key, "tgt_nk": tgt_node_key, "props": edge_props})

            # ============================
            # 3~4. 노드·엣지 적재 — GraphWriter (정합 2단계 2d, 2026-10-01)
            #   구조(라벨·엣지 타입·방향·키) strict: SoT 밖 라벨/삭제 엣지/역방향은 행 단위로 거부하고 보고
            #   속성 warn: 사용자가 고른 열은 사전 밖이어도 싣되 경고로 남긴다
            #   키: 사용자가 고른 키 열 값을 SoT 정경 키로 싣는다(예: actno → account_no, 정규화 포함).
            #       종전엔 엣지 양끝을 라벨 무관 ag_vertex 속성 검색 LIMIT 1 로 찾아 다른 노드에 붙을 수 있었다
            # ============================
            from app.services.graph_service import GraphService
            from app.services.graph_writer import GraphWriter, GraphWriteError
            from app.services.ontology_service import OntologyEnricher
            from app.services.rdb_to_graph_service import RdbToGraphService

            if not node_data_map:
                return True, 0, 0, "유효 데이터 0건"
            scope = ETLService._csv_scope(file, mapping)
            w = GraphWriter(cur, target_graph, mode='strict', prop_mode='warn', scope=scope)
            rejected, label_stats, ends = [], {}, {}
            for nk, node_data in node_data_map.items():
                manual = node_data['manual_label']
                label = manual if manual and manual != 'auto' else GraphService.determine_node_label(node_data['props'])
                try:
                    props = ETLService._to_canonical_key(label, node_data['props'], node_data['key_col'])
                    props = OntologyEnricher.enrich_node(label, props)
                    props = StandardCodeMapper.auto_enrich(label, props)
                    props = RdbToGraphService.make_node_props_v40(label, props, source_domain=mapping.get('source_domain', 'KICS'))
                    ends[nk] = (label, w.node(label, props))
                    label_stats[label] = label_stats.get(label, 0) + 1
                except (GraphWriteError, ValueError) as e:
                    rejected.append(f'노드 {nk}: {e}')
            for ed in edge_data_list:
                s_end, t_end = ends.get(ed['src_nk']), ends.get(ed['tgt_nk'])
                if not s_end or not t_end:
                    continue                                   # 끝 노드가 거부됨 — 노드 쪽에서 이미 보고
                try:
                    ep = OntologyEnricher.enrich_edge(edge_type, ed['props'])
                    ep = RdbToGraphService.make_edge_props_v40(edge_type, ep, source_domain=mapping.get('source_domain', 'KICS'))
                    w.edge(edge_type, s_end, t_end, ep)
                except (GraphWriteError, ValueError) as e:
                    rejected.append(f'엣지 {edge_type} {s_end[0]}->{t_end[0]}: {e}')
                    if len(rejected) > 1000:
                        break
            stats = w.flush()
            for label in label_stats:                         # MERGE 키 검색용 GIN 인덱스 (실제 쓴 라벨만)
                ETLService._create_gin_index(cur, target_graph, label)
            conn.commit()
            nodes_created_count, edges_created_count = stats['nodes'], stats['edges']
            logger.info(f"  [ETL] 노드 {nodes_created_count} · 엣지 {edges_created_count} (양끝 미매칭 {stats['edges_unmatched']})")
            logger.info(f"  [ETL] 라벨별 분포: {label_stats}")
            if rejected:
                logger.warning(f"  [ETL] SoT 정책 거부 {len(rejected)}건 — 예: {list(dict.fromkeys(rejected))[:3]}")

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
                            SELECT v1.id, v2.id,
                                   (SELECT relname FROM pg_class WHERE oid = v1.tableoid),
                                   (SELECT relname FROM pg_class WHERE oid = v2.tableoid)
                            FROM "{target_graph}"."ag_vertex" v1,
                                 "{target_graph}"."ag_vertex" v2
                            WHERE v1.properties ->> %s = %s
                              AND v2.properties ->> %s = %s
                            LIMIT 1
                            """
                            # 2026-10-01 핫픽스: CSV 셀 값이 이스케이프 없이 SQL 에 들어가던 주입 경로 → 파라미터 바인딩
                            cur.execute(edge_create_query, (add_src_key, add_src_val, add_tgt_key, add_tgt_val))
                            result = cur.fetchone()
                            
                            if result:
                                src_id, tgt_id, s_lbl, t_lbl = result
                                # V4.0 provenance 메타 주입 (source_domain/source_id/collected_at) — 엣지 출처 추적
                                from app.services.rdb_to_graph_service import RdbToGraphService
                                add_edge_props = RdbToGraphService.make_edge_props_v40(
                                    add_edge_type, {},
                                    source_domain=add_rel.get('source_domain', 'KICS'),
                                    source_id=add_rel.get('source_id'),
                                )
                                # 2d: 엣지 타입·방향·속성은 SoT 검사(strict) — 위반은 이 행만 건너뛰고 보고
                                try:
                                    add_edge_props = w.check_edge(add_edge_type, s_lbl, t_lbl, add_edge_props)
                                except GraphWriteError as e:
                                    rejected.append(f'추가 관계 {add_edge_type} {s_lbl}->{t_lbl}: {e}')
                                    continue
                                add_props_str = GraphWriter.literal_map(add_edge_props)[1:-1]
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
                            logger.error(f"    추가 엣지 생성 실패: {e}")
                            continue
                    
                    logger.info(f"    [{add_edge_type}] 엣지 처리 완료")
                
                edges_created_count += additional_edges_count
                logger.info(f"  [ETL] 추가 엣지 {additional_edges_count}개 CREATE 완료")
            
            conn.commit()
            logger.info(f"▶ [ETL] 모든 작업 완료! (Node: {nodes_created_count}, Edge: {edges_created_count})")
            
            msg = "적재 완료"
            if rejected:
                msg += f" (SoT 정책 거부 {len(rejected)}건: {'; '.join(list(dict.fromkeys(rejected))[:3])})"
            if stats.get('warnings'):
                msg += f" (사전 밖 속성 경고 {len(stats['warnings'])}종)"
            return True, nodes_created_count, edges_created_count, msg

        except Exception as e:
            logger.error(f"!!! [ETL Error] {e}")
            import traceback
            traceback.print_exc()
            return False, 0, 0, str(e)
        finally:
            if 'conn' in locals():
                conn.close()
    
