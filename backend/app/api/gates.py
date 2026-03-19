"""
Quality gate API endpoints
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, QualityGate, EvalTask
from app.models.schemas import (
    QualityGateCreate, QualityGateUpdate, QualityGateResponse,
    GateCheckRequest, GateCheckResponse,
    PaginationParams, PaginatedResponse, BaseResponse,
)
from app.services.eval_service import EvalService
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/gates", tags=["quality-gates"])


@router.post("", response_model=QualityGateResponse, status_code=status.HTTP_201_CREATED)
async def create_gate(
    data: QualityGateCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new quality gate"""
    # Check dataset exists
    dataset_service = DatasetService(db)
    dataset = await dataset_service.get_dataset(data.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    gate = QualityGate(
        name=data.name,
        dataset_id=data.dataset_id,
        rules=[rule.model_dump() for rule in data.rules],
        enabled=data.enabled,
    )
    db.add(gate)
    await db.flush()
    return gate


@router.get("", response_model=PaginatedResponse)
async def list_gates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    dataset_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """List quality gates"""
    query = select(QualityGate)
    
    if dataset_id:
        query = query.where(QualityGate.dataset_id == dataset_id)
    
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    # Get paginated results
    result = await db.execute(
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(QualityGate.created_at.desc())
    )
    gates = result.scalars().all()
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=gates,
    )


@router.get("/{gate_id}", response_model=QualityGateResponse)
async def get_gate(
    gate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get quality gate details"""
    result = await db.execute(
        select(QualityGate).where(QualityGate.id == gate_id)
    )
    gate = result.scalar_one_or_none()
    
    if not gate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quality gate not found",
        )
    
    return gate


@router.put("/{gate_id}", response_model=QualityGateResponse)
async def update_gate(
    gate_id: UUID,
    data: QualityGateUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update quality gate"""
    result = await db.execute(
        select(QualityGate).where(QualityGate.id == gate_id)
    )
    gate = result.scalar_one_or_none()
    
    if not gate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quality gate not found",
        )
    
    if data.name is not None:
        gate.name = data.name
    if data.rules is not None:
        gate.rules = [rule.model_dump() for rule in data.rules]
    if data.enabled is not None:
        gate.enabled = data.enabled
    
    await db.flush()
    return gate


@router.delete("/{gate_id}", response_model=BaseResponse)
async def delete_gate(
    gate_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete quality gate"""
    result = await db.execute(
        select(QualityGate).where(QualityGate.id == gate_id)
    )
    gate = result.scalar_one_or_none()
    
    if not gate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quality gate not found",
        )
    
    await db.delete(gate)
    await db.flush()
    
    return BaseResponse(message="Quality gate deleted successfully")


@router.post("/{gate_id}/check", response_model=GateCheckResponse)
async def check_gate(
    gate_id: UUID,
    request: GateCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute quality gate check"""
    # Get gate configuration
    result = await db.execute(
        select(QualityGate).where(QualityGate.id == gate_id)
    )
    gate = result.scalar_one_or_none()
    
    if not gate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quality gate not found",
        )
    
    if not gate.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quality gate is disabled",
        )
    
    # Execute evaluation
    from app.models.schemas import EvalTaskCreate, EvalTaskConfig
    
    eval_service = EvalService(db)
    
    # Create a task for this gate check
    task_data = EvalTaskCreate(
        name=f"Gate check: {gate.name}",
        dataset_id=gate.dataset_id,
        config=EvalTaskConfig(
            target_url=request.target_url,
            target_headers=request.target_headers,
            scoring_rules=request.scoring_rules,
        ),
    )
    
    task = await eval_service.create_task(task_data, created_by="gate_check")
    
    # Execute evaluation synchronously (for CI/CD integration)
    try:
        eval_result = await eval_service.execute_quick_eval(
            dataset_id=gate.dataset_id,
            config=task_data.config,
            max_cases=100,  # Limit for gate checks
        )
        
        # Evaluate gate rules
        summary = eval_result["summary"]
        details = []
        gate_passed = True
        
        for rule in gate.rules:
            metric = rule.get("metric")
            operator = rule.get("operator")
            threshold = rule.get("threshold", 0)
            
            # Get actual value
            if metric == "pass_rate":
                actual_value = summary.get("pass_rate", 0)
            elif metric == "avg_score":
                actual_value = summary.get("avg_score", 0)
            else:
                actual_value = 0
            
            # Evaluate condition
            if operator == "gt":
                rule_passed = actual_value > threshold
            elif operator == "gte":
                rule_passed = actual_value >= threshold
            elif operator == "lt":
                rule_passed = actual_value < threshold
            elif operator == "lte":
                rule_passed = actual_value <= threshold
            elif operator == "eq":
                rule_passed = actual_value == threshold
            else:
                rule_passed = False
            
            if not rule_passed:
                gate_passed = False
            
            details.append({
                "metric": metric,
                "operator": operator,
                "threshold": threshold,
                "actual_value": actual_value,
                "passed": rule_passed,
            })
        
        # Update task status
        task.status = "completed"
        task.result_summary = summary
        await db.flush()
        
        return GateCheckResponse(
            success=True,
            passed=gate_passed,
            details=details,
            eval_task_id=task.id,
        )
        
    except Exception as e:
        task.status = "failed"
        task.result_summary = {"error": str(e)}
        await db.flush()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gate check failed: {str(e)}",
        )


@router.post("/webhook/{gate_id}")
async def gate_webhook(
    gate_id: UUID,
    request: GateCheckRequest,
    db: AsyncSession = Depends(get_db),
):
    """Webhook endpoint for CI/CD integration"""
    # Same as check but returns simple boolean response
    result = await check_gate(gate_id, request, db)
    
    return {
        "passed": result.passed,
        "task_id": result.eval_task_id,
    }
