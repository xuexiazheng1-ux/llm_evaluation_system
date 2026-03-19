"""
Dataset service for business logic
"""
import json
import csv
import io
import base64
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import EvalDataset, TestCase
from app.models.schemas import (
    EvalDatasetCreate, EvalDatasetUpdate,
    TestCaseCreate, TestCaseUpdate,
    PaginationParams
)


class DatasetService:
    """Service for dataset operations"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_dataset(self, data: EvalDatasetCreate, created_by: Optional[str] = None) -> EvalDataset:
        """Create a new dataset"""
        dataset = EvalDataset(
            name=data.name,
            description=data.description,
            tags=data.tags,
            created_by=created_by,
        )
        self.session.add(dataset)
        await self.session.flush()
        return dataset
    
    async def get_dataset(self, dataset_id: UUID) -> Optional[EvalDataset]:
        """Get dataset by ID"""
        result = await self.session.execute(
            select(EvalDataset).where(EvalDataset.id == dataset_id)
        )
        return result.scalar_one_or_none()
    
    async def get_dataset_with_cases(self, dataset_id: UUID) -> Optional[EvalDataset]:
        """Get dataset with test cases"""
        from sqlalchemy.orm import selectinload
        
        result = await self.session.execute(
            select(EvalDataset)
            .where(EvalDataset.id == dataset_id)
            .options(selectinload(EvalDataset.test_cases))
        )
        dataset = result.scalar_one_or_none()
        return dataset
    
    async def list_datasets(
        self,
        pagination: PaginationParams,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> tuple[List[EvalDataset], int]:
        """List datasets with pagination"""
        query = select(EvalDataset)
        
        # Apply filters
        if search:
            query = query.where(
                (EvalDataset.name.ilike(f"%{search}%")) |
                (EvalDataset.description.ilike(f"%{search}%"))
            )
        
        if tags:
            # Filter by tags (JSON contains)
            for tag in tags:
                query = query.where(EvalDataset.tags.contains([tag]))
        
        # Get total count
        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        
        # Apply pagination
        query = query.offset((pagination.page - 1) * pagination.page_size)
        query = query.limit(pagination.page_size)
        query = query.order_by(EvalDataset.updated_at.desc())
        
        result = await self.session.execute(query)
        datasets = result.scalars().all()
        
        # Get test case counts
        for dataset in datasets:
            count_result = await self.session.execute(
                select(func.count(TestCase.id)).where(TestCase.dataset_id == dataset.id)
            )
            dataset.test_case_count = count_result.scalar()
        
        return list(datasets), total
    
    async def update_dataset(
        self,
        dataset_id: UUID,
        data: EvalDatasetUpdate,
    ) -> Optional[EvalDataset]:
        """Update dataset"""
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            return None
        
        if data.name is not None:
            dataset.name = data.name
        if data.description is not None:
            dataset.description = data.description
        if data.tags is not None:
            dataset.tags = data.tags
        
        await self.session.flush()
        return dataset
    
    async def delete_dataset(self, dataset_id: UUID) -> bool:
        """Delete dataset and all its test cases"""
        dataset = await self.get_dataset(dataset_id)
        if not dataset:
            return False
        
        await self.session.delete(dataset)
        await self.session.flush()
        return True
    
    # ============== Test Case Operations ==============
    
    async def add_test_case(self, dataset_id: UUID, data: TestCaseCreate) -> TestCase:
        """Add a test case to dataset"""
        test_case = TestCase(
            dataset_id=dataset_id,
            input=data.input,
            expected_output=data.expected_output,
            context=data.context,
            metadata=data.case_metadata if data.case_metadata is not None else {},
        )
        self.session.add(test_case)
        await self.session.flush()
        return test_case
    
    async def add_test_cases_batch(
        self,
        dataset_id: UUID,
        cases: List[TestCaseCreate],
    ) -> List[TestCase]:
        """Add multiple test cases"""
        test_cases = [
            TestCase(
                dataset_id=dataset_id,
                input=case.input,
                expected_output=case.expected_output,
                context=case.context,
                metadata=case.case_metadata if hasattr(case, 'case_metadata') else {},
            )
            for case in cases
        ]
        self.session.add_all(test_cases)
        await self.session.flush()
        return test_cases
    
    async def get_test_case(self, case_id: UUID) -> Optional[TestCase]:
        """Get test case by ID"""
        result = await self.session.execute(
            select(TestCase).where(TestCase.id == case_id)
        )
        return result.scalar_one_or_none()
    
    async def list_test_cases(
        self,
        dataset_id: UUID,
        pagination: PaginationParams,
    ) -> tuple[List[TestCase], int]:
        """List test cases for a dataset"""
        # Get total count
        count_result = await self.session.execute(
            select(func.count(TestCase.id)).where(TestCase.dataset_id == dataset_id)
        )
        total = count_result.scalar()
        
        # Get paginated results
        result = await self.session.execute(
            select(TestCase)
            .where(TestCase.dataset_id == dataset_id)
            .offset((pagination.page - 1) * pagination.page_size)
            .limit(pagination.page_size)
            .order_by(TestCase.created_at.desc())
        )
        cases = result.scalars().all()
        
        return list(cases), total
    
    async def update_test_case(
        self,
        case_id: UUID,
        data: TestCaseUpdate,
    ) -> Optional[TestCase]:
        """Update test case"""
        test_case = await self.get_test_case(case_id)
        if not test_case:
            return None
        
        if data.input is not None:
            test_case.input = data.input
        if data.expected_output is not None:
            test_case.expected_output = data.expected_output
        if data.context is not None:
            test_case.context = data.context
        if data.case_metadata is not None:
            test_case.metadata = data.case_metadata
        
        await self.session.flush()
        return test_case
    
    async def delete_test_case(self, case_id: UUID) -> bool:
        """Delete test case"""
        test_case = await self.get_test_case(case_id)
        if not test_case:
            return False
        
        await self.session.delete(test_case)
        await self.session.flush()
        return True
    
    # ============== Import/Export ==============
    
    async def import_from_json(
        self,
        dataset_id: UUID,
        content: str,
    ) -> int:
        """Import test cases from JSON"""
        # Decode base64 content
        decoded = base64.b64decode(content).decode("utf-8")
        data = json.loads(decoded)
        
        cases = []
        if isinstance(data, list):
            cases = data
        elif isinstance(data, dict):
            # Support multiple field names for test cases
            if "cases" in data:
                cases = data["cases"]
            elif "test_cases" in data:
                cases = data["test_cases"]
            else:
                # If it's a single test case object
                cases = [data]
        else:
            raise ValueError("Invalid JSON format: expected list or dict with 'cases' or 'test_cases' field")
        
        test_cases = []
        for case_data in cases:
            test_case = TestCaseCreate(
                input=case_data.get("input", ""),
                expected_output=case_data.get("expected_output"),
                context=case_data.get("context"),
                case_metadata=case_data.get("metadata") or case_data.get("case_metadata", {}),
            )
            test_cases.append(test_case)
        
        await self.add_test_cases_batch(dataset_id, test_cases)
        return len(test_cases)
    
    async def import_from_csv(
        self,
        dataset_id: UUID,
        content: str,
    ) -> int:
        """Import test cases from CSV"""
        # Decode base64 content
        decoded = base64.b64decode(content).decode("utf-8")
        
        # Parse CSV
        reader = csv.DictReader(io.StringIO(decoded))
        test_cases = []
        
        for row in reader:
            test_case = TestCaseCreate(
                input=row.get("input", ""),
                expected_output=row.get("expected_output") or None,
                context=row.get("context") or None,
                case_metadata={},
            )
            test_cases.append(test_case)
        
        await self.add_test_cases_batch(dataset_id, test_cases)
        return len(test_cases)
    
    async def export_to_json(self, dataset_id: UUID) -> str:
        """Export test cases to JSON"""
        result = await self.session.execute(
            select(TestCase).where(TestCase.dataset_id == dataset_id)
        )
        cases = result.scalars().all()
        
        data = {
            "dataset_id": str(dataset_id),
            "cases": [
                {
                    "input": case.input,
                    "expected_output": case.expected_output,
                    "context": case.context,
                    "metadata": case.metadata,
                }
                for case in cases
            ],
        }
        
        return json.dumps(data, ensure_ascii=False, indent=2)
    
    async def export_to_csv(self, dataset_id: UUID) -> str:
        """Export test cases to CSV"""
        result = await self.session.execute(
            select(TestCase).where(TestCase.dataset_id == dataset_id)
        )
        cases = result.scalars().all()
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["input", "expected_output", "context"])
        writer.writeheader()
        
        for case in cases:
            writer.writerow({
                "input": case.input,
                "expected_output": case.expected_output or "",
                "context": case.context or "",
            })
        
        return output.getvalue()
