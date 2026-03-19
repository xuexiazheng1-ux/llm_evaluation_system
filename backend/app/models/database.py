"""
Database models and connection setup
"""
from datetime import datetime
from typing import AsyncGenerator, Optional
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, Integer, DateTime, Boolean, 
    ForeignKey, JSON, DECIMAL, create_engine
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.core.config import settings

# Create async engine
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=0,
    echo=settings.DEBUG,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create sync engine for migrations
sync_database_url = settings.DATABASE_URL.replace("+asyncpg", "")
sync_engine = create_engine(sync_database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

Base = declarative_base()


# Database dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class EvalDataset(Base):
    """评测集表"""
    __tablename__ = "eval_datasets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(Integer, default=1)
    tags = Column(JSON, default=list)
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    test_cases = relationship("TestCase", back_populates="dataset", cascade="all, delete-orphan")
    eval_tasks = relationship("EvalTask", back_populates="dataset")


class TestCase(Base):
    """测试用例表"""
    __tablename__ = "test_cases"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("eval_datasets.id", ondelete="CASCADE"))
    input = Column(Text, nullable=False)  # 用户输入
    expected_output = Column(Text)  # 期望输出
    context = Column(Text)  # 上下文（RAG用）
    case_metadata = Column(JSON, default=dict)  # 标签、难度等
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    dataset = relationship("EvalDataset", back_populates="test_cases")
    eval_results = relationship("EvalResult", back_populates="test_case")


class ScoringRule(Base):
    """评分规则表"""
    __tablename__ = "scoring_rules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    rule_type = Column(String(50), nullable=False)  # predefined, geval
    metric_name = Column(String(100))  # DeepEval指标名
    config = Column(JSON, default=dict)  # 配置参数
    threshold = Column(DECIMAL(5, 2))  # 通过阈值
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EvalTask(Base):
    """评测任务表"""
    __tablename__ = "eval_tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("eval_datasets.id"))
    status = Column(String(50), default="pending")  # pending, running, completed, failed, cancelled
    config = Column(JSON, default=dict)  # 任务配置
    result_summary = Column(JSON, default=dict)  # 结果摘要
    celery_task_id = Column(String(255))  # Celery任务ID
    created_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Relationships
    dataset = relationship("EvalDataset", back_populates="eval_tasks")
    eval_results = relationship("EvalResult", back_populates="task", cascade="all, delete-orphan")


class EvalResult(Base):
    """评测结果表"""
    __tablename__ = "eval_results"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("eval_tasks.id", ondelete="CASCADE"))
    case_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.id"))
    actual_output = Column(Text)  # 实际输出
    metrics = Column(JSON, default=dict)  # 各指标得分
    overall_score = Column(DECIMAL(5, 2))  # 综合得分
    passed = Column(Boolean)  # 是否通过
    latency_ms = Column(Integer)  # 响应耗时
    error_message = Column(Text)  # 错误信息
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    task = relationship("EvalTask", back_populates="eval_results")
    test_case = relationship("TestCase", back_populates="eval_results")


class QualityGate(Base):
    """质量门禁配置表"""
    __tablename__ = "quality_gates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("eval_datasets.id"))
    rules = Column(JSON, default=dict)  # 门禁规则配置
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Create all tables
def create_tables():
    """Create all database tables (synchronous)"""
    Base.metadata.create_all(bind=sync_engine)


async def create_tables_async():
    """Create all database tables (asynchronous)"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
