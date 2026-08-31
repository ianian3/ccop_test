#!/usr/bin/env python3
"""카카오톡 통신영장 회신 로그(.log) → V4.7 그래프 JSON (결정론 파서, LLM 무관).

형식 (2차년도 EP6~8 실측):
  가입자 : <전화번호|이름>
  = 대화상대목록 : ...
  <행위자번호> : YYYY-MM-DD HH:MM:SS, <행위자 접속IP | '-'>
  ※ 행위자별 IP 집합이 상호 분리됨을 실측 검증(2026-08-25) — 각 라인 = 행위자 발신 이벤트.

V4.7 매핑 (신규 타입 0):
  행위자/가입자        → vt_telno
  발신 이벤트          → vt_msg 일 단위 집계 {msg_type:'kakao', aggregation_level:'daily',
                          event_count} — V4.6 G9 규칙 (개별 노드 폭증 방지)
  방향                → 행위자=상대: sent_msg(행위자→msg)+received_msg(msg→가입자) 확정
                        행위자=가입자: sent_msg만 (수신자 불명 — 방향 추정 금지)
  접속 IP             → used_ip(행위자→IP) valid_from/to=당일 min~max 관측 (V4.6 백필 규칙)
                        + sent_from_ip(msg집계→IP, V4.5 G2)
출력: batch_doc_to_graph.py 와 동일 envelope(entities/relations/…) — 비교·적재 도구 재사용.
실행: python3 scripts/parse_kakao_logs.py --root "/path/2차년도" --out results/kakao_logs_graph.json
"""
import argparse
import glob
import json
import os
import re
from collections import defaultdict, Counter

REC = re.compile(r'^(\S+) : (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}), (.+)$')
OWNER = re.compile(r'^가입자\s*:\s*(\S+)')
CARD_OWNER = re.compile(r'^가입 전화번호\s*:\s*(\S+)')      # 카드형 = 친구목록 회신
CARD_FRIEND = re.compile(r'^전화번호\s*:\s*(\S+)')
PHONE = re.compile(r'^\d{9,15}$')


def parse_log(path):
    """반환: (owner, rows, friends) — rows=착발신 이벤트, friends=친구목록(카드형)."""
    owner, rows, friends = None, [], []
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.strip().lstrip('﻿')
        m = OWNER.match(line) or CARD_OWNER.match(line)
        if m:
            owner = m.group(1)
            continue
        m = REC.match(line)
        if m:
            actor, d, t, ip = m.groups()
            ip = ip.strip()
            rows.append((actor, d, t, None if ip in ('-', '') else ip))
            continue
        m = CARD_FRIEND.match(line)
        if m:
            friends.append(m.group(1))
    return owner, rows, friends


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--out', default='results/kakao_logs_graph.json')
    args = ap.parse_args()

    logs = [p for p in glob.glob(os.path.join(args.root, '**', '*.log'), recursive=True)
            if '._DAV' not in p and not os.path.basename(p).startswith('._')]
    ents, rels = {}, {}
    # 집계 버킷: (행위자, 수신자|'', 날짜) → {count, ips, tmin, tmax}
    msg_agg = defaultdict(lambda: {'n': 0, 'ips': Counter(), 'tmin': None, 'tmax': None})
    ip_agg = defaultdict(lambda: {'n': 0, 'tmin': None, 'tmax': None})   # (행위자, IP, 날짜)
    n_rec, n_files, owners_nonphone = 0, 0, []

    def ent(etype, key, props, src):
        k = f'{etype}:{key}'
        e = ents.setdefault(k, {'type': etype, 'key': k, 'props': props,
                                'sources': [], 'reliability_tier': 2, 'verified': True})
        if src not in e['sources']:
            e['sources'].append(src)
        return k

    def rel(rtype, frm, to, props, src):
        k = (rtype, frm, to)
        r = rels.setdefault(k, {'type': rtype, 'from': frm, 'to': to,
                                'props': props, 'sources': []})
        if src not in r['sources']:
            r['sources'].append(src)

    n_card, n_blank, n_friend_edges = 0, 0, 0
    for path in logs:
        owner, rows, friends = parse_log(path)
        src = os.path.basename(path)
        owner_ok = bool(owner and PHONE.match(owner))
        if friends and owner_ok:                        # 카드형: 카톡 친구목록 회신
            n_card += 1
            o_k = ent('vt_telno', owner, {'telno': owner}, src)
            for f in friends:
                if PHONE.match(f):
                    f_k = ent('vt_telno', f, {'telno': f}, src)
                    rel('contacted', o_k, f_k,
                        {'channel': 'kakao_friend_list', 'confidence': 1.0}, src)
                    n_friend_edges += 1
            continue
        if not rows:
            n_blank += 1
            continue
        n_files += 1
        owner_is_phone = bool(owner and PHONE.match(owner))
        if owner and not owner_is_phone:
            owners_nonphone.append(owner)
        for actor, d, t, ip in rows:
            n_rec += 1
            recv = owner if (owner_is_phone and actor != owner) else ''   # 행위자=가입자면 수신자 불명
            b = msg_agg[(actor, recv, d, src)]
            b['n'] += 1
            b['tmin'] = min(b['tmin'] or t, t)
            b['tmax'] = max(b['tmax'] or t, t)
            if ip:
                b['ips'][ip] += 1
                ib = ip_agg[(actor, ip, d, src)]
                ib['n'] += 1
                ib['tmin'] = min(ib['tmin'] or t, t)
                ib['tmax'] = max(ib['tmax'] or t, t)

    for (actor, recv, d, src), b in msg_agg.items():
        a_k = ent('vt_telno', actor, {'telno': actor}, src)
        m_k = ent('vt_msg', f'kakao:{actor}>{recv or "?"}:{d}',
                  {'msg_type': 'kakao', 'aggregation_level': 'daily', 'event_count': b['n'],
                   'msg_dt': f'{d} {b["tmin"]}', 'msg_dt_last': f'{d} {b["tmax"]}'}, src)
        rel('sent_msg', a_k, m_k, {'confidence': 1.0}, src)
        if recv:
            r_k = ent('vt_telno', recv, {'telno': recv}, src)
            rel('received_msg', m_k, r_k, {'confidence': 1.0}, src)
        for ip in b['ips']:
            ip_k = ent('vt_ip', ip, {'ip_addr': ip}, src)
            rel('sent_from_ip', m_k, ip_k, {'confidence': 1.0}, src)
    for (actor, ip, d, src), ib in ip_agg.items():
        a_k = ent('vt_telno', actor, {'telno': actor}, src)
        ip_k = ent('vt_ip', ip, {'ip_addr': ip}, src)
        rel('used_ip', a_k, ip_k,
            {'valid_from': f'{d} {ib["tmin"]}', 'valid_to': f'{d} {ib["tmax"]}',
             'event_count': ib['n'], 'confidence': 1.0}, src)

    # 공유 IP (서로 다른 행위자 2+ ) — 공범 단서 자동 산출
    ip_users = defaultdict(set)
    for (rtype, frm, to) in rels:
        if rtype == 'used_ip':
            ip_users[to].add(frm)
    shared = {ip: sorted(us) for ip, us in ip_users.items() if len(us) >= 2}

    out = {
        'root': args.root, 'n_files': n_files, 'n_files_friendcard': n_card,
        'n_files_blank': n_blank, 'n_friend_edges': n_friend_edges, 'n_records': n_rec,
        'n_entities': len(ents), 'n_relations': len(rels),
        'n_msg_agg': sum(1 for e in ents.values() if e['type'] == 'vt_msg'),
        'n_shared_ip': len(shared),
        'shared_ips': {ip: us for ip, us in sorted(shared.items(), key=lambda x: -len(x[1]))[:20]},
        'owners_nonphone': sorted(set(owners_nonphone)),
        'entities': list(ents.values()),
        'relations': [dict(r) for r in rels.values()],
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, 'w'), ensure_ascii=False, indent=1)
    tc = Counter(e['type'] for e in ents.values())
    rc = Counter(r['type'] for r in rels.values())
    print(f"착발신 로그 {n_files} + 친구목록 카드 {n_card} + 빈 회신 {n_blank} / 레코드 {n_rec:,}"
          f" → 엔티티 {len(ents):,} / 관계 {len(rels):,} (집계율 {n_rec/max(len(rels),1):.1f}:1, 친구엣지 {n_friend_edges})")
    print('노드:', dict(tc))
    print('엣지:', dict(rc))
    print(f'공유 IP(행위자 2+): {len(shared)}개')
    for ip, us in list(out['shared_ips'].items())[:5]:
        print(f'  {ip} ← {len(us)}명: {[u.split(":")[1][:8]+"****" for u in us[:4]]}')
    print('저장:', args.out)


if __name__ == '__main__':
    main()
