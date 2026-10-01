# tests/test_partner_loader_e2e.py
"""
F05 end-to-end: 동봉 예제 CSV 로 main() 전체를 돌려 재적재·분할 납품 멱등성을 검증.
AgensGraph 대신, 적재기가 내는 Cypher(CREATE/SET/MERGE)를 해석해 상태를 쌓는 가짜 저장소 사용.
"""
import collections
import importlib.util
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
EX = ROOT / "handoff/csv_spec_v4.8/examples"
LOADERS = [ROOT / "handoff/csv_spec_v4.8/load_csv_to_graph.py", ROOT / "scripts/load_partner_csv.py"]


def parse_map(s):
    out = {}
    for k, v in re.findall(r"(\w+): ('(?:[^']|'')*'|-?[\d.]+)", s):
        out[k] = v[1:-1].replace("''", "'") if v.startswith("'") else (float(v) if '.' in v else int(v))
    return out

class Store:
    def __init__(self): self.nodes = collections.defaultdict(list); self.edges = {}

class Cur:
    def __init__(self, store): self.res = []; self.log = []; self.S = store
    def execute(self, q, p=None):
        self.log.append(q); self.res = []
        m = re.match(r"CREATE \(n:(\w+) \{(.*)\}\)$", q, re.S)
        if m: self.S.nodes[m.group(1)].append(parse_map(m.group(2))); return
        m = re.match(r"MATCH \(n:(\w+) \{(.*?)\}\) SET (.*)$", q, re.S)
        if m:
            lab, km = m.group(1), parse_map(m.group(2))          # 단일·복합 키 맵
            for n in self.S.nodes[lab]:
                if all(n.get(k) == v for k, v in km.items()):
                    for k, v in re.findall(r"n\.(\w+) = ('(?:[^']|'')*'|-?[\d.]+)", m.group(3)):
                        n.update(parse_map(f"{k}: {v}"))
            return
        m = re.match(r"MATCH \(x:(\w+) \{(.*?)\}\), \(y:(\w+) \{(.*?)\}\) MERGE \(x\)-\[r:(\w+)(?: \{(.*?)\})?\]->\(y\)(?: SET (.*))?$", q, re.S)
        if m:
            la, xa, lb, yb, el, mp, sets = m.groups()
            key = (el, la, tuple(sorted(parse_map(xa).items())), lb, tuple(sorted(parse_map(yb).items())), mp)
            props = self_props = self.S.edges.setdefault(key, {})
            if mp: props.update(parse_map(mp))
            if sets:
                for k, v in re.findall(r"r\.(\w+) = ('(?:[^']|'')*'|-?[\d.]+)", sets): props.update(parse_map(f"{k}: {v}"))
            return
        m = re.match(r"MATCH \(n:(\w+)\) RETURN properties\(n\)", q)
        if m: self.res = [(dict(n),) for n in self.S.nodes[m.group(1)]]; return
        m = re.match(r"MATCH \(x:(\w+)\)-\[r:(\w+)\]->\(y:(\w+)\) RETURN properties\(x\), properties\(y\), properties\(r\)", q)
        if m:
            la, el, lb = m.groups()
            for (e, a, xk, b, yk, mp), pr in self.S.edges.items():
                if e == el and a == la and b == lb:
                    self.res.append((dict(xk), dict(yk), dict(pr)))
            return
        m = re.match(r"MATCH \(n:(\w+)\) RETURN count\(n\)", q)
        if m: self.res = [(len(self.S.nodes[m.group(1)]),)]; return
        m = re.match(r"MATCH \(\)-\[r:(\w+)\]->\(\) RETURN count\(r\)", q)
        if m: self.res = [(sum(1 for k in self.S.edges if k[0] == m.group(1)),)]; return
    def fetchall(self): return self.res
    def fetchone(self): return self.res[0] if self.res else (0,)

class Conn:
    autocommit = True
    def __init__(self, store): self.store = store
    def cursor(self): return Cur(self.store)
    def commit(self): pass
    def close(self): pass



def _run(path, store, folders, monkeypatch):
    spec = importlib.util.spec_from_file_location(f"_e2e_{path.stem}", path)
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    monkeypatch.setattr(M.psycopg2, "connect", lambda **kw: Conn(store))
    for f in folders:
        monkeypatch.setattr(sys, "argv", ["x", str(f), "--graph", "g"])
        M.main()


def _snapshot(store):
    nodes = {l: sorted(sorted((k, str(v)) for k, v in n.items()) for n in ns)
             for l, ns in store.nodes.items()}
    return nodes, {k: sorted((a, str(b)) for a, b in v.items()) for k, v in store.edges.items()}


@pytest.mark.parametrize("path", LOADERS, ids=lambda p: p.parent.name)
def test_rerun_is_idempotent(path, monkeypatch, capsys):
    once, twice = Store(), Store()
    _run(path, once, [EX], monkeypatch)
    _run(path, twice, [EX, EX], monkeypatch)
    assert _snapshot(once) == _snapshot(twice)


@pytest.mark.parametrize("path", LOADERS, ids=lambda p: p.parent.name)
def test_split_delivery_equals_single_load(path, monkeypatch, capsys):
    """1차 core → 2차 optional → 전체 재적재 == 한 번에 전체 적재 (psn_id 해석 포함)."""
    once, split = Store(), Store()
    _run(path, once, [EX], monkeypatch)
    _run(path, split, [EX / "core", EX / "optional", EX], monkeypatch)
    assert _snapshot(once) == _snapshot(split)
    out = capsys.readouterr().out
    assert "인물 파일(tbl_vt_psn)에 없는 psn_id" not in out and "건너뛴 참조" not in out


@pytest.mark.parametrize("path", LOADERS, ids=lambda p: p.parent.name)
def test_case_person_relations_loaded(path, monkeypatch, capsys):
    """규격 컬럼 prsn_id 만 있는 tbl_eg_case_prsn 의 관계가 빠지지 않는다 (종전: 3행 전부 조용히 누락)."""
    st = Store()
    _run(path, st, [EX], monkeypatch)
    roles = sorted((dict(k[2])["psn_id"], k[0]) for k in st.edges if k[0] in ("suspect_in", "victim_in"))
    assert roles == [("P-2026-0001", "suspect_in"), ("P-2026-0002", "suspect_in"), ("P-2026-0003", "victim_in")]
    assert {n["psn_id"] for n in st.nodes["vt_psn"]} == {"P-2026-0001", "P-2026-0002", "P-2026-0003"}
