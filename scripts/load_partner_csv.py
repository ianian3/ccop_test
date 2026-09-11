#!/usr/bin/env python3
"""V4.8 규격 CSV 폴더 → 그래프 적재 (협력기관 납품본 수신용).

`handoff/csv_spec_v4.8/README.md` 규격대로 작성된 CSV 묶음을 읽어 V4.8 그래프를 만든다.
규격서가 약속한 동작(§4 집계·§3 추가컬럼)을 실제로 구현한 것이라, 규격서와 적재기가
어긋나지 않는지 확인하는 용도로도 쓴다.

핵심 동작
  · 통화/메시지 → `contacted` **쌍당 1엣지**로 접고 first_dt·last_dt·call_count·
    msg_count·total_dur_sec 집계 (건별 시각은 그래프에 두지 않는다 — 규격서 §4)
  · 이체 → `transferred_to` 쌍당 1엣지 + first_dlng_dt·last_dlng_dt·txn_count·total_amount
  · 금액·건수는 **숫자 타입**으로 저장 (문자열이면 비교·정렬이 조용히 틀린다)
  · 모든 노드·엣지에 source_id 부여 (없으면 파일명에서 생성)
  · 인물 식별: psn_id 가 있으면 그것으로, 없으면 flnm(이름)으로 — 규격서 §3.4
  · 멱등(MERGE). 같은 폴더를 두 번 적재해도 중복이 생기지 않는다

적재 후 `handoff/ontology_v4.8/code/audit_ontology_v48.py` 로 정경을 검증할 수 있다.

실행
  python3 scripts/load_partner_csv.py <CSV폴더> --graph partner_graph
  python3 scripts/load_partner_csv.py <CSV폴더> --graph partner_graph --reset
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
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith('.csv') or keyword not in fn:
            continue
        with open(os.path.join(folder, fn), encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                row = {(k or '').strip(): (v.strip() if isinstance(v, str) else v)
                       for k, v in row.items()}
                row.setdefault('_file', fn)
                out.append(row)
    return out


def sid(row, default):
    return (row.get('source_id') or '').strip() or default


class Loader:
    def __init__(self, cur):
        self.cur = cur
        self.n_node = 0
        self.n_edge = 0

    def node(self, label, key, val, props):
        if val in (None, ''):
            return False
        sets = [f"n.{k} = {v if isinstance(v, (int, float)) else chr(39)+esc(v)+chr(39)}"
                for k, v in props.items() if v not in (None, '')]
        q = f"MERGE (n:{label} {{{key}: '{esc(val)}'}})"
        if sets:
            q += ' SET ' + ', '.join(sets)
        self.cur.execute(q)
        self.n_node += 1
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
    L = Loader(cur)
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
        L.node('vt_case', 'flnm', r.get('incdnt_no'),
               {'incdnt_nm': r.get('incdnt_nm'), 'incdnt_typ_cd': r.get('incdnt_typ_cd'),
                'occrn_dt': r.get('occrn_dt'), 'damage_amt': num(r.get('damage_amt')),
                'crime_site': r.get('crime_site'), 'case_summary': r.get('incdnt_smry_cn'),
                'source_id': sid(r, 'CSV-case')})

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
        L.node('vt_case', 'flnm', cs, {'source_id': s})
        L.edge(el, ('vt_psn', 'name', p), ('vt_case', 'flnm', cs), {'source_id': s})
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
            sv = psn_key.get(sv, sv)
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
            sv = psn_key.get(sv, sv)
        L.node(lab, keyp, sv, {'source_id': s})
        L.node('vt_loc', 'loc_id', loc, {'source_id': s})
        L.edge('located_at', (lab, keyp, sv), ('vt_loc', 'loc_id', loc), {'source_id': s})

    # ── 결과 ──
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
