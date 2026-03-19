"""
Pydantic schemas for request/response validation
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


# ============== Base Schemas ==============

class BaseResponse(BaseModel):
    """Base response schema"""
    success: bool = True
    message: Optional[str] = None


class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    total: int
    page: int
    page_size: int
    items: List[Any]


# ============== Dataset Schemas ==============

class TestCaseBase(BaseModel):
    """Base test case schema"""
    model_config = ConfigDict(from_attributes=True)
    
    input: str
    expected_output: Optional[str] = None
    context: Optional[str] = None
    case_metadata: Dict[str, Any] = Field(default_factory=dict)


class TestCaseCreate(TestCaseBase):
    pass


class TestCaseUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    input: Optional[str] = None
    expected_output: Optional[str] = None
    context: Optional[str] = None
    case_metadata: Optional[Dict[str, Any]] = None


class TestCaseResponse(TestCaseBase):
    """Test case response schema"""
    
    id: UUID
    dataset_id: UUID
    created_at: datetime


class EvalDatasetBase(BaseModel):
    """Base dataset schema"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class EvalDatasetCreate(EvalDatasetBase):
    pass


class EvalDatasetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class EvalDatasetResponse(EvalDatasetBase):
    """Dataset response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    version: int
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    test_case_count: Optional[int] = None


class EvalDatasetDetailResponse(EvalDatasetResponse):
    """Dataset detail with test cases"""
    test_cases: List[TestCaseResponse] = []


class DatasetImportRequest(BaseModel):
    """Dataset import request"""
    format: str = Field(..., pattern="^(json|csv)$")
    content: str  # Base64 encoded file content


# ============== Scoring Rule Schemas ==============

class ScoringRuleBase(BaseModel):
    """Base scoring rule schema"""
    name: str = Field(..., min_length=1, max_length=255)
    rule_type: str = Field(..., pattern="^(predefined|geval)$")
    metric_name: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    threshold: Optional[Decimal] = Field(None, ge=0, le=1)


class ScoringRuleCreate(ScoringRuleBase):
    pass


class ScoringRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    config: Optional[Dict[str, Any]] = None
    threshold: Optional[Decimal] = Field(None, ge=0, le=1)


class ScoringRuleResponse(ScoringRuleBase):
    """Scoring rule response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    created_at: datetime
    updated_at: datetime


# ============== Evaluation Task Schemas ==============

class EvalTaskConfig(BaseModel):
    """Evaluation task configuration"""
    target_url: str  # 目标Agent API地址
    target_headers: Dict[str, str] = Field(default_factory=dict)
    scoring_rules: List[UUID]  # 评分规则ID列表
    concurrency: int = Field(default=1, ge=1, le=10)
    timeout: int = Field(default=60, ge=1, le=300)


class EvalTaskBase(BaseModel):
    """Base evaluation task schema"""
    name: str = Field(..., min_length=1, max_length=255)
    dataset_id: UUID


class EvalTaskCreate(EvalTaskBase):
    config: EvalTaskConfig


class EvalTaskResponse(EvalTaskBase):
    """Evaluation task response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    status: str
    config: Dict[str, Any]
    result_summary: Dict[str, Any]
    celery_task_id: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class EvalTaskDetailResponse(EvalTaskResponse):
    """Task detail with results"""
    dataset: Optional[EvalDatasetResponse] = None


class QuickEvalRequest(BaseModel):
    """Quick evaluation request (sync)"""
    dataset_id: UUID
    target_url: str
    target_headers: Dict[str, str] = Field(default_factory=dict)
    scoring_rules: List[UUID]
    max_cases: int = Field(default=10, ge=1, le=50)


class QuickEvalResponse(BaseResponse):
    """Quick evaluation response"""
    task_id: UUID
    results: List[Dict[str, Any]]
    summary: Dict[str, Any]


# ============== Evaluation Result Schemas ==============

class EvalResultResponse(BaseModel):
    """Evaluation result response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    task_id: UUID
    case_id: UUID
    actual_output: Optional[str]
    metrics: Dict[str, Any]
    overall_score: Optional[Decimal]
    passed: Optional[bool]
    latency_ms: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    test_case: Optional[TestCaseResponse] = None


class EvalResultListResponse(PaginatedResponse):
    """Paginated evaluation results"""
    items: List[EvalResultResponse]


# ============== Quality Gate Schemas ==============

class GateRule(BaseModel):
    """Quality gate rule"""
    metric: str  # pass_rate, avg_score, etc.
    operator: str = Field(..., pattern="^(gt|gte|lt|lte|eq)$")
    threshold: Decimal


class QualityGateBase(BaseModel):
    """Base quality gate schema"""
    name: str = Field(..., min_length=1, max_length=255)
    dataset_id: UUID
    rules: List[GateRule]
    enabled: bool = True


class QualityGateCreate(QualityGateBase):
    pass


class QualityGateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    rules: Optional[List[GateRule]] = None
    enabled: Optional[bool] = None


class QualityGateResponse(QualityGateBase):
    """Quality gate response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    created_at: datetime
    updated_at: datetime


class GateCheckRequest(BaseModel):
    """Quality gate check request"""
    target_url: str
    target_headers: Dict[str, str] = Field(default_factory=dict)
    scoring_rules: List[UUID]


class GateCheckResponse(BaseResponse):
    """Quality gate check response"""
    passed: bool
    details: List[Dict[str, Any]]
    eval_task_id: Optional[UUID] = None


# ============== Report Schemas ==============

class ReportSummary(BaseModel):
    """Report summary data"""
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: Decimal
    avg_score: Optional[Decimal]
    avg_latency_ms: Optional[int]
    metrics_breakdown: Dict[str, Any]


class ReportResponse(BaseModel):
    """Report response schema"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    task_id: UUID
    name: str
    summary: ReportSummary
    created_at: datetime


class DashboardStats(BaseModel):
    """Dashboard statistics"""
    total_datasets: int
    total_tasks: int
    total_cases: int
    today_tasks: int
    recent_pass_rate: Optional[Decimal]
    trend_data: List[Dict[str, Any]]
