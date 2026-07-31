"""
온톨로지 변환 및 시각화 테스트
- DB 연결 없이 순수 Python으로 실행 가능
- KICSCrimeDomainOntology, OntologyEnricher 검증
- 시각화용 데이터 구조 생성 검증

실행: pytest tests/test_ontology_transform_viz.py -v
빠른 실행: python tests/test_ontology_transform_viz.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.middleware.services.ontology_service import (
    KICSCrimeDomainOntology as Onto,
    OntologyEnricher,
)


# ─────────────────────────────────────────────────────────────
# 1. 온톨로지 정의 무결성 테스트
# ─────────────────────────────────────────────────────────────

class TestOntologyDefinition:
    """ONTOLOGY_FINAL_ARCHITECTURE.md §3 22노드, §4 엣지 카탈로그 일치 검증"""

    EXPECTED_NODE_LABELS = {
        'vt_src', 'vt_case', 'vt_petition',
        'vt_psn', 'vt_org',
        'vt_bacnt', 'vt_crypto', 'vt_ip', 'vt_site', 'vt_file',
        'vt_id', 'vt_email', 'vt_telno', 'vt_vhcl', 'vt_dev', 'vt_atm',
        'vt_loc',
        'vt_transfer', 'vt_call', 'vt_access', 'vt_msg', 'vt_movement',
        'vt_impersonation',   # V3.3 신설
        'pt_cluster', 'site_cluster',   # V3.7 신설 (군집 허브 노드: Case/Object 레이어)
    }

    EXPECTED_LAYERS = {'Source', 'Case', 'Person', 'Object', 'Location', 'Event'}

    def test_entity_count(self):
        """25개 엔티티 타입 정의 확인 (V3.7: pt_cluster/site_cluster 추가)"""
        count = len(Onto.ENTITIES)
        assert count == 25, f"엔티티 수 불일치: 기대 25개, 실제 {count}개"
        print(f"  ✅ 엔티티 수 정상: {count}개")

    def test_all_node_labels_defined(self):
        """GDB_LABEL_MAP이 23개 라벨을 모두 포함하는지 확인 (V3.3)"""
        defined_labels = set(Onto.GDB_LABEL_MAP.values())
        missing = self.EXPECTED_NODE_LABELS - defined_labels
        assert not missing, f"GDB_LABEL_MAP 누락 라벨: {missing}"
        print(f"  ✅ GDB_LABEL_MAP 23개 라벨 완전 등록")

    def test_concept_lookup_bidirectional(self):
        """GDB_LABEL_MAP ↔ CONCEPT_LOOKUP 양방향 일관성 확인 (V3.3 23개)"""
        for concept, label in Onto.GDB_LABEL_MAP.items():
            reverse = Onto.CONCEPT_LOOKUP.get(label)
            assert reverse == concept, (
                f"역매핑 불일치: {label} → {reverse} (기대: {concept})"
            )
        assert len(Onto.GDB_LABEL_MAP) == 25, f"GDB_LABEL_MAP 크기 불일치: {len(Onto.GDB_LABEL_MAP)}"
        print(f"  ✅ 양방향 매핑 일관성 정상 ({len(Onto.GDB_LABEL_MAP)}개)")

    def test_label_ko_map_coverage(self):
        """LABEL_KO_MAP이 23개 모든 GDB 라벨에 대한 한국어명을 가지는지 확인 (V3.3)"""
        missing = self.EXPECTED_NODE_LABELS - set(Onto.LABEL_KO_MAP.keys())
        assert not missing, f"LABEL_KO_MAP 누락 라벨: {missing}"
        assert Onto.LABEL_KO_MAP.get('vt_impersonation') == '사칭이벤트', "vt_impersonation 한국어명 오류"
        print(f"  ✅ LABEL_KO_MAP 한국어명 완전 등록 (23개)")

    def test_layers_completeness(self):
        """6개 레이어 존재 확인 및 모든 엔티티가 레이어에 속하는지 확인"""
        assert set(Onto.LAYERS.keys()) == self.EXPECTED_LAYERS, (
            f"레이어 불일치: {set(Onto.LAYERS.keys())}"
        )
        # LAYERS에 등록된 모든 개념명이 ENTITIES에 존재하는지
        for layer, concepts in Onto.LAYERS.items():
            for concept in concepts:
                assert concept in Onto.ENTITIES, (
                    f"LAYERS[{layer}].{concept}이 ENTITIES에 없음"
                )
        print(f"  ✅ 6개 레이어 정의 완전")

    def test_layers_gdb_coverage(self):
        """LAYERS_GDB가 22개 라벨을 모두 커버하는지 확인"""
        all_gdb = set()
        for labels in Onto.LAYERS_GDB.values():
            all_gdb.update(labels)
        missing = self.EXPECTED_NODE_LABELS - all_gdb
        assert not missing, f"LAYERS_GDB 누락 라벨: {missing}"
        extra = all_gdb - self.EXPECTED_NODE_LABELS
        assert not extra, f"LAYERS_GDB 미정의 라벨: {extra}"
        print(f"  ✅ LAYERS_GDB 22개 라벨 완전 커버")

    def test_relationship_required_fields(self):
        """모든 엣지 정의에 domain, range, label_ko, meaning 필드가 있는지 확인"""
        required_fields = {'domain', 'range', 'label_ko', 'meaning'}
        missing_fields = {}
        for rel_name, rel_def in Onto.RELATIONSHIPS.items():
            if rel_def.get('deprecated'):
                continue
            missing = required_fields - set(rel_def.keys())
            if missing:
                missing_fields[rel_name] = missing
        assert not missing_fields, f"엣지 정의 누락 필드:\n{json.dumps({k: list(v) for k, v in missing_fields.items()}, ensure_ascii=False, indent=2)}"
        print(f"  ✅ 엣지 정의 필수 필드 완전 ({len(Onto.RELATIONSHIPS)}개 엣지)")

    def test_inference_rules_count(self):
        """INFERENCE_RULES 통합 카탈로그 확인 (V4.2: 이원화 해소 — 단일 dict 13종)"""
        rules = Onto.INFERENCE_RULES
        assert isinstance(rules, dict), "INFERENCE_RULES는 SoT 단일 dict여야 함 (V4.2 이원화 해소)"
        assert len(rules) == 13, f"추론 규칙 수 불일치: 기대 13종, 실제 {len(rules)}종"
        detection = {n for n, r in rules.items() if r.get('rule_type') == 'detection'}
        enrichment = {n for n, r in rules.items() if r.get('rule_type') == 'enrichment'}
        assert len(detection) == 9, f"탐지 규칙 9종 기대, 실제 {len(detection)}종"
        assert len(enrichment) == 4, f"enrichment 규칙 4종 기대, 실제 {len(enrichment)}종"
        assert detection | enrichment == set(rules), "rule_type 미태깅 규칙 존재"
        for name, rule in rules.items():
            assert rule.get('rule_type') in ('detection', 'enrichment'), f"rule_type 오류: {name}"
            if rule['rule_type'] == 'detection':
                assert 'confidence' in rule, f"탐지 규칙 confidence 누락: {name}"
        # RelayStationDetection: 구 list(탐지)+구 V37(생성) 중복이 단일로 병합, 정보 무손실
        rs = rules['RelayStationDetection']
        assert rs['algorithm'] and rs['confidence'] and rs['output_edges'] == ['used_in_device']
        # 하위호환 뷰: INFERENCE_RULES_V37 == enrichment 부분집합 (기존 /ontology/meta API)
        assert set(Onto.INFERENCE_RULES_V37) == enrichment, "V37 하위호환 뷰 불일치"
        print(f"  ✅ 추론 규칙 통합 13종 (탐지 9 + enrichment 4), V37 뷰 정합")

    def test_label_alias_keyword_matching(self):
        """LABEL_ALIASES 스키마 pruning recall 보강 (arXiv 2505.05118 exact-match)"""
        node_labels = set(Onto.LABEL_KO_MAP.keys())
        alias_labels = set(Onto.LABEL_ALIASES.keys())
        assert alias_labels <= node_labels, f"별칭 사전에 미존재 라벨: {alias_labels - node_labels}"
        # 대표 질문 — router가 놓쳐도 키워드가 잡아야 (recall 보강)
        assert set(Onto.match_labels_by_keywords('계좌 이체 내역')) == {'vt_bacnt', 'vt_transfer'}
        assert 'vt_impersonation' in Onto.match_labels_by_keywords('기관 사칭 사건')
        assert Onto.match_labels_by_keywords('한국 수도는?') == []
        # valid_labels 교차 — 현재 그래프에 없는 라벨 제외 (precision 유지)
        assert Onto.match_labels_by_keywords('계좌 이체', valid_labels={'vt_bacnt'}) == ['vt_bacnt']
        # 빈/None 입력 안전
        assert Onto.match_labels_by_keywords('') == []
        assert Onto.match_labels_by_keywords(None) == []
        print(f"  ✅ LABEL_ALIASES {len(alias_labels)}종 · 키워드 매칭·교차·안전 정상")


# ─────────────────────────────────────────────────────────────
# 2. 온톨로지 변환(Enrichment) 테스트
# ─────────────────────────────────────────────────────────────

class TestOntologyEnrichment:
    """OntologyEnricher.enrich_node / enrich_edge 변환 결과 검증"""

    # (gdb_label, sample_properties, expected_type, expected_layer)
    NODE_TEST_CASES = [
        ('vt_src',      {'src_id': 'src-001', 'src_name': '더치트'},             'Source',   'Source'),
        ('vt_case',     {'flnm': '2026-CYBER-001', 'status': 'OPEN'},            'Case',     'Case'),
        ('vt_petition', {'petition_id': 'PET-001', 'rcpt_dt': '2026-01-01'},     'Case',     'Case'),
        ('vt_psn',      {'psn_id': 'psn-001', 'name': '홍길동'},                 'Person',   'Person'),
        ('vt_org',      {'org_id': 'org-001', 'org_name': '국민은행'},            'Person',   'Person'),
        ('vt_bacnt',    {'account_no': '110-1234', 'bank_cd': '004'},             'Object',   'Object'),
        ('vt_crypto',   {'wallet_addr': '1A2B3C', 'blockchain': 'BTC'},           'Object',   'Object'),
        ('vt_ip',       {'ip_addr': '192.168.1.1'},                               'Object',   'Object'),
        ('vt_site',     {'url_addr': 'http://phish.com'},                         'Object',   'Object'),
        ('vt_file',     {'hash_val': 'abc123', 'file_nm': 'malware.exe'},         'Object',   'Object'),
        ('vt_id',       {'id_val': 'user99', 'platform': 'Telegram'},             'Object',   'Object'),
        ('vt_email',    {'email_addr': 'test@naver.com'},                         'Object',   'Object'),
        ('vt_telno',    {'telno': '01012345678'},                                  'Object',   'Object'),
        ('vt_vhcl',     {'vhclno': '12가3456'},                                   'Object',   'Object'),
        ('vt_dev',      {'device_id': 'dev-001', 'imei': '354000000000001'},      'Object',   'Object'),
        ('vt_atm',      {'atm_id': 'ATM-001', 'bank_nm': 'KB국민은행'},           'Object',   'Object'),
        ('vt_loc',      {'loc_id': 'loc-001', 'loc_type': 'address'},             'Location', 'Location'),
        ('vt_transfer', {'event_id': 'evt-001', 'dlng_amt': 1000000},             'Event',    'Event'),
        ('vt_call',     {'event_id': 'call-001', 'call_strt_dt': '2026-01-01'},   'Event',    'Event'),
        ('vt_access',   {'access_id': 'lgn-001', 'access_dt': '2026-01-01'},      'Event',    'Event'),
        ('vt_msg',      {'event_id': 'msg-001', 'msg_type': 'SMS'},               'Event',    'Event'),
        ('vt_movement',     {'mov_id': 'mov-001', 'mov_type': 'lpr'},              'Event',    'Event'),
        ('vt_impersonation',{'event_id': 'imp-001', 'fake_name': '김민수 검사'},  'Event',    'Event'),  # V3.3
    ]

    def test_enrich_node_all_labels(self):
        """23개 모든 노드 라벨에 대한 enrich_node 변환 검증 (V3.3)"""
        errors = []
        for label, props, expected_type, expected_layer in self.NODE_TEST_CASES:
            result = OntologyEnricher.enrich_node(label, props)

            if result['ontology_type'] != expected_type:
                errors.append(
                    f"{label}: ontology_type={result['ontology_type']} (기대: {expected_type})"
                )
            if result['layer'] != expected_layer:
                errors.append(
                    f"{label}: layer={result['layer']} (기대: {expected_layer})"
                )
            if not result.get('kics_compliant'):
                errors.append(f"{label}: kics_compliant 미설정")
            if not result.get('domain_concept'):
                errors.append(f"{label}: domain_concept 누락")

        if errors:
            print("\n  ❌ enrich_node 변환 오류:")
            for e in errors:
                print(f"    - {e}")
        assert not errors, f"enrich_node 변환 오류 {len(errors)}건"
        print(f"  ✅ 23개 노드 라벨 enrich_node 변환 정상 (V3.3)")

    def test_enrich_node_preserves_original_props(self):
        """enrich_node가 원본 속성을 보존하는지 확인"""
        props = {'account_no': '110-1234', 'bank_cd': '004', 'is_burner': True}
        result = OntologyEnricher.enrich_node('vt_bacnt', props)
        assert result['account_no'] == '110-1234', "원본 속성 account_no 손실"
        assert result['bank_cd'] == '004', "원본 속성 bank_cd 손실"
        assert result['is_burner'] is True, "원본 속성 is_burner 손실"
        print("  ✅ enrich_node 원본 속성 보존 정상")

    def test_enrich_node_unknown_label_fallback(self):
        """알 수 없는 라벨에 대한 속성 기반 fallback 동작 확인"""
        # 라벨 없음, account_no 속성으로 fallback
        result = OntologyEnricher.enrich_node(None, {'account_no': '110-0000', 'bank_cd': '002'})
        assert result['entity_subtype'] == 'BankAccount', (
            f"fallback 실패: {result['entity_subtype']}"
        )
        print("  ✅ enrich_node 알 수 없는 라벨 fallback 정상")

    def test_enrich_edge_core_types(self):
        """핵심 엣지 타입 enrich_edge 변환 검증 (V3.3 신규 엣지 포함)"""
        test_edges = [
            ('suspect_in',     '피의자로 관련된 사건',    '피의자정보'),
            ('has_account',    '계좌 보유',               '금융거래정보'),
            ('from_account',   '출금 계좌',               '금융거래정보'),
            ('contacted',      '연락',                   '통신사실확인자료'),
            ('impersonates',   '사칭 대상(구)',            '사기범죄'),        # deprecated 처리 확인
            ('accomplice_of',  '공범 관계',               '공모사실'),
            ('used_for',       '사칭 수단',               '전기통신금융사기법 제3조'),   # V3.3
            ('targets',        '사칭 대상 기관',           '전기통신금융사기법 제3조'),   # V3.3
        ]
        for edge_type, expected_meaning, expected_legal in test_edges:
            result = OntologyEnricher.enrich_edge(edge_type, {})
            assert result['domain_meaning'] == expected_meaning, (
                f"{edge_type}: domain_meaning={result['domain_meaning']} (기대: {expected_meaning})"
            )
            assert result['legal_significance'] == expected_legal, (
                f"{edge_type}: legal_significance={result['legal_significance']} (기대: {expected_legal})"
            )
            assert result['kics_compliant'] is True
        print(f"  ✅ 핵심 엣지 {len(test_edges)}개 enrich_edge 변환 정상 (V3.3 포함)")

    def test_enrich_edge_preserves_props(self):
        """enrich_edge가 원본 속성을 보존하는지 확인"""
        props = {'confidence': 0.9, 'verified': True, 'source_id': 'src-001'}
        result = OntologyEnricher.enrich_edge('has_account', props)
        assert result['confidence'] == 0.9
        assert result['verified'] is True
        assert result['source_id'] == 'src-001'
        print("  ✅ enrich_edge 원본 속성 보존 정상")


# ─────────────────────────────────────────────────────────────
# 3. 유틸리티 메서드 테스트
# ─────────────────────────────────────────────────────────────

class TestOntologyUtils:
    """get_gdb_label, get_concept_name, get_label_ko 검증"""

    def test_get_gdb_label(self):
        """개념명 → GDB 라벨 변환"""
        assert Onto.get_gdb_label('Person') == 'vt_psn'
        assert Onto.get_gdb_label('BankAccount') == 'vt_bacnt'
        assert Onto.get_gdb_label('Transfer') == 'vt_transfer'
        assert Onto.get_gdb_label('Location') == 'vt_loc'
        assert Onto.get_gdb_label('UNKNOWN') == 'UNKNOWN'  # 미등록 → 원값 반환
        print("  ✅ get_gdb_label 정상")

    def test_get_concept_name(self):
        """GDB 라벨 → 개념명 변환"""
        assert Onto.get_concept_name('vt_psn') == 'Person'
        assert Onto.get_concept_name('vt_bacnt') == 'BankAccount'
        assert Onto.get_concept_name('vt_transfer') == 'Transfer'
        assert Onto.get_concept_name('vt_movement') == 'Movement'
        assert Onto.get_concept_name('no_such') == 'no_such'
        print("  ✅ get_concept_name 정상")

    def test_get_label_ko(self):
        """GDB 라벨 → 한국어명 변환"""
        assert Onto.get_label_ko('vt_psn') == '인물'
        assert Onto.get_label_ko('vt_bacnt') == '계좌'
        assert Onto.get_label_ko('vt_transfer') == '이체'
        assert Onto.get_label_ko('vt_src') == '소스'
        print("  ✅ get_label_ko 정상")

    def test_get_relationship_rules(self):
        """LLM 추론용 관계 규칙 반환 확인"""
        rules = Onto.get_relationship_rules()
        assert isinstance(rules, dict)
        assert len(rules) > 0
        # 튜플 키 형태 확인
        for key, val in rules.items():
            assert isinstance(key, tuple), f"규칙 키가 튜플이 아님: {key}"
            assert 'type' in val
            assert 'description' in val
        print(f"  ✅ get_relationship_rules {len(rules)}개 규칙 반환 정상")


# ─────────────────────────────────────────────────────────────
# 4. 시각화 데이터 구조 생성 테스트
# ─────────────────────────────────────────────────────────────

class TestVisualizationDataStructure:
    """온톨로지를 시각화 가능한 데이터 구조로 변환하는 기능 검증"""

    def _build_ontology_graph(self):
        """
        온톨로지 정의를 Cytoscape.js / D3.js 형태의 elements 배열로 변환.
        각 엔티티 → 노드, 각 관계 → 엣지.
        """
        nodes = []
        edges = []

        # 레이어별 색상
        layer_colors = {
            'Source':   '#9b59b6',
            'Case':     '#e74c3c',
            'Person':   '#3498db',
            'Object':   '#2ecc71',
            'Location': '#f39c12',
            'Event':    '#1abc9c',
        }

        # 노드 생성 (각 ENTITY)
        for concept_name, entity in Onto.ENTITIES.items():
            gdb_label = entity['label']
            layer = entity['layer']
            nodes.append({
                'group': 'nodes',
                'data': {
                    'id': gdb_label,
                    'label': Onto.get_label_ko(gdb_label),
                    'concept': concept_name,
                    'layer': layer,
                    'color': layer_colors.get(layer, '#bdc3c7'),
                    'legal_category': entity.get('legal_category', ''),
                    'properties': entity.get('properties', []),
                },
            })

        # 엣지 생성 (비Deprecated 관계만)
        edge_id = 0
        for rel_name, rel_def in Onto.RELATIONSHIPS.items():
            if rel_def.get('deprecated'):
                continue
            domain = rel_def['domain']
            range_ = rel_def['range']
            # 'Any' 타입 스킵 (시각화 불가)
            if domain == 'Any' or range_ == 'Any':
                continue
            src_label = Onto.GDB_LABEL_MAP.get(domain)
            tgt_label = Onto.GDB_LABEL_MAP.get(range_)
            if not src_label or not tgt_label:
                continue
            edges.append({
                'group': 'edges',
                'data': {
                    'id': f'rel-{edge_id}',
                    'source': src_label,
                    'target': tgt_label,
                    'label': rel_def.get('label_ko', rel_name),
                    'rel_type': rel_name,
                    'legal_significance': rel_def.get('legal_significance', ''),
                    'inferred': rel_def.get('inferred', False),
                },
            })
            edge_id += 1

        return nodes + edges

    def test_ontology_graph_node_count(self):
        """시각화 그래프 노드 수 = 25개 (V3.7: pt_cluster/site_cluster 포함)"""
        elements = self._build_ontology_graph()
        node_count = sum(1 for e in elements if e['group'] == 'nodes')
        assert node_count == 25, f"시각화 노드 수 불일치: {node_count}"
        print(f"  ✅ 시각화 노드 25개 생성 정상 (V3.7)")

    def test_ontology_graph_edge_minimum(self):
        """시각화 그래프 엣지 수 >= 20개 (유효 관계)"""
        elements = self._build_ontology_graph()
        edge_count = sum(1 for e in elements if e['group'] == 'edges')
        assert edge_count >= 20, f"시각화 엣지 수 부족: {edge_count}"
        print(f"  ✅ 시각화 엣지 {edge_count}개 생성 정상")

    def test_ontology_graph_required_fields(self):
        """모든 시각화 노드/엣지에 필수 필드 존재 확인"""
        elements = self._build_ontology_graph()
        for elem in elements:
            assert 'group' in elem
            assert 'data' in elem
            assert 'id' in elem['data']
            if elem['group'] == 'nodes':
                assert 'label' in elem['data']
                assert 'layer' in elem['data']
            else:
                assert 'source' in elem['data']
                assert 'target' in elem['data']
                assert 'rel_type' in elem['data']
        print(f"  ✅ 시각화 elements 필수 필드 검증 정상")

    def test_layer_summary(self):
        """레이어별 노드 수 집계 → 대시보드용 요약 구조 생성"""
        summary = {}
        for layer, gdb_labels in Onto.LAYERS_GDB.items():
            summary[layer] = {
                'count': len(gdb_labels),
                'labels': gdb_labels,
                'labels_ko': [Onto.get_label_ko(l) for l in gdb_labels],
            }

        assert summary['Source']['count'] == 1
        assert summary['Case']['count'] == 3      # V3.7: pt_cluster 추가 (2→3)
        assert summary['Person']['count'] == 2
        assert summary['Object']['count'] == 12   # V3.7: site_cluster 추가 (11→12)
        assert summary['Location']['count'] == 1
        assert summary['Event']['count'] == 6, \
            f"Event 레이어 노드 수 불일치: {summary['Event']['count']} (V3.3: vt_impersonation 포함 6개)"

        total = sum(v['count'] for v in summary.values())
        assert total == 25, f"레이어 요약 총합 불일치: {total} (V3.7: 25개)"
        assert 'vt_impersonation' in summary['Event']['labels'], "vt_impersonation이 Event 레이어에 없음"
        print(f"  ✅ 레이어 요약 정상: {json.dumps({k: v['count'] for k, v in summary.items()})}")

    def test_schema_api_payload(self):
        """/api/v1/schema/layers 엔드포인트 응답 구조 모사 (V3.3)"""
        # routes_api.py의 get_schema_layers 로직과 동일하게 구성
        entities = {}
        for name, info in Onto.ENTITIES.items():
            entities[name] = {
                'layer': info.get('layer', 'Unknown'),
                'label': info.get('label', ''),
                'label_ko': info.get('label_ko', ''),
                'legal_category': info.get('legal_category', ''),
            }

        relationships = {}
        for name, info in Onto.RELATIONSHIPS.items():
            relationships[name] = {
                'domain': info.get('domain', ''),
                'range': info.get('range', ''),
                'label_ko': info.get('label_ko', ''),
                'legal_significance': info.get('legal_significance', ''),
            }

        payload = {
            'layers': Onto.LAYERS,
            'entities': entities,
            'relationships': relationships,
            'entity_count': len(entities),
            'relationship_count': len(relationships),
        }

        assert payload['entity_count'] == 25, f"entity_count 불일치: {payload['entity_count']} (V3.7: 25)"
        assert payload['relationship_count'] == len(Onto.RELATIONSHIPS)
        assert 'Source' in payload['layers']
        # JSON 직렬화 가능 여부 확인
        json_str = json.dumps(payload, ensure_ascii=False)
        assert len(json_str) > 0
        print(f"  ✅ schema/layers API 페이로드 구조 정상 (엔티티: {payload['entity_count']}, 관계: {payload['relationship_count']})")


# ─────────────────────────────────────────────────────────────
# 5. COLUMN_PATTERNS 매핑 테스트
# ─────────────────────────────────────────────────────────────

class TestColumnPatterns:
    """CSV 컬럼 → KICS 온톨로지 매핑 검증"""

    COLUMN_TEST_CASES = [
        ('계좌번호',      'account',  'vt_bacnt',    'account_no'),
        ('전화번호',      'phone',    'vt_telno',    'telno'),
        ('ip주소',        'ip',       'vt_ip',       'ip_addr'),
        ('사건번호',      'case',     'vt_case',     'flnm'),
        ('이메일',        'email',    'vt_email',    'email_addr'),
        ('차량번호',      'vehicle',  'vt_vhcl',     'vhclno'),
        ('wallet_addr',  'crypto',   'vt_crypto',   'wallet_addr'),
        ('닉네임',        'nickname', 'vt_id',       'id_val'),
    ]

    def _match_column(self, col_name):
        """COLUMN_PATTERNS 패턴 매칭 (대소문자 무시)"""
        col_lower = col_name.lower()
        for pattern_key, pattern_def in Onto.COLUMN_PATTERNS.items():
            for p in pattern_def['patterns']:
                if p.lower() in col_lower or col_lower in p.lower():
                    return pattern_key, pattern_def
        return None, None

    def test_column_pattern_matching(self):
        """주요 컬럼명 → 온톨로지 패턴 매칭 확인"""
        errors = []
        for col_name, expected_key, expected_label, expected_prop in self.COLUMN_TEST_CASES:
            matched_key, matched_def = self._match_column(col_name)
            if matched_key != expected_key:
                errors.append(
                    f"'{col_name}' → 매칭 키 {matched_key} (기대: {expected_key})"
                )
                continue
            if matched_def['kics_label'] != expected_label:
                errors.append(
                    f"'{col_name}' → kics_label {matched_def['kics_label']} (기대: {expected_label})"
                )
            if matched_def['kics_property'] != expected_prop:
                errors.append(
                    f"'{col_name}' → kics_property {matched_def['kics_property']} (기대: {expected_prop})"
                )
        assert not errors, "컬럼 패턴 매칭 오류:\n" + "\n".join(errors)
        print(f"  ✅ 컬럼 패턴 매칭 {len(self.COLUMN_TEST_CASES)}개 정상")

    def test_column_patterns_all_have_description(self):
        """모든 COLUMN_PATTERNS에 description 필드가 있는지 확인"""
        missing = [k for k, v in Onto.COLUMN_PATTERNS.items() if 'description' not in v]
        assert not missing, f"description 누락 패턴: {missing}"
        print(f"  ✅ COLUMN_PATTERNS description 완전 등록")


# ─────────────────────────────────────────────────────────────
# 직접 실행 (pytest 없이)
# ─────────────────────────────────────────────────────────────

def run_all():
    test_classes = [
        TestOntologyDefinition,
        TestOntologyEnrichment,
        TestOntologyUtils,
        TestVisualizationDataStructure,
        TestColumnPatterns,
    ]

    total = passed = failed = 0

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith('test_')]
        print(f"\n{'─'*60}")
        print(f"[{cls.__name__}]")
        for method_name in methods:
            total += 1
            try:
                print(f"  {method_name} ...", end=' ')
                getattr(instance, method_name)()
                passed += 1
            except AssertionError as e:
                failed += 1
                print(f"\n  ❌ FAILED: {e}")
            except Exception as e:
                failed += 1
                print(f"\n  ❌ ERROR: {type(e).__name__}: {e}")

    print(f"\n{'='*60}")
    print(f"결과: {passed}/{total} 통과 | 실패: {failed}")
    return failed == 0


if __name__ == '__main__':
    success = run_all()
    sys.exit(0 if success else 1)
