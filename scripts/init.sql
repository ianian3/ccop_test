-- ================================================================
-- CCOP 통합 스키마 초기화 스크립트 (Unified Schema v1.1)
-- 
-- 1. [RDB] KICS 기반 원천 데이터 (System of Record)
-- 2. [GDB] POLE 기반 4-Layer 온톨로지 (Relationship Engine)
-- 3. [Vector] ChromaDB 기반 임베딩 (Semantic Engine) - 외부 서비스
-- ================================================================

-- 확장 모듈 활성화
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- AgensGraph는 기본 활성화됨

-- ================================================================
-- 1. RDB SCHEME (System of Record) - KICS 표준 준수
-- ================================================================

-- 1.1 공통 코드 그룹
CREATE TABLE code_group (
    group_code VARCHAR(20) PRIMARY KEY,
    group_name VARCHAR(50) NOT NULL,
    description TEXT,
    is_use BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(50) DEFAULT 'SYSTEM'
);

-- 1.2 공통 상세 코드
CREATE TABLE common_code (
    group_code VARCHAR(20) REFERENCES code_group(group_code),
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    sort_order INT DEFAULT 0,
    is_use BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (group_code, code)
);

-- 1.3 사건 정보 (Case)
CREATE TABLE case_info (
    id BIGSERIAL PRIMARY KEY,
    receipt_no VARCHAR(50) NOT NULL,     -- 접수번호 (UK)
    flnm VARCHAR(50),                    -- 사건번호 (KICS)
    crime_type VARCHAR(20),              -- 죄명분류코드
    damage_amount NUMERIC(15, 2),        -- 피해금액
    case_summary TEXT,                   -- 사건개요
    investigator_id VARCHAR(50),         -- 담당수사관
    status VARCHAR(20) DEFAULT 'OPEN',   -- 수사상태
    
    -- Audit Columns
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(50) DEFAULT 'SYSTEM',
    updated_at TIMESTAMPTZ,
    updated_by VARCHAR(50),
    is_deleted BOOLEAN DEFAULT FALSE,
    
    CONSTRAINT uk_case_receipt_no UNIQUE (receipt_no)
);

-- 1.4 인물 정보 (Person - Suspect/Victim)
CREATE TABLE person (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,          -- 성명
    rrn VARCHAR(200),                    -- 주민등록번호 (암호화 필수)
    role VARCHAR(20) NOT NULL,           -- 역할 (SUSPECT, VICTIM, WITNESS)
    contact VARCHAR(50),                 -- 연락처
    
    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- 1.5 증거 마스터 (Evidence Master)
CREATE TABLE evidence (
    id BIGSERIAL PRIMARY KEY,
    case_id BIGINT REFERENCES case_info(id),
    evidence_type VARCHAR(20) NOT NULL,  -- ACCOUNT, PHONE, IP, FILE
    evidence_value VARCHAR(200) NOT NULL,-- 실제 값 (계좌번호, 전화번호 등)
    source VARCHAR(50),                  -- 출처 (통신사, 은행 등)
    confidence NUMERIC(3, 2) DEFAULT 1.0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT uk_evidence_val UNIQUE (case_id, evidence_type, evidence_value)
);

-- ================================================================
-- 2. GDB SCHEME (Relationship Engine) - 4-Layer Ontology
-- ================================================================

-- 그래프 경로 설정
CREATE GRAPH investigation_graph;
SET graph_path = investigation_graph;

-- 2.1 Vertex Labels (Nodes)

-- Layer 1: Case
CREATE VLABEL vt_case;       -- 사건
CREATE VLABEL vt_inv;        -- 수사

-- Layer 2: Actor
CREATE VLABEL vt_psn;        -- 인물 (Person)
CREATE VLABEL vt_org;        -- 조직 (Organization)
CREATE VLABEL vt_dev;        -- 기기 (Device)

-- Layer 3: Action (Legacy - backward compatibility)
CREATE VLABEL vt_transfer;   -- 이체 (Transfer) [Legacy]
CREATE VLABEL vt_call;       -- 통화 (Call) [Legacy]
CREATE VLABEL vt_access;     -- 접속 (Access)
CREATE VLABEL vt_msg;        -- 메시지 (Message)

-- Layer 3: Event (Dynamic Ontology - 신규)
CREATE VLABEL vt_event;      -- 이벤트 (Event) - 이체/통화/접속 등 통합
CREATE VLABEL vt_persona;    -- 페르소나 (Persona) - 인물의 디지털 가면

-- Layer 4: Evidence
CREATE VLABEL vt_bacnt;      -- 계좌 (BankAccount)
CREATE VLABEL vt_telno;      -- 전화 (Phone)
CREATE VLABEL vt_ip;         -- IP주소 (NetworkTrace)
CREATE VLABEL vt_site;       -- 사이트 (WebTrace)
CREATE VLABEL vt_file;       -- 파일 (FileTrace)

-- 2.2 Edge Labels (Relationships)

-- Actor -> Action (수행)
CREATE ELABEL performed;     -- (Person)-[:performed]->(Action)

-- Action -> Evidence (사용) [Legacy]
CREATE ELABEL from_account;  -- (Transfer)-[:from_account]->(BankAccount)
CREATE ELABEL to_account;    -- (Transfer)-[:to_account]->(BankAccount)
CREATE ELABEL caller;        -- (Call)-[:caller]->(Phone)
CREATE ELABEL callee;        -- (Call)-[:callee]->(Phone)
CREATE ELABEL accessed_from; -- (Access)-[:accessed_from]->(IP)
CREATE ELABEL accessed_to;   -- (Access)-[:accessed_to]->(Site)

-- Event-Centric (신규)
CREATE ELABEL participated_in;  -- (Entity)-[:participated_in {role}]->(Event)
CREATE ELABEL uses_persona;     -- (Person)-[:uses_persona]->(Persona)
CREATE ELABEL event_involved;   -- (Event)-[:event_involved]->(Evidence)
CREATE ELABEL supported_by;     -- (Event)-[:supported_by]->(Evidence)

-- Case -> Evidence (직접 흔적)
CREATE ELABEL digital_trace; -- (Case)-[:digital_trace]->(Evidence)
CREATE ELABEL used_account;  -- (Case)-[:used_account]->(BankAccount)

-- Case -> Person (연루)
CREATE ELABEL involves;      -- (Case)-[:involves]->(Person)

-- 인덱스 (Graph Indexing)
CREATE PROPERTY INDEX ON vt_psn(name);
CREATE PROPERTY INDEX ON vt_bacnt(actno);
CREATE PROPERTY INDEX ON vt_telno(telno);
CREATE PROPERTY INDEX ON vt_case(flnm);

-- ================================================================
-- 3. VECTOR SCHEME (Semantic Engine)
-- ================================================================
-- 
-- 📌 Vector DB 아키텍처 결정사항 (2026-01-30)
-- 
-- CCOP은 ChromaDB를 Vector Store로 사용합니다.
-- 
-- 이유:
-- 1. 법률 PDF 문서의 임베딩 저장 및 검색에 특화
-- 2. OpenAI text-embedding-3-small (1536 dim) 사용
-- 3. Flask 앱과 독립적인 파일 기반 영속성
-- 
-- 데이터 위치: ./chroma_data/ (Docker 볼륨 마운트 권장)
-- 관련 코드: app/services/legal_rag_service.py
-- 
-- 참고: pgvector 확장은 AgensGraph 이미지에 미포함되어 있어
--       별도 설치 없이 ChromaDB로 통일합니다.
-- ================================================================


-- ================================================================
-- 초기 데이터 (Seed Data)
-- ================================================================

-- 범죄 유형 코드
INSERT INTO code_group (group_code, group_name) VALUES ('CRIME_TYPE', '범죄유형');
INSERT INTO common_code (group_code, code, name) VALUES 
('CRIME_TYPE', 'C101', '보이스피싱'),
('CRIME_TYPE', 'C102', '스미싱'),
('CRIME_TYPE', 'C103', '파밍'),
('CRIME_TYPE', 'C104', '메신저피싱'),
('CRIME_TYPE', 'C105', '투자사기'),
('CRIME_TYPE', 'C201', '몸캠피싱'),
('CRIME_TYPE', 'C202', '랜섬웨어'),
('CRIME_TYPE', 'C301', '자금세탁');

-- 금결원 은행 코드 (주요 은행)
INSERT INTO code_group (group_code, group_name) VALUES ('BANK', '은행코드');
INSERT INTO common_code (group_code, code, name) VALUES 
('BANK', '002', '산업은행'),
('BANK', '003', '기업은행'),
('BANK', '004', '국민은행'),
('BANK', '007', '수협은행'),
('BANK', '011', '농협은행'),
('BANK', '020', '우리은행'),
('BANK', '023', 'SC제일은행'),
('BANK', '027', '씨티은행'),
('BANK', '031', '대구은행'),
('BANK', '032', '부산은행'),
('BANK', '034', '광주은행'),
('BANK', '035', '제주은행'),
('BANK', '037', '전북은행'),
('BANK', '039', '경남은행'),
('BANK', '045', '새마을금고'),
('BANK', '048', '신협'),
('BANK', '071', '우체국'),
('BANK', '081', '하나은행'),
('BANK', '088', '신한은행'),
('BANK', '089', '케이뱅크'),
('BANK', '090', '카카오뱅크'),
('BANK', '092', '토스뱅크');

-- 통신사 코드
INSERT INTO code_group (group_code, group_name) VALUES ('CARRIER', '통신사코드');
INSERT INTO common_code (group_code, code, name) VALUES 
('CARRIER', '01', 'SKT'),
('CARRIER', '02', 'KT'),
('CARRIER', '03', 'LGU+'),
('CARRIER', '04', '알뜰폰(MVNO)');

-- 역할 코드
INSERT INTO code_group (group_code, group_name) VALUES ('ROLE', '역할코드');
INSERT INTO common_code (group_code, code, name) VALUES 
('ROLE', '01', '피의자'),
('ROLE', '02', '피해자'),
('ROLE', '03', '참고인'),
('ROLE', '04', '공범'),
('ROLE', '05', '수금책'),
('ROLE', '06', '대포주'),
('ROLE', '07', '총책');

-- 증거유형 코드
INSERT INTO code_group (group_code, group_name) VALUES ('EVIDENCE', '증거유형');
INSERT INTO common_code (group_code, code, name) VALUES 
('EVIDENCE', 'E01', '계좌정보'),
('EVIDENCE', 'E02', '이체내역'),
('EVIDENCE', 'E03', '전화번호'),
('EVIDENCE', 'E04', '통화내역'),
('EVIDENCE', 'E05', 'IP주소'),
('EVIDENCE', 'E06', '접속기록'),
('EVIDENCE', 'E07', '가입자정보'),
('EVIDENCE', 'E08', '웹사이트'),
('EVIDENCE', 'E09', '디지털파일'),
('EVIDENCE', 'E10', '가상자산');

-- 테스트용 사건 1건
INSERT INTO case_info (receipt_no, flnm, crime_type, case_summary) 
VALUES ('2026-001', '2026-000123', 'C101', '김철수 보이스피싱 피해신고');
