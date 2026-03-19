"""
Evaluation service
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from decimal import Decimal

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.celery_app import celery_app
from app.models.database import EvalTask, EvalResult, TestCase, ScoringRule
from app.models.schemas import EvalTaskCreate, EvalTaskConfig, PaginationParams
from app.tasks.evaluation import run_evaluation, run_single_case_evaluation


class EvalService:
    """Service for evaluation operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_task(
        self,
        data: EvalTaskCreate,
        created_by: Optional[str] = None,
    ) -> EvalTask:
        """Create a new evaluation task"""
        # Convert config to dict and ensure UUIDs are converted to strings
        config_dict = data.config.model_dump()
        # Convert scoring_rules UUIDs to strings for JSON serialization
        config_dict['scoring_rules'] = [str(rule_id) for rule_id in config_dict['scoring_rules']]
        
        task = EvalTask(
            name=data.name,
            dataset_id=data.dataset_id,
            status="pending",
            config=config_dict,
            created_by=created_by,
        )
        self.session.add(task)
        await self.session.flush()
        return task
    
    async def get_task(self, task_id: UUID) -> Optional[EvalTask]:
        """Get task by ID"""
        result = await self.session.execute(
            select(EvalTask).where(EvalTask.id == task_id)
        )
        return result.scalar_one_or_none()
    
    async def get_task_with_dataset(self, task_id: UUID) -> Optional[EvalTask]:
        """Get task with dataset info"""
        result = await self.session.execute(
            select(EvalTask)
            .where(EvalTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if task and task.dataset_id:
            from app.models.database import EvalDataset
            dataset_result = await self.session.execute(
                select(EvalDataset).where(EvalDataset.id == task.dataset_id)
            )
            task.dataset = dataset_result.scalar_one_or_none()
        return task
    
    async def list_tasks(
        self,
        pagination: PaginationParams,
        status: Optional[str] = None,
        dataset_id: Optional[UUID] = None,
    ) -> tuple[List[EvalTask], int]:
        """List evaluation tasks"""
        query = select(EvalTask)
        
        if status:
            query = query.where(EvalTask.status == status)
        if dataset_id:
            query = query.where(EvalTask.dataset_id == dataset_id)
        
        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Apply pagination
        query = query.offset((pagination.page - 1) * pagination.page_size)
        query = query.limit(pagination.page_size)
        query = query.order_by(EvalTask.created_at.desc())
        
        result = await self.session.execute(query)
        tasks = result.scalars().all()
        
        return list(tasks), total
    
    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a running task"""
        task = await self.get_task(task_id)
        if not task:
            return False
        
        if task.status not in ["pending", "running"]:
            return False
        
        # Revoke celery task if exists
        if task.celery_task_id:
            celery_app.control.revoke(task.celery_task_id, terminate=True)
        
        task.status = "cancelled"
        task.completed_at = datetime.utcnow()
        await self.session.flush()
        return True
    
    async def get_task_results(
        self,
        task_id: UUID,
        pagination: PaginationParams,
    ) -> tuple[List[EvalResult], int]:
        """Get evaluation results for a task"""
        # Get total count
        count_result = await self.session.execute(
            select(func.count(EvalResult.id)).where(EvalResult.task_id == task_id)
        )
        total = count_result.scalar()
        
        # Get paginated results with test_case loaded
        result = await self.session.execute(
            select(EvalResult)
            .options(selectinload(EvalResult.test_case))
            .where(EvalResult.task_id == task_id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
            .order_by(EvalResult.created_at.desc())
        )
        results = result.scalars().all()
        
        return list(results), total
    
    async def execute_quick_eval(
        self,
        dataset_id: UUID,
        config: EvalTaskConfig,
        max_cases: int = 10,
    ) -> Dict[str, Any]:
        """Execute quick synchronous evaluation"""
        # Get test cases
        result = await self.session.execute(
            select(TestCase)
            .where(TestCase.dataset_id == dataset_id)
            .limit(max_cases)
        )
        test_cases = result.scalars().all()
        
        if not test_cases:
            raise ValueError("No test cases found in dataset")
        
        # Get scoring rules
        rules_result = await self.session.execute(
            select(ScoringRule).where(ScoringRule.id.in_(config.scoring_rules))
        )
        scoring_rules = rules_result.scalars().all()
        
        # Prepare rule configs for task
        rule_configs = [
            {
                "rule_type": rule.rule_type,
                "metric_name": rule.metric_name,
                "config": rule.config or {},
                "threshold": float(rule.threshold) if rule.threshold else 0.5,
            }
            for rule in scoring_rules
        ]
        
        # Execute evaluations
        results = []
        for case in test_cases:
            result = run_single_case_evaluation.delay(
                case_id=str(case.id),
                target_url=config.target_url,
                target_headers=config.target_headers,
                scoring_rules=rule_configs,
                timeout=config.timeout,
            ).get(timeout=300)  # Wait max 5 minutes
            results.append(result)
        
        # Calculate summary
        passed = sum(1 for r in results if r.get("passed"))
        failed = sum(1 for r in results if not r.get("passed") and not r.get("error"))
        errors = sum(1 for r in results if r.get("error"))
        
        scores = [r.get("overall_score", 0) for r in results if r.get("overall_score")]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        return {
            "results": results,
            "summary": {
                "total": len(results),
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "pass_rate": passed / len(results) if results else 0,
                "avg_score": avg_score,
            },
        }
    
    async def should_use_async(self, dataset_id: UUID) -> bool:
        """Determine if async execution should be used based on case count"""
        result = await self.session.execute(
            select(func.count(TestCase.id)).where(TestCase.dataset_id == dataset_id)
        )
        count = result.scalar()
        return count > settings.EVAL_SYNC_THRESHOLD


from datetime import datetime
