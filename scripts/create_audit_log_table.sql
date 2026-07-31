-- =====================================================================
-- TB_AUDIT_LOG — 감사 로그 테이블 (Phase 1: 비주얼 쿼리 + T2C 감사)
-- =====================================================================
-- 용도: 수사관의 그래프 조작(T2C 질의 + 비주얼 조작: 확장/경로/네트워크)을
--       세션 단위로 기록 → 재현성·증거능력 확보.
-- 기록 지점:
--   · app/services/langgraph_agent.py  _write_audit_log()  (T2C 질의)
--   · app/routes.py                      _audit_visual()    (비주얼 조작, 비동기)
-- 실행: psql -f scripts/create_audit_log_table.sql  (또는 AgensGraph 클라이언트)
-- 주의: public 스키마에 생성 (앱 커넥션의 기본 search_path = "$user", public).
--       IF NOT EXISTS 라 재실행 안전.
-- =====================================================================

CREATE TABLE IF NOT EXISTS TB_AUDIT_LOG (
    audit_id      bigserial PRIMARY KEY,
    session_id    text,                        -- 수사 세션(프론트 _investSessionId)
    action_cd     text,                        -- EXPAND | MULTI_HOP | PATH | ACCOMPLICE | HUB | (T2C: QUERY 등)
    graph_path    text,                        -- 대상 그래프
    cypher_cn     text,                        -- 재현용 Cypher (Phase 1: 대표 쿼리)
    input_cn      text,                        -- 조작 파라미터 (node_id, depth, src->tgt 등)
    result_status text,                        -- success | not_found | error
    result_cnt    integer,                     -- 반환 요소 수
    exec_ms       integer,                     -- 서버 처리 소요(ms)
    created_at    timestamptz DEFAULT now()    -- 조작 시각 (감사 타임라인 정렬 기준)
);

CREATE INDEX IF NOT EXISTS ix_audit_session ON TB_AUDIT_LOG(session_id);
CREATE INDEX IF NOT EXISTS ix_audit_created ON TB_AUDIT_LOG(created_at);
