import json
import random
import os
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_jsonl(file_path):
    data = []
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return data
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    return data

def main():
    neo4j_path = "data/neo4j_agens_sft.jsonl"
    kics_path = "data/sft_dataset_v2_augmented.jsonl"
    output_path = "data/final_train_data.jsonl"
    
    # 1. 데이터 로드
    logger.info("📦 데이터셋 로드 중...")
    neo4j_data = load_jsonl(neo4j_path)
    kics_data = load_jsonl(kics_path)
    
    logger.info(f"   - Neo4j 원본: {len(neo4j_data)}건")
    logger.info(f"   - KICS 원본: {len(kics_data)}건")
    
    # 2. 샘플링 및 가중치 조절 (Mixing Strategy)
    # 전략: Neo4j는 10,000건만 샘플링 (문법 학습용)
    #      KICS는 5배 오버샘플링 (도메인 학습용 -> 614 * 5 = 3,070건)
    
    target_neo4j_count = min(10000, len(neo4j_data))
    sampled_neo4j = random.sample(neo4j_data, target_neo4j_count)
    
    kics_multiplier = 10 # 도메인 지식을 더 강하게 주입하기 위해 10배 복제
    oversampled_kics = kics_data * kics_multiplier
    
    # 3. 데이터 병합 및 셔플
    final_data = sampled_neo4j + oversampled_kics
    random.shuffle(final_data)
    
    logger.info(f"🚀 믹싱 결과:")
    logger.info(f"   - 샘플링된 Neo4j: {len(sampled_neo4j)}건")
    logger.info(f"   - 오버샘플링된 KICS: {len(oversampled_kics)}건 (원본 614건 x {kics_multiplier})")
    logger.info(f"   - 최종 학습 데이터: {len(final_data)}건")
    
    # 4. 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in final_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    logger.info(f"✅ 최종 학습 데이터셋 생성 완료! '{output_path}'")
    logger.info("Tip: 이제 'scripts/train_lora.py'를 실행하여 모델 학습을 시작할 수 있습니다.")

if __name__ == "__main__":
    main()
