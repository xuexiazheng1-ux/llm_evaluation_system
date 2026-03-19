"""
Celery application configuration
"""
from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "llm_eval",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.evaluation"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # Result settings
    result_expires=3600 * 24 * 7,  # Results expire after 7 days
    result_extended=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Disable prefetching for fair scheduling
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks
    
    # Task execution settings
    task_time_limit=3600,  # 1 hour hard time limit
    task_soft_time_limit=3000,  # 50 minutes soft time limit
    
    # Rate limiting for LLM API calls
    task_default_rate_limit="10/m",  # Default rate limit
)

# Configure task routes
celery_app.conf.task_routes = {
    "app.tasks.evaluation.run_evaluation": {"queue": "evaluation"},
    "app.tasks.evaluation.run_single_case": {"queue": "evaluation"},
}

# Configure queues
celery_app.conf.task_queues = {
    "evaluation": {
        "exchange": "evaluation",
        "routing_key": "evaluation",
    },
}


def get_task_info(task_id: str):
    """Get task information by task ID"""
    task = celery_app.AsyncResult(task_id)
    return {
        "task_id": task.id,
        "status": task.status,
        "result": task.result if task.ready() else None,
    }
