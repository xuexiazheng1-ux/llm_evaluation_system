"""
Report API endpoints
"""
from typing import Optional
from uuid import UUID
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db, EvalTask, EvalResult, EvalDataset, TestCase
from app.models.schemas import (
    ReportResponse, ReportSummary, DashboardStats,
    PaginationParams, PaginatedResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=PaginatedResponse)
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    dataset_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
):
    """List evaluation reports (from completed tasks)"""
    query = select(EvalTask).where(EvalTask.status == "completed")
    
    if dataset_id:
        query = query.where(EvalTask.dataset_id == dataset_id)
    
    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar()
    
    # Get paginated results
    result = await db.execute(
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(EvalTask.completed_at.desc())
    )
    tasks = result.scalars().all()
    
    # Convert to report format
    reports = []
    for task in tasks:
        summary = task.result_summary or {}
        report = {
            "id": task.id,
            "task_id": task.id,
            "name": task.name,
            "summary": {
                "total_cases": summary.get("total_cases", 0),
                "passed_cases": summary.get("passed_cases", 0),
                "failed_cases": summary.get("failed_cases", 0),
                "pass_rate": Decimal(str(summary.get("pass_rate", 0))),
                "avg_score": None,
                "avg_latency_ms": None,
                "metrics_breakdown": {},
            },
            "created_at": task.completed_at or task.created_at,
        }
        reports.append(report)
    
    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=reports,
    )


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get report details"""
    result = await db.execute(
        select(EvalTask).where(EvalTask.id == report_id, EvalTask.status == "completed")
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    
    summary = task.result_summary or {}
    
    # Get detailed metrics breakdown
    result = await db.execute(
        select(EvalResult).where(EvalResult.task_id == report_id)
    )
    eval_results = result.scalars().all()
    
    # Calculate metrics breakdown
    metrics_summary = {}
    latencies = []
    scores = []
    
    for eval_result in eval_results:
        if eval_result.latency_ms:
            latencies.append(eval_result.latency_ms)
        if eval_result.overall_score:
            scores.append(float(eval_result.overall_score))
        
        # Aggregate metrics
        for metric_name, metric_data in (eval_result.metrics or {}).items():
            if metric_name not in metrics_summary:
                metrics_summary[metric_name] = {
                    "total": 0,
                    "passed": 0,
                    "sum_score": 0,
                }
            metrics_summary[metric_name]["total"] += 1
            if metric_data.get("passed"):
                metrics_summary[metric_name]["passed"] += 1
            if metric_data.get("score"):
                metrics_summary[metric_name]["sum_score"] += metric_data["score"]
    
    # Calculate averages
    for metric_name in metrics_summary:
        total = metrics_summary[metric_name]["total"]
        if total > 0:
            metrics_summary[metric_name]["avg_score"] = (
                metrics_summary[metric_name]["sum_score"] / total
            )
            metrics_summary[metric_name]["pass_rate"] = (
                metrics_summary[metric_name]["passed"] / total
            )
    
    report_summary = {
        "total_cases": summary.get("total_cases", 0),
        "passed_cases": summary.get("passed_cases", 0),
        "failed_cases": summary.get("failed_cases", 0),
        "pass_rate": Decimal(str(summary.get("pass_rate", 0))),
        "avg_score": Decimal(str(sum(scores) / len(scores))) if scores else None,
        "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else None,
        "metrics_breakdown": metrics_summary,
    }
    
    return {
        "id": task.id,
        "task_id": task.id,
        "name": task.name,
        "summary": report_summary,
        "created_at": task.completed_at or task.created_at,
    }


@router.get("/{report_id}/download")
async def download_report(
    report_id: UUID,
    format: str = Query("json", pattern="^(json|html)$"),
    db: AsyncSession = Depends(get_db),
):
    """Download report in specified format"""
    result = await db.execute(
        select(EvalTask).where(EvalTask.id == report_id, EvalTask.status == "completed")
    )
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )
    
    # Get detailed results
    result = await db.execute(
        select(EvalResult, TestCase)
        .join(TestCase, EvalResult.case_id == TestCase.id)
        .where(EvalResult.task_id == report_id)
    )
    rows = result.all()
    
    if format == "json":
        import json
        
        report_data = {
            "report_id": str(report_id),
            "task_name": task.name,
            "summary": task.result_summary,
            "results": [
                {
                    "case_id": str(row.EvalResult.case_id),
                    "input": row.TestCase.input,
                    "expected_output": row.TestCase.expected_output,
                    "actual_output": row.EvalResult.actual_output,
                    "metrics": row.EvalResult.metrics,
                    "overall_score": float(row.EvalResult.overall_score) if row.EvalResult.overall_score else None,
                    "passed": row.EvalResult.passed,
                    "latency_ms": row.EvalResult.latency_ms,
                    "error_message": row.EvalResult.error_message,
                }
                for row in rows
            ],
        }
        
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=json.dumps(report_data, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=report_{report_id}.json"},
        )
    
    else:  # HTML format
        # Simple HTML report
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Evaluation Report - {task.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                .summary {{ background: #f5f5f5; padding: 15px; margin: 20px 0; }}
                .result {{ border: 1px solid #ddd; margin: 10px 0; padding: 10px; }}
                .passed {{ border-left: 4px solid #4caf50; }}
                .failed {{ border-left: 4px solid #f44336; }}
                .error {{ border-left: 4px solid #ff9800; }}
            </style>
        </head>
        <body>
            <h1>Evaluation Report: {task.name}</h1>
            <div class="summary">
                <h2>Summary</h2>
                <pre>{task.result_summary}</pre>
            </div>
            <h2>Detailed Results</h2>
        """
        
        for row in rows:
            status_class = "passed" if row.EvalResult.passed else "failed"
            if row.EvalResult.error_message:
                status_class = "error"
            
            html_content += f"""
            <div class="result {status_class}">
                <h3>Case: {row.TestCase.input[:100]}...</h3>
                <p><strong>Expected:</strong> {row.TestCase.expected_output or 'N/A'}</p>
                <p><strong>Actual:</strong> {row.EvalResult.actual_output or 'N/A'}</p>
                <p><strong>Score:</strong> {row.EvalResult.overall_score}</p>
                <p><strong>Status:</strong> {'Passed' if row.EvalResult.passed else 'Failed'}</p>
                {f'<p><strong>Error:</strong> {row.EvalResult.error_message}</p>' if row.EvalResult.error_message else ''}
            </div>
            """
        
        html_content += "</body></html>"
        
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            content=html_content,
            headers={"Content-Disposition": f"attachment; filename=report_{report_id}.html"},
        )


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics"""
    from datetime import datetime, timedelta
    
    # Total counts
    datasets_result = await db.execute(select(func.count(EvalDataset.id)))
    total_datasets = datasets_result.scalar()
    
    tasks_result = await db.execute(select(func.count(EvalTask.id)))
    total_tasks = tasks_result.scalar()
    
    # Today's tasks
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_tasks_result = await db.execute(
        select(func.count(EvalTask.id)).where(EvalTask.created_at >= today_start)
    )
    today_tasks = today_tasks_result.scalar()
    
    # Recent pass rate (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_tasks_result = await db.execute(
        select(EvalTask).where(
            EvalTask.created_at >= week_ago,
            EvalTask.status == "completed",
        )
    )
    recent_tasks = recent_tasks_result.scalars().all()
    
    if recent_tasks:
        total_pass_rate = sum(
            (t.result_summary or {}).get("pass_rate", 0) for t in recent_tasks
        )
        recent_pass_rate = Decimal(str(total_pass_rate / len(recent_tasks)))
    else:
        recent_pass_rate = None
    
    # Trend data (last 30 days)
    trend_data = []
    for i in range(30):
        day = datetime.utcnow() - timedelta(days=i)
        day_start = datetime.combine(day.date(), datetime.min.time())
        day_end = datetime.combine(day.date(), datetime.max.time())
        
        day_tasks_result = await db.execute(
            select(func.count(EvalTask.id)).where(
                EvalTask.created_at >= day_start,
                EvalTask.created_at <= day_end,
            )
        )
        day_tasks = day_tasks_result.scalar()
        
        trend_data.append({
            "date": day.date().isoformat(),
            "tasks": day_tasks,
        })
    
    trend_data.reverse()
    
    return {
        "total_datasets": total_datasets,
        "total_tasks": total_tasks,
        "total_cases": 0,  # Would need to calculate
        "today_tasks": today_tasks,
        "recent_pass_rate": recent_pass_rate,
        "trend_data": trend_data,
    }
