"""
온톨로지 기반 그래프 분석 서비스

CCOP V4.7 온톨로지 — POLE 정렬 6레이어 아키텍처 (현행 SSOT)
현행 설계 기준: docs/CCOP_ONTOLOGY_V4.1.md (+ 상세: ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md)
버전 이력:
  - v3.7: pt_cluster/site_cluster 노드(군집 허브 패턴), is_anonymous, used_in_device,
          clusters_with deprecated, RelayStationDetection 추론 규칙
  - V4.0: DOMAIN_USAGE·NODE_ID_STANDARD·INFERENCE_RULES_V37 메타를 SSOT로 격상
  - V4.1 (2026-07-31 정합화): 엣지 의미(RELATIONSHIPS)↔시각(EDGE_STYLE_V40) 이원화 해소
          — 실사용되나 카탈로그 한쪽에만 있던 엣지 등재(53 명목→60 실측), id 표준을 실 MERGE 키로 정정
  - V4.2 (2026-07-31 정합화): 추론 규칙 이원화 해소 — 구 INFERENCE_RULES(list 10)와
          INFERENCE_RULES_V37(dict 4)의 RelayStationDetection 중복을 단일 dict로 병합(13종).
          rule_type(detection/enrichment)으로 목적 구분, V37은 enrichment 하위호환 뷰.
  - V4.3 (2026-08-03): 시나리오 기반 직접 엣지 3종 추가(knows·linked_id·mentions_id) +
          sameAs range를 DigitalID까지 확장(유사 계정 해소). 엣지 60→63.
  - V4.4 (2026-08-03): 시나리오 reification 확장 — 이벤트 참여 엣지 3종(access_via·via_ip·
          mentions_location) + 금융/메시지 다형화(from/to_account·sent/received_msg·transferred_to). 엣지 63→66.
  - V4.5 (2026-08-06): ccop-analysis 번들(2차년도 실적재 검증) 대조 — 신규 엣지 5종
          (sent_from_ip·exchanged_to·linked_petition·eg_used_id·eg_used_email) + 확장 5종
          (accessed_to·used_ip·performed_by·linked_id·sameAs domain/range). 엣지 66→71.
          + 노드속성: edge_id(R7, EDGE_META) · 파생속성 등록부(R6, DERIVED_PROPERTY_REGISTRY —
          ip_role G12·aggregation_level G9 등 9종). R8(vt_access 서브타입)은 검토 보류.
  - V4.6 (2026-08-13): 시간축 bitemporal 정착 — used_ip/has_account/owns_phone valid_from·valid_to(E형),
          ip_role bitemporal 재설계(ip_role_current/timeline S1), 지연확장(aggregation_level #2),
          R8 vt_access 서브타입(access_type web|comm|banking) 확정, transferred_to 이체시각 기간집계.
  - V4.7 (2026-08-13): 수사단서 스키마 + 표준 DDL 정합 — represents 엣지(vt_psn→vt_org 법인대표,
          TB_INST_RPRSV_REL_T) + vt_psn.occp_nm(직업, TB_PSN_M.CR_NM) 신설. 표준 컬럼매핑 std_columns
          정착(RPRSV·CR_NM·CALL_HR 시분초변환·VLD_BGNG_DT/VLD_END_DT). 엣지 71→72.
  - V4.8 (2026-09-02): 2차년도 EP1~8 실적재 전수감사(docs/EP1_EP8_V47_AUDIT_20260902.md) 반영 —
          도메인 확장 3종: ① contacted Phone|DigitalID↔Phone|DigitalID(카톡 대화상대 4,107건,
          channel 속성 신설) ② registered_to domain+DigitalID(네이버 실명확인 가입자 1,914건 —
          uses_id '사용자'와 registered_to '명의자' 구분이 대포계정 표현의 핵심이라 대체 아닌 확장)
          ③ used_ip domain+BankAccount(계좌 인터넷뱅킹 접속 IP; 시각 레코드 있으면 R8 vt_access
          reification 우선). + sameAs→same_as 개명(AgensGraph 미인용 식별자 소문자화로 DB 실현명이
          'sameas'가 되던 문제 — snake_case 전면 통일, DB 4건 마이그레이션). 엣지 수 불변(72).
노드: 25 | 엣지: 72 (활성 70 + deprecated 2: clusters_with·owns_device) | 추론 규칙: 13종 통합 dict (탐지 9 + enrichment 4)
"""

class KICSCrimeDomainOntology:
    """KICS 기반 한국형 사이버 범죄 온톨로지 (V4.8 POLE 6레이어 · 72종 엣지[활성 70] · 추론규칙 13종)"""

    # 엣지 공통 메타속성 스키마 (EDGE_META_SCHEMA)
    EDGE_META_SCHEMA = {
        # ══ 필수 (모든 엣지) ══════════════════════════════════════
        'edge_id':         str,    # 전 엣지 공통 안정 ID — evidence_edge_ids 가 참조 (V4.5 R7)
        'source_id':       str,    # vt_src.src_id 참조 (MANDATORY)
        'rec_created':     str,    # ISO8601 — DB 기록 시점 (MANDATORY)
        'creation_method': str,    # 'manual' | 'etl' | 'ocr_ner' | 'osint' | 'inference'
        # ══ 신뢰도 (소유·귀속 엣지에 적용) ══════════════════════
        'confidence':      float,  # 0.0~1.0 (1.0 = 공식 문서)
        'credibility':     int,    # 1~5 (GraphAware 기준)
        'verified':        bool,   # False=주장, True=수사관·공식문서 확인
        # ══ 이중시간 (소유·관계 엣지에 적용) ════════════════════
        'valid_from':      str,    # 현실에서 유효 시작 (ISO8601)
        'valid_to':        str,    # 현실에서 유효 종료 (null=현재진행)
        # ══ 검증 정보 (verified=True 시 필수) ════════════════════
        'verified_by':     str,    # 수사관 ID
        'verified_at':     str,    # 검증 일시
    }

    # ══════════════════════════════════════════════════════════════════════════
    # 식별자 형식 표준 (V3.7 통합 표준화) - id_format 메타 (NODE_ID_STANDARD)
    # ══════════════════════════════════════════════════════════════════════════
    # 동일 노드 라벨이라도 도메인별 식별자 형식이 다를 수 있음 (예: vt_bacnt
    # 평문 vs MD5 해시 - OSINT 더치트 데이터). 각 노드 인스턴스의 id_format
    # 속성에 형식을 명시하여 Cross-source sameAs 자동 매칭 기반을 제공.
    NODE_ID_STANDARD = {
        'vt_bacnt': {
            'canonical_field':  'account_no',
            'id_formats':       ['plain_dash', 'md5', 'sha256'],
            'default_format':   'plain_dash',  # '110-2222-3333' (표시형)
            'normalization':    'strip_whitespace/dash + lowercase',  # 매칭키는 no-dash (norm_account)
        },
        'vt_telno': {
            'canonical_field':  'telno',
            'id_formats':       ['no_hyphen_e164', 'md5'],
            'default_format':   'no_hyphen_e164',  # '01012345678'
        },
        'vt_site': {
            'canonical_field':  'url_addr',
            'id_formats':       ['normalized_url'],
            'default_format':   'normalized_url',  # https://x.com (no www, no trailing /)
        },
        'vt_id': {
            'canonical_field':  '(platform, id_val)',  # 복합키
            'id_formats':       ['plain'],
            'default_format':   'plain',
        },
        'vt_ip': {
            'canonical_field':  'ip_addr',
            'id_formats':       ['ipv4_dotted', 'ipv6'],
            'default_format':   'ipv4_dotted',
        },
        'vt_file': {
            'canonical_field':  'hash_val',
            'id_formats':       ['md5', 'sha1', 'sha256'],
            'default_format':   'sha256',
        },
        'vt_psn': {
            'canonical_field':  'psn_id',
            'id_formats':       ['plain'],
            'default_format':   'plain',
        },
        'pt_cluster': {  # V3.7 신규
            'canonical_field':  'cluster_id',
            'id_formats':       ['plain'],
            'default_format':   'plain',
            'prefix_convention': {
                'investigation': 'ptc-{year}-{seq:04d}',
                'osint':         'osint-ptc-{seq:04d}',
            },
        },
        'site_cluster': {  # V3.7 신규
            'canonical_field':  'cluster_id',
            'id_formats':       ['plain'],
            'default_format':   'plain',
            'prefix_convention': {
                'investigation': 'sc-{year}-{seq:04d}',
                'osint':         'osint-sc-{seq:04d}',
            },
        },
        # V4.0 P2 — 나머지 16노드 id_format 표준 (감사 리포트 §6 보강)
        'vt_src':          {'canonical_field': 'src_id',        'id_formats': ['plain'],         'default_format': 'plain'},
        'vt_case':         {'canonical_field': 'flnm',          'id_formats': ['plain'],         'default_format': 'plain'},  # [정합화] 실 MERGE 키=flnm
        'vt_petition':     {'canonical_field': 'petition_id',   'id_formats': ['plain'],         'default_format': 'plain'},
        'vt_org':          {'canonical_field': 'org_id',        'id_formats': ['plain'],         'default_format': 'plain'},
        'vt_email':        {'canonical_field': 'email_addr',    'id_formats': ['normalized'],    'default_format': 'normalized'},  # [정합화] 실 MERGE 키=email_addr
        'vt_crypto':       {'canonical_field': 'wallet_addr',   'id_formats': ['base58check'],   'default_format': 'base58check'},  # [정합화] 실 MERGE 키=wallet_addr
        'vt_vhcl':         {'canonical_field': 'vhclno',        'id_formats': ['plain'],         'default_format': 'plain'},  # [정합화] 실 MERGE 키=vhclno
        'vt_dev':          {'canonical_field': 'dev_id',        'id_formats': ['plain', 'imei'], 'default_format': 'plain'},
        'vt_atm':          {'canonical_field': 'atm_id',        'id_formats': ['plain'],         'default_format': 'plain'},
        'vt_loc':          {'canonical_field': 'loc_id',        'id_formats': ['plain', 'geohash'], 'default_format': 'plain'},
        'vt_transfer':     {'canonical_field': 'transfer_id',   'id_formats': ['uuid'],          'default_format': 'uuid'},
        'vt_call':         {'canonical_field': 'call_id',       'id_formats': ['uuid'],          'default_format': 'uuid'},
        'vt_access':       {'canonical_field': 'access_id',     'id_formats': ['uuid'],          'default_format': 'uuid'},
        'vt_msg':          {'canonical_field': 'msg_id',        'id_formats': ['uuid'],          'default_format': 'uuid'},
        'vt_movement':     {'canonical_field': 'mov_id',        'id_formats': ['uuid'],          'default_format': 'uuid'},  # [정합화] 실 MERGE 키=mov_id
        'vt_impersonation':{'canonical_field': 'impersonation_id','id_formats': ['uuid'],        'default_format': 'uuid'},
    }

    # ══════════════════════════════════════════════════════════════════════════
    # 표준 DDL ↔ 적재 레거시 테이블 크로스워크 (마이그레이션 SoT) - STANDARD_TABLE_MAP
    # ══════════════════════════════════════════════════════════════════════════
    # CyberCOP V4.0 표준 DDL(DA팀 V3.7)과 적재코드 레거시 2종(public V2 대문자 /
    # test_v40 소문자) 테이블명 매핑. 적재가 표준과 0% 정합이라, 마이그레이션 시
    # 이 상수를 단일 참조원(SoT)으로 사용해 하드코딩 산재를 방지한다.
    # 상세 크로스워크: docs/STANDARD_DDL_ALIGNMENT_REVIEW_20260804.md §1
    # standard=None: 표준 마스터 부재 · 리스트: N:1(여러 표준 테이블 → 1 노드)
    STANDARD_TABLE_MAP = {
        'vt_src':          {'standard': 'TB_DATA_SOU_A',         'public_v2': 'TB_DATA_SRC',          'test_v40': None},
        'vt_case':         {'standard': 'TB_INCDNT_M',           'public_v2': 'TB_INCDNT_MST',        'test_v40': 'tb_incdnt_mst'},
        'vt_petition':     {'standard': 'TB_PETTN_M',            'public_v2': 'TB_PETTN_MST',         'test_v40': None},
        'vt_psn':          {'standard': 'TB_PSN_M',              'public_v2': 'TB_PRSN',              'test_v40': 'tb_prsn',
                            'std_columns': {'occp_nm': 'CR_NM'}},  # 직업: 온톨로지 occp_nm ↔ 표준 CR_NM(직업명, DA 확정 DDL 8/12)
        'vt_org':          {'standard': 'TB_INST_M',             'public_v2': 'TB_INST',              'test_v40': None},
        'vt_bacnt':        {'standard': 'TB_FNNC_BACNT_M',       'public_v2': 'TB_FIN_BACNT',         'test_v40': 'tb_fin_bacnt'},
        'vt_telno':        {'standard': 'TB_TELNO_M',            'public_v2': 'TB_TELNO_MST',         'test_v40': 'tb_telno_mst'},
        'vt_ip':           {'standard': 'TB_IP_ADDR_M',          'public_v2': None,                   'test_v40': None},  # 적재는 IP 마스터 없이 접속/도메인에서 파생
        'vt_site':         {'standard': 'TB_WEB_DMN_M',          'public_v2': 'TB_WEB_DMN',           'test_v40': None},
        'vt_file':         {'standard': 'TB_DGTL_FILE_LIST_M',   'public_v2': 'TB_DGTL_FILE_INVNT',   'test_v40': None},
        'vt_vhcl':         {'standard': 'TB_VHCL_M',             'public_v2': 'TB_VHCL_MST',          'test_v40': None},
        'vt_id':           {'standard': 'TB_DGTL_ID_M',          'public_v2': 'TB_DGTL_ID_MST',       'test_v40': None},
        'vt_email':        {'standard': 'TB_EML_ADDR_M',         'public_v2': 'TB_EMAIL_MST',         'test_v40': None},
        'vt_crypto':       {'standard': None,                    'public_v2': 'TB_CRYPTO_WALLET_MST', 'test_v40': None},  # 표준 마스터 부재
        'vt_dev':          {'standard': 'TB_ISTR_M',             'public_v2': 'TB_DEV_MST',           'test_v40': None},
        'vt_atm':          {'standard': 'TB_ATM_M',              'public_v2': 'TB_ATM_MST',           'test_v40': None},
        'vt_loc':          {'standard': 'TB_PSTN_M',             'public_v2': 'TB_LOC_MST',           'test_v40': None},
        'vt_transfer':     {'standard': 'TB_FNNC_BACNT_DLNG_T',  'public_v2': 'TB_FIN_BACNT_DLNG',    'test_v40': 'tb_fin_bacnt_dlng'},
        'vt_call':         {'standard': 'TB_TELNO_CALL_D',       'public_v2': 'TB_TELNO_CALL_DTL',    'test_v40': 'tb_telno_call_dtl',
                            # 컬럼 매핑(온톨로지 속성 ↔ 표준 DDL): 시간 조회 시 참조. 시각은 이름 일치, 통화시간만 상이(의미 동일).
                            # call_strt_dt↔CALL_STRT_DT(동일). ⚠️ CALL_HR=character(6) HHMMSS(시분초) → call_dur_sec=초 변환 필요: HH*3600+MM*60+SS
                            'std_columns': {'call_strt_dt': 'CALL_STRT_DT', 'call_dur_sec': 'CALL_HR'}},
        'vt_msg':          {'standard': ['TB_TELNO_SMS_MSG_T', 'TB_CTT_MSG_T'], 'public_v2': ['TB_TELNO_SMS_MSG', 'TB_CHAT_MSG'], 'test_v40': None},
        'vt_access':       {'standard': 'TB_SYS_LGN_EVT_T',      'public_v2': 'TB_SYS_LGN_EVT',       'test_v40': None,
                            # 시간축: access_dt↔CNTN_DT(접속일시 timestamp w/tz, E형). access_type↔CNTN_TYP_CD(접속타입코드 char(3), DA 신설 20260813 — 표준어 확정 ACCS_TYP_CD→CNTN_TYP_CD; web/comm/banking 코드값은 공통코드 별도)
                            'std_columns': {'access_dt': 'CNTN_DT', 'access_type': 'CNTN_TYP_CD'}},
        'vt_movement':     {'standard': ['TB_MOBL_PSTN_EVT_T', 'TB_TRFC_CARD_MVMN_T', 'TB_VHCL_NOPLT_RECG_EVT_T'], 'public_v2': ['TB_GEO_MBL_LOC_EVT', 'TB_VHCL_LPR_EVT'], 'test_v40': None},
        'vt_impersonation':{'standard': 'TB_FAAS_EVT_T',         'public_v2': 'TB_IMPRSN_REL',        'test_v40': None},
        'pt_cluster':      {'standard': 'TB_PETTN_CLSTR_T',      'public_v2': 'TB_PETTN_CLSTR',       'test_v40': None},
        'site_cluster':    {'standard': 'TB_OSINT_SITE_CLSTR_M', 'public_v2': None,                   'test_v40': None},
    }

    # ══════════════════════════════════════════════════════════════════════════
    # 파생속성 등록부 (V4.5 R6) - DERIVED_PROPERTY_REGISTRY
    # ══════════════════════════════════════════════════════════════════════════
    # 파생값(계산 속성)의 입력·규칙·재계산 시점을 일원화. 파생 순서가 결론을 바꾸는
    # 사례(ip_role: subject 기준 'shared' vs entity 기준 'single' — HANDOFF G12) 때문에
    # 재계산 시점을 규칙으로 고정. G9(집계)·G12(IP역할) 파생 + 6V 후처리 파생 포함.
    # (edge_id 는 파생 아닌 공통 식별자 — EDGE_META_SCHEMA 참조, V4.5 R7)
    DERIVED_PROPERTY_REGISTRY = {
        'ip_role': {                                    # V4.5 G12 → V4.6 bitemporal 재설계
            'node': 'vt_ip',
            'inputs': ['linked_subject_cnt', 'linked_entity_cnt', 'used_ip.valid_from/to'],
            'rule': ("linked_entity_cnt==1 → single_user · 2..θ-1 → shared_small · θ 이상 → "
                     "call_center(다수 실체 공유) · hosting → infra. θ(call_center 경계)는 고정 5가 "
                     "아닌 분포기반 이상치(5↑ 32개·10↑ 12개, 골 없음) — 구현: "
                     "ip_role_temporal.call_center_threshold(percentile/MAD)"),
            'temporal_rule': ("V4.6: used_ip valid_from/to 경계로 시간구간 분할 → 구간별(sameAs 해소 후) "
                              "entity_cnt로 role 판정 → 인접 동일구간 coalesce. 산출은 ip_role_timeline(구간 list)과 "
                              "ip_role_current(최신 구간). 설계: docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md"),
            'recompute': 'sameAs 해소 후(entity 기준). 구간 단위도 동일 순서(HANDOFF G12)',
            'stage_field': 'role_resolution_stage',
            'outputs': ['ip_role_current', 'ip_role_timeline'],
            'implementation_status': 'S1 스키마 등록 완료(used_ip 시간속성+파생 2종) / S3 구간계산 미구현(설계서 §4.2)',
        },
        'ip_role_current': {                            # V4.6 S1 (기존 단일 ip_role 대체·하위호환)
            'node': 'vt_ip',
            'inputs': ['ip_role_timeline'],
            'rule': "ip_role_timeline 최신 구간(마지막 valid_to)의 role. 무시간 쿼리/시각화는 이 값으로 그대로 동작(alias)",
            'recompute': 'ip_role_timeline 산출과 동시',
            'implementation_status': 'S1 등록 / S3 계산 미구현',
        },
        'ip_role_timeline': {                           # V4.6 S1
            'node': 'vt_ip',
            'inputs': ['used_ip.valid_from/to', 'linked_entity_cnt'],
            'rule': "used_ip 시간구간별 role 판정 list: [{from,to,role,entity_cnt,subject_cnt}] (인접 동일구간 coalesce)",
            'recompute': 'sameAs 해소 후',
            'implementation_status': 'S1 등록 / S3 계산 미구현',
        },
        'linked_subject_cnt': {'node': 'vt_ip', 'inputs': ['used_ip(역방향)'],
                               'rule': '이 IP에 붙는 식별자 수(해소 전)', 'recompute': 'used_ip 적재 후'},
        'linked_entity_cnt':  {'node': 'vt_ip', 'inputs': ['linked_subject_cnt', 'same_as'],
                               'rule': 'sameAs 해소 후 고유 실체 수', 'recompute': 'sameAs 해소 후'},
        'role_resolution_stage': {'node': 'vt_ip', 'inputs': ['ip_role'],
                                  'rule': "ip_role 산출 단계('subject'|'entity'|'period') — 'period'=V4.6 구간별 판정", 'recompute': 'ip_role과 동시'},
        'aggregation_level': {                          # V4.5 G9 → V4.6 #2 지연확장 설계
            'node': 'vt_access|vt_msg', 'inputs': ['event_count'],
            'rule': '집계 레벨(raw|hourly|daily). 지연 확장 3조건 충족 시 원본 이벤트로 확장',
            'aggregation_key': '(subject_id, bucket(시각, level), event_type) — 동일 key 원본이 1 집약노드로 접힘',
            'recompute': '적재 시',
            'implementation_status': ('#2 설계 완료(docs/ONTOLOGY_V46_LAZY_EXPANSION_DESIGN.md): 저장소는 '
                                      '원본 RDB 재사용(Bridge Key), E2 순수로직 lazy_expansion.should_expand/build_expansion. '
                                      'E3·E4(조회 어댑터·적재) 운영 DB 의존'),
        },
        'event_count':      {'node': 'vt_access|vt_msg', 'rule': '집계된 원본 이벤트 수', 'recompute': '적재 시'},
        'sample_event_ids': {
            'node': 'vt_access|vt_msg',
            'rule': '집계 노드의 대표 원본 이벤트 PK 표본(상한 N=20) — 지연 확장의 참조 키',
            'source_store': ('원본 RDB(Bridge Key) 재사용 — 신규 저장소 불필요(#2 설계). '
                             'vt_access→lgn_sn→TB_SYS_LGN_EVT · vt_msg→msg_sn→TB_TELNO_SMS_MSG/TB_CHAT_MSG. '
                             '조회: lazy_expansion.build_expansion(label, pks)'),
            'sample_cap': 20,
            'recompute': '적재 시',
        },
        'is_anonymous':     {'node': 'vt_psn', 'inputs': ['name', 'korn_flnm'],
                             'rule': 'name·korn_flnm 모두 공란 → true', 'recompute': '적재 후처리(6V-3)'},
        'reliability_tier': {'node': '*', 'inputs': ['source_domain'],
                             'rule': 'domain→tier(investigation 1·partner 2·inference 3·osint 4)', 'recompute': '적재(_postprocess_v40_meta)'},
    }

    # ══════════════════════════════════════════════════════════════════════════
    # 도메인 사용 매트릭스 (V3.7 통합 표준화) - DOMAIN_USAGE
    # ══════════════════════════════════════════════════════════════════════════
    # 동일 SSOT 카탈로그 위에서 도메인별 사용 가능성을 명시화.
    # 'primary': 1차 데이터 소스 | 'possible': 가능 | 'never': 의미론적 부적합
    # CCOP V3.6 OSINT 보고서 §10.2/10.3을 표준 메타로 격상.
    DOMAIN_USAGE = {
        'vt_src':         {'investigation': 'primary', 'osint': 'primary',  'partner': 'possible', 'inference': 'never'},
        'vt_case':        {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'never'},
        'vt_petition':    {'investigation': 'primary', 'osint': 'possible', 'partner': 'possible', 'inference': 'never'},
        'pt_cluster':     {'investigation': 'primary', 'osint': 'never',    'partner': 'never',    'inference': 'primary'},  # V3.7
        'vt_psn':         {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'possible'},
        'vt_org':         {'investigation': 'primary', 'osint': 'possible', 'partner': 'possible', 'inference': 'never'},
        'vt_bacnt':       {'investigation': 'primary', 'osint': 'primary',  'partner': 'primary',  'inference': 'never'},
        'vt_telno':       {'investigation': 'primary', 'osint': 'primary',  'partner': 'primary',  'inference': 'never'},
        'vt_ip':          {'investigation': 'primary', 'osint': 'primary',  'partner': 'possible', 'inference': 'never'},
        'vt_site':        {'investigation': 'possible','osint': 'primary',  'partner': 'possible', 'inference': 'never'},
        'site_cluster':   {'investigation': 'never',   'osint': 'primary',  'partner': 'never',    'inference': 'primary'},  # V3.7
        'vt_file':        {'investigation': 'possible','osint': 'primary',  'partner': 'possible', 'inference': 'never'},
        'vt_id':          {'investigation': 'possible','osint': 'primary',  'partner': 'never',    'inference': 'never'},
        'vt_email':       {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'never'},
        'vt_crypto':      {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'never'},
        'vt_vhcl':        {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'never'},
        'vt_dev':         {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'primary'},  # V3.7 relay_station
        'vt_atm':         {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'never'},
        'vt_loc':         {'investigation': 'primary', 'osint': 'possible', 'partner': 'possible', 'inference': 'never'},
        'vt_msg':         {'investigation': 'possible','osint': 'primary',  'partner': 'never',    'inference': 'never'},
        'vt_transfer':    {'investigation': 'primary', 'osint': 'possible', 'partner': 'primary',  'inference': 'never'},
        'vt_call':        {'investigation': 'primary', 'osint': 'never',    'partner': 'primary',  'inference': 'never'},
        'vt_access':      {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'never'},
        'vt_movement':    {'investigation': 'primary', 'osint': 'never',    'partner': 'possible', 'inference': 'never'},
        'vt_impersonation':{'investigation': 'primary','osint': 'possible', 'partner': 'never',    'inference': 'never'},
    }

    # ══════════════════════════════════════════════════════════════════════════
    # 추론 규칙 통합 카탈로그 (V4.2 정합화) — INFERENCE_RULES
    # ══════════════════════════════════════════════════════════════════════════
    # V4.1까지 이원화되어 있던 두 카탈로그를 단일 dict로 통합 (SoT 단일화):
    #   구 INFERENCE_RULES(list 10종, 탐지) + 구 INFERENCE_RULES_V37(dict 4종, enrichment)
    #   → 양쪽에 중복이던 RelayStationDetection을 무손실 1건으로 병합 → 총 13종
    # 키 = 규칙명(고유 → 중복 구조적 차단). rule_type 으로 목적 구분:
    #   detection  : 패턴 탐지 → 플래그/추론엣지 (pattern·trigger·threshold·confidence·legal_basis)
    #   enrichment : ETL 군집/엔티티 생성       (algorithm·input_nodes·output_nodes·frequency)
    # 하위호환: INFERENCE_RULES_V37 = enrichment 뷰(아래 자동 파생) → 기존 /ontology/meta API 무변경
    INFERENCE_RULES = {
        # ─── Detection 규칙 (9종): 패턴 탐지 → 플래그/추론엣지 ─────────────────
        'OrganizedCrime': {
            'rule_type':         'detection',
            'pattern':           'shared_resource_usage',
            'trigger':           '동일 계좌/전화가 3건+ 사건에서 사용',
            'threshold':         3,
            'confidence':        0.80,
            'output_edge':       'accomplice_of',
            'legal_basis':       '범죄수익은닉규제법',
        },
        'MoneyLaundering': {
            'rule_type':         'detection',
            'pattern':           'multi_hop_transfer',
            'trigger':           '3단계+ 계좌이체 (hop_level >= 3)',
            'threshold':         3,
            'confidence':        0.75,
            'output_edge':       'suspicious_transfer',
            'legal_basis':       '특정금융거래정보법',
        },
        'Accomplice': {
            'rule_type':         'detection',
            'pattern':           'shared_contacts',
            'trigger':           '2인 이상이 5건+ 공통 통화 대상 공유',
            'threshold':         5,
            'confidence':        0.70,
            'output_edge':       'accomplice_of',
            'legal_basis':       '형법 제30조 공동정범',
        },
        'BurnerAccount': {
            'rule_type':         'detection',
            'pattern':           'high_frequency_transfer',
            'trigger':           '1시간 내 10건+ 이체 또는 3일 이내 개설·사용·해지',
            'threshold':         10,
            'confidence':        0.85,
            'output_node_flag':  'vt_bacnt.is_burner = True',
            'legal_basis':       '전자금융거래법',
        },
        'BurnerPhone': {
            'rule_type':         'detection',
            'pattern':           'prepaid_high_activity',
            'trigger':           '선불폰 (join_typ_cd=PREPAID) + 스팸신고 3건+',
            'threshold':         3,
            'confidence':        0.80,
            'output_node_flag':  'vt_telno.is_burner = True',
            'legal_basis':       '전기통신사업법',
        },
        'EntityResolutionCandidate': {
            'rule_type':         'detection',
            'pattern':           'shared_phone_and_account',
            'trigger':           '두 vt_psn이 동일 전화번호 + 계좌 1개 이상 공유',
            'threshold':         1,
            'confidence':        0.85,
            'output_edge':       'same_as',
            'review_required':   True,   # 사람/조직 해소는 human-in-the-loop (자동 확정 금지)
            'legal_basis':       None,
        },
        'CrossDomainHub': {
            'rule_type':         'detection',
            'pattern':           'ip_account_phone_correlation',
            'trigger':           '동일 IP에서 다수 계좌+전화 접속',
            'threshold':         2,
            'confidence':        0.80,
            'output_flag':       'hub_suspect',
            'legal_basis':       '정보통신망법',
        },
        'NightCrimePattern': {
            'rule_type':         'detection',
            'pattern':           'night_time_activity',
            'trigger':           '00~06시 3건+ 이체/통화',
            'threshold':         3,
            'confidence':        0.65,
            'output_flag':       'night_activity',
            'legal_basis':       '야간 범행 가중처벌',
        },
        'RecruitChainAccomplice': {
            'rule_type':         'detection',
            'pattern':           'recruits_chain',
            'trigger':           '총책 → 조직원 → 말단 recruits 체인 2단계+',
            'threshold':         2,
            'confidence':        0.75,
            'output_edge':       'accomplice_of',
            'legal_basis':       '형법 제30조 공동정범',
        },
        # ─── Enrichment 규칙 (4종): ETL 군집/엔티티 생성 ──────────────────────
        'SiteClusterDetection': {
            'rule_type':         'enrichment',
            'description':       'HTML SimHash 지문 기반 피싱 캠페인 군집화',
            'input_nodes':       ['vt_site'],
            'input_attributes':  ['html_fingerprint', 'html_src'],
            'algorithm':         'simhash_64bit + union_find (Hamming distance <= 3)',
            'output_nodes':      ['site_cluster'],
            'output_edges':      ['belongs_to_campaign'],
            'min_cluster_size':  2,
            'applicable_domains':['osint', 'inference'],
            'frequency':         'batch_daily',
        },
        'PtClusterDetection': {
            'rule_type':         'enrichment',
            'description':       '진정서 유사도 군집화',
            'input_nodes':       ['vt_petition'],
            'input_attributes':  ['petition_text', 'TB_PETTN_CLSTR'],
            'algorithm':         'union_find (sim_score >= 0.7)',
            'output_nodes':      ['pt_cluster'],
            'output_edges':      ['belongs_to_cluster'],
            'applicable_domains':['investigation', 'inference'],
            'frequency':         'batch_daily',
        },
        'AnonymousFlagDetection': {
            'rule_type':         'enrichment',
            'description':       'name/korn_flnm 비식별 노드 → is_anonymous=true (vt_psn, vt_id)',
            'input_nodes':       ['vt_psn', 'vt_id'],
            'input_attributes':  ['name', 'korn_flnm', 'real_name'],
            'algorithm':         "WHERE name IS NULL OR name = '' OR name LIKE '%***%'",
            'output_nodes':      [],  # 신규 노드 생성 없음 (속성 플래그만 설정)
            'output_attributes': {'vt_psn.is_anonymous': True, 'vt_id.is_anonymous': True},
            'output_edges':      [],  # 신규 엣지 없음
            'applicable_domains':['investigation', 'osint'],
            'frequency':         'on_ingest',
        },
        # RelayStationDetection: 구 list(탐지) + 구 V37(생성)의 중복을 무손실 병합 (이원화 해소 핵심)
        'RelayStationDetection': {
            'rule_type':         'enrichment',   # vt_dev 노드/엣지 생성이 주기능, 동시에 탐지 신호
            'description':       '동일 IMEI 3대+ 공유 vt_telno → vt_dev(relay_station) 생성·탐지',
            'pattern':           'multi_phone_same_imei',
            'trigger':           '동일 IMEI(device_id)에 전화번호 3개+',
            'threshold':         3,
            'confidence':        0.90,
            'input_nodes':       ['vt_telno'],
            'input_attributes':  ['imei'],
            'algorithm':         'group_by imei, count >= 3',
            'output_nodes':      ['vt_dev'],
            'output_attributes': {'dev_type': 'relay_station'},
            'output_edges':      ['used_in_device'],
            'output_node_flag':  'vt_dev.dev_type = relay_station',
            'applicable_domains':['investigation', 'inference'],
            'frequency':         'batch_daily',
            'legal_basis':       '전기통신사업법 제30조 (불법중계기 제조·사용 금지)',
        },
    }

    # 하위호환 뷰 — 구 INFERENCE_RULES_V37 (enrichment 규칙만). 기존 /ontology/meta API 무변경.
    # ※ dict-comprehension의 최외곽 iterable(INFERENCE_RULES.items())만 클래스 스코프에서 평가되므로 정상 동작.
    INFERENCE_RULES_V37 = {
        _name: _rule for _name, _rule in INFERENCE_RULES.items()
        if _rule.get('rule_type') == 'enrichment'
    }

    # ══════════════════════════════════════════════════════════════════════════
    # 시각화 표준 (V4.0 L5) - VISUAL_STYLE_V40 + EDGE_STYLE_V40 + LAYOUT_PRESETS
    # ══════════════════════════════════════════════════════════════════════════
    # Cytoscape.js 호환 시각화 스타일 SSOT. 라벨/엣지별 색상·아이콘·모양·크기를
    # 단일 진실로 관리. 프론트엔드(index.html)는 본 메타를 import해서 적용.
    VISUAL_STYLE_V40 = {
        # Source Layer (회색 — 메타)
        'vt_src':           {'color': '#95A5A6', 'shape': 'rectangle', 'icon': 'src.png',     'size': 30, 'label_property': 'src_name'},
        # Case Layer (빨강 계열 — 사건)
        'vt_case':          {'color': '#E74C3C', 'shape': 'ellipse',   'icon': 'case.png',    'size': 50, 'label_property': 'flnm'},
        'vt_petition':      {'color': '#EC7063', 'shape': 'ellipse',   'icon': 'petition.png','size': 40, 'label_property': 'petition_id'},
        'pt_cluster':       {'color': '#FFD93D', 'shape': 'hexagon',   'icon': 'cluster.png', 'size': 60, 'label_property': 'cluster_id', 'is_hub': True},
        # Person Layer (파랑 계열 — 인물)
        'vt_psn':           {'color': '#3498DB', 'shape': 'ellipse',   'icon': 'person.png',  'size': 45, 'label_property': 'name',
                             'style_modifier': {
                                'is_anonymous':                        {'color': '#7F8C8D', 'border_style': 'dashed'},
                                'risk_level=HIGH':                     {'size': 55, 'border_width': 3},
                                'risk_level=CRITICAL':                 {'size': 65, 'border_width': 4, 'border_color': '#C0392B'},
                             }},
        'vt_org':           {'color': '#5DADE2', 'shape': 'diamond',   'icon': 'org.png',     'size': 45, 'label_property': 'org_name'},
        # Object Layer (청록·녹색 — 디지털 객체)
        'vt_bacnt':         {'color': '#4ECDC4', 'shape': 'rectangle', 'icon': 'account.png', 'size': 35, 'label_property': 'account_no',
                             'style_modifier': {
                                'is_burner':                           {'color': '#E67E22', 'border_style': 'dashed'},
                                'is_frozen':                           {'opacity': 0.5},
                             }},
        'vt_telno':         {'color': '#16A085', 'shape': 'rectangle', 'icon': 'phone.png',   'size': 35, 'label_property': 'telno',
                             'style_modifier': {
                                'is_burner':                           {'color': '#E67E22', 'border_style': 'dashed'},
                             }},
        'vt_ip':            {'color': '#1ABC9C', 'shape': 'rectangle', 'icon': 'ip.png',      'size': 30, 'label_property': 'ip_addr',
                             'style_modifier': {
                                'is_vpn':                              {'border_style': 'dotted'},
                                'threat_score>=80':                    {'color': '#C0392B', 'border_width': 3},
                             }},
        'vt_site':          {'color': '#9B59B6', 'shape': 'round-rectangle', 'icon': 'site.png',  'size': 35, 'label_property': 'url_addr',
                             'style_modifier': {
                                'is_malicious':                        {'color': '#8E44AD', 'border_color': '#C0392B', 'border_width': 3},
                             }},
        'site_cluster':     {'color': '#F39C12', 'shape': 'hexagon',   'icon': 'cluster.png', 'size': 60, 'label_property': 'campaign_name', 'is_hub': True},
        'vt_file':          {'color': '#8E44AD', 'shape': 'rectangle', 'icon': 'file.png',    'size': 30, 'label_property': 'file_nm',
                             'style_modifier': {
                                'is_malicious':                        {'color': '#C0392B'},
                             }},
        'vt_id':            {'color': '#5499C7', 'shape': 'ellipse',   'icon': 'id.png',      'size': 30, 'label_property': 'id_val',
                             'style_modifier': {
                                'is_anonymous':                        {'color': '#7F8C8D', 'border_style': 'dashed'},
                             }},
        'vt_email':         {'color': '#A569BD', 'shape': 'rectangle', 'icon': 'email.png',   'size': 30, 'label_property': 'email_addr'},
        'vt_crypto':        {'color': '#F1C40F', 'shape': 'rectangle', 'icon': 'crypto.png',  'size': 30, 'label_property': 'wallet_addr'},
        'vt_vhcl':          {'color': '#34495E', 'shape': 'rectangle', 'icon': 'car.png',     'size': 30, 'label_property': 'vhclno'},
        'vt_dev':           {'color': '#7D3C98', 'shape': 'rectangle', 'icon': 'device.png',  'size': 35, 'label_property': 'device_id',
                             'style_modifier': {
                                "dev_type='relay_station'":            {'color': '#C0392B', 'shape': 'octagon', 'border_width': 3, 'size': 50},
                             }},
        'vt_atm':           {'color': '#85929E', 'shape': 'rectangle', 'icon': 'atm.png',     'size': 30, 'label_property': 'atm_id'},
        # Event Layer (주황 계열 — 행위)
        'vt_transfer':      {'color': '#F39C12', 'shape': 'diamond',   'icon': 'transfer.png','size': 30, 'label_property': 'amount'},
        'vt_call':          {'color': '#E67E22', 'shape': 'diamond',   'icon': 'call.png',    'size': 25, 'label_property': 'call_dt'},
        'vt_access':        {'color': '#D35400', 'shape': 'diamond',   'icon': 'access.png',  'size': 25, 'label_property': 'access_dt'},
        'vt_msg':           {'color': '#E59866', 'shape': 'diamond',   'icon': 'msg.png',     'size': 30, 'label_property': 'msg_type'},
        'vt_movement':      {'color': '#DC7633', 'shape': 'diamond',   'icon': 'move.png',    'size': 25, 'label_property': 'mvmt_dt'},
        'vt_impersonation': {'color': '#CB4335', 'shape': 'diamond',   'icon': 'imprsn.png',  'size': 35, 'label_property': 'imprsn_type_cd'},
        # Location Layer (갈색)
        'vt_loc':           {'color': '#A04000', 'shape': 'pentagon',  'icon': 'location.png','size': 30, 'label_property': 'address'},
    }

    EDGE_STYLE_V40 = {
        # Case 역할 (빨강 — 강한 의미)
        'suspect_in':         {'color': '#C0392B', 'width': 3, 'arrow': 'triangle', 'style': 'solid'},
        'victim_in':          {'color': '#27AE60', 'width': 3, 'arrow': 'triangle', 'style': 'solid'},
        'witness_in':         {'color': '#F39C12', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'involves':           {'color': '#7F8C8D', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'filed_as':           {'color': '#16A085', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'related_case':       {'color': '#E67E22', 'width': 2, 'arrow': 'triangle-tee', 'style': 'solid'},
        # Evidence 엣지
        'eg_used_account':    {'color': '#3498DB', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'eg_used_phone':      {'color': '#16A085', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'eg_used_ip':         {'color': '#1ABC9C', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        # Person 소유/관계
        'has_account':        {'color': '#0066CC', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'owns_phone':         {'color': '#16A085', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'owns_vehicle':       {'color': '#34495E', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'drives':             {'color': '#34495E', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'member_of':          {'color': '#5DADE2', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'works_at':           {'color': '#5499C7', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'accomplice_of':      {'color': '#C0392B', 'width': 3, 'arrow': 'triangle-tee', 'style': 'solid'},
        'recruits':           {'color': '#922B21', 'width': 3, 'arrow': 'triangle', 'style': 'solid'},
        'blackmails':         {'color': '#641E16', 'width': 3, 'arrow': 'triangle', 'style': 'solid'},
        'same_as':             {'color': '#999999', 'width': 2, 'arrow': 'none',     'style': 'dashed'},
        'contradicts':        {'color': '#C0392B', 'width': 2, 'arrow': 'tee',      'style': 'dotted'},
        # V4.3 시나리오 직접 엣지 (속성적 연결)
        'knows':              {'color': '#7F8C8D', 'width': 2, 'arrow': 'none',     'style': 'solid'},
        'linked_id':          {'color': '#5499C7', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'mentions_id':        {'color': '#A569BD', 'width': 2, 'arrow': 'triangle', 'style': 'dotted'},
        # Event 흐름
        'from_account':       {'color': '#F39C12', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'to_account':         {'color': '#F39C12', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'caller':             {'color': '#E67E22', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'callee':             {'color': '#E67E22', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'sent_msg':           {'color': '#E59866', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'received_msg':       {'color': '#E59866', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'accessed_from':      {'color': '#D35400', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'accessed_to':        {'color': '#D35400', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        # Object 관계
        'belongs_to':         {'color': '#9B59B6', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'resolves_to':        {'color': '#1ABC9C', 'width': 1, 'arrow': 'triangle', 'style': 'solid'},
        'hosts':              {'color': '#1ABC9C', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'contains_file':      {'color': '#8E44AD', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'mentions_account':   {'color': '#5DADE2', 'width': 1, 'arrow': 'triangle-tee', 'style': 'solid'},
        'communicated_with':  {'color': '#16A085', 'width': 2, 'arrow': 'triangle-tee', 'style': 'solid'},
        # 사칭 (V3.3)
        'used_for':           {'color': '#CB4335', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'targets':            {'color': '#922B21', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        # 출처/검증
        'sourced_from':       {'color': '#BDC3C7', 'width': 1, 'arrow': 'triangle', 'style': 'dotted'},
        'verified_by':        {'color': '#27AE60', 'width': 1, 'arrow': 'triangle', 'style': 'dashed'},
        # V3.7 신규 엣지 (군집)
        'belongs_to_cluster': {'color': '#FFD93D', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'belongs_to_campaign':{'color': '#F39C12', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'used_in_device':     {'color': '#FF6600', 'width': 3, 'arrow': 'triangle', 'style': 'solid'},
        # 인물 → 디지털
        'uses_id':            {'color': '#5499C7', 'width': 1, 'arrow': 'triangle', 'style': 'solid'},
        'uses_email':         {'color': '#A569BD', 'width': 1, 'arrow': 'triangle', 'style': 'solid'},
        'owns_wallet':        {'color': '#F1C40F', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'uses_device':        {'color': '#7D3C98', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        # [V4.0 정합화] 의미 카탈로그에만 있던 실사용 엣지 스타일 등재 (2026-07-31)
        'used_ip':            {'color': '#5499C7', 'width': 1, 'arrow': 'triangle', 'style': 'solid'},    # Person→Digital 계열 (uses_id 동계열)
        'owns':               {'color': '#0066CC', 'width': 1, 'arrow': 'triangle', 'style': 'dashed'},   # 범용 소유 — has_account 계열의 보조형(얇은 대시)
        'controls':           {'color': '#0052A3', 'width': 2, 'arrow': 'triangle', 'style': 'dashed'},   # 실질지배 — 소유(진파랑)의 강조 대시
        'located_at':         {'color': '#00B894', 'width': 1, 'arrow': 'triangle', 'style': 'dotted'},   # Location 계열 (정적 위치, 점선)
        'owns_device':        {'color': '#7D3C98', 'width': 2, 'arrow': 'triangle', 'style': 'dashed'},   # uses_device 별칭(deprecated) — 동색 대시로 구분
        # 기타
        'registered_to':      {'color': '#5499C7', 'width': 1, 'arrow': 'triangle', 'style': 'solid'},
        'operates':           {'color': '#9B59B6', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'transferred_to':     {'color': '#F39C12', 'width': 1, 'arrow': 'triangle', 'style': 'solid'},
        'occurred_at':        {'color': '#A04000', 'width': 1, 'arrow': 'triangle', 'style': 'dotted'},
        'recorded_in':        {'color': '#7F8C8D', 'width': 1, 'arrow': 'triangle', 'style': 'dotted'},
        'performed_by':       {'color': '#3498DB', 'width': 1, 'arrow': 'triangle', 'style': 'dotted'},
        # V4.4 reification 참여 엣지
        'access_via':         {'color': '#D35400', 'width': 2, 'arrow': 'triangle', 'style': 'solid'},
        'via_ip':             {'color': '#1ABC9C', 'width': 1, 'arrow': 'triangle', 'style': 'dotted'},
        'mentions_location':  {'color': '#A04000', 'width': 2, 'arrow': 'triangle', 'style': 'dotted'},
        'linked_to':          {'color': '#BDC3C7', 'width': 1, 'arrow': 'triangle-tee', 'style': 'dashed'},
        'contacted':          {'color': '#E67E22', 'width': 1, 'arrow': 'triangle-tee', 'style': 'solid'},
        'impersonates':       {'color': '#CB4335', 'width': 2, 'arrow': 'triangle', 'style': 'dashed'},  # V3.3 read-only
        # Deprecated (시각화는 표시하되 색을 흐리게)
        'clusters_with':      {'color': '#CCCCCC', 'width': 1, 'arrow': 'triangle-tee', 'style': 'dotted', 'deprecated': True},
    }

    LAYOUT_PRESETS_V40 = {
        'case_centric': {
            'algorithm': 'breadthfirst',
            'root_label': 'vt_case',
            'directed': True,
            'description': '사건 중심 트리 — 사건→피의자→증거 흐름 시각화',
        },
        'cluster_view': {
            'algorithm': 'concentric',
            'center_label': ['pt_cluster', 'site_cluster'],
            'description': '군집 허브 중심 — pt_cluster/site_cluster 멤버십 시각화',
        },
        'timeline': {
            'algorithm': 'timeline',  # 커스텀 (시간 컬럼 기준 X축 배치)
            'sort_by': 'occurred_at',
            'description': '시간순 이벤트 흐름 — 통화/이체/접속의 시계열',
        },
        'investigation': {
            'algorithm': 'cose',
            'edge_length_property': 'reliability_tier',  # tier 낮을수록 가까이
            'description': '수사 종합 뷰 — 신뢰도 가중 force-directed',
        },
        'cross_domain': {
            'algorithm': 'cose-bilkent',
            'cluster_by': 'source_domain',  # 도메인별 클러스터링
            'description': 'Cross-domain — CCOP/OSINT 도메인 분리 시각화',
        },
    }

    INVESTIGATION_WORKFLOWS_V40 = {
        'case_to_suspects':       {'start': 'vt_case', 'hops': [('suspect_in', '<-')], 'end': 'vt_psn',
                                   'description': '사건 → 피의자 목록'},
        'suspect_to_assets':      {'start': 'vt_psn', 'hops': [('has_account', '->'), ('owns_phone', '->')],
                                   'description': '피의자 → 보유 자산 (계좌/전화)'},
        'phishing_campaign_view': {'start': 'site_cluster', 'hops': [('belongs_to_campaign', '<-')], 'end': 'vt_site',
                                   'description': '피싱 캠페인 → 멤버 사이트'},
        'fund_flow':              {'start': 'vt_bacnt', 'hops': [('from_account', '->'), ('to_account', '->')], 'depth': 5,
                                   'description': '자금 흐름 추적'},
        'relay_station_network':  {'start': "vt_dev WHERE dev_type='relay_station'",
                                   'hops': [('used_in_device', '<-')], 'end': 'vt_telno',
                                   'description': '중계기 → 연결된 전화번호'},
        'cross_graph_sameAs':     {'start': 'vt_bacnt (CCOP)', 'hops': [('same_as', '<->')], 'end': 'vt_bacnt (OSINT)',
                                   'description': '도메인 간 동일 자산 매칭'},
    }

    @classmethod
    def active_relationships(cls):
        """deprecated 제외 활성 엣지만 반환 (신규 생성·Text2Cypher 대상 스키마). 현재 활성 69/71."""
        return {e: d for e, d in cls.RELATIONSHIPS.items() if not d.get('deprecated')}

    @classmethod
    def get_visual_style(cls, label: str) -> dict:
        """라벨의 시각화 스타일 반환 (V4.0 L5)"""
        return cls.VISUAL_STYLE_V40.get(label, {'color': '#CCCCCC', 'shape': 'ellipse', 'size': 30})

    @classmethod
    def get_edge_style(cls, edge_label: str) -> dict:
        """엣지의 시각화 스타일 반환 (V4.0 L5)"""
        return cls.EDGE_STYLE_V40.get(edge_label, {'color': '#CCCCCC', 'width': 1, 'arrow': 'triangle', 'style': 'solid'})

    @classmethod
    def get_layout_preset(cls, preset_name: str) -> dict:
        """레이아웃 프리셋 반환"""
        return cls.LAYOUT_PRESETS_V40.get(preset_name, cls.LAYOUT_PRESETS_V40['investigation'])

    @classmethod
    def get_workflow(cls, workflow_name: str) -> dict:
        """수사 워크플로 반환"""
        return cls.INVESTIGATION_WORKFLOWS_V40.get(workflow_name, {})

    @classmethod
    def get_id_format(cls, label: str) -> dict:
        """노드 라벨의 식별자 형식 표준 반환 (V3.7)"""
        return cls.NODE_ID_STANDARD.get(label, {})

    @classmethod
    def get_domain_usage(cls, label: str, domain: str = None):
        """노드의 도메인별 사용 가능성 반환 (V3.7).
        domain 미지정 시 전체 dict 반환."""
        usage = cls.DOMAIN_USAGE.get(label, {})
        return usage if domain is None else usage.get(domain, 'unknown')

    @classmethod
    def is_applicable(cls, label: str, domain: str) -> bool:
        """특정 도메인에서 노드가 사용 가능한지 (primary/possible)"""
        return cls.get_domain_usage(label, domain) in ('primary', 'possible')

    # 엔티티 계층 (Entity Hierarchy) - POLE 정렬 6레이어 (v3.0)
    ENTITIES = {
        # ═══════════════════════════════════════════════════════════════════
        # SOURCE LAYER — 데이터 출처 (수직 관통, 모든 엣지가 참조)
        # ═══════════════════════════════════════════════════════════════════
        'Source': {
            'layer': 'Source',
            'label': 'vt_src',
            'label_ko': '소스',
            'properties': ['src_id', 'src_name', 'src_type', 'reliability_tier'],
            'attributes': ['collector', 'collected_at', 'update_cycle', 'contact'],
            'legal_category': '수사정보',
            'description': '데이터 출처 (수집 기관/채널/신뢰 등급)'
        },

        # ═══════════════════════════════════════════════════════════════════
        # CASE LAYER — 수사 맥락
        # ═══════════════════════════════════════════════════════════════════
        'Case': {
            'layer': 'Case',
            'label': 'vt_case',
            'label_ko': '사건',
            'properties': ['flnm', 'incdnt_no'],
            'attributes': ['incdnt_nm', 'incdnt_typ_cd', 'crime_type', 'occrn_dt',
                           'damage_amount', 'case_summary', 'status',
                           'chrgdp_nm', 'chrg_plcmn_nm', 'police_station',
                           'source_id', 'rec_created'],
            'role': 'anchor',
            'legal_category': '수사사건',
            'description': '수사 사건 케이스'
        },
        'Petition': {
            'layer': 'Case',
            'label': 'vt_petition',
            'label_ko': '진정서',
            'properties': ['petition_id'],
            'attributes': ['rcpt_dt', 'rcpt_channel', 'rcpt_station',
                           'crime_type_cd', 'damage_amt', 'incdt_dt',
                           'status', 'linked_case_id',
                           'preprocessed_by', 'ocr_confidence', 'schema_version', 'raw_id',
                           'source_id', 'rec_created'],
            'legal_category': '수사사건',
            'description': '진정서/신고 (수사 개시 전·후 모두 존재)'
        },
        'PetitionCluster': {
            'layer': 'Case',
            'label': 'pt_cluster',
            'label_ko': '진정서군집',
            'properties': ['cluster_id'],
            'attributes': ['cluster_method',   # 'simhash' | 'tfidf' | 'manual'
                           'crime_type_cd',    # 대표 범죄 유형
                           'damage_amt_sum',   # 군집 내 피해액 합계
                           'petition_cnt',     # 소속 진정서 수
                           'first_rcpt_dt', 'last_rcpt_dt',
                           'status',           # 'active' | 'merged' | 'closed'
                           'source_id', 'rec_created'],
            'legal_category': '수사사건',
            'description': '진정서 군집 허브 노드 — clusters_with O(n²) 엣지 대체 (v3.7)'
        },

        # ═══════════════════════════════════════════════════════════════════
        # PERSON LAYER (POLE-P) — 행위 주체
        # ═══════════════════════════════════════════════════════════════════
        'Person': {
            'layer': 'Person',
            'label': 'vt_psn',
            'label_ko': '인물',
            'properties': ['psn_id'],            # 단일 PK (성명불상 시 UUID 자동 부여)
            'attributes': ['korn_flnm', 'name',  # 성명 (korn_flnm=경찰청 표준, name=별칭)
                           'dob', 'gender', 'nationality',
                           'rrno_hash', 'passport_no', 'contact',
                           'aliases', 'risk_level',
                           'occp_nm',            # 직업 (수사단서 5건 보완 — TB_PSN_M.OCCP_NM 신설 반영)
                           'is_anonymous',       # True=성명불상 (v3.7 신규)
                           'source_id', 'rec_created', 'verified', 'confidence'],
            # ⚠️ role 속성 없음 — 엣지로 표현 (suspect_in / victim_in / witness_in)
            'legal_category': '피의자정보',
            'description': '인물 (피의자/피해자/참고인 — 역할은 엣지 타입으로; is_anonymous=True 시 성명불상)'
        },
        'Organization': {
            'layer': 'Person',
            'label': 'vt_org',
            'label_ko': '조직',
            'properties': ['org_id'],            # 단일 PK (org_name은 변경 가능 → 비PK)
            'attributes': ['org_name',           # 조직명 (검색용)
                           'org_category', 'inst_se_cd', 'brno', 'bank_cd', 'addr',
                           'member_count', 'activity_type', 'hierarchy_level',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '피의자정보',
            'description': '조직 (범죄단체 및 합법기관 통합, org_category로 분기)'
        },

        # ═══════════════════════════════════════════════════════════════════
        # OBJECT LAYER (POLE-O) — 객체·증거
        # ═══════════════════════════════════════════════════════════════════
        'BankAccount': {
            'layer': 'Object',
            'sublayer': 'Financial',
            'label': 'vt_bacnt',
            'label_ko': '계좌',
            'properties': ['account_no', 'bank_cd'],  # 복합 PK (경찰청 표준)
            'attributes': ['bank_nm', 'dpstr_nm', 'account_type', 'bacnt_opn_dt', 'inst_id',
                           'is_burner', 'is_frozen', 'total_received', 'total_sent', 'transaction_cnt',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '금융거래정보'
        },
        'CryptoWallet': {
            'layer': 'Object',
            'sublayer': 'Financial',
            'label': 'vt_crypto',
            'label_ko': '가상자산',
            'properties': ['wallet_addr', 'blockchain'],  # 복합 PK (동일 주소가 다른 체인에 존재 가능)
            'attributes': ['asset_type', 'exchange', 'balance',
                           'risk_score', 'kyc_verified', 'tx_cnt',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '가상자산거래정보'
        },
        'NetworkTrace': {
            'layer': 'Object',
            'sublayer': 'Digital',
            'label': 'vt_ip',
            'label_ko': 'IP주소',
            'properties': ['ip_addr'],
            'attributes': ['version', 'isp', 'asn', 'org', 'country', 'geo_region', 'city',
                           'is_vpn', 'is_tor', 'is_proxy', 'is_hosting', 'abuse_score',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '통신자료'
        },
        'WebTrace': {
            'layer': 'Object',
            'sublayer': 'Digital',
            'label': 'vt_site',
            'label_ko': '사이트',
            'properties': ['url_addr'],  # 단일 식별자 (site/domain 중복 제거)
            'attributes': ['dmn_addr', 'site_type', 'is_malicious', 'risk_grd',
                           'sign_kwrd', 'detct_dt',
                           'registrar', 'whois_org', 'reg_dt', 'exp_dt',
                           'page_title', 'page_hash',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '인터넷기록'
        },
        'SiteCluster': {
            'layer': 'Object',
            'sublayer': 'Digital',
            'label': 'site_cluster',
            'label_ko': '피싱캠페인군집',
            'properties': ['cluster_id'],
            'attributes': ['html_fingerprint',    # SimHash 64bit (캠페인 불변 식별자)
                           'campaign_name',        # 수사관 부여 캠페인명
                           'cluster_method',       # 'simhash' | 'manual'
                           'site_cnt',             # 소속 사이트 수
                           'ip_cnt',               # 관련 IP 수
                           'first_seen', 'last_seen',
                           'source_id', 'rec_created'],
            'legal_category': '인터넷기록',
            'description': '피싱 캠페인 군집 허브 노드 — HTML SimHash 지문으로 도메인/IP 교체 추적 (v3.7)'
        },
        'FileTrace': {
            'layer': 'Object',
            'sublayer': 'Digital',
            'label': 'vt_file',
            'label_ko': '파일',
            'properties': ['hash_val'],  # SHA-256 (hash_md5 제거)
            'attributes': ['file_nm', 'file_extsn_nm', 'file_sz', 'file_path',
                           'creat_dt', 'mdfr_dt', 'is_malicious', 'vt_score',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '디지털증거'
        },
        'DigitalID': {
            'layer': 'Object',
            'sublayer': 'Identity',
            'label': 'vt_id',
            'label_ko': '디지털ID',
            'properties': ['id_val', 'platform'],
            'attributes': ['id_type', 'profile_url', 'is_active', 'real_name',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '신원정보',
            'description': '플랫폼 계정 ID·닉네임 (vt_persona 흡수)'
        },
        'Email': {
            'layer': 'Object',
            'sublayer': 'Digital',
            'label': 'vt_email',
            'label_ko': '이메일',
            'properties': ['email_addr'],
            'attributes': ['domain', 'provider', 'is_disposable',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '통신자료'
        },
        'Phone': {
            'layer': 'Object',
            'sublayer': 'Communication',
            'label': 'vt_telno',
            'label_ko': '전화번호',
            'properties': ['telno'],
            'attributes': ['country_code', 'telco_nm', 'join_typ_cd',
                           'is_registered', 'is_burner', 'subs_holder', 'imsi', 'spam_cnt',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '통신사실확인자료'
        },
        'Vehicle': {
            'layer': 'Object',
            'sublayer': 'Physical',
            'label': 'vt_vhcl',
            'label_ko': '차량',
            'properties': ['vhclno'],
            'attributes': ['carmdl_nm', 'carmdl_dtl_nm', 'color',
                           'ownr_nm', 'rgst_dt', 'stolen_yn',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '차량정보',
            'description': '차량 (번호판 기반 식별)'
        },
        'Device': {
            'layer': 'Object',
            'sublayer': 'Digital',
            'label': 'vt_dev',
            'label_ko': '기기',
            'properties': ['device_id'],
            'attributes': ['dev_type', 'imei', 'mac_addr', 'model', 'os', 'os_version',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '디지털증거',
            # dev_type 허용값: smartphone | pc | tablet | relay_station | router | other
            # relay_station = 불법 중계기 (IMEI 공유 전화 3대+ 탐지 시 설정, v3.7)
            'description': '기기 (스마트폰/PC/태블릿/불법중계기 등)'
        },
        'ATM': {
            'layer': 'Object',
            'sublayer': 'Physical',
            'label': 'vt_atm',
            'label_ko': 'ATM',
            'properties': ['atm_id'],
            'attributes': ['bank_nm', 'bank_cd', 'loc_id', 'address', 'is_outdoor',
                           'source_id', 'rec_created'],
            'legal_category': '물리증거'
        },

        # ═══════════════════════════════════════════════════════════════════
        # LOCATION LAYER (POLE-L) — 위치
        # ═══════════════════════════════════════════════════════════════════
        'Location': {
            'layer': 'Location',
            'label': 'vt_loc',
            'label_ko': '위치',
            'properties': ['loc_id'],
            'attributes': ['loc_type',  # address | cell_tower | cctv | atm_loc | transit | poi
                           'address', 'lat', 'lng', 'place_name',
                           'sido_nm', 'sigungu_nm',
                           'bsst_nm', 'bsst_addr', 'telecom',  # cell_tower 시
                           'cctv_id', 'cctv_operator',          # cctv 시
                           'source_id', 'rec_created'],
            'legal_category': '위치정보'
        },

        # ═══════════════════════════════════════════════════════════════════
        # EVENT LAYER (POLE-E) — 시공간 행위
        # ═══════════════════════════════════════════════════════════════════
        'Transfer': {
            'layer': 'Event',
            'label': 'vt_transfer',
            'label_ko': '이체',
            'properties': ['event_id'],          # PK: ETL에서 DLNG_SN 값 사용
            'attributes': ['dlng_sn', 'dlng_amt', 'blnc_amt', 'dlng_se_cd',
                           'dlng_dt', 'dlng_memo_cn', 'trrc_psnnm', 'atm_mng_no',
                           'hop_level', 'is_suspicious',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '금융거래정보',
            'description': '자금 이체 행위 (Bridge Key: dlng_sn → TB_FIN_BACNT_DLNG)'
        },
        'Call': {
            'layer': 'Event',
            'label': 'vt_call',
            'label_ko': '통화',
            'properties': ['event_id'],          # PK: ETL에서 CALL_SN 값 사용
            'attributes': ['call_sn', 'call_strt_dt', 'call_dur_sec', 'call_typ_cd',
                           'dsptch_telno', 'rcptn_telno', 'bsst_loc_id',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '통신사실확인자료',
            'description': '통화 기록 (Bridge Key: call_sn → TB_TELNO_CALL_DTL)'
        },
        'Access': {
            'layer': 'Event',
            'label': 'vt_access',
            'label_ko': '접속',
            'properties': ['access_id'],         # PK: 'lgn-{lgn_sn}' 형식
            'attributes': ['lgn_sn', 'user_id', 'result_cd', 'service_nm',
                           'access_dt', 'access_type',   # V4.6 R8: web|comm|banking 서브타입 구분
                           # web 전용 5속성 (comm/banking 에선 의도적 공란 — 결함 아님):
                           'action', 'user_agent', 'status_code', 'bytes_sent', 'bytes_recv',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'access_subtypes': {                  # V4.6 R8: 서브타입별 유효 속성 매트릭스
                'web':     ['action', 'user_agent', 'status_code', 'bytes_sent', 'bytes_recv'],
                'comm':    [],   # 통신 접속 — web 5속성 미해당(공란 정상)
                'banking': [],   # 뱅킹 로그 — web 5속성 미해당(공란 정상)
            },
            'legal_category': '통신자료',
            'description': '웹/네트워크 접속 행위 web/comm/banking (Bridge Key: lgn_sn → TB_SYS_LGN_EVT). R8: 노드분할 대신 access_type 속성으로 서브타입 표현(재학습 회피)'
        },
        'Message': {
            'layer': 'Event',
            'label': 'vt_msg',
            'label_ko': '메시지',
            'properties': ['event_id'],          # PK: ETL에서 SMS_SN / MSG_SN 값 사용
            'attributes': ['msg_sn', 'msg_type', 'app_nm', 'room_id', 'dsptch_dt',
                           'content_hash', 'spam_yn', 'mentions_account',
                           'mentions_url', 'sentiment_cd',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '통신사실확인자료',
            'description': '메시지 (SMS, 메신저 등) (Bridge Key: msg_sn → TB_TELNO_SMS_MSG / TB_CHAT_MSG)'
        },
        'Movement': {
            'layer': 'Event',
            'label': 'vt_movement',
            'label_ko': '이동이벤트',
            'properties': ['mov_id'],
            'attributes': ['mov_type',  # lpr | cell_tower | transit_card | immigration
                           'timestamp', 'loc_id',
                           # lpr
                           'vhclno', 'cctv_id', 'rcgn_sn',
                           # cell_tower
                           'telno', 'evt_typ_nm', 'loc_evt_sn',
                           # transit_card
                           'card_no', 'tk_pnm', 'gf_pnm', 'vhcl_no', 'mv_sn',
                           # immigration (V4.7+ 2026-08-25: 2차년도 EP8 시나리오 요구 — 출입국 회신.
                           #   출입국일시→timestamp, 구분(출국/입국)→imgr_se_cd, 항공편→flight_no,
                           #   출입국항→port_nm(+occurred_at→vt_loc), 원본키→imgr_sn(Bridge Key).
                           #   ⚠️ 표준 DDL에 출입국 테이블 미보유 — 실데이터 확보/DA 협의 시 std_columns 확정)
                           'imgr_se_cd', 'flight_no', 'port_nm', 'imgr_sn',
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '위치정보',
            'description': 'LPR·기지국·교통카드·출입국 이동이벤트 통합 노드 (vt_lpr_evt + vt_loc_evt 대체)'
        },

        # ─────────────── V3.3 신설 ───────────────────────────────────
        'Impersonation': {
            'layer': 'Event',
            'label': 'vt_impersonation',
            'label_ko': '사칭이벤트',
            'properties': ['event_id'],
            'attributes': ['method',      # TELNO | EMAIL | ID | SITE
                           'fake_name',   # 사칭 가명 (예: '김민수 검사')
                           'script_type', # 사칭 시나리오 종류 (예: '보이스피싱-대출사기')
                           'start_dt',    # 사칭 발생/확인 시작 (= valid_from)
                           'end_dt',      # 사칭 확인 종료
                           'source_id', 'rec_created', 'verified', 'confidence'],
            'legal_category': '전기통신금융사기',
            'description': '사칭 이벤트 노드 — V3.3에서 impersonates 엣지에서 승격 (전기통신금융사기법 제3조)'
        },
    }
    
    # Layer별 엔티티 그룹 (v3.7 POLE 6레이어, 25노드)
    LAYERS = {
        'Source': ['Source'],
        'Case':   ['Case', 'Petition', 'PetitionCluster'],        # v3.7 +PetitionCluster
        'Person': ['Person', 'Organization'],
        'Object': ['BankAccount', 'CryptoWallet', 'NetworkTrace', 'WebTrace', 'SiteCluster',
                   'FileTrace', 'DigitalID', 'Email', 'Phone', 'Vehicle', 'Device', 'ATM'],  # v3.7 +SiteCluster
        'Location': ['Location'],
        'Event':  ['Transfer', 'Call', 'Access', 'Message', 'Movement', 'Impersonation'],
    }

    # ═══════════════════════════════════════════════════════════════════
    # 네이밍 통합 유틸리티 (Concept Name ↔ GDB Label 양방향 매핑)
    # ═══════════════════════════════════════════════════════════════════

    # 개념명 → GDB 라벨 매핑 (Person → vt_psn)
    GDB_LABEL_MAP = {
        'Source': 'vt_src',
        'Case': 'vt_case', 'Petition': 'vt_petition',
        'PetitionCluster': 'pt_cluster',                             # V3.7
        'Person': 'vt_psn', 'Organization': 'vt_org',
        'BankAccount': 'vt_bacnt', 'CryptoWallet': 'vt_crypto',
        'NetworkTrace': 'vt_ip', 'WebTrace': 'vt_site',
        'SiteCluster': 'site_cluster',                               # V3.7
        'FileTrace': 'vt_file',
        'DigitalID': 'vt_id', 'Email': 'vt_email',
        'Phone': 'vt_telno', 'Vehicle': 'vt_vhcl', 'Device': 'vt_dev', 'ATM': 'vt_atm',
        'Location': 'vt_loc',
        'Transfer': 'vt_transfer', 'Call': 'vt_call', 'Access': 'vt_access',
        'Message': 'vt_msg', 'Movement': 'vt_movement',
        'Impersonation': 'vt_impersonation',                         # V3.3
    }

    # GDB 라벨 → 개념명 역매핑 (vt_psn → Person)
    CONCEPT_LOOKUP = {
        'vt_src': 'Source',
        'vt_case': 'Case', 'vt_petition': 'Petition',
        'pt_cluster': 'PetitionCluster',                             # V3.7
        'vt_psn': 'Person', 'vt_org': 'Organization',
        'vt_bacnt': 'BankAccount', 'vt_crypto': 'CryptoWallet',
        'vt_ip': 'NetworkTrace', 'vt_site': 'WebTrace',
        'site_cluster': 'SiteCluster',                               # V3.7
        'vt_file': 'FileTrace',
        'vt_id': 'DigitalID', 'vt_email': 'Email',
        'vt_telno': 'Phone', 'vt_vhcl': 'Vehicle', 'vt_dev': 'Device', 'vt_atm': 'ATM',
        'vt_loc': 'Location',
        'vt_transfer': 'Transfer', 'vt_call': 'Call', 'vt_access': 'Access',
        'vt_msg': 'Message', 'vt_movement': 'Movement',
        'vt_impersonation': 'Impersonation',                         # V3.3
    }

    # GDB 라벨 → 한국어명 매핑
    LABEL_KO_MAP = {
        'vt_src': '소스',
        'vt_case': '사건', 'vt_petition': '진정서',
        'pt_cluster': '진정서군집',                                  # V3.7
        'vt_psn': '인물', 'vt_org': '조직',
        'vt_bacnt': '계좌', 'vt_crypto': '가상자산',
        'vt_ip': 'IP주소', 'vt_site': '사이트',
        'site_cluster': '피싱캠페인군집',                            # V3.7
        'vt_file': '파일',
        'vt_id': '디지털ID', 'vt_email': '이메일',
        'vt_telno': '전화번호', 'vt_vhcl': '차량', 'vt_dev': '기기', 'vt_atm': 'ATM',
        'vt_loc': '위치',
        'vt_transfer': '이체', 'vt_call': '통화', 'vt_access': '접속',
        'vt_msg': '메시지', 'vt_movement': '이동이벤트',
        'vt_impersonation': '사칭이벤트',                            # V3.3
    }

    # Layer별 GDB 라벨 그룹
    LAYERS_GDB = {
        'Source': ['vt_src'],
        'Case':   ['vt_case', 'vt_petition', 'pt_cluster'],          # V3.7 +pt_cluster
        'Person': ['vt_psn', 'vt_org'],
        'Object': ['vt_bacnt', 'vt_crypto', 'vt_ip', 'vt_site', 'site_cluster',  # V3.7 +site_cluster
                   'vt_file', 'vt_id', 'vt_email', 'vt_telno', 'vt_vhcl', 'vt_dev', 'vt_atm'],
        'Location': ['vt_loc'],
        'Event':  ['vt_transfer', 'vt_call', 'vt_access', 'vt_msg', 'vt_movement',
                   'vt_impersonation'],                               # V3.3
    }

    # ── Text2Cypher 스키마 pruning용 라벨 별칭 사전 (recall 안전장치) ──────────
    # router(LLM) semantic 예측이 놓친 노드 라벨을, 질문에 명시된 용어의 substring
    # 매칭으로 결정론적으로 보강한다. 근거: arXiv 2505.05118 (exact-match schema filtering).
    # ※ 지식 출처는 ai_service.route_question 프롬프트의 라벨 힌트와 동일 —
    #   향후 그 프롬프트를 본 dict에서 생성해 SoT 단일화 권장 (V4.3 후보).
    #   모호어(은행/번호/거래 등 다의어)는 과잉매칭 방지를 위해 의도적으로 제외.
    LABEL_ALIASES = {
        'vt_case':          ['사건', '범죄사건', '형사사건'],
        'vt_petition':      ['진정서', '진정', '신고서', '접수'],
        'vt_psn':           ['피의자', '피해자', '참고인', '용의자', '공범'],
        'vt_org':           ['조직', '단체', '범죄조직', '법인'],
        'vt_bacnt':         ['계좌', '통장', '대포통장', '계좌번호'],
        'vt_telno':         ['전화번호', '핸드폰', '휴대폰', '대포폰', '사칭번호'],
        'vt_ip':            ['아이피', '접속주소', '접속ip'],
        'vt_site':          ['사이트', '도메인', '홈페이지', '피싱사이트'],
        'vt_file':          ['악성코드', '악성파일', '해시값', '첨부파일'],
        'vt_id':            ['아이디', '계정', '닉네임'],
        'vt_email':         ['이메일', '메일주소', '이메일주소'],
        'vt_crypto':        ['가상화폐', '가상자산', '지갑주소', '코인', '블록체인', '비트코인'],
        'vt_vhcl':          ['차량', '번호판', '자동차', '차량번호'],
        'vt_dev':           ['중계기', '단말기', 'imei', 'relay'],
        'vt_atm':           ['현금인출기', '자동화기기'],
        'vt_loc':           ['위치', '좌표', '기지국', 'cctv'],
        'vt_transfer':      ['이체', '송금', '출금', '입금', '자금흐름', '자금세탁'],
        'vt_call':          ['통화', '통화내역', '전화기록'],
        'vt_access':        ['접속기록', '로그인', '접속로그'],
        'vt_msg':           ['문자메시지', '문자', '메시지', '채팅'],
        'vt_movement':      ['이동경로', '동선', '교통카드'],
        'vt_impersonation': ['사칭', '위장', '스푸핑', '기관사칭'],
    }

    @staticmethod
    def match_labels_by_keywords(question, valid_labels=None):
        """질문 텍스트에 명시된 스키마 용어를 substring 매칭해 노드 라벨을 반환.

        Text2Cypher 스키마 pruning의 recall 안전장치 — router(LLM) semantic 예측이
        놓친 라벨을 결정론적으로 보강한다. (근거: arXiv 2505.05118, exact-match filtering)
        valid_labels 지정 시 그 집합과 교차(현재 그래프에 실재하는 라벨만 반환).
        """
        if not question:
            return []
        q = str(question).lower()
        hits = []
        for label, aliases in KICSCrimeDomainOntology.LABEL_ALIASES.items():
            if valid_labels is not None and label not in valid_labels:
                continue
            if any(alias.lower() in q for alias in aliases):
                hits.append(label)
        return hits

    @classmethod
    def get_gdb_label(cls, concept_name):
        """개념명을 GDB 라벨로 변환 (Person → vt_psn)"""
        return cls.GDB_LABEL_MAP.get(concept_name, concept_name)
    
    @classmethod
    def get_concept_name(cls, gdb_label):
        """GDB 라벨을 개념명으로 변환 (vt_psn → Person)"""
        return cls.CONCEPT_LOOKUP.get(gdb_label, gdb_label)
    
    @classmethod
    def get_label_ko(cls, gdb_label):
        """GDB 라벨의 한국어명 반환 (vt_psn → 인물)"""
        return cls.LABEL_KO_MAP.get(gdb_label, gdb_label)
    
    @classmethod
    def get_relationship_gdb_labels(cls, rel_name):
        """관계 정의의 domain/range를 GDB 라벨로 반환"""
        rel = cls.RELATIONSHIPS.get(rel_name)
        if not rel:
            return None, None
        domain_gdb = cls.GDB_LABEL_MAP.get(rel['domain'], rel['domain'])
        range_gdb = cls.GDB_LABEL_MAP.get(rel['range'], rel['range'])
        return domain_gdb, range_gdb
    
    # 관계 시맨틱 (Relationship Semantics) - v3.0 통합 정의
    # source_types: LLM 추론 시 컬럼 타입 조합 → 관계 타입 결정에 사용
    RELATIONSHIPS = {
        # ═══════════════════════════════════════════════════════════
        # [CASE] 역할 엣지 — vt_psn.role 속성 → 엣지 타입으로 이전
        # ═══════════════════════════════════════════════════════════
        'suspect_in': {
            'domain': 'Person',
            'range': 'Case',
            'source_types': [('person', 'case'), ('suspect', 'case_id')],
            'semantic_relation': 'suspectIn',
            'label_ko': '피의자',
            'meaning': '인물이 사건의 피의자로 관련',
            'legal_significance': '피의자정보',
            'properties': ['confidence', 'verified', 'valid_from', 'source_id', 'rec_created']
        },
        'victim_in': {
            'domain': 'Person',
            'range': 'Case',
            'source_types': [('person', 'case'), ('victim', 'case_id')],
            'semantic_relation': 'victimIn',
            'label_ko': '피해자',
            'meaning': '인물이 사건의 피해자로 관련',
            'legal_significance': '피해자정보',
            'properties': ['damage_amount', 'valid_from', 'source_id', 'rec_created']
        },
        'witness_in': {
            'domain': 'Person',
            'range': 'Case',
            'source_types': [('person', 'case'), ('witness', 'case_id')],
            'semantic_relation': 'witnessIn',
            'label_ko': '참고인',
            'meaning': '인물이 사건의 참고인으로 관련',
            'legal_significance': '참고인진술',
            'properties': ['statement_date', 'source_id', 'rec_created']
        },
        # ═══════════════════════════════════════════════════════════
        # [ENTITY RESOLUTION] 동일인물/모순 엣지
        # ═══════════════════════════════════════════════════════════
        'same_as': {
            'domain': 'Person|DigitalID|Phone',  # V4.5 R5: 전화번호도 동일실체 해소 대상
            'range': 'Person|DigitalID|Phone',
            'source_types': [('person', 'person'), ('user_id', 'user_id')],
            'semantic_relation': 'same_as',
            'label_ko': '동일실체',
            'meaning': '두 vt_psn 또는 vt_id가 동일 실체로 해소됨 (엔티티 해소; 유사 계정 pokpok1270↔pokpokpok1270 포함)',
            'legal_significance': '신원확인',
            'properties': ['match_score', 'match_basis', 'review_status', 'rec_created'],
            'inferred': True
        },
        'contradicts': {
            'domain': 'Person',
            'range': 'Person',
            'source_types': [],
            'semantic_relation': 'contradicts',
            'label_ko': '모순정보',
            'meaning': '두 vt_psn 정보가 모순됨 (명의도용 등)',
            'legal_significance': '신원확인',
            'properties': ['conflict_field', 'conflict_detail', 'rec_created'],
            'inferred': True
        },
        # ═══════════════════════════════════════════════════════════
        # [V4.3] 시나리오 기반 직접 엣지 (속성적 연결) — 2026-08-03
        # ═══════════════════════════════════════════════════════════
        'knows': {
            'domain': 'Person',
            'range': 'Person',
            'source_types': [('person', 'person')],
            'semantic_relation': 'knows',
            'label_ko': '지인',
            'meaning': '두 인물의 사회적 지인 관계 (고향친구/동창 등, 공범 미확정 — accomplice_of와 구분)',
            'legal_significance': '관계정보',
            'properties': ['relation_type', 'confidence', 'valid_from', 'source_id', 'rec_created']
        },
        'linked_id': {
            'domain': 'Object|NetworkTrace',  # V4.5 G4: 역조회 입력이 IP인 경우
            'range': 'DigitalID',
            'source_types': [('account', 'id'), ('phone', 'id')],
            'semantic_relation': 'linkedToDigitalID',
            'label_ko': '식별자연결',
            'meaning': '계좌·전화 등 객체에 연결된 온라인 식별자 (공인인증서 발급 ID / 포털 역조회 계정)',
            'legal_significance': '신원확인',
            'properties': ['link_basis', 'confidence', 'valid_from', 'source_id', 'rec_created']
        },
        'mentions_id': {
            'domain': 'Message',
            'range': 'DigitalID',
            'source_types': [('message', 'id')],
            'semantic_relation': 'mentionsDigitalID',
            'label_ko': '계정기재',
            'meaning': '게시물/메시지에 기재된 온라인 계정 (광고글의 텔레그램 ID Zion7950 등)',
            'legal_significance': '증거물',
            'properties': ['confidence', 'source_id', 'rec_created']
        },
        # ═══════════════════════════════════════════════════════════
        # [PETITION] 진정서 관련 엣지
        # ═══════════════════════════════════════════════════════════
        'filed_as': {
            'domain': 'Petition',
            'range': 'Case',
            'source_types': [('petition', 'case')],
            'semantic_relation': 'filedAs',
            'label_ko': '사건전환',
            'meaning': '진정서가 수사 사건으로 전환됨',
            'legal_significance': '수사개시',
            'properties': ['converted_dt', 'converted_by', 'source_id', 'rec_created']
        },
        'clusters_with': {
            'domain': 'Petition',
            'range': 'Petition',
            'source_types': [],
            'semantic_relation': 'clustersWith',
            'label_ko': '유사진정서(deprecated)',
            'meaning': '[DEPRECATED v3.7] 유사 진정서 군집 연결 — belongs_to_cluster 패턴으로 교체',
            'legal_significance': None,
            'properties': ['sim_score', 'cluster_id', 'rec_created'],
            'inferred': True,
            'deprecated': True,            # v3.7: 신규 생성 금지, 레거시 조회용만 유지
            'replaced_by': 'belongs_to_cluster',
        },
        'belongs_to_cluster': {
            'domain': 'Petition',
            'range': 'PetitionCluster',
            'source_types': [],
            'semantic_relation': 'belongsToCluster',
            'label_ko': '군집소속',
            'meaning': '진정서가 진정서군집(pt_cluster) 허브 노드에 소속됨 (v3.7)',
            'legal_significance': None,
            'properties': ['sim_score', 'rec_created'],
            'inferred': True
        },
        # ═══════════════════════════════════════════════════════════
        # [New] Temporal Relationships (Dynamic Ontology)
        # ═══════════════════════════════════════════════════════════
        'uses_id': {
            'domain': 'Person',
            'range': 'DigitalID',
            'source_types': [('person', 'user_id'), ('person', 'id')],
            'semantic_relation': 'usesDigitalID',
            'label_ko': 'ID사용',
            'meaning': '인물이 플랫폼 ID/닉네임을 사용',
            'legal_significance': '신원확인',
            'properties': ['platform', 'valid_from', 'valid_to', 'source_id', 'rec_created']
        },
        'uses_email': {
            'domain': 'Person',
            'range': 'Email',
            'source_types': [('person', 'email')],
            'semantic_relation': 'usesEmail',
            'label_ko': '이메일사용',
            'meaning': '인물이 이메일 주소를 사용',
            'legal_significance': '신원확인',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']
        },
        'drives': {
            'domain': 'Person',
            'range': 'Vehicle',
            'source_types': [('person', 'vehicle')],
            'semantic_relation': 'drives',
            'label_ko': '차량운행',
            'meaning': '인물이 차량을 운행/소유',
            'legal_significance': '차량정보',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']
        },
        'recorded_in': {
            'domain': 'Any',  # Vehicle or Phone
            'range': 'Movement',
            'source_types': [('vehicle', 'movement'), ('phone', 'movement')],
            'semantic_relation': 'recordedIn',
            'label_ko': '이동기록',
            'meaning': '차량/전화번호가 이동이벤트에 기록됨',
            'legal_significance': '위치정보',
        },
        'occurred_at': {
            'domain': 'Any',  # Event nodes
            'range': 'Location',
            'source_types': [('event', 'location')],
            'semantic_relation': 'occurredAt',
            'label_ko': '발생위치',
            'meaning': '이벤트의 발생 위치',
            'legal_significance': '위치정보',
        },
        # ═══════════════════════════════════════════════════════════
        # [Layer 2 → Layer 4] Actor (행위자) → Evidence (증거) [소유관계]
        # 행위자가 직접 소유하거나 귀속된 증거 객체
        # ═══════════════════════════════════════════════════════════
        'owns': {
            'domain': 'Person',
            'range': 'Any',              # 범용 소유 (owns_phone/has_account 등으로 분기 권장)
            'source_types': [('person', 'phone')],
            'semantic_relation': 'owns',
            'label_ko': '소유',
            'meaning': '인물이 객체를 소유함 (범용 — 구체 엣지 우선 사용)',
            'legal_significance': '피의자정보',
            'properties': ['start_date', 'end_date', 'verification_source']
        },
        'owns_phone': {
            'domain': 'Person',
            'range': 'Phone',
            'source_types': [('person', 'phone'), ('user_id', 'phone')],
            'semantic_relation': 'ownsPhone',
            'label_ko': '전화소유',
            'meaning': '닉네임/인물이 전화번호를 소유함',
            'legal_significance': '통신사실확인자료',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']  # V4.6 시간순: 전화 소유/개통 유효구간(E형). 값 백필은 적재 시
        },
        'has_account': {
            'domain': 'Person',
            'range': 'BankAccount',
            'source_types': [('person', 'account'), ('user_id', 'account')],
            'semantic_relation': 'ownsFinancialResource',
            'label_ko': '계좌소유',
            'meaning': '닉네임/인물이 계좌를 소유함',
            'legal_significance': '금융거래정보',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']  # V4.6 시간순: 계좌 소유/개설 유효구간(E형). 값 백필은 적재 시
        },
        'used_ip': {
            'domain': 'Person|Phone|DigitalID|Device|BankAccount',  # V4.5 G3/G10: 전화·계정·기기(고립 IP 방지) / V4.8: 계좌 인터넷뱅킹 접속 IP(EP3 012 ipmac·EP9/10 뱅킹 IP)
            'range': 'NetworkTrace',
            'source_types': [('person', 'ip'), ('user_id', 'ip'), ('account', 'ip')],
            'semantic_relation': 'usedIPAddress',
            'label_ko': 'IP사용',
            'meaning': '닉네임/인물/계정/계좌(뱅킹 접속)가 IP 주소를 사용함. ※시각별 접속 레코드가 있는 소스는 R8 vt_access(banking)+access_via/accessed_from reification 우선, 요약 관계만 있으면 본 엣지 직결',
            'legal_significance': '디지털증거',
            'properties': ['valid_from', 'valid_to', 'confidence', 'source_id', 'rec_created']  # V4.6 S1: ip_role bitemporal 전제(시간축). 타입은 EDGE_META_SCHEMA 공통정의
        },
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 4 → Layer 4] Evidence (증거) Peer-to-Peer 연결
        # 증거 객체 간의 직접 연결 (핵심 분석 대상)
        # ═══════════════════════════════════════════════════════════
        'linked_to': {
            'domain': 'Any',
            'range': 'Any',
            'source_types': [('phone', 'account')],
            'semantic_relation': 'linkedResource',
            'label_ko': '연결됨',
            'meaning': '두 증거가 연결됨',
            'legal_significance': None
        },
        # ═══════════════════════════════════════════════════════════
        # 간접 관계 (Phase 1 확장)
        # ═══════════════════════════════════════════════════════════
        'transferred_to': {
            'domain': 'BankAccount',
            'range': 'BankAccount|CryptoWallet',      # V4.4 다형화: 가상자산 세탁 경로 포함
            'source_types': [('from_account', 'to_account'), ('sender_account', 'receiver_account')],
            'semantic_relation': 'transferredFundsTo',
            'label_ko': '이체(다단계추론)',
            'meaning': '다단계 자금 세탁 추론 엣지 — 직접 생성 금지, from/to_account Fan-out 이후 추론으로만 생성',
            'legal_significance': '금융거래정보',
            'properties': ['hop_level', 'first_dlng_dt', 'last_dlng_dt', 'txn_count', 'total_amount', 'time_basis',
                           'amount', 'transfer_date'],
            # V4.6: 추론경로(다단계)라 개별 amount/transfer_date보다 출발계좌 거래활동 기간집계가 적합 →
            #   first_dlng_dt·last_dlng_dt(거래기간)·txn_count·total_amount·time_basis 추가.
            #   개별 이체시각은 vt_transfer 이벤트 노드 소관(amount/transfer_date 하위호환 유지).
            'inferred': True,            # 추론 전용 (ETL 직접 생성 금지)
            'transitive': True,          # A→B→C 이면 A→C 추론 가능
            'inference_confidence': 0.85
        },
        'registered_to': {
            'domain': 'Phone|DigitalID', # V4.8: 포털 계정 실명확인 가입자(네이버 역조회 1,914건) — uses_id '사용자'와
            'range': 'Person',           #   registered_to '명의자' 구분이 대포계정(명의도용) 표현의 핵심이라 대체 아닌 확장
            'source_types': [('phone', 'owner'), ('phone', 'registrant'), ('user_id', 'registrant')],
            'semantic_relation': 'registeredOwner',
            'label_ko': '명의자',
            'meaning': '전화번호/플랫폼 계정의 등록(실명확인) 명의자',
            'legal_significance': '통신사실확인자료|가입자정보 제공요청(전기통신사업법 83조)',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']  # V4.6 G5: 명의 등록 유효구간(값 백필은 후속)
        },
        # ═══════════════════════════════════════════════════════════
        # [Layer 2 → Layer 2] Actor 간 관계 (KICS 확장)
        # ═══════════════════════════════════════════════════════════
        # [주의] Person→Organization 소속은 member_of / works_at 으로 분리됨
        # belongs_to (Person→Org) 중복 키 제거 — 아래 belongs_to (Account→Org) 단일 유지
        # controls 정의는 하단 [V4.0 정합화 C단계] 블록으로 단일화 (중복 제거)
        'accomplice_of': {
            'domain': 'Person',
            'range': 'Person',
            'source_types': [],
            'semantic_relation': 'accompliceOf',
            'label_ko': '공범',
            'meaning': '공범 관계',
            'legal_significance': '피의자정보',
            'inferred': True
        },
        # owns_device 정의는 하단 [V4.0 정합화 C단계] 블록으로 단일화 (deprecated·alias_of=uses_device)
        'member_of': {
            'domain': 'Person',
            'range': 'Organization',
            'source_types': [('person', 'org'), ('member', 'organization')],
            'semantic_relation': 'memberOf',
            'label_ko': '조직소속',
            'meaning': '인물이 조직(범죄단체 포함)에 소속됨',
            'legal_significance': '피의자정보',
            'properties': ['role', 'valid_from', 'valid_to', 'source_id', 'rec_created']
        },
        
        # ═══════════════════════════════════════════════════════════
        # [Layer 2 → Layer 3] Actor → Action (행위 수행)
        # [Layer 3 → Layer 4] Action → Evidence (행위가 사용한 증거)
        # ═══════════════════════════════════════════════════════════
        'from_account': {
            'domain': 'BankAccount|CryptoWallet|ATM',  # V4.4 다형화: 출금 주체 = 계좌/지갑/ATM
            'range': 'Transfer',
            'source_types': [('from_account', 'transfer'), ('출금계좌', '이체')],
            'semantic_relation': 'withdrawnFrom',
            'label_ko': '출금계좌',
            'meaning': '이체의 출금 계좌',
            'legal_significance': '금융거래정보'
        },
        'to_account': {
            'domain': 'Transfer',
            'range': 'BankAccount|CryptoWallet|ATM',   # V4.4 다형화: 입금 대상 = 계좌/지갑/ATM
            'source_types': [('transfer', 'to_account'), ('이체', '입금계좌')],
            'semantic_relation': 'depositedTo',
            'label_ko': '입금계좌',
            'meaning': '이체의 입금 계좌',
            'legal_significance': '금융거래정보'
        },
        'caller': {
            'domain': 'Phone',
            'range': 'Call',
            'source_types': [('caller', 'call'), ('발신번호', '통화')],
            'semantic_relation': 'calledFrom',
            'label_ko': '발신',
            'meaning': '통화의 발신 번호',
            'legal_significance': '통신사실확인자료'
        },
        'callee': {
            'domain': 'Call',
            'range': 'Phone',
            'source_types': [('call', 'callee'), ('통화', '수신번호')],
            'semantic_relation': 'calledTo',
            'label_ko': '수신',
            'meaning': '통화의 수신 번호',
            'legal_significance': '통신사실확인자료'
        },
        'accessed_from': {
            'domain': 'Access',
            'range': 'NetworkTrace',
            'source_types': [('access', 'ip'), ('접속', 'ip')],
            'semantic_relation': 'accessedFromIP',
            'label_ko': '접속IP',
            'meaning': '접속의 출발 IP',
            'legal_significance': '통신자료'
        },
        'sent_msg': {
            'domain': 'Phone|DigitalID',              # V4.4 다형화: 계정도 메시지 발신 주체
            'range': 'Message',
            'source_types': [('sender', 'message'), ('발신번호', '문자')],
            'semantic_relation': 'sentMessage',
            'label_ko': '발신',
            'meaning': '메시지 발신 번호',
            'legal_significance': '통신사실확인자료'
        },
        'received_msg': {                # E-4: ETL 사용 엣지 — 미등재 보완
            'domain': 'Message',
            'range': 'Phone|DigitalID',               # V4.4 다형화: 계정도 메시지 수신 주체
            'source_types': [('message', 'rcptn_telno'), ('메시지', '수신번호')],
            'semantic_relation': 'receivedByPhone',
            'label_ko': '수신번호',
            'meaning': '메시지 수신 전화번호 (received_by의 Phone 버전)',
            'legal_significance': '통신사실확인자료'
        },
        # ═══════════════════════════════════════════════════════════
        # [V4.4] 시나리오 reification 확장 — 이벤트 참여 엣지 (2026-08-03)
        # ═══════════════════════════════════════════════════════════
        'access_via': {
            'domain': 'Access',
            'range': 'Phone|DigitalID|BankAccount',
            'source_types': [('access', 'phone'), ('access', 'id'), ('access', 'account')],
            'semantic_relation': 'accessedVia',
            'label_ko': '접속수단',
            'meaning': '접속 이벤트에 사용된 통신수단/계정/모바일뱅킹 (vt_access 주체 다형)',
            'legal_significance': '통신자료',
            'properties': ['valid_from', 'confidence', 'source_id', 'rec_created']
        },
        'via_ip': {
            'domain': 'Transfer',
            'range': 'NetworkTrace',
            'source_types': [('transfer', 'ip')],
            'semantic_relation': 'transferViaIP',
            'label_ko': '이체접속IP',
            'meaning': '이체 이벤트의 접속 IP (모바일뱅킹 등)',
            'legal_significance': '통신자료',
            'properties': ['source_id', 'rec_created']
        },
        'mentions_location': {
            'domain': 'Message',
            'range': 'Location',
            'source_types': [('message', 'location')],
            'semantic_relation': 'mentionsLocation',
            'label_ko': '위치기재',
            'meaning': '메시지/게시물에 언급된 장소 (거래 장소/은닉 좌표 등)',
            'legal_significance': '증거물',
            'properties': ['confidence', 'source_id', 'rec_created']
        },
        'sourced_from': {                # §4.7 Meta/Provenance (v3.6 확정)
            'domain': 'Any',
            'range': 'Source',
            'source_types': [('node', 'src')],
            'semantic_relation': 'sourcedFrom',
            'label_ko': '출처',
            'meaning': '데이터 노드 → vt_src 역참조. tier 1~3만 엣지 생성, tier 4~5는 source_id 속성만 사용',
            'legal_significance': '수사정보',
            'properties': ['src_tier', 'rec_created']
        },
        'owns_vehicle': {                # E-6: ETL 사용 엣지 — 미등재 보완 (drives와 의미 구분)
            'domain': 'Person',
            'range': 'Vehicle',
            'source_types': [('person', 'vehicle'), ('owner', 'vhclno')],
            'semantic_relation': 'ownsVehicle',
            'label_ko': '차량소유',
            'meaning': '인물이 차량을 법적으로 소유함 (drives는 운행, owns_vehicle은 소유권)',
            'legal_significance': '차량정보',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']
        },
        # Note: Case→Action 직접 연결 제거됨 (4계층 모델 준수)
        # Case는 Actor를 통해서만 Action에 연결됨:
        # Case → Actor (involves) → Action (performed)
        
        # ═══════════════════════════════════════════════════════════
        # [Enhancement] 보강 엣지 — 교차 도메인 관계
        # ═══════════════════════════════════════════════════════════
        'related_case': {
            'domain': 'Case',
            'range': 'Case',
            'semantic_relation': 'relatedCase',
            'label_ko': '관련사건',
            'meaning': '공유 증거(계좌/전화) 기반 사건 연결',
            'inference': True,
            'confidence': 0.75,
            'legal_significance': '연쇄사건 추적'
        },
        'belongs_to': {
            'domain': 'BankAccount',
            'range': 'Organization',
            'source_types': [('account', 'org'), ('계좌', '기관')],
            'semantic_relation': 'belongsToOrg',
            'label_ko': '소속기관',
            'meaning': '계좌 소속 금융기관',
            'legal_significance': '금융거래정보'
        },
        'works_at': {
            'domain': 'Person',
            'range': 'Organization',
            'source_types': [('person', 'org'), ('인물', '조직')],
            'semantic_relation': 'worksAt',
            'label_ko': '소속',
            'meaning': '인물의 소속 조직',
            'legal_significance': '내부자 식별'
        },
        'represents': {                             # 수사단서 스키마 5건 보완 — DDL 신설 반영(TB_INST_RPRS_REL_T)
            'domain': 'Person',
            'range': 'Organization',
            'source_types': [('representative', 'organization'), ('대표', '법인')],  # PSN_ID → INST_ID
            'semantic_relation': 'represents',
            'label_ko': '대표',
            'meaning': '인물이 법인의 대표(대표이사/사내이사 등). 같은 대표의 다수 법인 탐지에 활용',
            'legal_significance': '법인등기',
            'properties': ['rprs_se_cd', 'valid_from', 'valid_to', 'source_id'],  # 대표구분·재임 유효구간
            'std_source': 'TB_INST_RPRSV_REL_T',    # 엣지 소스(기관대표자관계) — DA 확정 DDL 8/12 (RPRSV)
            'std_columns': {'rprs_se_cd': 'RPRS_SE_CD', 'valid_from': 'VLD_BGNG_DT', 'valid_to': 'VLD_END_DT', 'source_id': 'SRC_ID'}
        },
        'resolves_to': {
            'domain': 'WebTrace',        # 수정: DNS 표준 방향 — 도메인 → IP
            'range': 'NetworkTrace',
            'semantic_relation': 'resolvesToIP',
            'label_ko': 'DNS조회',
            'meaning': '도메인이 IP 주소로 조회됨 (DNS A/AAAA 레코드)',
            'source_types': [('site', 'ip'), ('domain', 'ip')],
            'inference': True,
            'legal_significance': '네트워크 추적'
        },
        'mentions_account': {
            'domain': 'Message',
            'range': 'BankAccount',
            'semantic_relation': 'mentionsAccount',
            'label_ko': '계좌언급',
            'meaning': '메시지 내 계좌번호 언급',
            'inference': True,
            'confidence': 0.85,
            'legal_significance': '보이스피싱 핵심증거'
        },

        # ═══════════════════════════════════════════════════════════
        # [사칭(Impersonation) 엣지] — 전기통신금융사기법 제3조
        # 스카이월드와이드 보완 항목 분석 반영 (2026-04-06)
        # ═══════════════════════════════════════════════════════════
        # ─────────────── V3.3 신설 엣지 ─────────────────────────────────
        'used_for': {
            'domain': 'Any',                 # vt_telno | vt_id | vt_email | vt_site
            'range': 'Impersonation',        # vt_impersonation
            'source_types': [
                ('phone', 'impersonation'), ('id', 'impersonation'),
                ('email', 'impersonation'), ('site', 'impersonation'),
            ],
            'semantic_relation': 'usedForImpersonation',
            'label_ko': '사칭수단',
            'meaning': '전화번호/계정/이메일/사이트가 사칭 이벤트의 수단으로 사용됨',
            'legal_significance': '전기통신금융사기법 제3조',
        },
        'targets': {
            'domain': 'Impersonation',       # vt_impersonation
            'range': 'Organization',         # vt_org (사칭당한 기관)
            'source_types': [('impersonation', 'org')],
            'semantic_relation': 'targetsOrganization',
            'label_ko': '사칭대상',
            'meaning': '사칭 이벤트의 타겟 기관 (사칭당한 기관)',
            'legal_significance': '전기통신금융사기법 제3조',
        },

        # ═══════════════════════════════════════════════════════════
        # [v3.4 신규] 6종 — 8대 사이버범죄 시뮬레이션 검증 완료
        # operates(5/8), recruits(4/8), blackmails(1/8),
        # hosts(2/8), contains_file(2/8), located_at(ATM 필수)
        # ═══════════════════════════════════════════════════════════
        'operates': {
            'domain': 'Person',           # Person 또는 Organization
            'range': 'Any',               # WebTrace(Site) 또는 DigitalID
            'source_types': [
                ('person', 'site'), ('org', 'site'),
                ('person', 'id'), ('org', 'id'),
            ],
            'semantic_relation': 'operatesPlatform',
            'label_ko': '운영',
            'meaning': '인물/조직이 플랫폼·채널·사이트를 운영함',
            'legal_significance': '범죄사실',
            'properties': ['valid_from', 'valid_to', 'role', 'source_id', 'rec_created']
        },
        'recruits': {
            'domain': 'Person',
            'range': 'Person',
            'source_types': [('recruiter', 'recruit'), ('person', 'person')],
            'semantic_relation': 'recruits',
            'label_ko': '모집',
            'meaning': '인물이 다른 인물을 모집함 (대포통장·판매원·투자자 유인)',
            'legal_significance': '피의자정보',
            'properties': ['recruit_type', 'date', 'source_id', 'rec_created']
        },
        'blackmails': {
            'domain': 'Person',
            'range': 'Person',
            'source_types': [('blackmailer', 'victim'), ('협박자', '피협박자')],
            'semantic_relation': 'blackmails',
            'label_ko': '협박',
            'meaning': '인물이 다른 인물을 협박함 (몸캠피싱·랜섬웨어)',
            'legal_significance': '협박죄 구성요건',
            'properties': ['method', 'date', 'source_id', 'rec_created']
        },
        'hosts': {
            'domain': 'NetworkTrace',
            'range': 'WebTrace',
            'source_types': [('ip', 'site'), ('server_ip', 'domain')],
            'semantic_relation': 'hostsWebsite',
            'label_ko': '호스팅',
            'meaning': '서버 IP가 사이트를 호스팅함 (인프라 추적)',
            'legal_significance': '네트워크 추적',
            'properties': ['port', 'detected_at', 'source_id', 'rec_created']
        },
        'contains_file': {
            'domain': 'Any',              # WebTrace·Message·DigitalID
            'range': 'FileTrace',
            'source_types': [
                ('site', 'file'), ('message', 'file'), ('id', 'file'),
            ],
            'semantic_relation': 'containsFile',
            'label_ko': '파일내장',
            'meaning': '사이트·메시지·ID가 파일을 내장/배포함 (증거물)',
            'legal_significance': '디지털증거',
            'properties': ['file_role', 'detected_at', 'source_id', 'rec_created']
        },
        # located_at 정의는 하단 [V4.0 정합화 C단계] 블록으로 단일화 (occurred_at과 구별)
        'used_in_device': {
            'domain': 'Phone',
            'range': 'Device',
            'source_types': [('phone', 'device'), ('telno', 'imei')],
            'semantic_relation': 'usedInDevice',
            'label_ko': '기기내사용',
            'meaning': '전화번호(유심)이 특정 기기(IMEI)에서 사용됨 — 동일 IMEI에 3개+ 전화번호 시 불법중계기 의심 (v3.7)',
            'legal_significance': '통신사실확인자료',
            'properties': ['first_seen', 'last_seen', 'source_id', 'rec_created']
        },
        'belongs_to_campaign': {
            'domain': 'WebTrace',
            'range': 'SiteCluster',
            'source_types': [('site', 'site_cluster')],
            'semantic_relation': 'belongsToCampaign',
            'label_ko': '캠페인소속',
            'meaning': '사이트가 피싱캠페인군집(site_cluster) 허브 노드에 소속됨 (v3.7)',
            'legal_significance': '인터넷기록',
            'properties': ['sim_score', 'detected_at', 'source_id', 'rec_created'],
            'inferred': True
        },

        # ═══════════════════════════════════════════════════════════
        # [v3.5 공식 등재] Case → Object 증거 연결 (graph_service 비공식 → 공식)
        # ═══════════════════════════════════════════════════════════
        'eg_used_account': {
            'domain': 'Case',
            'range': 'BankAccount',
            'source_types': [('case', 'account'), ('사건', '계좌')],
            'semantic_relation': 'egUsedAccount',
            'label_ko': '피해금 수령 계좌',
            'meaning': '사건에서 증거로 사용된 계좌 (피해금 수령·이체 경로)',
            'legal_significance': '금융거래정보',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']  # V4.6 G5: 계좌 유효구간(값 백필은 후속)
        },
        'eg_used_phone': {
            'domain': 'Case',
            'range': 'Phone',
            'source_types': [('case', 'phone'), ('사건', '전화번호')],
            'semantic_relation': 'egUsedPhone',
            'label_ko': '범죄 사용 전화번호',
            'meaning': '사건에서 증거로 사용된 전화번호 (보이스피싱·연락 수단)',
            'legal_significance': '통신사실확인자료',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']  # V4.6 G5: 전화 유효구간(값 백필은 후속)
        },
        'eg_used_ip': {
            'domain': 'Case',
            'range': 'NetworkTrace',
            'source_types': [('case', 'ip'), ('사건', 'ip주소')],
            'semantic_relation': 'egUsedIP',
            'label_ko': '범죄 사용 IP',
            'meaning': '사건에서 증거로 사용된 IP 주소 (접속·공격 출발지)',
            'legal_significance': '통신자료',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']  # V4.6 시간순: eg_used_account/phone 일관성(E형)
        },

        # ═══════════════════════════════════════════════════════════
        # [v3.5 공식 등재] accessed_to — Event → WebTrace
        # v3.4 문서에 "제거됨" 오기, 코드에 존재하며 설계상 필수
        # ═══════════════════════════════════════════════════════════
        'accessed_to': {
            'domain': 'Access',
            'range': 'WebTrace|BankAccount|DigitalID',  # V4.5 G8: 인터넷뱅킹 접속(계좌)·계정 접속 정식 표현
            'source_types': [('access', 'site'), ('접속', '사이트')],
            'semantic_relation': 'accessedTo',
            'label_ko': '목적지',
            'meaning': '접속이벤트의 목적지 사이트 (accessed_from과 쌍으로 사용)',
            'legal_significance': '통신자료',
            'properties': ['source_id', 'rec_created']
        },
        # ═══════════════════════════════════════════════════════════
        # [V4.0 정합화] 시각 카탈로그(EDGE_STYLE_V40)에만 있던 실사용 엣지 8종
        #   — 의미 정의를 CCOP_Ontology_V4.0.xlsx 엣지카탈로그 기준으로 등재 (2026-07-31)
        # ═══════════════════════════════════════════════════════════
        'involves': {
            'domain': 'Case',
            'range': 'Person',
            'source_types': [],
            'semantic_relation': 'involves',
            'label_ko': '사건관련',
            'meaning': '사건에 관련된 인물 (역할 미상 시 suspect_in/victim_in/witness_in 대신 사용)',
            'legal_significance': '사건관련성',
            'properties': ['source_id', 'rec_created']
        },
        'communicated_with': {
            'domain': 'NetworkTrace',
            'range': 'NetworkTrace',
            'source_types': [],
            'semantic_relation': 'communicatedWith',
            'label_ko': 'IP통신',
            'meaning': 'IP 간 직접 통신 이력',
            'legal_significance': '통신사실확인자료',
            'properties': ['source_id', 'rec_created']
        },
        'contacted': {
            'domain': 'Phone|DigitalID',   # V4.8: 카톡 '대화상대 목록'(계정간 연락관계 요약) 4,107건 실적재 반영
            'range': 'Phone|DigitalID',    #   — 개별 메시지 이벤트가 아닌 집계 관계라 sent/received_msg reification 불가
            'source_types': [],
            'semantic_relation': 'contacted',
            'label_ko': '연락관계',
            'meaning': '전화번호/메신저 계정 간 통화·연락 관계 (vt_call·대화상대 목록의 요약 엣지 성격)',
            'legal_significance': '통신사실확인자료|압수수색(메신저 대화내역)',
            'properties': ['source_id', 'rec_created', 'channel']  # V4.8: channel='call'|'kakao'|'sms' — 연락 수단 구분
        },
        'impersonates': {
            'domain': 'Person',
            'range': 'Organization',
            'source_types': [],
            'semantic_relation': 'impersonates',
            'label_ko': '사칭',
            'meaning': '인물이 기관/조직을 사칭 (v3.3에서 vt_impersonation 노드로 승격 — 본 직접 엣지는 read-only 유지)',
            'legal_significance': '사칭수법',
            'properties': ['source_id', 'rec_created']
        },
        'owns_wallet': {
            'domain': 'Person',
            'range': 'CryptoWallet',
            'source_types': [],
            'semantic_relation': 'ownsWallet',
            'label_ko': '지갑소유',
            'meaning': '인물이 가상자산 지갑을 소유',
            'legal_significance': '재산관계',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']  # V4.6 시간순: 지갑 소유/최초확인 유효구간(E형)
        },
        'performed_by': {
            'domain': 'Any',  # Access or Movement
            'range': 'Person|Phone|DigitalID|Device',  # V4.5 G1: 수행주체 확장(actor_type로 구분, 미해소 식별자 허용)
            'source_types': [],
            'semantic_relation': 'performedBy',
            'label_ko': '수행주체',
            'meaning': '접속(vt_access)·이동(vt_movement) 이벤트의 수행 주체 인물',
            'legal_significance': '행위귀속',
            'properties': ['source_id', 'rec_created']
        },
        'uses_device': {
            'domain': 'Person',
            'range': 'Device',
            'source_types': [],
            'semantic_relation': 'usesDevice',
            'label_ko': '기기사용',
            'meaning': '인물이 기기를 소유/사용',
            'legal_significance': '디지털증거',
            'properties': ['valid_from', 'valid_to', 'source_id', 'rec_created']
        },
        'verified_by': {
            'domain': 'Person',
            'range': 'Person',
            'source_types': [],
            'semantic_relation': 'verifiedBy',
            'label_ko': '검증자',
            'meaning': '수사관(인물)이 대상 정보를 검증함 (Provenance 계열)',
            'legal_significance': '증거검증',
            'properties': ['verified_dt', 'source_id', 'rec_created']
        },
        # ── [V4.0 정합화 C단계] 의미-only 였던 3종 처리 (2026-07-31) ──
        'controls': {
            'domain': 'Person',
            'range': 'BankAccount',
            'source_types': [],
            'semantic_relation': 'controls',
            'label_ko': '실질지배',
            'meaning': '인물이 계좌를 실질 지배(명의자와 무관한 실사용자) — 소유(has_account)와 구별',
            'legal_significance': '실사용자',
            'properties': ['confidence', 'source_id', 'rec_created']
        },
        'located_at': {
            'domain': 'Any',  # ATM / Organization 등 고정 객체
            'range': 'Location',
            'source_types': [],
            'semantic_relation': 'locatedAt',
            'label_ko': '위치',
            'meaning': '고정 객체(ATM·기관 등)의 정적 위치 (이벤트 경유 occurred_at과 구별)',
            'legal_significance': '위치정보',
            'properties': ['source_id', 'rec_created']
        },
        'owns_device': {
            'domain': 'Person',
            'range': 'Device',
            'source_types': [],
            'semantic_relation': 'usesDevice',
            'label_ko': '기기소유',
            'meaning': '[DEPRECATED — uses_device 사용] 인물이 기기를 소유. 신규 데이터는 uses_device로 통일',
            'legal_significance': '디지털증거',
            'deprecated': True,
            'alias_of': 'uses_device',
            'properties': ['source_id', 'rec_created']
        },
        # ══════════════════════════════════════════════════════════════════════
        # V4.5 반영 (ccop-analysis 번들 대조 — 2차년도 실적재 검증에서 발견한 신규 엣지)
        # ══════════════════════════════════════════════════════════════════════
        'sent_from_ip': {
            'domain': 'Message',
            'range': 'NetworkTrace',
            'source_types': [],
            'semantic_relation': 'sentFromIp',
            'label_ko': '발신IP',
            'meaning': '메시지가 특정 IP에서 발신됨 — 착발신내역이 메시지+접속을 한 레코드로 제공(V4.5 G2)',
            'legal_significance': '통신사실확인자료',
            'properties': ['sent_at', 'source_id', 'rec_created']
        },
        'exchanged_to': {
            'domain': 'BankAccount',
            'range': 'CryptoWallet',
            'source_types': [],
            'semantic_relation': 'exchangedTo',
            'label_ko': '환전',
            'meaning': '계좌 자금이 가상자산 지갑으로 환전됨 — 자금 종단 브리지(V4.5 G6)',
            'legal_significance': '자금추적',
            'properties': ['amount', 'exchanged_at', 'source_id', 'rec_created']
        },
        'linked_petition': {
            'domain': 'Petition',
            'range': 'Case',
            'source_types': [],
            'semantic_relation': 'linkedPetition',
            'label_ko': '진정연계',
            'meaning': '진정서가 사건에 연계됨 — 기존 linked_to(Petition→Case) 대체(V4.5 R2)',
            'legal_significance': '사건관리',
            'properties': ['source_id', 'rec_created']
        },
        'eg_used_id': {
            'domain': 'Case',
            'range': 'DigitalID',
            'source_types': [],
            'semantic_relation': 'egUsedId',
            'label_ko': '사건사용ID',
            'meaning': '사건에서 사용·언급된 디지털ID(V4.5 R3 신설)',
            'legal_significance': '수사대상',
            'properties': ['source_id', 'rec_created']
        },
        'eg_used_email': {
            'domain': 'Case',
            'range': 'Email',
            'source_types': [],
            'semantic_relation': 'egUsedEmail',
            'label_ko': '사건사용이메일',
            'meaning': '사건에서 사용·언급된 이메일(V4.5 R3 신설)',
            'legal_significance': '수사대상',
            'properties': ['source_id', 'rec_created']
        },
    }
    
    @classmethod
    def get_relationship_rules(cls):
        """LLM 추론용 관계 규칙 반환 (source_types → relation_type)"""
        rules = {}
        for rel_type, rel_def in cls.RELATIONSHIPS.items():
            for source_types in rel_def.get('source_types', []):
                rules[source_types] = {
                    'type': rel_type,
                    'description': rel_def.get('meaning', ''),
                    'legal_significance': rel_def.get('legal_significance')
                }
        return rules

    # 컬럼 타입 추론 패턴 v3.0 완전판 (ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md §8 기준)
    COLUMN_PATTERNS = {
        # ── 노드 식별 패턴 ──────────────────────────────────────────────
        'case': {
            'patterns': ['사건', 'case', '사건번호', '접수번호', 'flnm', 'incdnt_no'],
            'kics_label': 'vt_case', 'kics_property': 'flnm',
            'description': '사건번호/관리번호'
        },
        'petition': {
            'patterns': ['진정서', 'petition', '신고번호', 'dclr_sn', 'complaint', '민원'],
            'kics_label': 'vt_petition', 'kics_property': 'petition_id',
            'description': '진정서/신고접수번호'
        },
        'person': {
            'patterns': ['이름', 'name', '성명', '피해자', '피의자', '인물', 'korn_flnm'],
            'kics_label': 'vt_psn', 'kics_property': 'name',
            'description': '인물'
        },
        'suspect': {
            'patterns': ['피의자', 'suspect', '용의자', '범인', 'rrno', '주민번호'],
            'kics_label': 'vt_psn', 'kics_property': 'rrno_hash',
            'description': '피의자 식별자 (주민번호 → 해시)'
        },
        'account': {
            'patterns': ['계좌', 'account', 'bacnt', 'actno', 'bank', '은행', 'account_no'],
            'kics_label': 'vt_bacnt', 'kics_property': 'account_no',
            'description': '계좌번호'
        },
        'bank_cd': {
            'patterns': ['은행코드', 'bank_cd', 'bank_code', '금융기관코드'],
            'kics_label': 'vt_bacnt', 'kics_property': 'bank_cd', 'is_attribute': True,
            'description': '은행코드 (account_no와 복합 PK)'
        },
        'phone': {
            'patterns': ['전화', 'phone', 'telno', 'tel', 'mobile', '휴대폰', '연락처'],
            'kics_label': 'vt_telno', 'kics_property': 'telno',
            'description': '전화번호'
        },
        'ip': {
            'patterns': ['IP', 'ip주소', 'ip_addr', 'ipaddr', '아이피'],
            'kics_label': 'vt_ip', 'kics_property': 'ip_addr',
            'description': 'IP 주소'
        },
        'site': {
            'patterns': ['사이트', 'site', 'url', 'url_addr', 'domain', '웹', '링크'],
            'kics_label': 'vt_site', 'kics_property': 'url_addr',
            'description': '웹사이트/URL'
        },
        'file': {
            'patterns': ['파일', 'file', 'filename', 'file_nm', 'hash', 'hash_val'],
            'kics_label': 'vt_file', 'kics_property': 'hash_val',
            'description': '파일 (SHA-256 해시 기준)'
        },
        'user_id': {
            'patterns': ['사용자ID', 'user_id', 'login_id', 'account_id', 'uid', '아이디'],
            'kics_label': 'vt_id', 'kics_property': 'id_val',
            'description': '디지털 ID/계정'
        },
        'nickname': {
            'patterns': ['닉네임', 'nickname', 'nick', '별명', 'alias'],
            'kics_label': 'vt_id', 'kics_property': 'id_val',
            'description': '닉네임/별명'
        },
        'email': {
            'patterns': ['이메일', 'email', 'e-mail', 'mail', 'email_addr', '전자우편'],
            'kics_label': 'vt_email', 'kics_property': 'email_addr',
            'description': '이메일 주소'
        },
        'vehicle': {
            'patterns': ['차량', 'vehicle', '차량번호', 'vhclno', 'car', '번호판'],
            'kics_label': 'vt_vhcl', 'kics_property': 'vhclno',
            'description': '차량 번호'
        },
        'crypto': {
            'patterns': ['지갑', 'wallet', 'wallet_addr', '가상자산', 'crypto', 'btc', 'eth'],
            'kics_label': 'vt_crypto', 'kics_property': 'wallet_addr',
            'description': '가상자산 지갑 주소'
        },
        'atm': {
            'patterns': ['atm', 'atm_id', 'atm_mng_no', '현금인출기'],
            'kics_label': 'vt_atm', 'kics_property': 'atm_id',
            'description': 'ATM 관리번호'
        },
        'device': {
            'patterns': ['기기', 'device', 'imei', 'device_id', 'mac', 'mac_addr', '단말기', '중계기'],
            'kics_label': 'vt_dev', 'kics_property': 'device_id',
            'description': '기기 (IMEI·MAC 주소 기준 식별, relay_station 포함)'
        },
        'org': {
            'patterns': ['조직', 'org', '기관', '회사', '은행명', 'institution', 'inst_nm'],
            'kics_label': 'vt_org', 'kics_property': 'org_name',
            'description': '조직/기관명'
        },

        # ── 속성 패턴 (노드 생성 없음) ────────────────────────────────
        'date': {
            'patterns': ['일시', 'date', '시간', 'time', '발생일시', '거래일시', 'occrn_dt', 'dlng_dt'],
            'kics_label': '', 'kics_property': 'timestamp', 'is_attribute': True,
            'description': '사건/이벤트 발생 일시'
        },
        'amount': {
            'patterns': ['금액', 'amount', '거래금액', '피해금액', 'dlng_amt', 'dam_amt'],
            'kics_label': '', 'kics_property': 'amount', 'is_attribute': True,
            'description': '이체/피해 금액'
        },
        'damage_amt': {
            'patterns': ['피해금액', 'damage_amount', '피해액', 'dam_amt'],
            'kics_label': '', 'kics_property': 'damage_amount', 'is_attribute': True,
            'description': '피해 금액'
        },
        'sender': {
            'patterns': ['출금', '송금계좌', '보낸사람', 'from', 'dsptch', 'sender'],
            'kics_label': 'vt_transfer', 'kics_property': 'from_account',
            'description': '이체 출발 계좌'
        },
        'receiver': {
            'patterns': ['입금', '수취계좌', '받는사람', 'to', 'rcptn', 'receiver'],
            'kics_label': 'vt_transfer', 'kics_property': 'to_account',
            'description': '이체 도착 계좌'
        },
        'caller': {
            'patterns': ['발신', 'caller', '발신번호', 'dsptch_telno'],
            'kics_label': 'vt_telno', 'kics_property': 'telno',
            'description': '발신 번호'
        },
        'callee': {
            'patterns': ['수신', 'callee', '수신번호', 'rcptn_telno'],
            'kics_label': 'vt_telno', 'kics_property': 'telno',
            'description': '수신 번호'
        },
        'duration': {
            'patterns': ['통화시간', 'duration', 'call_dur_sec'],
            'kics_label': '', 'kics_property': 'call_dur_sec', 'is_attribute': True,
            'description': '통화 시간 (초)'
        },
        'lat': {
            'patterns': ['위도', 'lat', 'latitude', 'bsst_lat'],
            'kics_label': '', 'kics_property': 'lat', 'is_attribute': True,
            'description': '위도 좌표'
        },
        'lng': {
            'patterns': ['경도', 'lng', 'longitude', 'bsst_lot'],
            'kics_label': '', 'kics_property': 'lng', 'is_attribute': True,
            'description': '경도 좌표'
        },
        'crime': {
            'patterns': ['죄명', '범죄유형', 'crime', '범죄유형명', 'incdnt_typ_cd'],
            'kics_label': 'vt_case', 'kics_property': 'crime_type', 'is_attribute': True,
            'description': '범죄 유형/죄명'
        },
        'message': {
            'patterns': ['메시지', 'message', '내용', 'content', '문자내용', '채팅'],
            'kics_label': 'vt_msg', 'kics_property': 'content_hash',
            'description': '메시지 내용 (해시)'
        },
        'sequence': {
            'patterns': ['순번', '번호', 'seq', 'index', 'idx', 'no'],
            'kics_label': '', 'kics_property': 'seq', 'is_attribute': True,
            'description': '순서 번호'
        },
    }

    # ─────────────────────────────────────────────
    # 온톨로지 컬럼 타입 → RDB col_map 키 매핑
    # rdb_service.py에서 이 매핑을 참조하여
    # COLUMN_PATTERNS.type → col_map[key]로 변환
    # ─────────────────────────────────────────────
    COLUMN_TYPE_TO_RDB = {
        'case_id': 'case',
        'case': 'case',
        'petition': 'petition',
        'suspect': 'suspect',
        'phone': 'phone',
        'account': 'account',
        'bank_cd': 'bank_cd',
        'ip': 'ip',
        'user_id': 'user_id',
        'person': 'name',
        'nickname': 'nickname',
        'email': 'email',
        'crypto': 'crypto',
        'date': 'date',
        'amount': 'amount',
        'crime': 'crime',
        'sender': 'sender',
        'receiver': 'receiver',
        'caller': 'caller',
        'callee': 'callee',
        'duration': 'duration',
        'site': 'site',
        'file': 'file',
        'message': 'message',
        'org': 'org',
        'vehicle': 'vehicle',
        'lat': 'lat',
        'lng': 'lng',
    }
    
    # 추론 규칙(INFERENCE_RULES)은 클래스 상단으로 통합 이동 (V4.2 정합화):
    #   구 list 10종(탐지) + 구 INFERENCE_RULES_V37 4종(enrichment) → 단일 dict 13종
    #   (RelayStationDetection 중복 병합). 상단의 INFERENCE_RULES 정의를 참조.


class OntologyEnricher:
    """ETL 시 KICS 온톨로지 메타데이터 추가"""
    
    # V3.7 노드 라벨 → (ontology_type, entity_subtype, domain_concept, legal_category, layer) 직접 매핑
    _LABEL_META = {
        'vt_src':      ('Source',   'Source',          '소스',           '수사정보',           'Source'),
        'vt_case':     ('Case',     'Case',             '사건',           '수사사건',           'Case'),
        'vt_petition': ('Case',     'Petition',         '진정서',         '수사사건',           'Case'),
        'pt_cluster':  ('Case',     'PetitionCluster',  '진정서군집',     '수사사건',           'Case'),    # V3.7
        'vt_psn':      ('Person',   'Person',           '인물',           '피의자정보',         'Person'),
        'vt_org':      ('Person',   'Organization',     '조직',           '피의자정보',         'Person'),
        'vt_bacnt':    ('Object',   'BankAccount',      '계좌',           '금융거래정보',       'Object'),
        'vt_crypto':   ('Object',   'CryptoWallet',     '가상자산',       '가상자산거래정보',   'Object'),
        'vt_ip':       ('Object',   'NetworkTrace',     'IP주소',         '통신자료',           'Object'),
        'vt_site':     ('Object',   'WebTrace',         '사이트',         '인터넷기록',         'Object'),
        'site_cluster':('Object',   'SiteCluster',      '피싱캠페인군집', '인터넷기록',         'Object'),  # V3.7
        'vt_file':     ('Object',   'FileTrace',        '파일',           '디지털증거',         'Object'),
        'vt_id':       ('Object',   'DigitalID',        '디지털ID',       '신원정보',           'Object'),
        'vt_email':    ('Object',   'Email',            '이메일',         '통신자료',           'Object'),
        'vt_telno':    ('Object',   'Phone',            '전화번호',       '통신사실확인자료',   'Object'),
        'vt_vhcl':     ('Object',   'Vehicle',          '차량',           '차량정보',           'Object'),
        'vt_dev':      ('Object',   'Device',           '기기',           '디지털증거',         'Object'),
        'vt_atm':      ('Object',   'ATM',              'ATM',            '물리증거',           'Object'),
        'vt_loc':      ('Location', 'Location',         '위치',           '위치정보',           'Location'),
        'vt_transfer': ('Event',    'Transfer',         '이체이벤트',     '금융거래정보',       'Event'),
        'vt_call':     ('Event',    'Call',             '통화이벤트',     '통신사실확인자료',   'Event'),
        'vt_access':   ('Event',    'Access',           '접속이벤트',     '통신자료',           'Event'),
        'vt_msg':      ('Event',    'Message',          '메시지이벤트',   '통신사실확인자료',   'Event'),
        'vt_movement':      ('Event', 'Movement',      '이동이벤트',     '위치정보',           'Event'),
        'vt_impersonation': ('Event', 'Impersonation', '사칭이벤트',     '전기통신금융사기',   'Event'),  # V3.3
    }

    @staticmethod
    def enrich_node(node_label, properties):
        """KICS V3.2 기반 온톨로지 매핑 — 라벨 우선, 속성 보조"""
        ontology_type = "Unknown"
        entity_subtype = None
        domain_concept = "알 수 없음"
        legal_category = None
        layer = "Unknown"

        # 1) 라벨 직접 매핑 (V3.3 23노드)
        if node_label and node_label in OntologyEnricher._LABEL_META:
            ontology_type, entity_subtype, domain_concept, legal_category, layer = \
                OntologyEnricher._LABEL_META[node_label]
        else:
            # 2) 속성 기반 분류 (하위 호환)
            pass

        # 속성 기반 분류 (라벨 매핑 실패 시 fallback)
        if ontology_type == "Unknown":
            pass  # 아래 elif 체인으로 진입

        if ontology_type != "Unknown":
            # 라벨 매핑 성공 — 직접 반환
            enriched_props = properties.copy()
            enriched_props['ontology_type'] = ontology_type
            enriched_props['entity_subtype'] = entity_subtype
            enriched_props['domain_concept'] = domain_concept
            enriched_props['legal_category'] = legal_category
            enriched_props['layer'] = layer
            enriched_props['kics_compliant'] = True
            return enriched_props

        # === 속성 기반 fallback (라벨 없는 레거시 호출용) ===
        # === 소스 (Source) ===
        if 'src_id' in properties or 'reliability_tier' in properties:
            ontology_type = "Source"
            entity_subtype = "Source"
            domain_concept = "소스"
            legal_category = "수사정보"

        # === 사건 (Case) ===
        elif 'flnm' in properties or 'incdnt_no' in properties or 'receipt_no' in properties:
            ontology_type = "Case"
            entity_subtype = "Case"
            domain_concept = "사건"
            legal_category = "수사사건"

        # === 진정서 (Petition) ===
        elif 'petition_id' in properties or 'rcpt_dt' in properties:
            ontology_type = "Case"
            entity_subtype = "Petition"
            domain_concept = "진정서"
            legal_category = "수사사건"

        # === 이벤트 (Event layer) — 우선순위 높음 ===
        elif 'transfer_id' in properties or 'dlng_sn' in properties:
            ontology_type = "Event"
            entity_subtype = "Transfer"
            domain_concept = "이체이벤트"
            legal_category = "금융거래정보"

        elif 'call_id' in properties or 'call_sn' in properties:
            ontology_type = "Event"
            entity_subtype = "Call"
            domain_concept = "통화이벤트"
            legal_category = "통신사실확인자료"

        elif 'access_id' in properties:
            ontology_type = "Event"
            entity_subtype = "Access"
            domain_concept = "접속이벤트"
            legal_category = "통신자료"

        elif 'msg_id' in properties:
            ontology_type = "Event"
            entity_subtype = "Message"
            domain_concept = "메시지이벤트"
            legal_category = "통신사실확인자료"

        elif 'mov_id' in properties or 'mov_type' in properties:
            ontology_type = "Event"
            entity_subtype = "Movement"
            domain_concept = "이동이벤트"
            legal_category = "위치정보"

        elif 'fake_name' in properties or 'script_type' in properties:
            # V3.3 사칭이벤트 (vt_impersonation) — 라벨 없이 속성만으로 fallback
            ontology_type = "Event"
            entity_subtype = "Impersonation"
            domain_concept = "사칭이벤트"
            legal_category = "전기통신금융사기"

        # === 금융증거 (Object - Financial) ===
        elif 'account_no' in properties or 'actno' in properties or 'bacnt' in properties:
            ontology_type = "Object"
            entity_subtype = "BankAccount"
            domain_concept = "계좌"
            legal_category = "금융거래정보"

        elif 'wallet_addr' in properties or 'crypto_addr' in properties:
            ontology_type = "Object"
            entity_subtype = "CryptoWallet"
            domain_concept = "가상자산"
            legal_category = "가상자산거래정보"

        # === 디지털증거 (Object - Digital) ===
        elif 'ip_addr' in properties or 'ip' in properties or 'ipaddr' in properties:
            ontology_type = "Object"
            entity_subtype = "NetworkTrace"
            domain_concept = "IP주소"
            legal_category = "통신자료"

        elif 'url_addr' in properties or 'url' in properties or 'site' in properties:
            ontology_type = "Object"
            entity_subtype = "WebTrace"
            domain_concept = "사이트"
            legal_category = "인터넷기록"

        elif 'hash_val' in properties or 'file_nm' in properties or 'file' in properties or 'filename' in properties:
            ontology_type = "Object"
            entity_subtype = "FileTrace"
            domain_concept = "파일"
            legal_category = "디지털증거"

        elif 'id_val' in properties:
            ontology_type = "Object"
            entity_subtype = "DigitalID"
            domain_concept = "디지털ID"
            legal_category = "신원정보"

        elif 'email_addr' in properties:
            ontology_type = "Object"
            entity_subtype = "Email"
            domain_concept = "이메일"
            legal_category = "통신자료"

        # === 통신증거 (Object - Communication) ===
        elif 'telno' in properties or 'phone' in properties:
            ontology_type = "Object"
            entity_subtype = "Phone"
            domain_concept = "전화번호"
            legal_category = "통신사실확인자료"

        # === 차량/기기 (Object - Physical) ===
        elif 'vhclno' in properties or 'vehicle_no' in properties:
            ontology_type = "Object"
            entity_subtype = "Vehicle"
            domain_concept = "차량"
            legal_category = "차량정보"

        elif 'device_id' in properties or 'imei' in properties or 'mac_addr' in properties:
            ontology_type = "Object"
            entity_subtype = "Device"
            domain_concept = "기기"
            legal_category = "디지털증거"

        elif 'atm_id' in properties or 'atm' in properties:
            ontology_type = "Object"
            entity_subtype = "ATM"
            domain_concept = "ATM"
            legal_category = "물리증거"

        # === 인물/조직 (Person Layer) ===
        elif 'psn_id' in properties or 'name' in properties or 'korn_flnm' in properties or 'rrno_hash' in properties:
            ontology_type = "Person"
            entity_subtype = "Person"
            domain_concept = "인물"
            legal_category = "피의자정보"

        elif 'org_id' in properties or 'org_name' in properties:
            ontology_type = "Person"
            entity_subtype = "Organization"
            domain_concept = "조직"
            legal_category = "피의자정보"

        # === 위치 (Location Layer) ===
        elif 'loc_id' in properties:
            ontology_type = "Location"
            entity_subtype = "Location"
            domain_concept = "위치"
            legal_category = "위치정보"
        
        # ontology_type → layer 매핑 (fallback용)
        _type_to_layer = {
            'Source': 'Source', 'Case': 'Case', 'Person': 'Person',
            'Object': 'Object', 'Location': 'Location', 'Event': 'Event',
        }
        layer = _type_to_layer.get(ontology_type, 'Unknown')

        # 메타데이터 추가
        enriched_props = properties.copy()
        enriched_props['ontology_type'] = ontology_type
        enriched_props['entity_subtype'] = entity_subtype if entity_subtype else ontology_type
        enriched_props['domain_concept'] = domain_concept
        enriched_props['legal_category'] = legal_category
        enriched_props['layer'] = layer
        enriched_props['kics_compliant'] = True

        return enriched_props

    @staticmethod
    def enrich_edge(edge_type, properties):
        """KICS 기반 엣지 온톨로지 매핑"""
        semantic_relation = edge_type
        domain_meaning = edge_type
        legal_significance = None
        
        # V3.2 KICS 엣지 타입별 의미론적 관계 매핑 (53개 관계)
        EDGE_SEMANTICS = {
            # ── Person → Case (역할 엣지) ──
            'suspect_in':     {'semantic_relation': 'suspectIn',         'domain_meaning': '피의자로 관련된 사건',     'legal_significance': '피의자정보'},
            'victim_in':      {'semantic_relation': 'victimIn',          'domain_meaning': '피해자로 관련된 사건',     'legal_significance': '피해자정보'},
            'witness_in':     {'semantic_relation': 'witnessIn',         'domain_meaning': '참고인으로 관련된 사건',   'legal_significance': '참고인진술'},
            # ── Petition 관계 ──
            'filed_as':       {'semantic_relation': 'filedAs',           'domain_meaning': '진정서 → 사건 전환',       'legal_significance': '수사개시'},
            'clusters_with':  {'semantic_relation': 'clustersWith',      'domain_meaning': '유사 진정서 군집',         'legal_significance': None},
            # ── Person 관계 ──
            'same_as':         {'semantic_relation': 'same_as',            'domain_meaning': '동일인물 해소',            'legal_significance': '신원확인'},
            'contradicts':    {'semantic_relation': 'contradicts',       'domain_meaning': '모순 정보',                'legal_significance': '신원확인'},
            'impersonates':   {'semantic_relation': 'impersonates',      'domain_meaning': '사칭 대상(구)',            'legal_significance': '사기범죄'},
            'represents':     {'semantic_relation': 'represents',        'domain_meaning': '법인 대표',                'legal_significance': '법인등기'},
            # V3.3 사칭 노드 패턴
            'used_for':       {'semantic_relation': 'usedForImpersonation','domain_meaning': '사칭 수단',              'legal_significance': '전기통신금융사기법 제3조'},
            'targets':        {'semantic_relation': 'targetsOrganization', 'domain_meaning': '사칭 대상 기관',         'legal_significance': '전기통신금융사기법 제3조'},
            'accomplice_of':  {'semantic_relation': 'accompliceOf',      'domain_meaning': '공범 관계',                'legal_significance': '공모사실'},
            # ── 소유/사용 ──
            'owns':           {'semantic_relation': 'owns',              'domain_meaning': '소유',                    'legal_significance': '소유관계'},
            'has_account':    {'semantic_relation': 'hasFinancialAccount','domain_meaning': '계좌 보유',               'legal_significance': '금융거래정보'},
            'uses':           {'semantic_relation': 'uses',              'domain_meaning': '사용',                    'legal_significance': '증거물'},
            'controls':       {'semantic_relation': 'controls',          'domain_meaning': '통제',                    'legal_significance': '범죄사실'},
            'drives':         {'semantic_relation': 'drives',            'domain_meaning': '차량 운전',               'legal_significance': '차량정보'},
            'located_at':     {'semantic_relation': 'locatedAt',         'domain_meaning': '위치',                    'legal_significance': '위치정보'},
            'belongs_to':     {'semantic_relation': 'belongsTo',         'domain_meaning': '소속',                    'legal_significance': '조직관계'},
            # ── 이체 관계 ──
            'from_account':   {'semantic_relation': 'fromAccount',       'domain_meaning': '출금 계좌',               'legal_significance': '금융거래정보'},
            'to_account':     {'semantic_relation': 'toAccount',         'domain_meaning': '입금 계좌',               'legal_significance': '금융거래정보'},
            'transferred_to': {'semantic_relation': 'transferredTo',     'domain_meaning': '이체 대상',               'legal_significance': '금융거래정보'},
            'eg_used_account':{'semantic_relation': 'egUsedAccount',     'domain_meaning': '피해금 수령 계좌',         'legal_significance': '금융거래정보'},
            # ── 통화 관계 ──
            'caller':         {'semantic_relation': 'caller',            'domain_meaning': '발신자',                  'legal_significance': '통신사실확인자료'},
            'callee':         {'semantic_relation': 'callee',            'domain_meaning': '수신자',                  'legal_significance': '통신사실확인자료'},
            'contacted':      {'semantic_relation': 'contacted',         'domain_meaning': '연락',                    'legal_significance': '통신사실확인자료'},
            'communicated_with':{'semantic_relation':'communicatedWith', 'domain_meaning': '통신 관계',               'legal_significance': '통신자료'},
            # ── 접속/디지털 ──
            'accessed':       {'semantic_relation': 'accessed',          'domain_meaning': '접속',                    'legal_significance': '통신자료'},
            'accessed_from':  {'semantic_relation': 'accessedFrom',      'domain_meaning': '출발 IP',                 'legal_significance': '통신자료'},
            'accessed_to':    {'semantic_relation': 'accessedTo',        'domain_meaning': '목적지',                  'legal_significance': '통신자료'},
            'linked_to':      {'semantic_relation': 'linkedTo',          'domain_meaning': '연결',                    'legal_significance': '디지털증거'},
            'eg_used_ip':     {'semantic_relation': 'egUsedIP',          'domain_meaning': '범죄 사용 IP',            'legal_significance': '통신자료'},
            'eg_used_phone':  {'semantic_relation': 'egUsedPhone',       'domain_meaning': '범죄 사용 전화번호',      'legal_significance': '통신사실확인자료'},
            # ── 이동 ──
            'movement_from':  {'semantic_relation': 'movementFrom',      'domain_meaning': '출발 위치',               'legal_significance': '위치정보'},
            'movement_to':    {'semantic_relation': 'movementTo',        'domain_meaning': '도착 위치',               'legal_significance': '위치정보'},
            # ── V3.7 신규 엣지 ──
            'belongs_to_cluster':{'semantic_relation': 'belongsToCluster',  'domain_meaning': '진정서 → 군집 소속',  'legal_significance': None},
            'used_in_device':    {'semantic_relation': 'usedInDevice',      'domain_meaning': '유심 → 기기 사용',    'legal_significance': '통신사실확인자료'},
            'belongs_to_campaign':{'semantic_relation': 'belongsToCampaign','domain_meaning': '사이트 → 캠페인 소속','legal_significance': '인터넷기록'},
            # ── 진정서/ETRI ──
            'connects_to':    {'semantic_relation': 'connectsTo',        'domain_meaning': 'C2 연결',                 'legal_significance': '디지털증거'},
            'drops':          {'semantic_relation': 'drops',             'domain_meaning': '악성파일 드롭',           'legal_significance': '디지털증거'},
            'part_of_campaign':{'semantic_relation':'partOfCampaign',    'domain_meaning': '캠페인 소속',             'legal_significance': '디지털증거'},
            # ── Deprecated 호환 ──
            'involves':       {'semantic_relation': 'involvesPerson',    'domain_meaning': '관련 인물 (구버전)',       'legal_significance': '피의자정보'},
            'involves_org':   {'semantic_relation': 'involvesOrg',       'domain_meaning': '관련 조직 (구버전)',       'legal_significance': '피의자정보'},
            # ── 레거시 ──
            'digital_trace':  {'semantic_relation': 'investigatesDigitalTrace','domain_meaning': '디지털 흔적',       'legal_significance': '디지털증거'},
            'used_account':   {'semantic_relation': 'usedFinancialResource',   'domain_meaning': '금융 계좌 사용',    'legal_significance': '금융거래정보'},
            'used_phone':     {'semantic_relation': 'usedCommunicationDevice', 'domain_meaning': '전화번호 사용',     'legal_significance': '통신사실확인자료'},
            'visited_site':   {'semantic_relation': 'visitedWebsite',          'domain_meaning': '사이트 방문',       'legal_significance': '인터넷기록'},
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
                # Fix #1: Event 노드 인식 추가
                elif 'event_type' in props or 'event_id' in props:
                    concept = 'Event'
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
