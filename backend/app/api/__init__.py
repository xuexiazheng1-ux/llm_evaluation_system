"""
API routers
"""
from fastapi import APIRouter

from app.api import datasets, rules, evaluate, reports, gates

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(datasets.router)
api_router.include_router(rules.router)
api_router.include_router(evaluate.router)
api_router.include_router(reports.router)
api_router.include_router(gates.router)
