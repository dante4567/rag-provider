"""
Evaluation Routes - Gold query evaluation and quality tracking

Provides API endpoints for:
- Running evaluation against gold query sets
- Managing gold queries
- Viewing evaluation history
- Comparing evaluation runs
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
import json

from src.services.evaluation_service import (
    EvaluationService,
    GoldQuery,
    EvaluationRun
)

router = APIRouter(tags=["evaluation"])

# Global service instance
evaluation_service = EvaluationService()


class AddGoldQueryRequest(BaseModel):
    """Request to add a gold query"""
    query_text: str
    expected_doc_ids: List[str]
    category: str = "general"
    min_precision: float = 0.6
    notes: str = ""


class RunEvaluationRequest(BaseModel):
    """Request to run evaluation"""
    top_k: int = 10


class EvaluationRunSummary(BaseModel):
    """Summary of evaluation run"""
    run_id: str
    timestamp: str
    total_queries: int
    avg_precision_at_5: float
    avg_precision_at_10: float
    avg_recall_at_5: float
    avg_recall_at_10: float
    avg_mrr: float
    pass_rate: float
    failed_queries: List[str]


@router.get("/evaluation/gold-queries")
async def list_gold_queries():
    """
    List all gold queries in the current set

    Returns:
        List of gold queries with metadata
    """
    try:
        if not evaluation_service.gold_queries:
            # Try to load from file
            evaluation_service.load_gold_queries()

        queries = []
        for query in evaluation_service.gold_queries:
            queries.append({
                "query_id": query.query_id,
                "query_text": query.query_text,
                "expected_doc_ids": query.expected_doc_ids,
                "category": query.category,
                "min_precision_at_5": query.min_precision_at_5,
                "notes": query.notes
            })

        return {
            "total_queries": len(queries),
            "queries": queries
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list gold queries: {str(e)}")


@router.post("/evaluation/gold-queries")
async def add_gold_query(request: AddGoldQueryRequest):
    """
    Add a new gold query to the set

    Args:
        request: Gold query details

    Returns:
        Created gold query with generated ID
    """
    try:
        query = evaluation_service.add_gold_query(
            query_text=request.query_text,
            expected_doc_ids=request.expected_doc_ids,
            category=request.category,
            min_precision=request.min_precision,
            notes=request.notes
        )

        # Save to file
        evaluation_service.save_gold_queries()

        return {
            "success": True,
            "query_id": query.query_id,
            "query_text": query.query_text,
            "expected_doc_count": len(query.expected_doc_ids)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add gold query: {str(e)}")


@router.post("/evaluation/run", response_model=EvaluationRunSummary)
async def run_evaluation(request: RunEvaluationRequest):
    """
    Run evaluation against all gold queries

    Args:
        request: Evaluation parameters (top_k)

    Returns:
        Evaluation run results with metrics
    """
    try:
        # Import RAG service
        from app import RAGService

        if not evaluation_service.gold_queries:
            evaluation_service.load_gold_queries()

        if not evaluation_service.gold_queries:
            raise HTTPException(
                status_code=400,
                detail="No gold queries loaded. Add queries first or load from file."
            )

        # Create search function
        async def search_function(query_text: str, top_k: int) -> List[str]:
            """Wrapper for RAG search that returns doc IDs"""
            try:
                results = await RAGService.vector_service.hybrid_search(
                    query=query_text,
                    top_k=top_k,
                    apply_mmr=True
                )
                return [r.get('document_id', r.get('id', '')) for r in results]
            except Exception:
                return []

        # Run evaluation
        evaluation_run = await evaluation_service.run_evaluation(
            search_function,
            top_k=request.top_k
        )

        return EvaluationRunSummary(
            run_id=evaluation_run.run_id,
            timestamp=evaluation_run.timestamp,
            total_queries=evaluation_run.total_queries,
            avg_precision_at_5=evaluation_run.avg_precision_at_5,
            avg_precision_at_10=evaluation_run.avg_precision_at_10,
            avg_recall_at_5=evaluation_run.avg_recall_at_5,
            avg_recall_at_10=evaluation_run.avg_recall_at_10,
            avg_mrr=evaluation_run.avg_mrr,
            pass_rate=evaluation_run.pass_rate,
            failed_queries=evaluation_run.failed_queries
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get("/evaluation/history")
async def get_evaluation_history(limit: int = 10):
    """
    Get recent evaluation runs

    Args:
        limit: Maximum number of runs to return

    Returns:
        List of evaluation run summaries
    """
    try:
        history = evaluation_service.load_evaluation_history(limit=limit)

        runs = []
        for run in history:
            runs.append({
                "run_id": run.run_id,
                "timestamp": run.timestamp,
                "total_queries": run.total_queries,
                "avg_precision_at_5": run.avg_precision_at_5,
                "avg_recall_at_5": run.avg_recall_at_5,
                "avg_mrr": run.avg_mrr,
                "pass_rate": run.pass_rate
            })

        return {
            "history_count": len(runs),
            "runs": runs
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load history: {str(e)}")


@router.get("/evaluation/report/{run_id}")
async def get_evaluation_report(run_id: str):
    """
    Get detailed report for a specific evaluation run

    Args:
        run_id: Evaluation run ID

    Returns:
        Markdown-formatted evaluation report
    """
    try:
        # Load the specific run
        from pathlib import Path
        result_path = evaluation_service.results_dir / f"{run_id}.json"

        if not result_path.exists():
            raise HTTPException(status_code=404, detail=f"Evaluation run not found: {run_id}")

        with open(result_path, 'r') as f:
            data = json.load(f)

        # Reconstruct evaluation run
        from src.services.evaluation_service import QueryResult
        query_results = [QueryResult(**qr) for qr in data.get('query_results', [])]
        data['query_results'] = query_results
        evaluation_run = EvaluationRun(**data)

        # Generate report
        report = evaluation_service.generate_report(evaluation_run)

        return {
            "run_id": run_id,
            "report_markdown": report
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/evaluation/compare")
async def compare_evaluation_runs(run_id_1: str, run_id_2: str):
    """
    Compare two evaluation runs to detect regression/improvement

    Args:
        run_id_1: First run ID (baseline)
        run_id_2: Second run ID (current)

    Returns:
        Comparison with delta metrics
    """
    try:
        from pathlib import Path

        # Load both runs
        path1 = evaluation_service.results_dir / f"{run_id_1}.json"
        path2 = evaluation_service.results_dir / f"{run_id_2}.json"

        if not path1.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id_1}")
        if not path2.exists():
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id_2}")

        with open(path1, 'r') as f:
            data1 = json.load(f)
        with open(path2, 'r') as f:
            data2 = json.load(f)

        from src.services.evaluation_service import QueryResult

        data1['query_results'] = [QueryResult(**qr) for qr in data1.get('query_results', [])]
        data2['query_results'] = [QueryResult(**qr) for qr in data2.get('query_results', [])]

        run1 = EvaluationRun(**data1)
        run2 = EvaluationRun(**data2)

        # Compare
        comparison = evaluation_service.compare_runs(run1, run2)

        return comparison

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare runs: {str(e)}")


@router.post("/evaluation/upload-gold-set")
async def upload_gold_query_set(file: UploadFile = File(...)):
    """
    Upload a gold query set YAML file

    Args:
        file: YAML file containing gold queries

    Returns:
        Number of queries loaded
    """
    try:
        import tempfile
        from pathlib import Path

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.yaml') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Load queries from temp file
            count = evaluation_service.load_gold_queries(tmp_path)

            # Save to permanent location
            evaluation_service.save_gold_queries()

            return {
                "success": True,
                "queries_loaded": count,
                "message": f"Loaded {count} gold queries"
            }

        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload gold query set: {str(e)}")


@router.get("/evaluation/status")
async def get_evaluation_status():
    """
    Get current evaluation system status

    Returns:
        Status including gold query count, recent runs, etc.
    """
    try:
        # Load current queries if not loaded
        if not evaluation_service.gold_queries:
            evaluation_service.load_gold_queries()

        # Load recent history
        history = evaluation_service.load_evaluation_history(limit=5)

        latest_run = None
        if history:
            latest = history[0]
            latest_run = {
                "run_id": latest.run_id,
                "timestamp": latest.timestamp,
                "avg_precision_at_5": latest.avg_precision_at_5,
                "pass_rate": latest.pass_rate
            }

        return {
            "gold_query_count": len(evaluation_service.gold_queries),
            "evaluation_runs_count": len(history),
            "latest_run": latest_run,
            "gold_queries_file": str(evaluation_service.gold_set_path),
            "results_directory": str(evaluation_service.results_dir)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
