logger = logging.getLogger(__name__)

def create_graph_indexes(cur, graph_name):
import logging
    """
    KICS 노드 타입별 인덱스 생성 (성능 최적화)
    
    AgensGraph는 각 라벨을 별도 테이블로 저장하며,
    properties는 JSONB 타입으로 저장됩니다.
    GIN 인덱스를 사용하여 JSONB 쿼리 성능을 향상시킵니다.
    """
    
    # KICS 노드 타입별 주요 속성 매핑
    INDEX_MAPPINGS = {
        'vt_flnm': ['flnm', 'receipt_no'],           # 접수번호
        'vt_bacnt': ['actno', 'bacnt', 'account_no'], # 계좌번호
        'vt_telno': ['telno', 'phone'],               # 전화번호
        'vt_site': ['url', 'site', 'domain'],         # 사이트
        'vt_ip': ['ip', 'ip_addr', 'ipaddr'],         # IP주소
        'vt_file': ['file', 'filename', 'filepath'],  # 파일
        'vt_atm': ['atm', 'atm_id'],                  # ATM
        'vt_id': ['id', 'user_id', 'nickname'],       # ID/닉네임
        'vt_psn': ['name', 'suspect']                 # 사람/용의자
    }
    
    created_indexes = []
    
    for label, properties in INDEX_MAPPINGS.items():
        try:
            # 1. 전체 properties에 대한 GIN 인덱스 (전반적 성능 향상)
            idx_name = f"idx_{label}_properties"
            create_idx_query = f"""
            CREATE INDEX IF NOT EXISTS {idx_name}
            ON "{graph_name}"."{label}"
            USING GIN (properties)
            """
            cur.execute(create_idx_query)
            created_indexes.append(f"{label}(properties)")
            
            # 2. 주요 속성별 개별 인덱스 (특정 쿼리 최적화)
            for prop in properties:
                idx_name = f"idx_{label}_{prop}"
                # JSONB 필드의 특정 키에 대한 인덱스
                create_idx_query = f"""
                CREATE INDEX IF NOT EXISTS {idx_name}
                ON "{graph_name}"."{label}"
                USING GIN ((properties -> '{prop}'))
                """
                cur.execute(create_idx_query)
                created_indexes.append(f"{label}.{prop}")
                
        except Exception as e:
            # 인덱스 생성 실패는 치명적이지 않으므로 계속 진행
            logger.error(f"  [경고] 인덱스 생성 실패 ({label}): {e}")
            continue
    
    if created_indexes:
        logger.info(f"  [ETL] 인덱스 생성 완료: {len(created_indexes)}개")
    else:
        logger.info(f"  [ETL] 인덱스 생성 스킵 (이미 존재)")
