"""
Scoring rule service
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import ScoringRule
from app.models.schemas import ScoringRuleCreate, ScoringRuleUpdate, PaginationParams


class RuleService:
    """Service for scoring rule operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_rule(self, data: ScoringRuleCreate) -> ScoringRule:
        """Create a new scoring rule"""
        rule = ScoringRule(
            name=data.name,
            rule_type=data.rule_type,
            metric_name=data.metric_name,
            config=data.config,
            threshold=data.threshold,
        )
        self.session.add(rule)
        await self.session.flush()
        return rule
    
    async def get_rule(self, rule_id: UUID) -> Optional[ScoringRule]:
        """Get rule by ID"""
        result = await self.session.execute(
            select(ScoringRule).where(ScoringRule.id == rule_id)
        )
        return result.scalar_one_or_none()
    
    async def list_rules(
        self,
        pagination: PaginationParams,
        rule_type: Optional[str] = None,
    ) -> tuple[List[ScoringRule], int]:
        """List scoring rules"""
        query = select(ScoringRule)
        
        if rule_type:
            query = query.where(ScoringRule.rule_type == rule_type)
        
        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Apply pagination
        query = query.offset((pagination.page - 1) * pagination.page_size)
        query = query.limit(pagination.page_size)
        query = query.order_by(ScoringRule.created_at.desc())
        
        result = await self.session.execute(query)
        rules = result.scalars().all()
        
        return list(rules), total
    
    async def update_rule(
        self,
        rule_id: UUID,
        data: ScoringRuleUpdate,
    ) -> Optional[ScoringRule]:
        """Update scoring rule"""
        rule = await self.get_rule(rule_id)
        if not rule:
            return None
        
        if data.name is not None:
            rule.name = data.name
        if data.config is not None:
            rule.config = data.config
        if data.threshold is not None:
            rule.threshold = data.threshold
        
        await self.session.flush()
        return rule
    
    async def delete_rule(self, rule_id: UUID) -> bool:
        """Delete scoring rule"""
        rule = await self.get_rule(rule_id)
        if not rule:
            return False
        
        await self.session.delete(rule)
        await self.session.flush()
        return True
    
    async def get_rules_by_ids(self, rule_ids: List[UUID]) -> List[ScoringRule]:
        """Get multiple rules by IDs"""
        result = await self.session.execute(
            select(ScoringRule).where(ScoringRule.id.in_(rule_ids))
        )
        return list(result.scalars().all())
