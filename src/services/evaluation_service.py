"""
Evaluation Service - Gold Query Set Testing for RAG Quality

Implements blueprint requirement: "30-50 real queries with expected docs,
nightly precision@5"

Features:
- Gold query set management
- Precision@k, Recall@k, MRR metrics
- Historical tracking and comparison
- Automated evaluation runs
- Performance regression detection
"""

import json
import logging
from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
import yaml

logger = logging.getLogger(__name__)


@dataclass
class GoldQuery:
    """Single gold standard query with expected results"""
    query_id: str
    query_text: str
    expected_doc_ids: List[str]
    category: str = "general"  # e.g., factual, reasoning, multi-hop
    min_precision_at_5: float = 0.6  # Minimum acceptable precision@5
    notes: str = ""


@dataclass
class QueryResult:
    """Result of running a single query"""
    query_id: str
    query_text: str
    retrieved_doc_ids: List[str]
    expected_doc_ids: List[str]
    precision_at_5: float
    precision_at_10: float
    recall_at_5: float
    recall_at_10: float
    mrr: float  # Mean Reciprocal Rank
    found_count: int
    expected_count: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EvaluationRun:
    """Complete evaluation run results"""
    run_id: str
    timestamp: str
    total_queries: int
    avg_precision_at_5: float
    avg_precision_at_10: float
    avg_recall_at_5: float
    avg_recall_at_10: float
    avg_mrr: float
    pass_rate: float  # % queries meeting min_precision_at_5
    query_results: List[QueryResult] = field(default_factory=list)
    failed_queries: List[str] = field(default_factory=list)


class EvaluationService:
    """Service for evaluating RAG retrieval quality with gold queries"""

    def __init__(self, gold_set_path: Optional[str] = None):
        """
        Initialize evaluation service

        Args:
            gold_set_path: Path to gold query set YAML file
        """
        self.gold_set_path = gold_set_path or "evaluation/gold_queries.yaml"
        self.results_dir = Path("evaluation/results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.gold_queries: List[GoldQuery] = []
        self.history: List[EvaluationRun] = []

    def load_gold_queries(self, file_path: Optional[str] = None) -> int:
        """
        Load gold query set from YAML file

        Args:
            file_path: Path to YAML file (optional)

        Returns:
            Number of queries loaded
        """
        path = Path(file_path or self.gold_set_path)

        if not path.exists():
            logger.warning(f"Gold query file not found: {path}")
            return 0

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            queries = data.get('queries', [])
            self.gold_queries = []

            for q in queries:
                gold_query = GoldQuery(
                    query_id=q.get('query_id', ''),
                    query_text=q.get('query_text', ''),
                    expected_doc_ids=q.get('expected_doc_ids', []),
                    category=q.get('category', 'general'),
                    min_precision_at_5=q.get('min_precision_at_5', 0.6),
                    notes=q.get('notes', '')
                )
                self.gold_queries.append(gold_query)

            logger.info(f"Loaded {len(self.gold_queries)} gold queries from {path}")
            return len(self.gold_queries)

        except Exception as e:
            logger.error(f"Failed to load gold queries: {e}")
            return 0

    def save_gold_queries(self, file_path: Optional[str] = None) -> bool:
        """
        Save gold query set to YAML file

        Args:
            file_path: Path to YAML file (optional)

        Returns:
            True if successful
        """
        path = Path(file_path or self.gold_set_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                'version': '1.0',
                'created_at': datetime.now().isoformat(),
                'query_count': len(self.gold_queries),
                'queries': [asdict(q) for q in self.gold_queries]
            }

            with open(path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            logger.info(f"Saved {len(self.gold_queries)} gold queries to {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save gold queries: {e}")
            return False

    def add_gold_query(
        self,
        query_text: str,
        expected_doc_ids: List[str],
        category: str = "general",
        min_precision: float = 0.6,
        notes: str = ""
    ) -> GoldQuery:
        """
        Add a new gold query to the set

        Args:
            query_text: Query string
            expected_doc_ids: List of document IDs that should be retrieved
            category: Query category
            min_precision: Minimum acceptable precision@5
            notes: Optional notes

        Returns:
            Created GoldQuery object
        """
        query_id = f"q{len(self.gold_queries) + 1:03d}"

        gold_query = GoldQuery(
            query_id=query_id,
            query_text=query_text,
            expected_doc_ids=expected_doc_ids,
            category=category,
            min_precision_at_5=min_precision,
            notes=notes
        )

        self.gold_queries.append(gold_query)
        return gold_query

    def calculate_precision_at_k(
        self,
        retrieved: List[str],
        expected: List[str],
        k: int
    ) -> float:
        """
        Calculate precision@k

        Args:
            retrieved: Retrieved document IDs (in rank order)
            expected: Expected document IDs
            k: Number of top results to consider

        Returns:
            Precision@k (0-1)
        """
        if not retrieved or not expected:
            return 0.0

        top_k = retrieved[:k]
        expected_set = set(expected)

        relevant_retrieved = len([doc_id for doc_id in top_k if doc_id in expected_set])
        return relevant_retrieved / min(k, len(top_k))

    def calculate_recall_at_k(
        self,
        retrieved: List[str],
        expected: List[str],
        k: int
    ) -> float:
        """
        Calculate recall@k

        Args:
            retrieved: Retrieved document IDs (in rank order)
            expected: Expected document IDs
            k: Number of top results to consider

        Returns:
            Recall@k (0-1)
        """
        if not expected:
            return 0.0

        top_k = retrieved[:k]
        expected_set = set(expected)

        relevant_retrieved = len([doc_id for doc_id in top_k if doc_id in expected_set])
        return relevant_retrieved / len(expected)

    def calculate_mrr(self, retrieved: List[str], expected: List[str]) -> float:
        """
        Calculate Mean Reciprocal Rank

        Args:
            retrieved: Retrieved document IDs (in rank order)
            expected: Expected document IDs

        Returns:
            MRR score (0-1)
        """
        if not retrieved or not expected:
            return 0.0

        expected_set = set(expected)

        for rank, doc_id in enumerate(retrieved, 1):
            if doc_id in expected_set:
                return 1.0 / rank

        return 0.0

    def evaluate_query(
        self,
        gold_query: GoldQuery,
        retrieved_doc_ids: List[str]
    ) -> QueryResult:
        """
        Evaluate a single query against gold standard

        Args:
            gold_query: Gold query with expected results
            retrieved_doc_ids: Document IDs retrieved by system (in rank order)

        Returns:
            QueryResult with metrics
        """
        expected_set = set(gold_query.expected_doc_ids)
        found_count = len([doc_id for doc_id in retrieved_doc_ids if doc_id in expected_set])

        result = QueryResult(
            query_id=gold_query.query_id,
            query_text=gold_query.query_text,
            retrieved_doc_ids=retrieved_doc_ids[:10],  # Store top 10
            expected_doc_ids=gold_query.expected_doc_ids,
            precision_at_5=self.calculate_precision_at_k(retrieved_doc_ids, gold_query.expected_doc_ids, 5),
            precision_at_10=self.calculate_precision_at_k(retrieved_doc_ids, gold_query.expected_doc_ids, 10),
            recall_at_5=self.calculate_recall_at_k(retrieved_doc_ids, gold_query.expected_doc_ids, 5),
            recall_at_10=self.calculate_recall_at_k(retrieved_doc_ids, gold_query.expected_doc_ids, 10),
            mrr=self.calculate_mrr(retrieved_doc_ids, gold_query.expected_doc_ids),
            found_count=found_count,
            expected_count=len(gold_query.expected_doc_ids)
        )

        return result

    async def run_evaluation(
        self,
        search_function,
        top_k: int = 10
    ) -> EvaluationRun:
        """
        Run complete evaluation against all gold queries

        Args:
            search_function: Async function that takes (query_text, top_k) and returns doc_ids
            top_k: Number of results to retrieve per query

        Returns:
            EvaluationRun with aggregate metrics
        """
        if not self.gold_queries:
            logger.warning("No gold queries loaded")
            return EvaluationRun(
                run_id="",
                timestamp=datetime.now().isoformat(),
                total_queries=0,
                avg_precision_at_5=0.0,
                avg_precision_at_10=0.0,
                avg_recall_at_5=0.0,
                avg_recall_at_10=0.0,
                avg_mrr=0.0,
                pass_rate=0.0
            )

        run_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        query_results = []
        failed_queries = []

        logger.info(f"Starting evaluation run {run_id} with {len(self.gold_queries)} queries")

        for gold_query in self.gold_queries:
            try:
                # Run search
                retrieved_doc_ids = await search_function(gold_query.query_text, top_k)

                # Evaluate
                result = self.evaluate_query(gold_query, retrieved_doc_ids)
                query_results.append(result)

                logger.debug(f"Query {gold_query.query_id}: P@5={result.precision_at_5:.3f}, R@5={result.recall_at_5:.3f}")

            except Exception as e:
                logger.error(f"Failed to evaluate query {gold_query.query_id}: {e}")
                failed_queries.append(gold_query.query_id)

        # Calculate aggregate metrics
        if query_results:
            avg_precision_at_5 = sum(r.precision_at_5 for r in query_results) / len(query_results)
            avg_precision_at_10 = sum(r.precision_at_10 for r in query_results) / len(query_results)
            avg_recall_at_5 = sum(r.recall_at_5 for r in query_results) / len(query_results)
            avg_recall_at_10 = sum(r.recall_at_10 for r in query_results) / len(query_results)
            avg_mrr = sum(r.mrr for r in query_results) / len(query_results)

            # Calculate pass rate (queries meeting min_precision_at_5)
            passed = sum(
                1 for i, r in enumerate(query_results)
                if r.precision_at_5 >= self.gold_queries[i].min_precision_at_5
            )
            pass_rate = passed / len(query_results)
        else:
            avg_precision_at_5 = avg_precision_at_10 = 0.0
            avg_recall_at_5 = avg_recall_at_10 = 0.0
            avg_mrr = pass_rate = 0.0

        evaluation_run = EvaluationRun(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            total_queries=len(self.gold_queries),
            avg_precision_at_5=avg_precision_at_5,
            avg_precision_at_10=avg_precision_at_10,
            avg_recall_at_5=avg_recall_at_5,
            avg_recall_at_10=avg_recall_at_10,
            avg_mrr=avg_mrr,
            pass_rate=pass_rate,
            query_results=query_results,
            failed_queries=failed_queries
        )

        self.history.append(evaluation_run)
        self._save_evaluation_run(evaluation_run)

        logger.info(f"Evaluation complete: P@5={avg_precision_at_5:.3f}, Pass rate={pass_rate:.1%}")

        return evaluation_run

    def _save_evaluation_run(self, evaluation_run: EvaluationRun) -> bool:
        """Save evaluation run to JSON file"""
        try:
            file_path = self.results_dir / f"{evaluation_run.run_id}.json"

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(evaluation_run), f, indent=2)

            logger.info(f"Saved evaluation results to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save evaluation run: {e}")
            return False

    def load_evaluation_history(self, limit: int = 10) -> List[EvaluationRun]:
        """
        Load recent evaluation runs from disk

        Args:
            limit: Maximum number of runs to load

        Returns:
            List of EvaluationRun objects (newest first)
        """
        try:
            run_files = sorted(
                self.results_dir.glob("eval_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            history = []
            for file_path in run_files[:limit]:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Convert dicts back to dataclasses
                query_results = [QueryResult(**qr) for qr in data.get('query_results', [])]
                data['query_results'] = query_results

                run = EvaluationRun(**data)
                history.append(run)

            self.history = history
            logger.info(f"Loaded {len(history)} evaluation runs")
            return history

        except Exception as e:
            logger.error(f"Failed to load evaluation history: {e}")
            return []

    def compare_runs(
        self,
        run1: EvaluationRun,
        run2: EvaluationRun
    ) -> Dict[str, float]:
        """
        Compare two evaluation runs to detect regression/improvement

        Args:
            run1: First evaluation run (baseline)
            run2: Second evaluation run (current)

        Returns:
            Dict with delta metrics
        """
        return {
            'precision_at_5_delta': run2.avg_precision_at_5 - run1.avg_precision_at_5,
            'precision_at_10_delta': run2.avg_precision_at_10 - run1.avg_precision_at_10,
            'recall_at_5_delta': run2.avg_recall_at_5 - run1.avg_recall_at_5,
            'recall_at_10_delta': run2.avg_recall_at_10 - run1.avg_recall_at_10,
            'mrr_delta': run2.avg_mrr - run1.avg_mrr,
            'pass_rate_delta': run2.pass_rate - run1.pass_rate,
            'timestamp_1': run1.timestamp,
            'timestamp_2': run2.timestamp
        }

    def generate_report(self, evaluation_run: EvaluationRun) -> str:
        """
        Generate human-readable evaluation report

        Args:
            evaluation_run: Evaluation run to report on

        Returns:
            Markdown-formatted report
        """
        report = f"""# Evaluation Report: {evaluation_run.run_id}

**Timestamp:** {evaluation_run.timestamp}
**Total Queries:** {evaluation_run.total_queries}

## Aggregate Metrics

| Metric | Value |
|--------|-------|
| Precision@5 | {evaluation_run.avg_precision_at_5:.3f} |
| Precision@10 | {evaluation_run.avg_precision_at_10:.3f} |
| Recall@5 | {evaluation_run.avg_recall_at_5:.3f} |
| Recall@10 | {evaluation_run.avg_recall_at_10:.3f} |
| MRR | {evaluation_run.avg_mrr:.3f} |
| Pass Rate | {evaluation_run.pass_rate:.1%} |

## Query Results

"""

        # Add per-query results
        for result in evaluation_run.query_results:
            status = "✅" if result.precision_at_5 >= 0.6 else "⚠️"
            report += f"""
### {status} {result.query_id}: {result.query_text}

- **Precision@5:** {result.precision_at_5:.3f}
- **Recall@5:** {result.recall_at_5:.3f}
- **MRR:** {result.mrr:.3f}
- **Found:** {result.found_count}/{result.expected_count} expected documents
"""

        # Add failed queries if any
        if evaluation_run.failed_queries:
            report += f"\n## Failed Queries\n\n"
            for query_id in evaluation_run.failed_queries:
                report += f"- {query_id}\n"

        return report
