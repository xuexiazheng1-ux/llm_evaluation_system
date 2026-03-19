"""
Celery tasks for evaluation execution
"""
import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime
from decimal import Decimal

from celery import shared_task, Task
from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import settings
from app.core.deepeval_integration import deepeval_manager

logger = logging.getLogger(__name__)
from app.models.database import (
    EvalTask, EvalResult, TestCase, ScoringRule,
    AsyncSessionLocal, sync_engine, SessionLocal
)
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker


class DatabaseTask(Task):
    """Base task with database session management"""
    _session = None
    
    def after_return(self, *args, **kwargs):
        """Clean up after task completion"""
        if self._session:
            self._session.close()
            self._session = None


def get_sync_session():
    """Get synchronous database session"""
    Session = sessionmaker(bind=sync_engine)
    return Session()


@shared_task(
    bind=True,
    base=DatabaseTask,
    queue="evaluation",
    max_retries=3,
    default_retry_delay=60,
)
def run_evaluation(self, task_id: str):
    """
    Run evaluation task for a dataset
    
    Args:
        task_id: Evaluation task UUID
    """
    session = get_sync_session()
    
    try:
        # Update task status to running
        session.execute(
            update(EvalTask)
            .where(EvalTask.id == task_id)
            .values(status="running", started_at=datetime.utcnow())
        )
        session.commit()
        
        # Get task details
        task = session.get(EvalTask, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        config = task.config or {}
        target_url = config.get("target_url")
        target_headers = config.get("target_headers", {})
        scoring_rule_ids = config.get("scoring_rules", [])
        concurrency = config.get("concurrency", 1)
        timeout = config.get("timeout", settings.EVAL_TIMEOUT)
        
        # Get test cases
        test_cases = session.execute(
            select(TestCase).where(TestCase.dataset_id == task.dataset_id)
        ).scalars().all()
        
        if not test_cases:
            raise ValueError("No test cases found in dataset")
        
        # Get scoring rules
        scoring_rules = session.execute(
            select(ScoringRule).where(ScoringRule.id.in_(scoring_rule_ids))
        ).scalars().all()
        
        # Create DeepEval metrics
        metrics = []
        for rule in scoring_rules:
            metric = deepeval_manager.create_metric(
                rule.rule_type,
                rule.metric_name,
                rule.config or {},
                float(rule.threshold) if rule.threshold else 0.5,
            )
            metrics.append(metric)
        
        # Run evaluation for each test case
        results_summary = {
            "total": len(test_cases),
            "completed": 0,
            "passed": 0,
            "failed": 0,
            "errors": 0,
        }
        
        for i, test_case in enumerate(test_cases):
            try:
                # Call target agent
                agent_response = asyncio.run(
                    deepeval_manager.call_target_agent(
                        target_url=target_url,
                        input_text=test_case.input,
                        headers=target_headers,
                        timeout=timeout,
                    )
                )
                
                if agent_response.get("error"):
                    # Record error result
                    eval_result = EvalResult(
                        task_id=task_id,
                        case_id=test_case.id,
                        actual_output=None,
                        metrics={},
                        overall_score=Decimal("0"),
                        passed=False,
                        latency_ms=agent_response.get("latency_ms"),
                        error_message=agent_response.get("error"),
                    )
                    results_summary["errors"] += 1
                else:
                    # Log actual output for verification
                    logger.info(f"[Task {task_id}] Case {test_case.id}: actual_output from {target_url} = {agent_response['output'][:200]}...")
                    
                    # Evaluate the response
                    evaluation = deepeval_manager.evaluate_single_case(
                        input_text=test_case.input,
                        actual_output=agent_response["output"],
                        expected_output=test_case.expected_output,
                        context=test_case.context,
                        metrics=metrics,
                    )
                    
                    # Record result
                    eval_result = EvalResult(
                        task_id=task_id,
                        case_id=test_case.id,
                        actual_output=agent_response["output"],
                        metrics=evaluation["metrics"],
                        overall_score=evaluation["overall_score"],
                        passed=evaluation["passed"],
                        latency_ms=agent_response.get("latency_ms"),
                        error_message=None,
                    )
                    
                    if evaluation["passed"]:
                        results_summary["passed"] += 1
                    else:
                        results_summary["failed"] += 1
                
                session.add(eval_result)
                results_summary["completed"] += 1
                
                # Update progress every 5 cases
                if i % 5 == 0:
                    session.commit()
                    self.update_state(
                        state="PROGRESS",
                        meta={
                            "current": i + 1,
                            "total": len(test_cases),
                            "percent": int((i + 1) / len(test_cases) * 100),
                        }
                    )
                
            except Exception as e:
                # Record error for this case
                eval_result = EvalResult(
                    task_id=task_id,
                    case_id=test_case.id,
                    actual_output=None,
                    metrics={},
                    overall_score=Decimal("0"),
                    passed=False,
                    latency_ms=0,
                    error_message=str(e),
                )
                session.add(eval_result)
                results_summary["errors"] += 1
        
        # Final commit
        session.commit()
        
        # Calculate pass rate
        if results_summary["completed"] > 0:
            pass_rate = results_summary["passed"] / results_summary["completed"]
        else:
            pass_rate = 0.0
        
        # Update task with results
        result_summary = {
            "total_cases": results_summary["total"],
            "completed_cases": results_summary["completed"],
            "passed_cases": results_summary["passed"],
            "failed_cases": results_summary["failed"],
            "error_cases": results_summary["errors"],
            "pass_rate": float(pass_rate),
        }
        
        session.execute(
            update(EvalTask)
            .where(EvalTask.id == task_id)
            .values(
                status="completed",
                completed_at=datetime.utcnow(),
                result_summary=result_summary,
            )
        )
        session.commit()
        
        return result_summary
        
    except SoftTimeLimitExceeded:
        # Handle task timeout
        session.execute(
            update(EvalTask)
            .where(EvalTask.id == task_id)
            .values(
                status="failed",
                completed_at=datetime.utcnow(),
                result_summary={"error": "Task timeout"},
            )
        )
        session.commit()
        raise
        
    except Exception as exc:
        # Handle other errors
        session.execute(
            update(EvalTask)
            .where(EvalTask.id == task_id)
            .values(
                status="failed",
                completed_at=datetime.utcnow(),
                result_summary={"error": str(exc)},
            )
        )
        session.commit()
        
        # Retry on failure
        raise self.retry(exc=exc)
        
    finally:
        session.close()


@shared_task(queue="evaluation")
def run_single_case_evaluation(
    case_id: str,
    target_url: str,
    target_headers: Dict[str, Any],
    scoring_rules: List[Dict[str, Any]],
    timeout: int = 60,
) -> Dict[str, Any]:
    """
    Run evaluation for a single test case (for sync/quick evaluation)
    
    Args:
        case_id: Test case UUID
        target_url: Target agent URL
        target_headers: HTTP headers
        scoring_rules: List of scoring rule configurations
        timeout: Request timeout
    
    Returns:
        Evaluation result
    """
    session = get_sync_session()
    
    try:
        # Get test case
        test_case = session.get(TestCase, case_id)
        if not test_case:
            return {"error": f"Test case {case_id} not found"}
        
        # Create metrics
        metrics = []
        for rule_config in scoring_rules:
            metric = deepeval_manager.create_metric(
                rule_config["rule_type"],
                rule_config.get("metric_name"),
                rule_config.get("config", {}),
                rule_config.get("threshold", 0.5),
            )
            metrics.append(metric)
        
        # Call target agent
        agent_response = asyncio.run(
            deepeval_manager.call_target_agent(
                target_url=target_url,
                input_text=test_case.input,
                headers=target_headers,
                timeout=timeout,
            )
        )
        
        if agent_response.get("error"):
            return {
                "case_id": case_id,
                "input": test_case.input,
                "error": agent_response["error"],
                "latency_ms": agent_response.get("latency_ms"),
                "passed": False,
            }
        
        # Evaluate
        evaluation = deepeval_manager.evaluate_single_case(
            input_text=test_case.input,
            actual_output=agent_response["output"],
            expected_output=test_case.expected_output,
            context=test_case.context,
            metrics=metrics,
        )
        
        return {
            "case_id": case_id,
            "input": test_case.input,
            "expected_output": test_case.expected_output,
            "actual_output": agent_response["output"],
            "metrics": evaluation["metrics"],
            "overall_score": float(evaluation["overall_score"]),
            "passed": evaluation["passed"],
            "latency_ms": agent_response.get("latency_ms"),
        }
        
    finally:
        session.close()
