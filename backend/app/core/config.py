"""
Application configuration settings
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "LLM Evaluation System"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/llm_eval"
    DATABASE_POOL_SIZE: int = 20
    
    # Redis (for Celery and caching)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # MinIO (Object Storage)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET_NAME: str = "llm-eval"
    MINIO_SECURE: bool = False
    
    # OpenAI / LLM
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    
    # LLM Provider Settings
    LLM_PROVIDER_TYPE: str = "openai"  # openai, deepseek, claude, custom
    LLM_PROVIDER_MODEL: str = "gpt-3.5-turbo"
    LLM_CUSTOM_PAYLOAD_TEMPLATE: Optional[str] = None  # JSON string
    LLM_CUSTOM_OUTPUT_PATH: str = "choices.0.message.content"
    LLM_CUSTOM_HEADERS: Optional[str] = None  # JSON string
    
    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    CELERY_WORKER_CONCURRENCY: int = 4
    
    # Evaluation Settings
    EVAL_SYNC_THRESHOLD: int = 10  # 用例数小于此值时同步执行
    EVAL_MAX_CONCURRENT: int = 5   # 最大并发评测数
    EVAL_TIMEOUT: int = 60         # 单个用例超时时间(秒)
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-configure Celery URLs from Redis URL if not set
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL


settings = Settings()
