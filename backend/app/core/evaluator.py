"""
自定义评测器，直接使用 DeepSeek API 进行评分
绕过 DeepEval 的默认行为
"""
import os
import httpx
import json
from typing import Dict, Any, Optional
from decimal import Decimal


class DeepSeekEvaluator:
    """使用 DeepSeek API 直接进行评测"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
        self.model = "deepseek-chat"
    
    async def evaluate(
        self,
        input_text: str,
        actual_output: str,
        expected_output: Optional[str],
        metric_name: str = "answer_relevancy"
    ) -> Dict[str, Any]:
        """
        使用 DeepSeek API 进行评测
        
        Returns:
            {
                "score": float (0-1),
                "passed": bool,
                "reason": str,
                "suggestions": List[str]
            }
        """
        # 构建评测提示词
        prompt = self._build_evaluation_prompt(
            input_text, actual_output, expected_output, metric_name
        )
        
        # 调用 DeepSeek API
        result = await self._call_api(prompt)
        
        # 解析结果
        return self._parse_result(result, metric_name)
    
    def _build_evaluation_prompt(
        self,
        input_text: str,
        actual_output: str,
        expected_output: Optional[str],
        metric_name: str
    ) -> str:
        """构建评测提示词"""
        
        if metric_name == "answer_relevancy":
            criteria = """评估回答与问题的相关性。考虑：
1. 回答是否直接针对问题
2. 回答是否包含无关信息
3. 回答是否完整回答了问题"""
        elif metric_name == "faithfulness":
            criteria = """评估回答的忠实度。考虑：
1. 回答是否基于提供的上下文
2. 回答是否包含虚构信息
3. 回答是否准确反映了上下文内容"""
        else:
            criteria = """评估回答质量。考虑：
1. 回答的准确性
2. 回答的完整性
3. 回答的清晰度"""
        
        expected_section = f"\n期望回答：{expected_output}" if expected_output else ""
        
        return f"""你是一个专业的回答质量评估专家。请评估以下回答的质量。

评估标准：{criteria}

用户问题：{input_text}
实际回答：{actual_output}{expected_section}

请按以下格式输出评估结果（JSON格式）：
{{
    "score": 0.0-1.0,  // 综合得分
    "passed": true/false,  // 是否通过（score >= 0.6 为通过）
    "reason": "详细说明评估理由",
    "suggestions": ["改进建议1", "改进建议2"]
}}

只输出 JSON，不要其他内容。"""
    
    async def _call_api(self, prompt: str) -> str:
        """调用 DeepSeek API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    def _parse_result(self, result: str, metric_name: str) -> Dict[str, Any]:
        """解析 API 返回的结果"""
        try:
            # 尝试解析 JSON
            # 去除可能的 markdown 代码块标记
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.startswith("```"):
                result = result[3:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()
            
            data = json.loads(result)
            
            return {
                "score": float(data.get("score", 0)),
                "passed": data.get("passed", False),
                "reason": data.get("reason", "无详细说明"),
                "suggestions": data.get("suggestions", []),
            }
        except Exception as e:
            # 解析失败返回默认值
            return {
                "score": 0.0,
                "passed": False,
                "reason": f"评测结果解析失败: {str(e)}",
                "suggestions": ["请检查模型输出格式"],
            }


# 全局评测器实例
evaluator = None

def get_evaluator() -> DeepSeekEvaluator:
    """获取评测器实例"""
    global evaluator
    if evaluator is None:
        evaluator = DeepSeekEvaluator()
    return evaluator
