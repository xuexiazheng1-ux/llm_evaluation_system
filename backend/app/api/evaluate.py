"""
Evaluation API endpoints
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import (
    EvalTaskCreate, EvalTaskResponse, EvalTaskDetailResponse,
    QuickEvalRequest, QuickEvalResponse, EvalResultResponse,
    PaginationParams, PaginatedResponse, BaseResponse,
)
from app.services.eval_service import EvalService
from app.tasks.evaluation import run_evaluation

router = APIRouter(prefix="/evaluate", tags=["evaluation"])


@router.post("/tasks", response_model=EvalTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_eval_task(
    data: EvalTaskCreate,
    db: AsyncSession = Depends(get_db),
    created_by: Optional[str] = None,
):
    """Create a new evaluation task"""
    service = EvalService(db)
    
    # Check if dataset exists
    from app.services.dataset_service import DatasetService
    dataset_service = DatasetService(db)
    dataset = await dataset_service.get_dataset(data.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    # Create task
    task = await service.create_task(data, created_by)
    
    # Determine sync or async execution
    use_async = await service.should_use_async(data.dataset_id)
    
    if use_async:
        # Submit to Celery for async execution
        celery_task = run_evaluation.delay(str(task.id))
        task.celery_task_id = celery_task.id
        await db.flush()
    else:
        # For small datasets, execute synchronously
        # Still use Celery but wait for result
        celery_task = run_evaluation.delay(str(task.id))
        task.celery_task_id = celery_task.id
        await db.flush()
    
    return task


@router.get("/tasks", response_model=PaginatedResponse)
async def list_eval_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, pattern="^(pending|running|completed|failed|cancelled)$"),
    dataset_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """List evaluation tasks"""
    service = EvalService(db)
    pagination = PaginationParams(page=page, page_size=page_size)
    tasks, total = await service.list_tasks(pagination, status, dataset_id)
    
    # Convert SQLAlchemy models to Pydantic schemas
    task_responses = [EvalTaskResponse.model_validate(task) for task in tasks]
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=task_responses,
    )


@router.get("/tasks/{task_id}", response_model=EvalTaskDetailResponse)
async def get_eval_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation task details"""
    service = EvalService(db)
    task = await service.get_task_with_dataset(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    return task


@router.post("/tasks/{task_id}/cancel", response_model=BaseResponse)
async def cancel_eval_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running evaluation task"""
    service = EvalService(db)
    success = await service.cancel_task(task_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task not found or cannot be cancelled",
        )
    
    return BaseResponse(message="Task cancelled successfully")


@router.get("/tasks/{task_id}/results", response_model=PaginatedResponse)
async def get_eval_results(
    task_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get evaluation results for a task"""
    service = EvalService(db)
    
    # Check task exists
    task = await service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    pagination = PaginationParams(page=page, page_size=page_size)
    results, total = await service.get_task_results(task_id, pagination)
    
    # Convert SQLAlchemy models to Pydantic schemas
    result_responses = [EvalResultResponse.model_validate(result) for result in results]
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=result_responses,
    )


@router.post("/quick", response_model=QuickEvalResponse)
async def quick_evaluate(
    request: QuickEvalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Quick synchronous evaluation (for small datasets)"""
    service = EvalService(db)
    
    # Check dataset exists
    from app.services.dataset_service import DatasetService
    dataset_service = DatasetService(db)
    dataset = await dataset_service.get_dataset(request.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    # Check case count
    case_count = len(dataset.test_cases) if hasattr(dataset, 'test_cases') else 100
    if case_count > request.max_cases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset has too many cases. Use async evaluation for datasets with more than {request.max_cases} cases.",
        )
    
    try:
        from app.models.schemas import EvalTaskConfig
        config = EvalTaskConfig(
            target_url=request.target_url,
            target_headers=request.target_headers,
            scoring_rules=request.scoring_rules,
        )
        
        result = await service.execute_quick_eval(
            dataset_id=request.dataset_id,
            config=config,
            max_cases=request.max_cases,
        )
        
        return QuickEvalResponse(
            task_id=None,  # No persistent task for quick eval
            results=result["results"],
            summary=result["summary"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {str(e)}",
        )


@router.get("/tasks/{task_id}/status")
async def get_task_status(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get task status (for polling)"""
    from app.core.celery_app import get_task_info
    
    service = EvalService(db)
    task = await service.get_task(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    
    response = {
        "task_id": task_id,
        "status": task.status,
        "result_summary": task.result_summary,
    }
    
    # If task has celery task ID, get celery status too
    if task.celery_task_id:
        celery_info = get_task_info(task.celery_task_id)
        response["celery_status"] = celery_info["status"]
    
    return response
