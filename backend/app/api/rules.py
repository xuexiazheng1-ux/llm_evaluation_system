"""
Scoring rule API endpoints
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import (
    ScoringRuleCreate, ScoringRuleUpdate, ScoringRuleResponse,
    PaginationParams, PaginatedResponse, BaseResponse,
)
from app.services.rule_service import RuleService

router = APIRouter(prefix="/rules", tags=["scoring-rules"])


@router.post("", response_model=ScoringRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    data: ScoringRuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new scoring rule"""
    service = RuleService(db)
    rule = await service.create_rule(data)
    return rule


@router.get("", response_model=PaginatedResponse)
async def list_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rule_type: Optional[str] = Query(None, pattern="^(predefined|geval)$"),
    db: AsyncSession = Depends(get_db),
):
    """List scoring rules"""
    service = RuleService(db)
    pagination = PaginationParams(page=page, page_size=page_size)
    rules, total = await service.list_rules(pagination, rule_type)
    
    # Convert SQLAlchemy models to Pydantic schemas
    rule_responses = [
        ScoringRuleResponse.model_validate(rule) for rule in rules
    ]
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=rule_responses,
    )


@router.get("/{rule_id}", response_model=ScoringRuleResponse)
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get scoring rule details"""
    service = RuleService(db)
    rule = await service.get_rule(rule_id)
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scoring rule not found",
        )
    
    return rule


@router.put("/{rule_id}", response_model=ScoringRuleResponse)
async def update_rule(
    rule_id: UUID,
    data: ScoringRuleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update scoring rule"""
    service = RuleService(db)
    rule = await service.update_rule(rule_id, data)
    
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scoring rule not found",
        )
    
    return rule


@router.delete("/{rule_id}", response_model=BaseResponse)
async def delete_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete scoring rule"""
    service = RuleService(db)
    success = await service.delete_rule(rule_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scoring rule not found",
        )
    
    return BaseResponse(message="Scoring rule deleted successfully")
