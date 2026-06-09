import json, re

data = json.load(open('data/ccop_v32_final_sharegpt.json'))
total = len(data)

stats = {
    "V3.2 Edge (impersonates, filed_as, etc.)": 0,
    "Shortest Path": 0,
    "Multi-Hop (2+ edges)": 0,
    "1-Hop / Directional": 0,
    "Basic (No edges)": 0,
    "With Condition (WHERE/Filter)": 0,
    "SQL Wrapper Format": 0,
    "Native Cypher Format": 0,
    "General / Guardrail": 0
}

v32_edges = ["impersonates", "filed_as", "clusters_with", "belongs_to", "sameAs", "resolves_to", "eg_used_account", "eg_used_phone", "eg_used_ip"]

for item in data:
    gpt = item["conversations"][2]["value"].upper()
    human = item["conversations"][1]["value"]
    
    # 1. Output Format
    if "SELECT" in gpt and "CYPHER(" in gpt.replace(" ", ""):
        stats["SQL Wrapper Format"] += 1
    else:
        stats["Native Cypher Format"] += 1
        
    # 2. General Guardrail
    if "GENERAL:" in gpt:
        stats["General / Guardrail"] += 1
        continue
        
    # 3. V3.2 Specific Edges
    if any(e.upper() in gpt for e in v32_edges):
        stats["V3.2 Edge (impersonates, filed_as, etc.)"] += 1
        
    # 4. Complexity & Topology
    if "SHORTESTPATH" in gpt or "[*" in gpt or "SHORTEST_PATH" in gpt:
        stats["Shortest Path"] += 1
    elif gpt.count("-[") >= 2 or gpt.count("<-[") >= 2 or (gpt.count("-[") + gpt.count("<-[")) >= 2:
        stats["Multi-Hop (2+ edges)"] += 1
    elif "->" in gpt or "<-" in gpt or "]-" in gpt or "-[" in gpt:
        stats["1-Hop / Directional"] += 1
    else:
        stats["Basic (No edges)"] += 1
        
    # 5. Data Conditions
    if "WHERE" in gpt or ">" in gpt or "<" in gpt or "LIMIT" in gpt or "ORDER BY" in gpt:
        stats["With Condition (WHERE/Filter)"] += 1

print("="*60)
print(f"📊 Dataset Total Size: {total:,} queries")
print("="*60)
print("[ 🏗️ Topology & Complexity (구조 복잡도) ]")
for k in ["Basic (No edges)", "1-Hop / Directional", "Multi-Hop (2+ edges)", "Shortest Path"]:
    print(f"  - {k:25s}: {stats[k]:6,} 개 ({stats[k]/total*100:5.1f}%)")

print("\n[ 🎯 Core Features Focus (주요 학습 포인트) ]")
for k in ["V3.2 Edge (impersonates, filed_as, etc.)", "With Condition (WHERE/Filter)", "General / Guardrail"]:
    print(f"  - {k:40s}: {stats[k]:6,} 개 ({stats[k]/total*100:5.1f}%)")

print("\n[ 📝 Output Syntax Format (출력 문법 비율) ]")
for k in ["SQL Wrapper Format", "Native Cypher Format"]:
    print(f"  - {k:25s}: {stats[k]:6,} 개 ({stats[k]/total*100:5.1f}%)")
print("="*60)
