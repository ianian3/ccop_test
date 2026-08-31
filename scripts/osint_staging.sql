-- =====================================================================
-- CCOP OSINT 대량 적재 — Staging DDL + Provenance 사이드카  (초안 / 실구현 착수용)
-- 스택: AgensGraph(PostgreSQL 기반). 아키텍처: Landing → Staging(정규화) → Graph(MERGE)
-- 실행: psql -f scripts/osint_staging.sql  (또는 AgensGraph 클라이언트)
-- ⚠️ AgensGraph 버전별 확인 지점은 [AGVER] 주석으로 표시
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS graph_meta;

-- ── 1) 배치(매니페스트) 추적 ─────────────────────────────────
CREATE TABLE IF NOT EXISTS staging.osint_batch (
    batch_id       bigserial PRIMARY KEY,
    agency_id      text NOT NULL,
    delivery_type  text NOT NULL CHECK (delivery_type IN ('snapshot','delta')),
    schema_version text,
    window_from    timestamptz,
    window_to      timestamptz,
    declared_nodes int,
    declared_edges int,
    sha256         text,
    received_at    timestamptz DEFAULT now(),
    status         text NOT NULL DEFAULT 'received'   -- received|validated|loaded|failed
);

-- ── 2) 노드 스테이징 (COPY 대상, 정규화 완료본) ──────────────
CREATE TABLE IF NOT EXISTS staging.osint_nodes (
    batch_id         bigint NOT NULL REFERENCES staging.osint_batch(batch_id) ON DELETE CASCADE,
    label            text  NOT NULL,
    id_field         text  NOT NULL,
    id_value         text  NOT NULL,          -- 정규화된 표준 식별자 값
    id_format        text  NOT NULL,
    node_key         text  NOT NULL,          -- 자연키: md5(label || '|' || id_value)  ← dedup/idempotent 기준
    attrs            jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_id        text  NOT NULL,
    reliability_tier int   NOT NULL DEFAULT 4,
    collected_at     timestamptz,
    confidence       real,
    evidence_ref     text,
    op               text  NOT NULL DEFAULT 'upsert' CHECK (op IN ('upsert','delete'))
);
CREATE INDEX IF NOT EXISTS ix_stg_nodes_batch ON staging.osint_nodes(batch_id);
CREATE INDEX IF NOT EXISTS ix_stg_nodes_key   ON staging.osint_nodes(label, node_key);

-- ── 3) 엣지 스테이징 (양 끝을 node_key로 참조) ───────────────
CREATE TABLE IF NOT EXISTS staging.osint_edges (
    batch_id         bigint NOT NULL REFERENCES staging.osint_batch(batch_id) ON DELETE CASCADE,
    edge_type        text NOT NULL,
    from_label       text NOT NULL,  from_value text NOT NULL,  from_key text NOT NULL,
    to_label         text NOT NULL,  to_value   text NOT NULL,  to_key   text NOT NULL,
    attrs            jsonb NOT NULL DEFAULT '{}'::jsonb,
    source_id        text NOT NULL,
    reliability_tier int  NOT NULL DEFAULT 4,
    rec_created      timestamptz,
    confidence       real,
    op               text NOT NULL DEFAULT 'upsert' CHECK (op IN ('upsert','delete'))
);
CREATE INDEX IF NOT EXISTS ix_stg_edges_batch ON staging.osint_edges(batch_id);
CREATE INDEX IF NOT EXISTS ix_stg_edges_from  ON staging.osint_edges(from_label, from_key);

-- ── 4) 격리(dead-letter) — 검증 실패 레코드 ──────────────────
CREATE TABLE IF NOT EXISTS staging.osint_quarantine (
    batch_id   bigint,
    kind       text,        -- node | edge | manifest
    raw        jsonb,
    reason     text,
    created_at timestamptz DEFAULT now()
);

-- ── 5) node_source 사이드카 — 다중출처 provenance (노드 복제 없이) ──
-- tier-4 OSINT는 sourced_from 엣지 대신 이 테이블로 "누가·언제·얼마 신뢰"를 추적
CREATE TABLE IF NOT EXISTS graph_meta.node_source (
    node_key         text NOT NULL,
    label            text NOT NULL,
    source_id        text NOT NULL,
    reliability_tier int,
    first_seen       timestamptz,
    last_seen        timestamptz,
    confidence       real,
    evidence_ref     text,
    PRIMARY KEY (node_key, source_id)
);
CREATE INDEX IF NOT EXISTS ix_node_source_key ON graph_meta.node_source(node_key);

-- ── 6) 그래프/라벨 (최초 1회) ── AgensGraph ──────────────────
-- [AGVER] 아래는 AgensGraph 구문. 버전에 맞게 확인/조정.
-- CREATE GRAPH IF NOT EXISTS osint_graph;
-- SET graph_path = osint_graph;
-- -- 노드 라벨(V4.0 25종 중 OSINT 대상)
-- CREATE VLABEL IF NOT EXISTS vt_src;   CREATE VLABEL IF NOT EXISTS vt_site;
-- CREATE VLABEL IF NOT EXISTS site_cluster; CREATE VLABEL IF NOT EXISTS vt_ip;
-- CREATE VLABEL IF NOT EXISTS vt_file;  CREATE VLABEL IF NOT EXISTS vt_id;
-- CREATE VLABEL IF NOT EXISTS vt_msg;   CREATE VLABEL IF NOT EXISTS vt_bacnt;
-- CREATE VLABEL IF NOT EXISTS vt_telno; CREATE VLABEL IF NOT EXISTS vt_transfer;
-- CREATE VLABEL IF NOT EXISTS vt_org;   CREATE VLABEL IF NOT EXISTS vt_psn;
-- -- 엣지 라벨
-- CREATE ELABEL IF NOT EXISTS belongs_to_campaign; CREATE ELABEL IF NOT EXISTS resolves_to;
-- CREATE ELABEL IF NOT EXISTS hosts; CREATE ELABEL IF NOT EXISTS communicated_with;
-- CREATE ELABEL IF NOT EXISTS contains_file; CREATE ELABEL IF NOT EXISTS mentions_account;
-- CREATE ELABEL IF NOT EXISTS operates; CREATE ELABEL IF NOT EXISTS registered_to;
-- CREATE ELABEL IF NOT EXISTS sameAs;
-- -- [AGVER] node_key 유니크 프로퍼티 인덱스 (MERGE 키 성능/정합) — 라벨별 1회:
-- --   CREATE UNIQUE PROPERTY INDEX ON vt_site (node_key);   ... (각 라벨)

-- ── 7) sameAs 후보 뷰 (배치 엔티티해소 입력) ─────────────────
-- 정규화 식별자가 같은데 도메인이 다른 노드 쌍 = sameAs 후보 (blocking)
-- 실제 sameAs 엣지 생성은 배치 잡에서 검토 후 수행 (전건 자동생성 금지)
CREATE OR REPLACE VIEW graph_meta.sameas_candidates AS
    SELECT a.node_key AS osint_key, a.label, a.id_value
    FROM   staging.osint_nodes a
    WHERE  a.label IN ('vt_bacnt','vt_telno','vt_ip','vt_site','vt_file','vt_id','vt_transfer','vt_msg');
    -- 수사 도메인 그래프의 동일 id_value 노드와 조인 → 후보 산출 (구현 시 확장)
