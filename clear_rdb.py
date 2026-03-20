from app import create_app
from app.services.rdb_service import RDBService

app = create_app()
with app.app_context():
    conn, cur = RDBService.get_db_connection()
    tables_to_clear = [
        'TB_DGTL_FILE_INVNT', 'TB_EML_TRNS_EVT', 'TB_SYS_LGN_EVT',
        'TB_DRUG_SLANG', 'TB_DRUG_CLUE', 'TB_FRD_VCTM_RPT',
        'TB_WEB_MLGN_IDC', 'TB_WEB_ATCH', 'TB_WEB_PAGE', 'TB_WEB_URL', 'TB_WEB_DMN',
        'TB_VHCL_TOLL_EVT', 'TB_VHCL_LPR_EVT', 'TB_VHCL_MST',
        'TB_GEO_TRST_CARD_TRIP', 'TB_GEO_MBL_LOC_EVT',
        'TB_CHAT_MSG', 'TB_TELNO_SMS_MSG', 'TB_TELNO_CALL_DTL', 'TB_TELNO_JOIN', 'TB_TELNO_MST',
        'TB_FIN_EXTRC_BACNT', 'TB_FIN_BACNT_DLNG', 'TB_FIN_BACNT',
        'TB_INST', 'TB_PRSN', 'TB_INCDNT_MST'
    ]
    for table in tables_to_clear:
        try:
            cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
        except Exception as e:
            pass
    conn.commit()
    print("Database fully truncated.")
    cur.close()
    conn.close()

from app.services.graph_service import GraphService
with app.app_context():
    conn, cur = GraphService.get_db_connection()
    try:
        cur.execute("DROP GRAPH IF EXISTS tccop_graph_v4 CASCADE")
        conn.commit()
    except Exception as e:
        conn.rollback()
    
    cur.close()
    conn.close()
    print("Graph tccop_graph_v4 dropped.")
