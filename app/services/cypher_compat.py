"""
V4.9 표기 호환 변환 — LLM 이 생성한 Cypher 의 폐기·개명 이름을 V4.9 표기로 바꾼다 (2026-10-01 정합 1단계).

배경: 배포된 v48 sLLM 의 학습 시스템 프롬프트(prompts/t2c_v47_system.txt)는 학습과 바이트 단위로 같아야 해서
고칠 수 없는데, 그 프롬프트가 V4.9 에서 삭제된 vt_email·uses_email·accomplice_of 등을 가르친다.
프롬프트 대신 생성 결과를 결정론적으로 변환한다. 규칙은 전부 SoT(ontology_service) 에서 온다:
  DEPRECATED_EDGES · DEPRECATED_LABELS · renamed_props(ATTRIBUTE_DICTIONARY 별칭표)

데이터 인지: 대상 그래프에 옛 라벨·엣지가 실제로 있으면(운영 DB 재빌드 전) 바꾸지 않는다.
속성은 그래프마다 옛/새 이름이 섞여 있어 `x.old` → `coalesce(x.new, x.old)` 로 양쪽 모두 읽는다.
"""
import re

from app.services.ontology_service import KICSCrimeDomainOntology as O

_NODE = re.compile(r'\((\w*)\s*:\s*([A-Za-z_]\w*)\s*(\{[^}]*\})?\s*\)')
_REL = re.compile(r'(<?-)\[([^\]]*)\](->?)')
_REL_TYPES = re.compile(r'^(\s*\w*\s*):\s*([A-Za-z_][\w|:]*)(.*)$', re.S)


def _keep(name, present):
    """대상 그래프에 옛 이름이 실제로 있으면 그대로 둔다."""
    return present is not None and name in present


def _rename_map_keys(props_text, rename):
    for old, new in rename.items():
        props_text = re.sub(rf'(?<![\w.]){re.escape(old)}(\s*:)', rf'{new}\1', props_text)
    return props_text


_CLAUSE = re.compile(r'\b(RETURN|ORDER\s+BY|SKIP|LIMIT|WITH|WHERE|MATCH|OPTIONAL\s+MATCH|UNION)\b', re.I)


def _rewrite_prop(text, ref, var, old, new, expr):
    """절 단위로 속성 참조를 바꾼다 (RETURN alias · ORDER BY alias · 그 밖 coalesce)."""
    parts = _CLAUSE.split(text)              # [앞, 키워드, 본문, 키워드, 본문, ...]
    aliases = []
    for i in range(1, len(parts), 2):
        kw, body = parts[i].upper().split()[0], parts[i + 1]
        if kw == 'RETURN':
            def _item(m):
                alias = m.group(2) or old
                aliases.append(alias)
                return f'{expr} AS {alias}'
            body = re.sub(ref + r'(\s+AS\s+(\w+))?', _item, body, flags=re.I)
        elif kw == 'ORDER':
            body = re.sub(ref, aliases[-1] if aliases else f'{var}.{new}', body)
        else:
            body = re.sub(ref, expr, body)
        parts[i + 1] = body
    parts[0] = re.sub(ref, expr, parts[0])
    return ''.join(parts)


def rewrite_v49(cypher, present=None):
    """Returns (new_cypher, changes, errors).

    present: 대상 그래프에 실제 있는 라벨·엣지 이름 집합. None 이면 모른다고 보고 항상 V4.9 로 바꾼다.
    errors : 대체가 없는 삭제 엣지(accomplice_of 등) — 실행해도 0건이므로 생성 단계에서 거부·재생성 유도.
    """
    if not cypher:
        return cypher, [], []
    changes, errors = [], []
    var_label = {}

    # ① 노드 라벨 — 폐기 라벨을 V4.9 라벨 + 구분 속성으로
    def _node(m):
        var, label, props = m.group(1), m.group(2), m.group(3) or ''
        dep = O.DEPRECATED_LABELS.get(label)
        if dep and not _keep(label, present):
            new = dep['replace']
            inner = props[1:-1].strip() if props else ''
            inner = _rename_map_keys(inner, dep.get('rename', {}))
            extra = ', '.join(f"{k}: '{v}'" for k, v in dep.get('props', {}).items()
                              if not re.search(rf'(?<![\w.]){k}\s*:', inner))
            inner = ', '.join(x for x in (extra, inner) if x)
            changes.append(f'{label}→{new}')
            if var:
                var_label[var] = (new, dep.get('rename', {}))
            return f'({var}:{new}' + (f' {{{inner}}}' if inner else '') + ')'
        if var:
            var_label.setdefault(var, (label, {}))
        return m.group(0)

    out = _NODE.sub(_node, cypher)

    # ② 엣지 — 개명·방향 반전, 대체 없는 삭제 엣지는 오류
    def _rel(m):
        left, inner, right = m.group(1), m.group(2), m.group(3)
        tm = _REL_TYPES.match(inner)
        if not tm:
            return m.group(0)
        head, types, tail = tm.group(1), tm.group(2), tm.group(3)
        names = [t for t in re.split(r'[|:]+', types) if t]
        new_names, flip = [], False
        for t in names:
            dep = O.DEPRECATED_EDGES.get(t)
            if not dep or _keep(t, present):
                new_names.append(t)
                continue
            if dep.get('replace') is None:
                errors.append(f"'{t}' 는 V4.9 에서 삭제됨 — {dep.get('why', '대체 없음')}")
                new_names.append(t)
                continue
            new_names.append(dep['replace'])
            changes.append(f"{t}→{dep['replace']}" + (' (방향 반전)' if dep.get('reverse') else ''))
            flip = flip or bool(dep.get('reverse'))
        if new_names == names:
            return m.group(0)
        new_inner = f"{head}:{'|'.join(dict.fromkeys(new_names))}{tail}"
        if flip and len(names) == 1:
            if left == '<-' and right == '-':
                left, right = '-', '->'
            elif left == '-' and right == '->':
                left, right = '<-', '-'
        return f'{left}[{new_inner}]{right}'

    out = _REL.sub(_rel, out)

    # ③ 속성 — 라벨별 개명(별칭표) + 폐기 라벨 변환으로 바뀐 속성.
    #   절(clause)별로 다르게 쓴다: AgensGraph 는 ORDER BY 에 함수식을 못 받고 alias 만 받는다(실측).
    #     RETURN  `x.old [AS a]` → `coalesce(x.new, x.old) AS a(없으면 old)`
    #     ORDER BY `x.old`       → RETURN 에 만든 alias, 없으면 `x.new`
    #     그 밖(WHERE·WITH 등)   → `coalesce(x.new, x.old)`
    for var, (label, extra) in var_label.items():
        rename = {**O.renamed_props(label), **extra}
        for old, new in rename.items():
            ref = rf'(?<![\w.]){re.escape(var)}\.{re.escape(old)}(?!\w)'
            if not re.search(ref, out):
                continue
            label_changed = extra.get(old) == new          # 라벨 자체가 바뀐 노드 — 옛 속성은 없다
            expr = f'{var}.{new}' if label_changed else f'coalesce({var}.{new}, {var}.{old})'
            out = _rewrite_prop(out, ref, var, old, new, expr)
            changes.append(f'{var}.{old}→{new}')
    return out, changes, errors
