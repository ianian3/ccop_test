"""
ShareGPT → LF native messages format 변환

LF가 ShareGPT의 'gpt' role을 Qwen template에서 잘못 마스킹하는 문제 우회.
messages format은 OpenAI 표준이라 LF가 가장 깨끗하게 처리.

입력:  train/t2c_v37_train.json, train/t2c_v37_eval.json (ShareGPT)
출력:  train/t2c_v37_train_msg.json, train/t2c_v37_eval_msg.json (messages)
"""

import json
from pathlib import Path

TRAIN_DIR = Path(__file__).parent.parent / "train"

for src_name in ['t2c_v37_train.json', 't2c_v37_eval.json']:
    src = TRAIN_DIR / src_name
    if not src.exists():
        print(f"⚠️  {src} 없음")
        continue

    data = json.load(open(src))
    converted = []
    for s in data:
        system_msg = ""
        msgs = []
        for t in s['conversations']:
            role = t['from']
            value = t['value']
            if role == 'system':
                system_msg = value
            elif role == 'human':
                msgs.append({"role": "user", "content": value})
            elif role in ('gpt', 'assistant'):
                msgs.append({"role": "assistant", "content": value})

        # system은 별도 컬럼으로 분리 (LF가 dataset_info에서 system 컬럼 인식)
        converted.append({"messages": msgs, "system": system_msg})

    out = src.parent / src_name.replace('.json', '_msg.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(converted, f, ensure_ascii=False, indent=2)
    print(f"✅ {src.name} → {out.name} ({len(converted):,}개)")

    # 검증: 첫 샘플 구조 확인
    print(f"   sample[0] keys: {list(converted[0].keys())}")
    print(f"   sample[0] messages roles: {[m['role'] for m in converted[0]['messages']]}")
