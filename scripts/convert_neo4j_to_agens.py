import json
import re
from datasets import load_dataset
import logging
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_return_columns(cypher):
    """
    Cypher 쿼리의 RETURN 절을 분석하여 AgensGraph SQL Wrapper의 COLUMN 정의를 생성합니다.
    예: RETURN p.name, p.age -> (name agtype, age agtype)
    """
    # 1. RETURN 이후의 문자열 추출 (대소문자 무시)
    match = re.search(r"RETURN\s+(.*)", cypher, re.IGNORECASE | re.DOTALL)
    if not match:
        return "result agtype" 
    
    return_part = match.group(1).strip()
    # 2. 쉼표로 분리 (간단 처리)
    items = [item.strip() for item in return_part.split(",")]
    
    cols = []
    for i, item in enumerate(items):
        # Alias가 있는 경우 (AS)
        alias_match = re.search(r"AS\s+(\w+)", item, re.IGNORECASE)
        if alias_match:
            name = alias_match.group(1)
        # 속성 접근인 경우 (p.name)
        elif "." in item:
            name = item.split(".")[-1]
        # 변수 자체인 경우 (p)
        else:
            name = item.replace("(", "").replace(")", "").replace("*", "all")
        
        # 특수문자 제거 및 정규화
        name = re.sub(r'[^a-zA-Z0-9_]', '', name)
        if not name or name.isdigit():
            name = f"col_{i}"
            
        cols.append(f"{name} agtype")
    
    return ", ".join(cols)

def convert_example(example, graph_name="investigation_graph"):
    """
    Neo4j Cypher -> AgensGraph SQL Wrapper 변환
    """
    native_cypher = example['cypher'].strip()
    # 마지막 세미콜론 제거
    if native_cypher.endswith(";"):
        native_cypher = native_cypher[:-1]
        
    # 컬럼 정의 파싱
    columns = parse_return_columns(native_cypher)
    
    # SQL Wrapper 생성
    agens_query = f"SELECT * FROM cypher('{graph_name}', $$ {native_cypher} $$) AS ({columns});"
    
    return {
        "instruction": "Convert the following natural language question into an AgensGraph Cypher query.",
        "input": example['question'],
        "output": agens_query,
        "graph_path": graph_name,
        "native_cypher": native_cypher
    }

def main():
    dataset_name = "neo4j/text2cypher-2025v1"
    output_dir = "data"
    output_file = os.path.join(output_dir, "neo4j_agens_sft.jsonl")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    logger.info(f"🚀 '{dataset_name}' 데이터셋 로드 중...")
    try:
        # 데이터셋 로드
        ds = load_dataset(dataset_name, split="train")
        
        logger.info(f"✨ 총 {len(ds)}개의 데이터를 변환 중...")
        
        converted_count = 0
        with open(output_file, "w", encoding="utf-8") as f:
            for i, example in enumerate(ds):
                try:
                    converted = convert_example(example)
                    f.write(json.dumps(converted, ensure_ascii=False) + "\n")
                    converted_count += 1
                except Exception as e:
                    pass
                    
        logger.info(f"✅ 변환 완료! '{output_file}'에 {converted_count}개의 데이터가 저장되었습니다.")
        
    except Exception as e:
        logger.error(f"❌ 데이터셋 로드 실패: {e}")

if __name__ == "__main__":
    main()
