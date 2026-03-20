import os
import sys
import json
import logging
import argparse
from tqdm import tqdm
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from typing import List

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Pydantic Schema for LLM Output
class CypherPair(BaseModel):
    instruction: str = Field(description="The natural language forensic question")
    output: str = Field(description="The generated SQL-Wrapped Cypher query")

class CypherBatch(BaseModel):
    items: List[CypherPair]

def load_seed_data(filepath):
    seed_data = []
    if not os.path.exists(filepath):
         logger.warning(f"Seed file {filepath} not found. Proceeding without seeds.")
         return seed_data
         
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                seed_data.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return seed_data

def generate_synthetic_data(api_key=None, seed_path=None, output_path=None, total_samples=500, batch_size=20):
    # Load .env variables first
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
    
    final_api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not final_api_key:
        logger.error("No OpenAI API key found. Please provide --key or set OPENAI_API_KEY in .env")
        return
        
    os.environ["OPENAI_API_KEY"] = final_api_key
    
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
        return

    seed_data = load_seed_data(seed_path)
    seed_examples_str = ""
    # Select a few representative seeds to guide generation
    if seed_data:
        samples = seed_data[:10]  # Take top 10 as context
        for s in samples:
            raw_cypher = s['output'].replace('{', '{{').replace('}', '}}')
            raw_inst = s['instruction'].replace('{', '{{').replace('}', '}}')
            seed_examples_str += f"- Question: {raw_inst}\n  Cypher: {raw_cypher}\n\n"

    parser = JsonOutputParser(pydantic_object=CypherBatch)

    system_prompt = f"""
    당신은 AgensGraph 데이터베이스 쿼리를 전문적으로 다루는 수사관 AI를 학습시키기 위한 최상급 데이터(Synthetic Data) 생성기입니다.
    
    목표: 범죄 수사관이 AgensGraph(tccop_graph_v6) 데이터베이스에 던질 법한 다양한 난이도(1-Hop ~ 3-Hop 이상)의 자연어 질의응답(Text-to-Cypher) 데이터셋을 총 {batch_size}개 생성하십시오.
    
    [필수 규칙 및 주의사항] - **매우 중요** (AI가 자주 틀리는 부분)
    1. **Type Casting (문자열 비교)**:
       - `amount`(금액)과 `duration`(통화시간)은 숫자형이 아닌 **문자열(String)** 타입입니다. 비교할 때 반드시 따옴표를 사용하세요. (예: `WHERE t.amount = '500000'` O, `WHERE t.amount = 500000` X)
       - `ORDER BY` 사용 시 `c->>'duration'` 처럼 문자열 추출 후 캐스팅 없이 문자열 비교 정렬에 의존하거나, 그냥 노드를 통째로 RETURN하세요.
    2. **엣지 방향성 강제**:
       - `(c:vt_case)-[:involves]->(p:vt_psn)` (사건이 피의자/피해자를 involve함)
       - `(vt_bacnt)-[:from_account]->(vt_transfer)` (계좌에서 이체 시작)
       - `(vt_transfer)-[:to_account]->(vt_bacnt)` (이체가 계좌로 도착)
       - `(vt_telno)-[:caller]->(vt_call)` (전화번호가 통화 시작)
       - `(vt_call)-[:callee]->(vt_telno)` (통화가 전화번호에 도착)
       - `(vt_psn)-[:owns_phone]->(vt_telno)`, `(vt_psn)-[:has_account]->(vt_bacnt)`, `(vt_psn)-[:used_ip]->(vt_ip)`
    3. **출력 구조 (SQL-Wrapped Cypher)**:
       - 무조건 `SELECT * FROM cypher('tccop_graph_v6', $$ MATCH ... RETURN ... $$) AS (col agtype, ...);` 래퍼로 감싸야 합니다.
       - 컬럼의 타입은 항상 `agtype` 입니다.
    
    [시드 데이터 (참고용 형식과 도메인 어조)]
    {seed_examples_str}
    
    위 시드 예시를 바탕으로, 동일한 어조와 문법 규칙을 준수하되, **서로 다른 수사 도메인(IP 추적, 대포통장 추적, 보이스피싱 통화경로 추적, 공범 연루 사건 검색 등)과 파라미터(id, 번호, 금액, 날짜 등)를 창의적으로 변형하여 완전히 새로운 질문-쿼리 쌍 {batch_size}개를 JSON List 형태로 반환**하십시오.
    
    {{format_instructions}}
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", f"{batch_size}개의 고품질 텍스트-사이퍼 쌍을 생성해주세요.")
    ])

    chain = prompt | llm | parser

    generated_count = 0
    iterations = (total_samples // batch_size) + (1 if total_samples % batch_size != 0 else 0)

    logger.info(f"Target: {total_samples} samples. Starting {iterations} iterations...")

    # Load existing so we don't overwrite
    items_to_save = []
    if os.path.exists(output_path):
        with open(output_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                     items_to_save.append(json.loads(line))
        logger.info(f"Loaded {len(items_to_save)} existing samples from {output_path}.")
    else:
        # Include seed automatically in the extended dataset
        items_to_save.extend(seed_data)

    generated_count = len(items_to_save)
    target_count = generated_count + total_samples

    import copy

    with tqdm(total=total_samples, desc="Generating") as pbar:
        while generated_count < target_count:
            try:
                response = chain.invoke({"format_instructions": parser.get_format_instructions()})
                
                # Check format
                if "items" in response and isinstance(response["items"], list):
                    batch_items = response["items"]
                else:
                    logger.warning("Unexpected LLM output format. Retrying...")
                    continue
                
                for item in batch_items:
                    data = {
                        "instruction": item['instruction'],
                        "input": "Translate the natural language forensic question into a valid AgensGraph Cypher query.",
                        "output": item['output'],
                        "graph_path": "tccop_graph_v6"
                    }
                    items_to_save.append(data)
                
                generated_count += len(batch_items)
                pbar.update(len(batch_items))
                
                # Save aggressively
                with open(output_path, 'w', encoding='utf-8') as f:
                    for s in items_to_save:
                        f.write(json.dumps(s, ensure_ascii=False) + '\n')
                        
            except Exception as e:
                logger.error(f"Error during LLM generation loop: {e}")
                
    logger.info(f"Synthetic data generation complete. Total samples: {len(items_to_save)}. Saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Synthetic SFT dataset for AgensGraph Text-to-Cypher")
    parser.add_argument("--key", type=str, default=None, help="OpenAI API Key (starts with sk-...)")
    parser.add_argument("--count", type=int, default=500, help="Total number of samples to generate")
    parser.add_argument("--batch", type=int, default=20, help="Batch size per LLM request")
    
    args = parser.parse_args()
    
    SEED_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sft_dataset_v1.jsonl")
    OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sft_dataset_v2_augmented.jsonl")
    
    generate_synthetic_data(args.key, SEED_PATH, OUTPUT_PATH, total_samples=args.count, batch_size=args.batch)
