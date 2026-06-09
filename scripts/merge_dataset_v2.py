import os
import json
import random

def merge_datasets():
    base_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/neo4j_agens_sft.jsonl'))
    multihop_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/sft_multihop_v2_1k.jsonl'))
    output_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/neo4j_agens_sft_V2_hybrid.jsonl'))

    if not os.path.exists(base_file):
        print(f"❌ [에러] 기본 데이터셋이 존재하지 않습니다: {base_file}")
        return

    if not os.path.exists(multihop_file):
        print(f"❌ [에러] 증강 데이터셋이 존재하지 않습니다: {multihop_file}")
        return

    # 각 데이터셋의 내용 읽기
    with open(base_file, 'r', encoding='utf-8') as f:
        base_data = [line.strip() for line in f if line.strip()]
        
    with open(multihop_file, 'r', encoding='utf-8') as f:
        multihop_data = [line.strip() for line in f if line.strip()]

    print(f"✅ 기존 기초 학습셋 크기: {len(base_data):,} 건")
    print(f"✅ V2 다중 홉(Multi-Hop) 추가셋 크기: {len(multihop_data):,} 건")

    # 두 데이터셋을 합침
    combined_data = base_data + multihop_data

    # 데이터 순서 무작위 셔플링 (과적합 방지 및 골고루 학습되도록 섞기)
    random.shuffle(combined_data)

    with open(output_file, 'w', encoding='utf-8') as f:
        for line in combined_data:
            f.write(line + "\n")

    print("\n" + "="*60)
    print(f"🚀 [병합 완료] 총 {len(combined_data):,} 건의 하이브리드 V2 학습 데이터가 생성되었습니다!")
    print(f"📂 최종 저장 경로: {output_file}")
    print("="*60)

if __name__ == "__main__":
    merge_datasets()
