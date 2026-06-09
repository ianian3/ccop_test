import glob

# 24~31번 줄의 깨진 블록을 올바른 코드로 교체
BAD_BLOCK = [
    'try:\n',
    '    try:\n',
    '    from transformers.modeling_rope_utils import RopeParameters\n',
    'except ImportError:\n',
    '    class RopeParameters:\n',
    '        pass\n',
    'except ImportError:\n',
    '    RopeParameters = None\n',
]
GOOD_BLOCK = (
    'try:\n'
    '    from transformers.modeling_rope_utils import RopeParameters\n'
    'except ImportError:\n'
    '    class RopeParameters:\n'
    '        pass\n'
)

files = glob.glob(
    '/home/ai-kyw-dev/.cache/huggingface/modules/**/configuration_exaone.py',
    recursive=True
)

for f in files:
    with open(f, 'r') as fp:
        content = fp.read()

    bad = ''.join(BAD_BLOCK)
    if bad in content:
        content = content.replace(bad, GOOD_BLOCK)
        with open(f, 'w') as fp:
            fp.write(content)
        print(f'패치완료: {f}')
    else:
        print(f'블록 불일치, 라인 직접 교체 시도: {f}')
        lines = content.splitlines(keepends=True)
        # 24~31번 줄 (0-indexed: 23~30) 강제 교체
        result = lines[:23] + [GOOD_BLOCK] + lines[31:]
        with open(f, 'w') as fp:
            fp.writelines(result)
        print(f'  → 라인 교체 완료')
