"""
csv_spec_v48.py — V4.8 전달 CSV 규격 등록부 (UI 적재 경로용, 감사 F07).

전달 규격(handoff/csv_spec_v4.8)의 파일 종류와, UI 적재(RDBService.import_predefined_schema_to_rdb)
가 실제로 처리하는 종류를 한곳에 둔다. 규격 목록은 validate_csv_v48.py 의 SPEC 과 같아야 하며
tests/test_csv_spec_registry.py 가 대조한다.

UI 가 처리하지 않는 규격 파일을 넘기면 이전에는 INSERT 0회로 success=True 가 반환됐다.
이제 적재 전에 판정해 오류로 돌려준다(전달용 CLI 적재기 안내).
"""

# 규격 파일 키워드 — 긴 것부터 (tbl_eg_case_prsn 이 tbl_eg_case 보다 먼저 잡혀야 한다)
SPEC_KINDS = (
    'tbl_eg_bactno_poss', 'tbl_eg_telno_poss', 'tbl_eg_case_prsn', 'tbl_eg_id_use',
    'tbl_eg_id_msg', 'tbl_eg_ip_use', 'tbl_eg_loc_use', 'tbl_eg_call', 'tbl_eg_case',
    'tbl_eg_rmt',
    'tbl_vt_psn', 'tbl_vt_telno', 'tbl_vt_bacnt', 'tbl_vt_ip', 'tbl_vt_id', 'tbl_vt_loc',
)

# UI RDB 적재(test_v40) 핸들러가 있는 종류
UI_SUPPORTED_KINDS = frozenset({
    'tbl_vt_psn', 'tbl_vt_telno', 'tbl_vt_bacnt',
    'tbl_eg_call', 'tbl_eg_rmt', 'tbl_eg_bactno_poss', 'tbl_eg_telno_poss',
    'tbl_eg_case_prsn', 'tbl_eg_case',
})

CLI_HINT = ("전달용 CLI 적재기로 적재하세요: "
            "python3 handoff/csv_spec_v4.8/load_csv_to_graph.py <CSV폴더> --graph <그래프명>")


def match_kind(filename):
    """파일명 → 규격 키워드. 규격 밖이면 None."""
    fn = (filename or '').lower()
    for kind in SPEC_KINDS:
        if kind in fn:
            return kind
    return None


def ui_support(filename):
    """UI 적재 가능 여부. Returns: (kind | None, ok: bool, 사유 메시지 | None)"""
    kind = match_kind(filename)
    if kind is None:
        return None, False, (f"'{filename}': V4.8 규격 파일명(tbl_vt_*/tbl_eg_*)이 아닙니다. "
                             f"규격 파일명: {', '.join(SPEC_KINDS)}")
    if kind not in UI_SUPPORTED_KINDS:
        return kind, False, (f"'{filename}'({kind})은 UI 적재가 지원하지 않는 규격입니다 — "
                             f"적재되지 않았습니다. {CLI_HINT}")
    return kind, True, None
