"""
query_guard.py — 읽기 전용 그래프 조회 경로의 공용 가드 (감사 F02).

적용 경로: GraphService.execute_cypher(T2C/조회), /api/v1/graph-query, /api/v1/graph/read.

이중 방어:
  1) 앱 검사 check_read_only — 쓰기/DDL/권한/트랜잭션 키워드, 위험 함수, 다중 문장 차단.
     문자열·주석을 벗겨내지 않고 원문 그대로 검사한다. 앱 파서와 DB 파서의 인용 규칙이
     조금만 달라도(예: '\\' 이스케이프, // 주석) 벗겨낸 틈으로 쓰기 구문이 숨어 들어올 수
     있기 때문. 대가로 문자열 안의 단어(예: 'SET')도 차단되지만 보수적 오탐을 택한다.
  2) DB 세션 apply_read_only_session — default_transaction_read_only + statement_timeout.
     앱 검사를 우회해도 DB 가 쓰기를 거부하고, pg_sleep 류 장기 실행은 시간 상한에 걸린다.
     (호출마다 새 연결을 열고 닫는 경로 전용 — 풀 연결에 쓰면 설정이 다음 사용자에게 샌다)
"""
import os
import re

# 위치 무관 차단: Cypher 쓰기 + SQL DML/DDL/DCL (쓰기 CTE `WITH x AS (INSERT ...)` 포함)
_WRITE_KEYWORDS = (
    'CREATE', 'DELETE', 'DETACH', 'MERGE', 'REMOVE', 'SET', 'DROP',
    'INSERT', 'UPDATE', 'UPSERT', 'TRUNCATE', 'ALTER', 'GRANT', 'REVOKE',
)
# 문장 맨 앞에서만 차단: SQL 유틸리티·트랜잭션·세션 명령. 다중 문장을 막으므로 맨 앞만 보면
# 충분하고, 위치 무관으로 막으면 `(call:vt_call)`·`s.cluster` 같은 식별자가 오탐된다.
_LEADING_COMMANDS = (
    'COPY', 'VACUUM', 'ANALYZE', 'CALL', 'DO', 'EXECUTE', 'PREPARE', 'DEALLOCATE', 'LOCK',
    'COMMENT', 'REINDEX', 'CLUSTER', 'REFRESH', 'LISTEN', 'UNLISTEN', 'NOTIFY', 'RESET',
    'DISCARD', 'IMPORT', 'SECURITY', 'REASSIGN', 'CHECKPOINT', 'LOAD',
    'BEGIN', 'START', 'COMMIT', 'END', 'ABORT', 'ROLLBACK', 'SAVEPOINT', 'RELEASE',
)
# 읽기 문장 안에서도 부작용·지연·파일/네트워크 접근을 일으키는 함수
_DANGEROUS_FUNCTIONS = (
    'pg_sleep', 'pg_sleep_for', 'pg_sleep_until', 'set_config',
    'pg_read_file', 'pg_read_binary_file', 'pg_ls_dir', 'pg_stat_file',
    'lo_import', 'lo_export', 'lo_get', 'lo_put', 'lo_from_bytea',
    'dblink', 'dblink_exec', 'dblink_connect',
    'pg_terminate_backend', 'pg_cancel_backend', 'pg_reload_conf', 'pg_rotate_logfile',
    'pg_advisory_lock', 'pg_advisory_xact_lock', 'pg_notify', 'nextval', 'setval',
)
_WRITE_RE = re.compile(r'\b(' + '|'.join(_WRITE_KEYWORDS) + r')\b', re.IGNORECASE)
_LEADING_RE = re.compile(r'^\s*(' + '|'.join(_LEADING_COMMANDS) + r')\b', re.IGNORECASE)
_FUNC_RE = re.compile(r'\b(' + '|'.join(_DANGEROUS_FUNCTIONS) + r')\s*\(', re.IGNORECASE)


def statement_timeout_ms() -> int:
    """읽기 조회 1건의 DB 실행 시간 상한 (ms). env CYPHER_STATEMENT_TIMEOUT_MS, 기본 60초."""
    try:
        return max(1000, int(os.getenv('CYPHER_STATEMENT_TIMEOUT_MS', '60000')))
    except ValueError:
        return 60000


def max_rows() -> int:
    """읽기 조회 1건이 앱으로 가져오는 행 수 상한. env CYPHER_MAX_ROWS, 기본 20000."""
    try:
        return max(1, int(os.getenv('CYPHER_MAX_ROWS', '20000')))
    except ValueError:
        return 20000


def check_read_only(query: str):
    """읽기 전용 위반 사유를 반환. 통과면 None.

    Returns: None | 위반 토큰 문자열 (예: 'INSERT', 'pg_sleep()', ';')
    """
    if not query or not query.strip():
        return 'EMPTY'
    body = query.strip()
    # 끝의 세미콜론 1개는 허용, 그 외 세미콜론은 다중 문장으로 간주
    if body.endswith(';'):
        body = body[:-1]
    if ';' in body:
        return ';'
    m = _WRITE_RE.search(body) or _LEADING_RE.match(body)
    if m:
        return m.group(1).upper()
    m = _FUNC_RE.search(body)
    if m:
        return m.group(1).lower() + '()'
    return None


def apply_read_only_session(cur, timeout_ms: int = None):
    """새 연결 세션을 읽기 전용 + 실행 시간 상한으로 설정 (DB 계층 방어)."""
    cur.execute("SET default_transaction_read_only = on")
    cur.execute("SET statement_timeout = %s", (int(timeout_ms or statement_timeout_ms()),))


def fetch_capped(cur, limit: int):
    """최대 limit 행만 가져온다. Returns: (rows, truncated)"""
    rows = cur.fetchmany(limit + 1)
    if len(rows) > limit:
        return rows[:limit], True
    return rows, False
