-- KICS Ontology Layer 3 (Action) Support Schema Update

-- 1. rdb_transfers: 금융 이체 행위 (Mapping to vt_transfer)
CREATE TABLE IF NOT EXISTS rdb_transfers (
    trx_id SERIAL PRIMARY KEY,
    amount BIGINT NOT NULL DEFAULT 0,
    trx_date TIMESTAMP,
    sender_actno VARCHAR(50),
    receiver_actno VARCHAR(50),
    bank_code VARCHAR(10),
    memo VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sender FOREIGN KEY(sender_actno) REFERENCES rdb_accounts(actno) ON DELETE SET NULL,
    CONSTRAINT fk_receiver FOREIGN KEY(receiver_actno) REFERENCES rdb_accounts(actno) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_transfers_date ON rdb_transfers(trx_date);
CREATE INDEX IF NOT EXISTS idx_transfers_sender ON rdb_transfers(sender_actno);
CREATE INDEX IF NOT EXISTS idx_transfers_receiver ON rdb_transfers(receiver_actno);

-- 2. rdb_calls: 통화/문자 행위 (Mapping to vt_call, vt_msg)
CREATE TABLE IF NOT EXISTS rdb_calls (
    call_id SERIAL PRIMARY KEY,
    type VARCHAR(10) DEFAULT 'CALL', -- CALL, SMS, MMS
    duration INT DEFAULT 0,          -- seconds
    call_date TIMESTAMP,
    caller_no VARCHAR(20),
    callee_no VARCHAR(20),
    cell_location VARCHAR(100),      -- Station Location
    content_preview VARCHAR(255),    -- SMS content summary
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_caller FOREIGN KEY(caller_no) REFERENCES rdb_phones(telno) ON DELETE SET NULL,
    CONSTRAINT fk_callee FOREIGN KEY(callee_no) REFERENCES rdb_phones(telno) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_calls_date ON rdb_calls(call_date);
CREATE INDEX IF NOT EXISTS idx_calls_caller ON rdb_calls(caller_no);
CREATE INDEX IF NOT EXISTS idx_calls_callee ON rdb_calls(callee_no);
