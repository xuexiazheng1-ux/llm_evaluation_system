"""
Convert xianyu_seller_faq.md to test cases for LLM evaluation system
"""
import json
import re

# Read the FAQ document
with open("xianyu_seller_faq.md", "r", encoding="utf-8") as f:
    content = f.read()

# Extract Q&A pairs
test_cases = []

# Pattern to match Q&A blocks
# Match: #### X. Title
# - **标准问**：question
# - **相似问**：variants
# - **答案模板**：answer

qa_blocks = re.findall(
    r'#### \d+\..*?\n- \*\*标准问\*\*：(.*?)\n- \*\*相似问\*\*：(.*?)\n- \*\*答案模板\*\*：\s*\n\s*>\s*(.*?)(?=\n\n|####|$)',
    content,
    re.DOTALL
)

for i, (question, variants, answer) in enumerate(qa_blocks, 1):
    # Clean up the text
    question = question.strip()
    variants = variants.strip()
    answer = answer.strip().replace('\n  > ', ' ').replace('>', '').strip()
    
    # Remove markdown bold markers
    answer = re.sub(r'\*\*(.*?)\*\*', r'\1', answer)
    
    test_case = {
        "input": question,
        "expected_output": answer,
        "context": f"相似问：{variants}",
        "tags": ["闲鱼客服", "售前咨询" if i <= 4 else "价格交易" if i <= 7 else "下单发货" if i <= 10 else "售后服务" if i <= 13 else "账号规则"]
    }
    test_cases.append(test_case)

# Create dataset structure
dataset = {
    "name": "闲鱼卖家机器人客服评测集",
    "description": "基于闲鱼卖家FAQ知识库构建的评测集，覆盖售前咨询、价格交易、下单发货、售后服务、账号规则等场景",
    "tags": ["闲鱼", "客服机器人", "电商"],
    "test_cases": test_cases
}

# Save to JSON file
output_file = "xianyu_test_cases.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(dataset, f, ensure_ascii=False, indent=2)

print(f"Successfully converted {len(test_cases)} Q&A pairs to test cases!")
print(f"Output file: {output_file}")
print("\nPreview of first 3 test cases:")
for i, tc in enumerate(test_cases[:3], 1):
    print(f"\n--- Test Case {i} ---")
    print(f"Input: {tc['input']}")
    print(f"Expected: {tc['expected_output'][:100]}...")
