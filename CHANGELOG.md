# Changelog

All notable changes to the CCOP project will be documented in this file.

## [1.1.0] - 2026-02-20
### Added
- **5-Phase Ontology Architecture**: Redesigned the Graph database structure spanning Phase 1 (Basic mapping) through Phase 5 (Intelligent Semantic Analysis).
- **4-Layer Cognitive Model**: Separated Graph nodes dynamically into Case (L1) -> Actor (L2) -> Action (L3) -> Evidence (L4) for precise relationship tracking.
- **KICS Standardization**: Synchronized ontology models (16 Node Labels) and shortened attribute names (`actno`, `flnm`, `rrn`) targeting 100% compliance with Korea Information System of Criminal Justice Services.
- **Multi-hop Precision UI (Exact N-Hop)**: Revamped Cypher algorithms restricting exact target traversal on N-hop expansion avoiding Graph 'Hairball' effects.
- **AI-powered Automatic ETL Mapping**: Uploading raw CSV allows OpenAI to automatically map column relationships to standard Ontology Edge classifications.
- **Legal Context RAG System**: Integrated a ChromaDB vector datastore alongside GPT-4 generation resolving identical historic court cases based on visible graph combinations.
- **Partner Dashboard & API**: Added onboarding systems and Graph visualization tabs allowing administrative filtering and external integration tracking.

### Changed
- Refactored `graph_service.py` to extract pure Exact Graph connections without rendering non-related intermediate edges in multi-hop requests.
- Restructured `index.html` UI panels incorporating legend layers, unified Node Context Menus, Toast Notifications, and invisible intermediate Nodes rendering.
- Updated `docker-compose.yml` to inject robust PostgreSQL, AgensGraph, and ChromaDB integrations.

### Fixed
- Fixed bug referencing non-existent edge types defaulting unmapped nodes to `ag_edge` without fetching inner properties.
- Resolved "undefined" payload logic from Front-End when Graph expansions returned complex structures.
