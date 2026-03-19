"""
DeepEval integration for LLM evaluation
"""
import os
import time
import json
from typing import List, Dict, Any, Optional
from decimal import Decimal

import httpx
from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRelevancyMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase

from app.core.config import settings
from app.core.llm_providers import get_provider, LLMProvider
from app.core.evaluator import get_evaluator


class DeepEvalManager:
    """Manager for DeepEval operations"""
    
    # Map of predefined metrics
    PREDEFINED_METRICS = {
        "answer_relevancy": AnswerRelevancyMetric,
        "faithfulness": FaithfulnessMetric,
        "contextual_relevancy": ContextualRelevancyMetric,
    }
    
    def __init__(self):
        self._setup_api_key()
        self._provider = self._create_provider()
    
    def _setup_api_key(self):
        """Setup OpenAI API key for DeepEval"""
        # DeepEval requires OpenAI API for evaluation
        # We use DeepSeek API which is OpenAI-compatible
        if settings.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
        if settings.OPENAI_BASE_URL:
            os.environ["OPENAI_BASE_URL"] = settings.OPENAI_BASE_URL
        
        # For DeepSeek, configure to use OpenAI-compatible API
        if settings.LLM_PROVIDER_TYPE == "deepseek":
            os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
            os.environ["OPENAI_BASE_URL"] = settings.OPENAI_BASE_URL or "https://api.deepseek.com/v1"
    
    def _create_provider(self) -> LLMProvider:
        """Create LLM provider based on configuration"""
        provider_type = settings.LLM_PROVIDER_TYPE
        
        if provider_type == "custom":
            # Parse custom configuration
            payload_template = json.loads(settings.LLM_CUSTOM_PAYLOAD_TEMPLATE) if settings.LLM_CUSTOM_PAYLOAD_TEMPLATE else {}
            headers = json.loads(settings.LLM_CUSTOM_HEADERS) if settings.LLM_CUSTOM_HEADERS else {}
            return get_provider(
                "custom",
                model=settings.LLM_PROVIDER_MODEL,
                payload_template=payload_template,
                output_path=settings.LLM_CUSTOM_OUTPUT_PATH,
                header_template=headers,
            )
        else:
            return get_provider(provider_type, model=settings.LLM_PROVIDER_MODEL)
    
    def create_metric(self, rule_type: str, metric_name: str, config: Dict[str, Any], threshold: float = 0.5):
        """
        Create a DeepEval metric based on configuration
        
        Args:
            rule_type: 'predefined' or 'geval'
            metric_name: Name of the metric
            config: Metric configuration
            threshold: Pass threshold (0-1)
        
        Returns:
            DeepEval metric instance
        """
        if rule_type == "predefined":
            return self._create_predefined_metric(metric_name, threshold)
        elif rule_type == "geval":
            return self._create_geval_metric(config, threshold)
        else:
            raise ValueError(f"Unknown rule type: {rule_type}")
    
    def _create_predefined_metric(self, metric_name: str, threshold: float):
        """Create a predefined DeepEval metric"""
        if metric_name not in self.PREDEFINED_METRICS:
            raise ValueError(f"Unknown predefined metric: {metric_name}")
        
        metric_class = self.PREDEFINED_METRICS[metric_name]
        
        # For DeepSeek, don't specify model - use default gpt-3.5-turbo
        # which DeepSeek API will handle via OpenAI compatibility
        return metric_class(threshold=threshold)
    
    def _create_geval_metric(self, config: Dict[str, Any], threshold: float):
        """Create a GEval metric from configuration"""
        criteria = config.get("criteria", "")
        evaluation_steps = config.get("evaluation_steps", [])
        
        # GEval requires evaluation_params to define what parameters to evaluate
        # We use ["actual_output"] as the default parameter to evaluate
        from deepeval.test_case import LLMTestCaseParams
        
        # For DeepSeek, don't specify model - use default
        return GEval(
            name=config.get("name", "Custom GEval"),
            criteria=criteria,
            evaluation_steps=evaluation_steps,
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=threshold,
        )
    
    async def call_target_agent(
        self,
        target_url: str,
        input_text: str,
        headers: Dict[str, str] = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Call the target agent API (the system being evaluated)
        Supports AnythingLLM and other OpenAI-compatible APIs
        
        Args:
            target_url: Agent API endpoint (e.g., http://192.168.1.6:7999/api/v1/workspace/{slug}/chat)
            input_text: User input
            headers: HTTP headers (should include Authorization for AnythingLLM)
            timeout: Request timeout
        
        Returns:
            Dict with 'output' and metadata
        """
        headers = headers or {}
        default_headers = {
            "Content-Type": "application/json",
        }
        default_headers.update(headers)
        
        # Detect if this is an AnythingLLM / OpenAI compatible API
        # AnythingLLM expects: { "message": "user input", "mode": "chat" }
        # Or standard OpenAI format: { "model": "...", "messages": [...] }
        
        # Try AnythingLLM format first
        if "/workspace/" in target_url or "/chat" in target_url:
            payload = {
                "message": input_text,
                "mode": "chat"
            }
        else:
            # Default simple format
            payload = {"input": input_text}
        
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    target_url,
                    json=payload,
                    headers=default_headers,
                    timeout=timeout
                )
                response.raise_for_status()
                latency_ms = int((time.time() - start_time) * 1000)
                
                data = response.json()
                
                # Extract output from target agent response
                output = self._extract_output_from_agent(data)
                
                # Log for verification
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"[AnythingLLM] URL: {target_url}, Input: {input_text[:50]}... -> Output: {output[:100]}...")
                
                return {
                    "output": output,
                    "raw_response": data,
                    "latency_ms": latency_ms,
                    "status_code": response.status_code,
                }
            except httpx.TimeoutException:
                return {
                    "output": None,
                    "error": "Request timeout",
                    "latency_ms": timeout * 1000,
                    "status_code": None,
                }
            except httpx.HTTPStatusError as e:
                return {
                    "output": None,
                    "error": f"HTTP error: {e.response.status_code} - {e.response.text}",
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "status_code": e.response.status_code,
                }
            except Exception as e:
                return {
                    "output": None,
                    "error": str(e),
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "status_code": None,
                }
    
    def _extract_output_from_agent(self, response_data: Dict[str, Any]) -> str:
        """Extract text output from target agent response (AnythingLLM, OpenAI, etc.)"""
        # Try AnythingLLM specific format first
        # AnythingLLM returns: { "textResponse": "...", "sources": [...] }
        if "textResponse" in response_data:
            return str(response_data["textResponse"])
        
        # Try common response formats
        if "output" in response_data:
            return str(response_data["output"])
        if "response" in response_data:
            return str(response_data["response"])
        if "text" in response_data:
            return str(response_data["text"])
        if "content" in response_data:
            return str(response_data["content"])
        if "message" in response_data:
            msg = response_data["message"]
            if isinstance(msg, dict) and "content" in msg:
                return str(msg["content"])
            return str(msg)
        if "choices" in response_data and len(response_data["choices"]) > 0:
            choice = response_data["choices"][0]
            if isinstance(choice, dict):
                if "message" in choice and isinstance(choice["message"], dict):
                    return str(choice["message"].get("content", ""))
                if "text" in choice:
                    return str(choice["text"])
        
        # Try other common fields
        if "result" in response_data:
            return str(response_data["result"])
        if "answer" in response_data:
            return str(response_data["answer"])
        if "data" in response_data:
            data = response_data["data"]
            if isinstance(data, str):
                return data
            if isinstance(data, dict) and "text" in data:
                return str(data["text"])
        
        # If no known format, return string representation
        return str(response_data)
    
    def _extract_output(self, response_data: Dict[str, Any]) -> str:
        """Extract text output from various API response formats"""
        # Try common response formats
        if "output" in response_data:
            return str(response_data["output"])
        if "response" in response_data:
            return str(response_data["response"])
        if "text" in response_data:
            return str(response_data["text"])
        if "content" in response_data:
            return str(response_data["content"])
        if "message" in response_data:
            msg = response_data["message"]
            if isinstance(msg, dict) and "content" in msg:
                return str(msg["content"])
            return str(msg)
        if "choices" in response_data and len(response_data["choices"]) > 0:
            choice = response_data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return str(choice["message"]["content"])
            if "text" in choice:
                return str(choice["text"])
        
        # Fallback: return string representation
        return str(response_data)
    
    def evaluate_single_case(
        self,
        input_text: str,
        actual_output: str,
        expected_output: Optional[str],
        context: Optional[str],
        metrics: List[Any]
    ) -> Dict[str, Any]:
        """
        Evaluate a single test case
        
        For DeepSeek, use custom evaluator instead of DeepEval metrics
        to avoid API compatibility issues.
        
        Args:
            input_text: User input
            actual_output: Agent's actual output
            expected_output: Expected output (optional)
            context: Context information (optional)
            metrics: List of metrics (ignored for DeepSeek, kept for compatibility)
        
        Returns:
            Evaluation results
        """
        import asyncio
        import re
        
        # Remove <think> tags and their content from actual_output before evaluation
        if actual_output:
            actual_output = re.sub(r'<think>[\s\S]*?</think>', '', actual_output).strip()
        
        # Use custom evaluator for DeepSeek
        if settings.LLM_PROVIDER_TYPE == "deepseek":
            evaluator = get_evaluator()
            # Run async evaluate in sync context
            result = asyncio.run(evaluator.evaluate(
                input_text=input_text,
                actual_output=actual_output,
                expected_output=expected_output,
                metric_name="answer_relevancy"
            ))
            
            return {
                "metrics": {"AnswerRelevancy": result},
                "overall_score": Decimal(str(result["score"])),
                "passed": result["passed"],
            }
        
        # For other providers, use DeepEval metrics
        test_case = LLMTestCase(
            input=input_text,
            actual_output=actual_output,
            expected_output=expected_output,
            retrieval_context=[context] if context else None,
        )
        
        results = {}
        overall_score = 0.0
        passed = True
        
        for metric in metrics:
            try:
                metric.measure(test_case)
                metric_name = metric.__class__.__name__
                score = float(metric.score)
                is_passed = metric.is_successful()
                reason = metric.reason if hasattr(metric, "reason") else None
                
                suggestions = self._generate_suggestions(metric_name, score, reason, test_case)
                
                results[metric_name] = {
                    "score": score,
                    "passed": is_passed,
                    "reason": reason,
                    "suggestions": suggestions,
                }
                overall_score += score
                if not is_passed:
                    passed = False
            except Exception as e:
                results[metric.__class__.__name__] = {
                    "score": 0.0,
                    "passed": False,
                    "error": str(e),
                    "suggestions": ["评测过程发生错误，请检查配置重试"],
                }
                passed = False
        
        if metrics:
            overall_score = overall_score / len(metrics)
        
        return {
            "metrics": results,
            "overall_score": Decimal(str(overall_score)),
            "passed": passed,
        }
    
    def _generate_suggestions(self, metric_name: str, score: float, reason: str, test_case) -> list:
        """Generate optimization suggestions based on evaluation results"""
        suggestions = []
        
        # Score-based general suggestions
        if score < 0.3:
            suggestions.append("得分较低，建议重新设计回答策略")
        elif score < 0.6:
            suggestions.append("回答质量有待提升，可参考期望输出进行优化")
        elif score < 0.8:
            suggestions.append("回答基本符合要求，仍有改进空间")
        
        # Metric-specific suggestions
        if "AnswerRelevancy" in metric_name:
            if score < 0.5:
                suggestions.append("回答与问题相关性较低，建议确保回答直接针对用户问题")
                suggestions.append("避免提供与问题无关的背景信息")
        elif "Faithfulness" in metric_name:
            if score < 0.5:
                suggestions.append("回答不够忠实于上下文，建议基于提供的上下文生成回答")
                suggestions.append("避免引入上下文中未提及的信息")
        elif "ContextualRelevancy" in metric_name:
            if score < 0.5:
                suggestions.append("上下文相关性较低，建议检索更相关的上下文信息")
        elif "GEval" in metric_name:
            if score < 0.5:
                suggestions.append("未达到自定义评估标准，请参考评估标准改进回答")
        
        # Add reason-based suggestion if available
        if reason and score < 0.7:
            suggestions.append(f"评估说明: {reason}")
        
        # Add comparison suggestion if expected output exists
        if test_case.expected_output and score < 0.8:
            suggestions.append("可参考期望输出的表述方式进行优化")
        
        return suggestions if suggestions else ["表现良好，继续保持"]


# Global instance
deepeval_manager = DeepEvalManager()
