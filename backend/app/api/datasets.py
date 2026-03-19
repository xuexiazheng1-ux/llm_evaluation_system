"""
Dataset API endpoints
"""
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import (
    EvalDatasetCreate, EvalDatasetUpdate, EvalDatasetResponse,
    EvalDatasetDetailResponse, TestCaseCreate, TestCaseUpdate,
    TestCaseResponse, PaginationParams, PaginatedResponse,
    BaseResponse, DatasetImportRequest,
)
from app.services.dataset_service import DatasetService

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("", response_model=EvalDatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    data: EvalDatasetCreate,
    db: AsyncSession = Depends(get_db),
    created_by: Optional[str] = None,  # TODO: Get from auth
):
    """Create a new dataset"""
    service = DatasetService(db)
    dataset = await service.create_dataset(data, created_by)
    return dataset


@router.get("", response_model=PaginatedResponse)
async def list_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    tags: Optional[List[str]] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List datasets with pagination"""
    service = DatasetService(db)
    pagination = PaginationParams(page=page, page_size=page_size)
    datasets, total = await service.list_datasets(pagination, search, tags)
    
    # Convert SQLAlchemy models to Pydantic schemas
    dataset_responses = [
        EvalDatasetResponse.model_validate(dataset) for dataset in datasets
    ]
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=dataset_responses,
    )


@router.get("/{dataset_id}", response_model=EvalDatasetDetailResponse)
async def get_dataset(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get dataset details with test cases"""
    service = DatasetService(db)
    dataset = await service.get_dataset_with_cases(dataset_id)
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    return dataset


@router.put("/{dataset_id}", response_model=EvalDatasetResponse)
async def update_dataset(
    dataset_id: UUID,
    data: EvalDatasetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update dataset"""
    service = DatasetService(db)
    dataset = await service.update_dataset(dataset_id, data)
    
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    return dataset


@router.delete("/{dataset_id}", response_model=BaseResponse)
async def delete_dataset(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete dataset"""
    service = DatasetService(db)
    success = await service.delete_dataset(dataset_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    return BaseResponse(message="Dataset deleted successfully")


# ============== Test Case Endpoints ==============

@router.post("/{dataset_id}/cases", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
async def add_test_case(
    dataset_id: UUID,
    data: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
):
    """Add a test case to dataset"""
    service = DatasetService(db)
    
    # Check dataset exists
    dataset = await service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    test_case = await service.add_test_case(dataset_id, data)
    return test_case


@router.get("/{dataset_id}/cases", response_model=PaginatedResponse)
async def list_test_cases(
    dataset_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List test cases for a dataset"""
    service = DatasetService(db)
    
    # Check dataset exists
    dataset = await service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    pagination = PaginationParams(page=page, page_size=page_size)
    cases, total = await service.list_test_cases(dataset_id, pagination)
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=cases,
    )


@router.put("/{dataset_id}/cases/{case_id}", response_model=TestCaseResponse)
async def update_test_case(
    dataset_id: UUID,
    case_id: UUID,
    data: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a test case"""
    service = DatasetService(db)
    test_case = await service.update_test_case(case_id, data)
    
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )
    
    return test_case


@router.delete("/{dataset_id}/cases/{case_id}", response_model=BaseResponse)
async def delete_test_case(
    dataset_id: UUID,
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a test case"""
    service = DatasetService(db)
    success = await service.delete_test_case(case_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test case not found",
        )
    
    return BaseResponse(message="Test case deleted successfully")


# ============== Import/Export Endpoints ==============

@router.post("/{dataset_id}/import", response_model=BaseResponse)
async def import_test_cases(
    dataset_id: UUID,
    request: DatasetImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Import test cases from JSON or CSV"""
    service = DatasetService(db)
    
    # Check dataset exists
    dataset = await service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    try:
        if request.format == "json":
            count = await service.import_from_json(dataset_id, request.content)
        elif request.format == "csv":
            count = await service.import_from_csv(dataset_id, request.content)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported format: {request.format}",
            )
        
        return BaseResponse(
            success=True,
            message=f"Successfully imported {count} test cases",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}",
        )


@router.get("/{dataset_id}/export")
async def export_test_cases(
    dataset_id: UUID,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db),
):
    """Export test cases to JSON or CSV"""
    service = DatasetService(db)
    
    # Check dataset exists
    dataset = await service.get_dataset(dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset not found",
        )
    
    try:
        if format == "json":
            content = await service.export_to_json(dataset_id)
            media_type = "application/json"
            filename = f"dataset_{dataset_id}.json"
        else:
            content = await service.export_to_csv(dataset_id)
            media_type = "text/csv"
            filename = f"dataset_{dataset_id}.csv"
        
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}",
        )
