"""
온톨로지 기반 그래프 분석 서비스

KICS (Korean Investigation Computer System) 기반 사이버 범죄 수사 온톨로지
"""

class KICSCrimeDomainOntology:
    """KICS 기반 한국형 사이버 범죄 온톨로지"""
    
    # 엔티티 계층 (Entity Hierarchy)
    ENTITIES = {
        # === 중심 엔티티 ===
        'Case': {
            'label_ko': '사건',
            'properties': ['flnm', 'receipt_no'],
            'attributes': ['police_station', 'investigator', 'crime_type', 
                          'damage_amount', 'case_summary'],
            'role': 'anchor',
            'description': '수사 사건 케이스'
        },
        
        # === 용의자 정보 ===
        'Suspect': {
            'label_ko': '용의자',
            'properties': ['name', 'suspect_id'],
            'role': 'person',
            'description': '피의자/용의자 정보'
        },
        
        'ContactInfo': {
            'label_ko': '연락처',
            'parent': 'Suspect',
            'properties': ['telno', 'phone'],
            'attributes': ['telecom_provider'],
            'legal_category': '통신사실확인자료'
        },
        
        # === 금융 증거 ===
        'BankAccount': {
            'label_ko': '계좌',
            'parent': 'FinancialEvidence',
            'properties': ['actno', 'bacnt', 'account_no'],
            'attributes': ['bank', 'account_holder'],
            'legal_category': '금융거래정보'
        },
        
        'CryptoWallet': {
            'label_ko': '가상자산',
            'parent': 'FinancialEvidence', 
            'properties': ['wallet_addr', 'crypto_addr'],
            'attributes': ['asset_type', 'exchange_type'],
            'legal_category': '가상자산거래정보'
        },
        
        # === 디지털 증거 ===
        'NetworkTrace': {
            'label_ko': 'IP주소',
            'parent': 'DigitalEvidence',
            'properties': ['ip', 'ip_addr'],
            'attributes': ['isp', 'location'],
            'legal_category': '통신자료'
        },
        
        'WebTrace': {
            'label_ko': '사이트',
            'parent': 'DigitalEvidence',
            'properties': ['url', 'site', 'domain'],
            'attributes': ['site_type'],
            'legal_category': '인터넷기록'
        },
        
        'FileTrace': {
            'label_ko': '파일',
            'parent': 'DigitalEvidence',
            'properties': ['file', 'filename', 'filepath'],
            'attributes': ['file_type', 'file_size'],
            'legal_category': '디지털증거'
        },
        
        # === 물리 증거 ===
        'ATM': {
            'label_ko': 'ATM',
            'parent': 'PhysicalEvidence',
            'properties': ['atm', 'atm_id'],
            'attributes': ['location', 'bank'],
            'legal_category': '물리증거'
        }
    }
    
    # 관계 시맨틱 (Relationship Semantics)
    RELATIONSHIPS = {
        'digital_trace': {
            'domain': 'Case',
            'range': 'DigitalEvidence',
            'semantic_relation': 'investigatesDigitalTrace',
            'label_ko': '디지털흔적',
            'meaning': '사건에서 디지털 흔적을 조사함',
            'legal_significance': '디지털증거'
        },
        'used_account': {
            'domain': 'Case',
            'range': 'BankAccount',
            'semantic_relation': 'usedFinancialResource',
            'label_ko': '계좌사용',
            'meaning': '사건에서 계좌를 사용함',
            'legal_significance': '금융거래정보'
        },
        'used_crypto': {
            'domain': 'Case',
            'range': 'CryptoWallet',
            'semantic_relation': 'usedCryptoAsset',
            'label_ko': '가상자산사용',
            'meaning': '사건에서 가상자산을 사용함',
            'legal_significance': '가상자산거래정보'
        },
        'used_phone': {
            'domain': 'Case',
            'range': 'ContactInfo',
            'semantic_relation': 'usedCommunicationDevice',
            'label_ko': '전화사용',
            'meaning': '사건에서 전화번호를 사용함',
            'legal_significance': '통신사실확인자료'
        },
        'accessed_ip': {
            'domain': 'Case',
            'range': 'NetworkTrace',
            'semantic_relation': 'accessedFromIP',
            'label_ko': 'IP접속',
            'meaning': 'IP주소에서 접속함',
            'legal_significance': '통신자료'
        },
        'visited_site': {
            'domain': 'Case',
            'range': 'WebTrace',
            'semantic_relation': 'visitedWebsite',
            'label_ko': '사이트방문',
            'meaning': '사이트를 방문함',
            'legal_significance': '인터넷기록'
        }
    }
    
    # 추론 규칙 (KICS-Specific Inference Rules)
    INFERENCE_RULES = [
        {
            'name': 'OrganizedCrime',
            'pattern': 'shared_resource_usage',
            'threshold': 3,
            'description': '동일 전화번호가 3건 이상 사건에서 사용 → 조직범죄 가능',
            'confidence': 0.80,
            'legal_basis': '범죄수익은닉규제법'
        },
        {
            'name': 'MoneyLaundering',
            'pattern': 'multi_hop_transfer',
            'threshold': 3,
            'description': '3단계 이상 계좌이체 → 자금세탁 의심',
            'confidence': 0.75,
            'legal_basis': '특정금융거래정보법'
        }
    ]


class OntologyEnricher:
    """ETL 시 KICS 온톨로지 메타데이터 추가"""
    
    @staticmethod
    def enrich_node(node_label, properties):
        """KICS 기반 온톨로지 매핑"""
        ontology_type = "Unknown"
        entity_subtype = None
        domain_concept = "알 수 없음"
        legal_category = None
        
        # === 사건 (Case) ===
        if 'flnm' in properties or 'receipt_no' in properties:
            ontology_type = "Case"
            entity_subtype = "Case"
            domain_concept = "사건"
            legal_category = "수사사건"
        
        # === 금융증거 (Financial Evidence) ===
        elif 'actno' in properties or 'bacnt' in properties or 'account_no' in properties:
            ontology_type = "FinancialEvidence"
            entity_subtype = "BankAccount"
            domain_concept = "계좌"
            legal_category = "금융거래정보"
        
        elif 'wallet_addr' in properties or 'crypto_addr' in properties:
            ontology_type = "FinancialEvidence"
            entity_subtype = "CryptoWallet"
            domain_concept = "가상자산"
            legal_category = "가상자산거래정보"
        
        # === 디지털증거 (Digital Evidence) ===
        elif 'ip' in properties or 'ip_addr' in properties or 'ipaddr' in properties:
            ontology_type = "DigitalEvidence"
            entity_subtype = "NetworkTrace"
            domain_concept = "IP주소"
            legal_category = "통신자료"
        
        elif 'url' in properties or 'site' in properties or 'domain' in properties:
            ontology_type = "DigitalEvidence"
            entity_subtype = "WebTrace"
            domain_concept = "사이트"
            legal_category = "인터넷기록"
        
        elif 'file' in properties or 'filename' in properties or 'filepath' in properties:
            ontology_type = "DigitalEvidence"
            entity_subtype = "FileTrace"
            domain_concept = "파일"
            legal_category = "디지털증거"
        
        # === 용의자/연락처 (Suspect) ===
        elif 'telno' in properties or 'phone' in properties:
            ontology_type = "Suspect"
            entity_subtype = "ContactInfo"
            domain_concept = "전화번호"
            legal_category = "통신사실확인자료"
        
        elif 'name' in properties or 'suspect' in properties:
            ontology_type = "Suspect"
            entity_subtype = "Suspect"
            domain_concept = "용의자"
            legal_category = "피의자정보"
        
        elif 'id' in properties or 'user_id' in properties or 'nickname' in properties:
            ontology_type = "Suspect"
            entity_subtype = "DigitalIdentity"
            domain_concept = "디지털ID"
            legal_category = "인터넷기록"
        
        # === 물리증거 (Physical Evidence) ===
        elif 'atm' in properties or 'atm_id' in properties:
            ontology_type = "PhysicalEvidence"
            entity_subtype = "ATM"
            domain_concept = "ATM"
            legal_category = "물리증거"
        
        # 메타데이터 추가
        enriched_props = properties.copy()
        enriched_props['ontology_type'] = ontology_type
        enriched_props['entity_subtype'] = entity_subtype if entity_subtype else ontology_type
        enriched_props['domain_concept'] = domain_concept
        enriched_props['legal_category'] = legal_category
        enriched_props['kics_compliant'] = True
        
        return enriched_props
    
    @staticmethod
    def enrich_edge(edge_type, properties):
        """KICS 기반 엣지 온톨로지 매핑"""
        semantic_relation = edge_type
        domain_meaning = edge_type
        legal_significance = None
        
        # KICS 엣지 타입별 의미론적 관계 매핑
        EDGE_SEMANTICS = {
            'digital_trace': {
                'semantic_relation': 'investigatesDigitalTrace',
                'domain_meaning': '디지털 흔적 조사',
                'legal_significance': '디지털증거'
            },
            'used_account': {
                'semantic_relation': 'usedFinancialResource',
                'domain_meaning': '금융 계좌 사용',
                'legal_significance': '금융거래정보'
            },
            'used_crypto': {
                'semantic_relation': 'usedCryptoAsset',
                'domain_meaning': '가상자산 사용',
                'legal_significance': '가상자산거래정보'
            },
            'used_phone': {
                'semantic_relation': 'usedCommunicationDevice',
                'domain_meaning': '전화번호 사용',
                'legal_significance': '통신사실확인자료'
            },
            'accessed_ip': {
                'semantic_relation': 'accessedFromIP',
                'domain_meaning': 'IP 접속',
                'legal_significance': '통신자료'
            },
            'visited_site': {
                'semantic_relation': 'visitedWebsite',
                'domain_meaning': '사이트 방문',
                'legal_significance': '인터넷기록'
            }
        }
        
        if edge_type in EDGE_SEMANTICS:
            semantic_relation = EDGE_SEMANTICS[edge_type]['semantic_relation']
            domain_meaning = EDGE_SEMANTICS[edge_type]['domain_meaning']
            legal_significance = EDGE_SEMANTICS[edge_type]['legal_significance']
        
        # 메타데이터 추가
        enriched_props = properties.copy()
        enriched_props['semantic_relation'] = semantic_relation
        enriched_props['domain_meaning'] = domain_meaning
        if legal_significance:
            enriched_props['legal_significance'] = legal_significance
        enriched_props['kics_compliant'] = True
        
        return enriched_props


class SemanticAnalyzer:
    """그래프 패턴의 의미론적 해석"""
    
    @staticmethod
    def analyze(elements, context_texts):
        """온톨로지 기반 분석"""
        
        # 1. 개념 분류
        concepts = SemanticAnalyzer._classify_concepts(elements)
        
        # 2. 관계 해석
        relationships = SemanticAnalyzer._interpret_relationships(elements)
        
        # 3. 패턴 탐지
        patterns = SemanticAnalyzer._detect_patterns(elements, concepts)
        
        return {
            'concepts': concepts,
            'relationships': relationships,
            'patterns': patterns,
            'summary': SemanticAnalyzer._generate_summary(concepts, relationships, patterns)
        }
    
    @staticmethod
    def _classify_concepts(elements):
        """노드를 도메인 개념으로 분류"""
        concepts = {}
        concept_counts = {}
        
        for elem in elements:
            if elem['group'] == 'nodes':
                node_id = elem['data']['id']
                props = elem['data'].get('props', {})
                
                # 온톨로지 매핑
                concept = 'Unknown'
                if 'flnm' in props:
                    concept = 'Case'
                elif 'telno' in props or 'phone' in props:
                    concept = 'Suspect'
                elif 'file' in props or 'site' in props or 'url' in props or 'ip' in props:
                    concept = 'DigitalEvidence'
                elif 'actno' in props or 'bacnt' in props or 'account' in props:
                    concept = 'FinancialEvidence'
                
                concepts[node_id] = concept
                concept_counts[concept] = concept_counts.get(concept, 0) + 1
        
        return {
            'mapping': concepts,
            'counts': concept_counts
        }
    
    @staticmethod
    def _interpret_relationships(elements):
        """관계의 의미 해석"""
        relationships = []
        
        for elem in elements:
            if elem['group'] == 'edges':
                edge_type = elem['data'].get('label', 'unknown')
                edge_props = elem['data'].get('props', {})
                
                if edge_type in KICSCrimeDomainOntology.RELATIONSHIPS:
                    rel_info = KICSCrimeDomainOntology.RELATIONSHIPS[edge_type]
                    
                    interpretation = {
                        'type': edge_type,
                        'meaning': rel_info['meaning'],
                        'properties': {k: v for k, v in edge_props.items() 
                                      if k not in ['source', 'updated']}
                    }
                    relationships.append(interpretation)
        
        return relationships
    
    @staticmethod
    def _detect_patterns(elements, concepts):
        """의미 있는 그래프 패턴 탐지"""
        patterns = []
        
        # 패턴 1: 공유 리소스 (동일 전화번호/계좌를 여러 사건에서 사용)
        resource_usage = {}  # {resource_id: [case_ids]}
        
        for elem in elements:
            if elem['group'] == 'edges':
                source = elem['data']['source']
                target = elem['data']['target']
                
                # Case -> Resource 패턴
                if concepts['mapping'].get(source) == 'Case':
                    resource = target
                    if resource not in resource_usage:
                        resource_usage[resource] = []
                    resource_usage[resource].append(source)
        
        # 복수 사용 리소스 탐지
        for resource, cases in resource_usage.items():
            if len(cases) > 1:
                resource_concept = concepts['mapping'].get(resource, 'Unknown')
                patterns.append({
                    'type': 'SharedResource',
                    'resource': resource,
                    'resource_type': resource_concept,
                    'cases': cases,
                    'count': len(cases),
                    'implication': f'{len(cases)}개 사건에서 동일 {resource_concept} 사용 - 조직 범죄 또는 연관 사건 가능성'
                })
        
        return patterns
    
    @staticmethod
    def _generate_summary(concepts, relationships, patterns):
        """분석 요약 생성"""
        summary_lines = []
        
        # 개념 요약
        if concepts['counts']:
            summary_lines.append("[엔티티 분류]")
            for concept, count in concepts['counts'].items():
                if concept != 'Unknown':
                    label = KICSCrimeDomainOntology.ENTITIES.get(concept, {}).get('label_ko', concept)
                    summary_lines.append(f"- {label}: {count}개")
        
        # 관계 요약
        if relationships:
            summary_lines.append("\n[관계 분석]")
            rel_types = {}
            for rel in relationships:
                rel_type = rel['type']
                if rel_type not in rel_types:
                    rel_types[rel_type] = []
                rel_types[rel_type].append(rel)
            
            for rel_type, rels in rel_types.items():
                meaning = KICSCrimeDomainOntology.RELATIONSHIPS.get(rel_type, {}).get('meaning', rel_type)
                summary_lines.append(f"- {meaning}: {len(rels)}건")
        
        # 패턴 요약
        if patterns:
            summary_lines.append("\n[탐지된 패턴]")
            for pattern in patterns:
                summary_lines.append(f"- {pattern['implication']}")
        
        return "\n".join(summary_lines)
