"""
LLM Provider Adapters - 统一不同大模型API的调用接口
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import httpx


class LLMProvider(ABC):
    """大模型提供商抽象基类"""
    
    @abstractmethod
    def build_payload(self, input_text: str, **kwargs) -> Dict[str, Any]:
        """构建请求体"""
        pass
    
    @abstractmethod
    def extract_output(self, response_data: Dict[str, Any]) -> str:
        """从响应中提取输出文本"""
        pass
    
    @abstractmethod
    def get_headers(self, api_key: str) -> Dict[str, str]:
        """获取请求头"""
        pass


class OpenAICompatibleProvider(LLMProvider):
    """
    OpenAI兼容格式（DeepSeek、OpenAI、智谱等）
    格式：{model, messages: [{role, content}]}
    """
    
    def __init__(self, model: str = "gpt-3.5-turbo"):
        self.model = model
    
    def build_payload(self, input_text: str, **kwargs) -> Dict[str, Any]:
        return {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": "user", "content": input_text}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
    
    def extract_output(self, response_data: Dict[str, Any]) -> str:
        # OpenAI标准格式: choices[0].message.content
        if "choices" in response_data and len(response_data["choices"]) > 0:
            choice = response_data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return str(choice["message"][content]).strip()
            if "text" in choice:
                return str(choice["text"]).strip()
        # 错误处理
        if "error" in response_data:
            raise ValueError(f"API Error: {response_data['error']}")
        raise ValueError(f"Unknown response format: {response_data}")
    
    def get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }


class ClaudeProvider(LLMProvider):
    """
    Anthropic Claude 格式
    格式：{model, messages, max_tokens}
    """
    
    def __init__(self, model: str = "claude-3-sonnet-20240229"):
        self.model = model
    
    def build_payload(self, input_text: str, **kwargs) -> Dict[str, Any]:
        return {
            "model": kwargs.get("model", self.model),
            "messages": [{"role": "user", "content": input_text}],
            "max_tokens": kwargs.get("max_tokens", 2000),
        }
    
    def extract_output(self, response_data: Dict[str, Any]) -> str:
        # Claude格式: content[0].text
        if "content" in response_data and len(response_data["content"]) > 0:
            return str(response_data["content"][0].get("text", "")).strip()
        if "completion" in response_data:
            return str(response_data["completion"]).strip()
        raise ValueError(f"Unknown Claude response format: {response_data}")
    
    def get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }


class CustomProvider(LLMProvider):
    """
    自定义格式 - 通过配置适配
    """
    
    def __init__(
        self,
        model: str,
        payload_template: Dict[str, Any],
        output_path: str,  # 如: "choices.0.message.content"
        header_template: Optional[Dict[str, str]] = None,
    ):
        self.model = model
        self.payload_template = payload_template
        self.output_path = output_path
        self.header_template = header_template or {}
    
    def build_payload(self, input_text: str, **kwargs) -> Dict[str, Any]:
        # 使用模板并替换变量
        import copy
        payload = copy.deepcopy(self.payload_template)
        
        # 替换 {input} 占位符
        def replace_placeholder(obj):
            if isinstance(obj, str):
                return obj.replace("{input}", input_text).replace("{model}", self.model)
            elif isinstance(obj, dict):
                return {k: replace_placeholder(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_placeholder(item) for item in obj]
            return obj
        
        return replace_placeholder(payload)
    
    def extract_output(self, response_data: Dict[str, Any]) -> str:
        # 按路径提取值，如 "choices.0.message.content"
        keys = self.output_path.split(".")
        value = response_data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            elif isinstance(value, list) and key.isdigit():
                value = value[int(key)]
            else:
                raise ValueError(f"Cannot extract path '{self.output_path}' from response")
        return str(value).strip()
    
    def get_headers(self, api_key: str) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        headers.update(self.header_template)
        # 替换 {api_key} 占位符
        for key in headers:
            if "{api_key}" in headers[key]:
                headers[key] = headers[key].replace("{api_key}", api_key)
        return headers


# 提供商工厂
PROVIDER_REGISTRY = {
    "openai": OpenAICompatibleProvider,
    "deepseek": OpenAICompatibleProvider,
    "claude": ClaudeProvider,
    "anthropic": ClaudeProvider,
    "custom": CustomProvider,
}


def get_provider(provider_type: str, **kwargs) -> LLMProvider:
    """获取对应的大模型提供商适配器"""
    if provider_type not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider_type}. Available: {list(PROVIDER_REGISTRY.keys())}")
    
    provider_class = PROVIDER_REGISTRY[provider_type]
    return provider_class(**kwargs)
