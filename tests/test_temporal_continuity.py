"""V4.6 Q1 — 시간순 연속성 쿼리 주입 순수로직 테스트 (DB 무관).

설계: docs/TEMPORAL_CONTINUITY_QUERY_DESIGN.md
검증: V/E/N 분류 · 조건 주입 · N형 warnings.
"""
from app.services.temporal_continuity import classify_edge, parse_path, inject


# ── 분류 (분류표 SoT 파생) ──────────────────────────────────────────

def test_classify_e_form():
    assert classify_edge('used_ip') == ('E', 'valid_from')
    assert classify_edge('transferred_to') == ('E', 'transfer_date')
    assert classify_edge('exchanged_to') == ('E', 'exchanged_at')
    assert classify_edge('has_account') == ('E', 'valid_from')      # 보완 반영 확인


def test_classify_v_form():
    assert classify_edge('from_account')[0] == 'V'   # Transfer 경유
    assert classify_edge('caller')[0] == 'V'         # Call 경유
    assert classify_edge('accessed_from')[0] == 'V'  # Access 경유


def test_classify_n_form():
    assert classify_edge('sameAs') == ('N', None)
    assert classify_edge('linked_to') == ('N', None)
    assert classify_edge('contacted') == ('N', None)


# ── 파싱 ────────────────────────────────────────────────────────────

def test_parse_path_basic():
    seq = parse_path("MATCH (a:vt_bacnt)-[e1:transferred_to]->(b:vt_bacnt) RETURN a")
    kinds = [s[0] for s in seq]
    assert kinds == ['node', 'edge', 'node']
    assert seq[0][1:] == ('a', 'vt_bacnt')
    assert seq[1][1:] == ('e1', 'transferred_to', '->')


# ── 주입: E형 (자금세탁) ────────────────────────────────────────────

def test_inject_e_form_moneylaundering():
    cy = "MATCH (a:vt_bacnt)-[e1:transferred_to]->(b:vt_bacnt)-[e2:transferred_to]->(c:vt_bacnt) RETURN a,b,c"
    out, w = inject(cy)
    assert "date(e1.transfer_date) <= date(e2.transfer_date)" in out
    assert "WHERE" in out
    assert w == []


# ── 주입: V형 (접속, Event 노드 경유) ───────────────────────────────

def test_inject_v_form_access():
    cy = ("MATCH (a1:vt_access)-[:accessed_from]->(ip:vt_ip)"
          "<-[:accessed_from]-(a2:vt_access) RETURN ip")
    out, w = inject(cy)
    assert "date(a1.access_dt) <= date(a2.access_dt)" in out
    assert w == []


# ── 주입: N형 혼합 → warning, 조건 생략 ─────────────────────────────

def test_inject_mixed_n_warns():
    cy = "MATCH (p:vt_psn)-[u:used_ip]->(ip:vt_ip)<-[s:sameAs]-(ip2:vt_ip) RETURN p"
    out, w = inject(cy)
    assert len(w) == 1 and "sameAs" in w[0]
    assert "<=" not in out                    # N형 껴서 조건 미주입


# ── 주입: 전량 N형 → 조건 0, warning ────────────────────────────────

def test_inject_all_n():
    cy = "MATCH (a:vt_psn)-[:sameAs]->(b:vt_psn)-[:knows]-(c:vt_psn) RETURN a"
    out, w = inject(cy)
    # knows 는 E형(valid_from), sameAs 는 N형 → 한 구간 warning
    assert any("sameAs" in x for x in w)


# ── 기존 WHERE 있는 경우 AND 확장 ──────────────────────────────────

def test_inject_existing_where():
    cy = ("MATCH (a:vt_bacnt)-[e1:transferred_to]->(b:vt_bacnt)-[e2:transferred_to]->(c) "
          "WHERE a.is_frozen = 'true' RETURN a")
    out, w = inject(cy)
    assert "WHERE (date(e1.transfer_date) <= date(e2.transfer_date)) AND" in out
    assert "a.is_frozen" in out


# ── 단일 엣지: 선후 없음 → 무변경 ──────────────────────────────────

def test_inject_single_edge_noop():
    cy = "MATCH (ip:vt_ip)-[e:used_ip]-(p) RETURN ip"
    out, w = inject(cy)
    assert out == cy and w == []
