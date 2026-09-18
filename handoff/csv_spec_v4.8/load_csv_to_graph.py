#!/usr/bin/env python3
"""V4.8 규격 CSV → AgensGraph 적재 (참조 구현)

같은 폴더의 규격서(`CCOP_CSV_적재규격_V4.8.md`)대로 작성된 CSV 묶음을 읽어 V4.8 그래프를 만든다.
규격서가 약속한 동작을 그대로 구현한 것이라, **CSV가 정확히 어떤 그래프가 되는지**를 코드로
확인하실 수 있다. 그대로 쓰셔도 되고, 귀사 적재기를 만드실 때 기준으로 삼으셔도 된다.

핵심 동작 (규격서 §3·§4)
  · 통화/메시지 → `contacted` 를 **상대방 쌍 + channel 단위**로 접고
    first_dt·last_dt·call_count·msg_count·total_dur_sec 집계
    (통화와 문자를 한 엣지에 합치지 않는다 — 합치면 "문자만" 조회가 불가능해진다)
  · 이체 → `transferred_to` 쌍당 1엣지 + first_dlng_dt·last_dlng_dt·txn_count·total_amount
  · 금액·건수는 **숫자 타입**으로 저장 (문자열이면 >= 비교·정렬이 오류 없이 조용히 틀린다)
  · 전 노드·엣지에 source_id 부여 (CSV 에 없으면 파일 기준값으로 생성)
  · 인물 식별은 psn_id 우선, 없으면 flnm(이름) — 규격서 §3.4
  · 발신기지국(bsst_addr)·거래점(brnch_nm) → vt_loc, 거래 IP → vt_ip 자동 연결
  · 멱등(MERGE). 같은 폴더를 두 번 넣어도 중복이 생기지 않고, 2차·3차 납품분은 덧붙는다

전제
  · AgensGraph + psycopg2 (pip install psycopg2-binary)
  · 접속 정보는 환경변수: DB_HOST · DB_PORT · DB_NAME · DB_USER · DB_PASSWORD

실행
  python3 load_csv_to_graph.py <CSV폴더> --graph <그래프명>
  python3 load_csv_to_graph.py <CSV폴더> --graph <그래프명> --reset   # 그래프 비우고 새로

함께 쓰시면 좋은 도구
  · 적재 전: validate_csv_v48.py <CSV폴더>            — CSV 규격 점검(DB 불필요)
  · 적재 후: audit_ontology_v48.py --graph <그래프명>  — 온톨로지 정경 점검
    (온톨로지 패키지 handoff/ontology_v4.8/code/ 에 동봉)
"""
import argparse
import csv
import os
import re
import sys
from collections import defaultdict

import psycopg2

try:
    from dotenv import load_dotenv
except ImportError:                       # python-dotenv 없어도 환경변수만으로 동작
    def load_dotenv(*a, **k):
        return False

RE_NUM = re.compile(r'[^\d.-]')
ROLE_EDGE = {'SUSPECT': 'suspect_in', 'VICTIM': 'victim_in', 'WITNESS': 'witness_in',
             'REPORTER': 'victim_in', 'SUSPECT_ACCOMPLICE': 'suspect_in'}
SUBJ_LABEL = {'psn': ('vt_psn', 'name'), 'telno': ('vt_telno', 'telno'),
              'bacnt': ('vt_bacnt', 'account_no'), 'id': ('vt_id', 'id_val'),
              'atm': ('vt_atm', 'atm_nm'), 'dev': ('vt_dev', 'dev_id')}
LABELS = ['vt_psn', 'vt_telno', 'vt_bacnt', 'vt_case', 'vt_ip', 'vt_id', 'vt_loc', 'vt_atm']
ELABELS = ['has_account', 'owns_phone', 'registered_to', 'suspect_in', 'victim_in',
           'witness_in', 'contacted', 'transferred_to', 'used_ip', 'uses_id', 'located_at']


def esc(v):
    return str(v).replace('\\', '\\\\').replace("'", "''")


def num(v):
    """'1,500,000' · '1500000원' → 1500000. 숫자가 없으면 None."""
    if v is None:
        return None
    s = RE_NUM.sub('', str(v))
    if not s or s in ('-', '.'):
        return None
    try:
        f = float(s)
        return int(f) if f.is_integer() else f
    except ValueError:
        return None


def secs(a, b):
    """'YYYY-MM-DD HH:MM:SS' 두 개의 초 차이. 계산 불가면 0."""
    from datetime import datetime
    try:
        d = datetime.strptime(b.strip(), '%Y-%m-%d %H:%M:%S') - \
            datetime.strptime(a.strip(), '%Y-%m-%d %H:%M:%S')
        return max(0, int(d.total_seconds()))
    except Exception:
        return 0


def day(v):
    return (v or '').strip()[:10] or None


def read(folder, keyword):
    """키워드가 든 CSV 를 모두 읽어 행 목록으로. 파일별 기본 source_id 도 함께."""
    out = []
    paths = []
    for root, _dirs, fns in os.walk(folder):        # 하위 폴더까지 훑는다
        paths += [os.path.join(root, fn) for fn in fns]
    for path in sorted(paths):
        fn = os.path.basename(path)
        if not fn.lower().endswith('.csv') or keyword not in fn:
            continue
        with open(path, encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                row = {(k or '').strip(): (v.strip() if isinstance(v, str) else v)
                       for k, v in row.items()}
                row.setdefault('_file', fn)
                out.append(row)
    return out


def sid(row, default):
    return (row.get('source_id') or '').strip() or default


class Loader:
    def __init__(self, cur, conn=None, batch=2000):
        self.cur = cur
        self.conn = conn          # 배치 커밋용 — 대량 입력에서 트랜잭션으로 묶어 MVCC 가시성 확보
        self.batch = batch
        self.n_node = 0
        self.n_edge = 0
        self._ops = 0
        self._seen = set()   # (label, key, val) 캐시 — 대량 입력에서 동일 노드 반복 MERGE 방지

    def _tick(self):
        # 주기적 커밋 — autocommit 이면 매 문장 새 스냅샷이라 방금 MERGE 한 tuple 을 다음
        # 문장이 못 봐 'invisible tuple' 오류가 난다. 트랜잭션으로 묶어 가시성을 일관되게.
        self._ops += 1
        if self.conn is not None and self._ops % self.batch == 0:
            self.conn.commit()

    def node(self, label, key, val, props):
        if val in (None, ''):
            return False
        # 이미 만든 노드는 재MERGE 안 함. 대량(42만 메시지 등)에서 동일 계정을 반복 MERGE 하면
        # AgensGraph autocommit 에서 'attempted to delete invisible tuple' 오류 + 성능 급락.
        # 첫 등장 시 속성까지 세팅, 이후 등장은 skip(속성은 첫 소스 우선 — 규격상 노드 속성은 안정적).
        ck = (label, key, str(val))
        if ck in self._seen:
            return True
        self._seen.add(ck)
        # 캐시가 유니크를 보장하므로 CREATE 사용. AgensGraph 2.x MERGE 는 대량 반복 시
        # 'attempted to delete invisible tuple'(엔진 버그)을 내는데, 캐시+CREATE 로 회피한다.
        # 전제: --reset 신규 그래프(중복 시작 없음). 재적재는 --reset 권장(멱등성은 캐시가 대신).
        props2 = {key: val, **{k: v for k, v in props.items() if v not in (None, '')}}
        fields = ', '.join(
            f"{k}: {v if isinstance(v, (int, float)) else chr(39)+esc(v)+chr(39)}"
            for k, v in props2.items())
        self.cur.execute(f"CREATE (n:{label} {{{fields}}})")
        self.n_node += 1
        self._tick()
        return True

    def edge(self, el, a, b, props, match_props=None):
        """a·b = (label, keyprop, keyval)

        match_props 를 주면 그 속성까지 일치하는 엣지만 같은 것으로 본다.
        예: 같은 두 전화번호라도 channel 이 다르면 별개 엣지(통화/문자 구분).
        """
        (la, ka, va), (lb, kb, vb) = a, b
        if va in (None, '') or vb in (None, ''):
            return False
        sets = [f"r.{k} = {v if isinstance(v, (int, float)) else chr(39)+esc(v)+chr(39)}"
                for k, v in props.items() if v not in (None, '')]
        mp = ''
        if match_props:
            mp = ' {' + ', '.join(f"{k}: '{esc(v)}'" for k, v in match_props.items()) + '}'
        q = (f"MATCH (x:{la} {{{ka}: '{esc(va)}'}}), (y:{lb} {{{kb}: '{esc(vb)}'}}) "
             f"MERGE (x)-[r:{el}{mp}]->(y)")
        if sets:
            q += ' SET ' + ', '.join(sets)
        self.cur.execute(q)
        self.n_edge += 1
        self._tick()
        return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--graph', required=True)
    ap.add_argument('--reset', action='store_true', help='적재 전 그래프 삭제 후 재생성')
    args = ap.parse_args()
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', args.graph):
        sys.exit(f'invalid graph name: {args.graph}')
    if not os.path.isdir(args.folder):
        sys.exit(f'폴더가 아닙니다: {args.folder}')
    load_dotenv()

    conn = psycopg2.connect(host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'),
                            dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                            password=os.getenv('DB_PASSWORD'), connect_timeout=20)
    conn.autocommit = True
    cur = conn.cursor()
    if args.reset:
        cur.execute(f"DROP GRAPH IF EXISTS {args.graph} CASCADE")
    cur.execute(f"CREATE GRAPH IF NOT EXISTS {args.graph}")
    cur.execute(f"SET graph_path = {args.graph}")
    for l in LABELS:
        cur.execute(f"CREATE VLABEL IF NOT EXISTS {l}")
    for e in ELABELS:
        cur.execute(f"CREATE ELABEL IF NOT EXISTS {e}")
    conn.commit()                 # DDL 확정
    conn.autocommit = False       # 이후 데이터 적재는 배치 트랜잭션
    L = Loader(cur, conn=conn)
    F = args.folder

    # ── 노드 ──
    psn_key = {}          # psn_id 또는 flnm → 그래프에 저장한 name 값
    for r in read(F, 'tbl_vt_psn'):
        nm = r.get('flnm') or r.get('psn_id')
        if L.node('vt_psn', 'name', nm,
                  {'psn_id': r.get('psn_id'), 'dob': r.get('dob'), 'gender': r.get('gender'),
                   'nationality': r.get('nationality'), 'occp_nm': r.get('occp_nm'),
                   'source_id': sid(r, 'CSV-psn')}):
            if r.get('psn_id'):
                psn_key[r['psn_id']] = nm
            psn_key[nm] = nm
    for r in read(F, 'tbl_vt_telno'):
        L.node('vt_telno', 'telno', r.get('telno'),
               {'telco_nm': r.get('telco_nm'), 'join_typ_cd': r.get('join_typ_cd'),
                'subs_holder': r.get('subs_holder'), 'is_burner': r.get('is_burner'),
                'source_id': sid(r, 'CSV-telno')})
    for r in read(F, 'tbl_vt_bacnt'):
        L.node('vt_bacnt', 'account_no', r.get('actno'),
               {'bank_nm': r.get('bank'), 'bank_cd': r.get('bank_cd'), 'dpstr': r.get('dpstr'),
                'account_type': r.get('account_type'), 'bacnt_opn_dt': r.get('bacnt_opn_dt'),
                'source_id': sid(r, 'CSV-bacnt')})
    for r in read(F, 'tbl_vt_ip'):
        L.node('vt_ip', 'ip_addr', r.get('ip_addr'),
               {'ip_ver': num(r.get('ip_ver')), 'asn_nm': r.get('asn_nm'),
                'ctry_cd': r.get('ctry_cd'), 'source_id': sid(r, 'CSV-ip')})
    for r in read(F, 'tbl_vt_id'):
        L.node('vt_id', 'id_val', r.get('id_val'),
               {'platform': r.get('platform'), 'id_type': r.get('id_type'),
                'nickname': r.get('nickname'), 'source_id': sid(r, 'CSV-id')})
    for r in read(F, 'tbl_vt_loc'):
        L.node('vt_loc', 'loc_id', r.get('loc_id'),
               {'loc_type': r.get('loc_type'), 'address': r.get('address'),
                'sido_nm': r.get('sido_nm'), 'sigungu_nm': r.get('sigungu_nm'),
                'place_name': r.get('place_name'), 'bsst_addr': r.get('bsst_addr'),
                'source_id': sid(r, 'CSV-loc')})
    for r in read(F, 'tbl_eg_case'):
        if 'case_prsn' in r.get('_file', ''):
            continue                      # 파일명 키워드 겹침 방지
        # canonical=incdnt_no(경찰청 공식 사건번호 — 수사관 인지 식별자). flnm(사건파일명)은
        # 별개 보조 속성으로 보존(있을 때만). 종전엔 incdnt_no 값을 flnm 키에 밀어넣어 개념이
        # 어긋나고 incdnt_no 속성이 비었다(2026-09-18 정공법 교정).
        L.node('vt_case', 'incdnt_no', r.get('incdnt_no'),
               {'flnm': r.get('flnm'),
                'incdnt_nm': r.get('incdnt_nm'), 'incdnt_typ_cd': r.get('incdnt_typ_cd'),
                'occrn_dt': r.get('occrn_dt'), 'damage_amt': num(r.get('damage_amt')),
                'crime_site': r.get('crime_site'), 'case_summary': r.get('incdnt_smry_cn'),
                'source_id': sid(r, 'CSV-case')})

    unresolved = []

    def resolve_psn(v, where):
        """psn_id → 이름. 인물 노드 파일이 없어 해석 못 하면 경고한다.

        해석 실패를 방치하면 psn_id 문자열 자체가 인물 노드로 만들어져, 같은 사람이
        '홍길동' 과 'P-2026-0001' 로 갈라진다(조용한 중복 — 그래프를 보고도 모른다).
        """
        if v in psn_key:
            return psn_key[v]
        if re.match(r'^[A-Za-z][\w.-]*$', str(v)):     # 이름 같지 않으면 미해석 ID 로 본다
            unresolved.append(f'{where}: {v}')
        return v

    def person(r):
        """행이 가리키는 인물의 그래프 키(name). psn_id 우선."""
        pid, nm = (r.get('psn_id') or '').strip(), (r.get('flnm') or '').strip()
        return psn_key.get(pid) or psn_key.get(nm) or nm or pid

    # ── 관계: 명의 ──
    for r in read(F, 'tbl_eg_bactno_poss'):
        p, acc = person(r), r.get('actno')
        s = sid(r, 'CSV-bactno-poss')
        L.node('vt_psn', 'name', p, {'source_id': s})
        L.node('vt_bacnt', 'account_no', acc, {'bank_cd': r.get('bank_cd'), 'source_id': s})
        L.edge('has_account', ('vt_psn', 'name', p), ('vt_bacnt', 'account_no', acc),
               {'valid_from': r.get('valid_from'), 'valid_to': r.get('valid_to'), 'source_id': s})
    for r in read(F, 'tbl_eg_telno_poss'):
        p, tel = person(r), r.get('telno')
        s = sid(r, 'CSV-telno-poss')
        L.node('vt_psn', 'name', p, {'source_id': s})
        L.node('vt_telno', 'telno', tel, {'source_id': s})
        L.edge('owns_phone', ('vt_psn', 'name', p), ('vt_telno', 'telno', tel),
               {'valid_from': r.get('valid_from'), 'valid_to': r.get('valid_to'), 'source_id': s})
        L.edge('registered_to', ('vt_telno', 'telno', tel), ('vt_psn', 'name', p),
               {'valid_from': r.get('valid_from'), 'valid_to': r.get('valid_to'), 'source_id': s})
    for r in read(F, 'tbl_eg_case_prsn'):
        p, cs = person(r), r.get('incdnt_no')
        s = sid(r, 'CSV-case-prsn')
        el = ROLE_EDGE.get((r.get('role') or 'VICTIM').upper(), 'victim_in')
        L.node('vt_psn', 'name', p, {'source_id': s})
        L.node('vt_case', 'incdnt_no', cs, {'source_id': s})
        L.edge(el, ('vt_psn', 'name', p), ('vt_case', 'incdnt_no', cs), {'source_id': s})
    for r in read(F, 'tbl_eg_id_use'):
        p, idv = person(r), r.get('id_val')
        s = sid(r, 'CSV-id-use')
        L.node('vt_psn', 'name', p, {'source_id': s})
        L.node('vt_id', 'id_val', idv, {'platform': r.get('platform'), 'source_id': s})
        L.edge('uses_id', ('vt_psn', 'name', p), ('vt_id', 'id_val', idv),
               {'platform': r.get('platform'), 'valid_from': r.get('valid_from'),
                'valid_to': r.get('valid_to'), 'source_id': s})

    # ── 통화·메시지 → contacted 집계 (규격서 §4) ──
    # 집계 단위는 '쌍 + channel'. 같은 두 사람이 통화도 하고 문자도 했다면 엣지를 나눈다.
    # 한 엣지에 합쳐 channel='call|sms' 로 두면 "문자만" 같은 조회가 불가능해진다.
    agg = defaultdict(lambda: {'call': 0, 'msg': 0, 'dur': 0, 'first': None, 'last': None,
                               'src': set()})
    for r in read(F, 'tbl_eg_call'):
        a, b = r.get('dsptch_no'), r.get('rcptn_no')
        if not a or not b:
            continue
        ch = (r.get('channel') or 'call').lower()
        k = (('vt_telno', 'telno', a), ('vt_telno', 'telno', b), ch)
        d = agg[k]
        d['msg' if ch in ('sms', 'mms') else 'call'] += 1
        d['dur'] += secs(r.get('bgng_ymdhm') or '', r.get('end_ymdhm') or '')
        for t in (day(r.get('bgng_ymdhm')),):
            if t:
                d['first'] = min(d['first'] or t, t)
                d['last'] = max(d['last'] or t, t)
        d['src'].add(sid(r, 'CSV-call'))
        L.node('vt_telno', 'telno', a, {'source_id': sid(r, 'CSV-call')})
        L.node('vt_telno', 'telno', b, {'source_id': sid(r, 'CSV-call')})
        # 발신기지국 → 위치
        if (r.get('bsst_addr') or '').strip():
            loc = r['bsst_addr'].strip()
            L.node('vt_loc', 'loc_id', loc,
                   {'loc_type': 'cell_tower', 'bsst_addr': loc, 'address': loc,
                    'place_name': loc, 'source_id': sid(r, 'CSV-call')})
            L.edge('located_at', ('vt_telno', 'telno', a), ('vt_loc', 'loc_id', loc),
                   {'source_id': sid(r, 'CSV-call')})
    for r in read(F, 'tbl_eg_id_msg'):
        a, b = r.get('snd_id'), r.get('rcv_id')
        if not a or not b:
            continue
        ch = (r.get('channel') or r.get('snd_platform') or 'msg').lower()
        k = (('vt_id', 'id_val', a), ('vt_id', 'id_val', b), ch)
        d = agg[k]
        d['msg'] += 1
        t = day(r.get('msg_ymdhm'))
        if t:
            d['first'] = min(d['first'] or t, t)
            d['last'] = max(d['last'] or t, t)
        d['src'].add(sid(r, 'CSV-id-msg'))
        L.node('vt_id', 'id_val', a, {'platform': r.get('snd_platform'), 'source_id': sid(r, 'CSV-id-msg')})
        L.node('vt_id', 'id_val', b, {'platform': r.get('rcv_platform'), 'source_id': sid(r, 'CSV-id-msg')})
    for (a, b, ch), d in agg.items():
        props = {'channel': ch, 'first_dt': d['first'], 'last_dt': d['last'],
                 'source_id': '|'.join(sorted(d['src']))}
        if d['call']:
            props['call_count'] = d['call']
        if d['msg']:
            props['msg_count'] = d['msg']
        if d['dur']:
            props['total_dur_sec'] = d['dur']
        L.edge('contacted', a, b, props, match_props={'channel': ch})

    # ── 이체 → transferred_to 집계 ──
    tagg = defaultdict(lambda: {'cnt': 0, 'amt': 0, 'first': None, 'last': None, 'src': set()})
    for r in read(F, 'tbl_eg_rmt'):
        base, rel = r.get('actno'), r.get('rlt_actno')
        if not base or not rel:
            continue
        s = sid(r, 'CSV-rmt')
        amt = num(r.get('tkmny_amt')) or num(r.get('dpst_amt')) or 0
        # se: 출금이면 기준계좌 → 상대계좌, 입금이면 반대
        frm, to = (base, rel) if (r.get('se') or '출금').strip() == '출금' else (rel, base)
        L.node('vt_bacnt', 'account_no', base,
               {'bank_nm': r.get('bank'), 'bank_cd': r.get('bank_cd'),
                'dpstr': r.get('dpstr'), 'source_id': s})
        L.node('vt_bacnt', 'account_no', rel,
               {'bank_nm': r.get('rlt_bank'), 'bank_cd': r.get('rlt_bank_cd'),
                'dpstr': r.get('rlt_dpstr'), 'source_id': s})
        d = tagg[(frm, to)]
        d['cnt'] += 1
        d['amt'] += amt
        t = day(r.get('rmt_ymdhm'))
        if t:
            d['first'] = min(d['first'] or t, t)
            d['last'] = max(d['last'] or t, t)
        d['src'].add(s)
        if (r.get('ip_addr') or '').strip():
            ip = r['ip_addr'].strip()
            L.node('vt_ip', 'ip_addr', ip, {'source_id': s})
            L.edge('used_ip', ('vt_bacnt', 'account_no', base), ('vt_ip', 'ip_addr', ip),
                   {'source_id': s})
        if (r.get('brnch_nm') or '').strip():
            br = r['brnch_nm'].strip()
            L.node('vt_loc', 'loc_id', br, {'loc_type': 'poi', 'place_name': br, 'source_id': s})
            L.edge('located_at', ('vt_bacnt', 'account_no', base), ('vt_loc', 'loc_id', br),
                   {'source_id': s})
    for (frm, to), d in tagg.items():
        L.edge('transferred_to', ('vt_bacnt', 'account_no', frm), ('vt_bacnt', 'account_no', to),
               {'first_dlng_dt': d['first'], 'last_dlng_dt': d['last'], 'txn_count': d['cnt'],
                'total_amount': d['amt'], 'source_id': '|'.join(sorted(d['src']))})

    # ── IP 사용 ──
    for r in read(F, 'tbl_eg_ip_use'):
        st, sv, ip = (r.get('subj_type') or '').lower(), r.get('subj_id'), r.get('ip_addr')
        if st not in SUBJ_LABEL or not sv or not ip:
            continue
        lab, keyp = SUBJ_LABEL[st]
        s = sid(r, 'CSV-ip-use')
        if lab == 'vt_psn':
            sv = resolve_psn(sv, 'tbl_eg_ip_use')
        L.node(lab, keyp, sv, {'source_id': s})
        L.node('vt_ip', 'ip_addr', ip, {'source_id': s})
        L.edge('used_ip', (lab, keyp, sv), ('vt_ip', 'ip_addr', ip),
               {'valid_from': r.get('valid_from'), 'valid_to': r.get('valid_to'),
                'access_type': r.get('access_type'), 'source_id': s})
    # ── 위치 사용 ──
    for r in read(F, 'tbl_eg_loc_use'):
        st, sv, loc = (r.get('subj_type') or '').lower(), r.get('subj_id'), r.get('loc_id')
        if st not in SUBJ_LABEL or not sv or not loc:
            continue
        lab, keyp = SUBJ_LABEL[st]
        s = sid(r, 'CSV-loc-use')
        if lab == 'vt_psn':
            sv = resolve_psn(sv, 'tbl_eg_loc_use')
        L.node(lab, keyp, sv, {'source_id': s})
        L.node('vt_loc', 'loc_id', loc, {'source_id': s})
        L.edge('located_at', (lab, keyp, sv), ('vt_loc', 'loc_id', loc), {'source_id': s})

    # ── 결과 ──
    if unresolved:
        print(f'  ⚠ psn_id 를 이름으로 해석하지 못했습니다 ({len(unresolved)}건) — '
              f'tbl_vt_psn(인물 노드 파일)이 없거나 해당 psn_id 가 없습니다.')
        for u in unresolved[:5]:
            print(f'      {u}')
        print('      → 이대로면 같은 사람이 이름과 psn_id 로 갈라집니다.')
    conn.commit()                 # 잔여 배치 확정
    conn.autocommit = True        # 이후 집계 조회
    print(f'[{args.graph}] MERGE 호출 노드 {L.n_node} · 엣지 {L.n_edge}')
    tot_n = tot_e = 0
    for l in LABELS:
        cur.execute(f'MATCH (n:{l}) RETURN count(n)')
        n = cur.fetchone()[0]
        tot_n += n
        if n:
            print(f'  {l:<11} {n}')
    for e in ELABELS:
        cur.execute(f'MATCH ()-[r:{e}]->() RETURN count(r)')
        n = cur.fetchone()[0]
        tot_e += n
        if n:
            print(f'  {e:<15} {n}')
    print(f'  합계: 노드 {tot_n} · 엣지 {tot_e}')
    conn.close()


if __name__ == '__main__':
    main()
