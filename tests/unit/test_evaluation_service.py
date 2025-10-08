"""
Unit tests for EvaluationService

Tests gold query evaluation including:
- Gold query management
- Metric calculations (precision@k, recall@k, MRR)
- Evaluation runs
- Historical tracking
- Report generation
"""
import pytest
import json
from pathlib import Path
from datetime import datetime
from src.services.evaluation_service import (
    EvaluationService,
    GoldQuery,
    QueryResult,
    EvaluationRun
)


# =============================================================================
# EvaluationService Tests
# =============================================================================

class TestEvaluationService:
    """Test the EvaluationService class"""

    @pytest.fixture
    def service(self, tmp_path):
        """Create EvaluationService with temp directory"""
        gold_set_path = tmp_path / "gold_queries.yaml"
        service = EvaluationService(gold_set_path=str(gold_set_path))
        service.results_dir = tmp_path / "results"
        service.results_dir.mkdir(parents=True, exist_ok=True)
        return service

    @pytest.fixture
    def sample_gold_queries(self):
        """Create sample gold queries"""
        return [
            GoldQuery(
                query_id="q001",
                query_text="What is machine learning?",
                expected_doc_ids=["doc1", "doc2", "doc3"],
                category="factual",
                min_precision_at_5=0.6
            ),
            GoldQuery(
                query_id="q002",
                query_text="How does neural network training work?",
                expected_doc_ids=["doc2", "doc4"],
                category="reasoning",
                min_precision_at_5=0.5
            )
        ]

    def test_init(self, service):
        """Test EvaluationService initialization"""
        assert service is not None
        assert service.gold_queries == []
        assert service.history == []
        assert service.results_dir.exists()

    def test_add_gold_query(self, service):
        """Test adding a gold query"""
        query = service.add_gold_query(
            query_text="Test query",
            expected_doc_ids=["doc1", "doc2"],
            category="test",
            min_precision=0.7
        )

        assert query.query_id == "q001"
        assert query.query_text == "Test query"
        assert query.expected_doc_ids == ["doc1", "doc2"]
        assert query.category == "test"
        assert query.min_precision_at_5 == 0.7
        assert len(service.gold_queries) == 1

    def test_add_multiple_gold_queries(self, service):
        """Test adding multiple queries generates sequential IDs"""
        query1 = service.add_gold_query("Query 1", ["doc1"])
        query2 = service.add_gold_query("Query 2", ["doc2"])
        query3 = service.add_gold_query("Query 3", ["doc3"])

        assert query1.query_id == "q001"
        assert query2.query_id == "q002"
        assert query3.query_id == "q003"
        assert len(service.gold_queries) == 3


# =============================================================================
# Metric Calculation Tests
# =============================================================================

class TestMetricCalculations:
    """Test metric calculation methods"""

    @pytest.fixture
    def service(self):
        return EvaluationService()

    def test_precision_at_k_perfect(self, service):
        """Test precision@k with perfect retrieval"""
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        expected = ["doc1", "doc2", "doc3", "doc4", "doc5"]

        precision = service.calculate_precision_at_k(retrieved, expected, 5)
        assert precision == 1.0

    def test_precision_at_k_partial(self, service):
        """Test precision@k with partial matches"""
        retrieved = ["doc1", "doc2", "doc_x", "doc3", "doc_y"]
        expected = ["doc1", "doc2", "doc3"]

        precision = service.calculate_precision_at_k(retrieved, expected, 5)
        assert precision == 0.6  # 3 relevant out of 5

    def test_precision_at_k_no_matches(self, service):
        """Test precision@k with no matches"""
        retrieved = ["doc_x", "doc_y", "doc_z"]
        expected = ["doc1", "doc2", "doc3"]

        precision = service.calculate_precision_at_k(retrieved, expected, 5)
        assert precision == 0.0

    def test_precision_at_k_empty_retrieved(self, service):
        """Test precision@k with empty retrieved list"""
        retrieved = []
        expected = ["doc1", "doc2"]

        precision = service.calculate_precision_at_k(retrieved, expected, 5)
        assert precision == 0.0

    def test_recall_at_k_perfect(self, service):
        """Test recall@k with perfect retrieval"""
        retrieved = ["doc1", "doc2", "doc3"]
        expected = ["doc1", "doc2", "doc3"]

        recall = service.calculate_recall_at_k(retrieved, expected, 5)
        assert recall == 1.0

    def test_recall_at_k_partial(self, service):
        """Test recall@k with partial matches"""
        retrieved = ["doc1", "doc_x", "doc2"]
        expected = ["doc1", "doc2", "doc3", "doc4"]

        recall = service.calculate_recall_at_k(retrieved, expected, 5)
        assert recall == 0.5  # Found 2 out of 4 expected

    def test_recall_at_k_exceeds_k(self, service):
        """Test recall@k when more docs expected than k"""
        retrieved = ["doc1", "doc2", "doc3"]
        expected = ["doc1", "doc2", "doc3", "doc4", "doc5", "doc6"]

        recall = service.calculate_recall_at_k(retrieved, expected, 3)
        assert recall == 0.5  # Found 3 out of 6 expected

    def test_mrr_first_position(self, service):
        """Test MRR when first result is relevant"""
        retrieved = ["doc1", "doc_x", "doc_y"]
        expected = ["doc1", "doc2"]

        mrr = service.calculate_mrr(retrieved, expected)
        assert mrr == 1.0  # 1/1

    def test_mrr_second_position(self, service):
        """Test MRR when second result is relevant"""
        retrieved = ["doc_x", "doc1", "doc_y"]
        expected = ["doc1", "doc2"]

        mrr = service.calculate_mrr(retrieved, expected)
        assert mrr == 0.5  # 1/2

    def test_mrr_third_position(self, service):
        """Test MRR when third result is relevant"""
        retrieved = ["doc_x", "doc_y", "doc1"]
        expected = ["doc1"]

        mrr = service.calculate_mrr(retrieved, expected)
        assert mrr == pytest.approx(0.333, rel=0.01)  # 1/3

    def test_mrr_no_matches(self, service):
        """Test MRR with no relevant results"""
        retrieved = ["doc_x", "doc_y", "doc_z"]
        expected = ["doc1", "doc2"]

        mrr = service.calculate_mrr(retrieved, expected)
        assert mrr == 0.0


# =============================================================================
# Query Evaluation Tests
# =============================================================================

class TestQueryEvaluation:
    """Test single query evaluation"""

    @pytest.fixture
    def service(self):
        return EvaluationService()

    @pytest.fixture
    def gold_query(self):
        return GoldQuery(
            query_id="q001",
            query_text="Test query",
            expected_doc_ids=["doc1", "doc2", "doc3"],
            min_precision_at_5=0.6
        )

    def test_evaluate_query_perfect(self, service, gold_query):
        """Test evaluation with perfect results"""
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]

        result = service.evaluate_query(gold_query, retrieved)

        assert result.query_id == "q001"
        assert result.precision_at_5 == 0.6  # 3 relevant out of 5
        assert result.recall_at_5 == 1.0  # Found all 3 expected
        assert result.mrr == 1.0  # First result relevant
        assert result.found_count == 3
        assert result.expected_count == 3

    def test_evaluate_query_partial(self, service, gold_query):
        """Test evaluation with partial matches"""
        retrieved = ["doc1", "doc_x", "doc2", "doc_y", "doc_z"]

        result = service.evaluate_query(gold_query, retrieved)

        assert result.precision_at_5 == 0.4  # 2 relevant out of 5
        assert result.recall_at_5 == pytest.approx(0.667, rel=0.01)  # Found 2 out of 3
        assert result.mrr == 1.0  # First result relevant
        assert result.found_count == 2

    def test_evaluate_query_stores_metadata(self, service, gold_query):
        """Test that evaluation stores metadata correctly"""
        retrieved = ["doc1", "doc2", "doc3"]

        result = service.evaluate_query(gold_query, retrieved)

        assert result.query_text == "Test query"
        assert result.expected_doc_ids == ["doc1", "doc2", "doc3"]
        assert len(result.retrieved_doc_ids) <= 10  # Stores max 10
        assert isinstance(result.timestamp, str)


# =============================================================================
# File I/O Tests
# =============================================================================

class TestFileIO:
    """Test loading and saving gold queries"""

    @pytest.fixture
    def service(self, tmp_path):
        gold_set_path = tmp_path / "gold_queries.yaml"
        service = EvaluationService(gold_set_path=str(gold_set_path))
        service.results_dir = tmp_path / "results"
        service.results_dir.mkdir(exist_ok=True)
        return service

    def test_save_gold_queries(self, service):
        """Test saving gold queries to YAML"""
        service.add_gold_query("Query 1", ["doc1", "doc2"])
        service.add_gold_query("Query 2", ["doc3"])

        success = service.save_gold_queries()
        assert success is True
        assert Path(service.gold_set_path).exists()

    def test_load_gold_queries(self, service):
        """Test loading gold queries from YAML"""
        # Create and save queries
        service.add_gold_query("Query 1", ["doc1", "doc2"], category="test")
        service.save_gold_queries()

        # Create new service and load
        new_service = EvaluationService(gold_set_path=service.gold_set_path)
        count = new_service.load_gold_queries()

        assert count == 1
        assert len(new_service.gold_queries) == 1
        assert new_service.gold_queries[0].query_text == "Query 1"
        assert new_service.gold_queries[0].expected_doc_ids == ["doc1", "doc2"]

    def test_load_nonexistent_file(self, service):
        """Test loading from nonexistent file"""
        count = service.load_gold_queries("/nonexistent/file.yaml")
        assert count == 0
        assert len(service.gold_queries) == 0

    def test_save_evaluation_run(self, service):
        """Test saving evaluation run to JSON"""
        evaluation_run = EvaluationRun(
            run_id="test_run",
            timestamp=datetime.now().isoformat(),
            total_queries=2,
            avg_precision_at_5=0.75,
            avg_precision_at_10=0.70,
            avg_recall_at_5=0.80,
            avg_recall_at_10=0.85,
            avg_mrr=0.90,
            pass_rate=1.0
        )

        success = service._save_evaluation_run(evaluation_run)
        assert success is True

        result_file = service.results_dir / "test_run.json"
        assert result_file.exists()

        # Verify content
        with open(result_file, 'r') as f:
            data = json.load(f)
        assert data['run_id'] == "test_run"
        assert data['avg_precision_at_5'] == 0.75


# =============================================================================
# Evaluation Run Tests
# =============================================================================

class TestEvaluationRuns:
    """Test complete evaluation runs"""

    @pytest.fixture
    def service(self, tmp_path):
        service = EvaluationService()
        service.results_dir = tmp_path / "results"
        service.results_dir.mkdir(exist_ok=True)

        # Add sample queries
        service.add_gold_query("Query 1", ["doc1", "doc2"], min_precision=0.6)
        service.add_gold_query("Query 2", ["doc3"], min_precision=0.5)

        return service

    @pytest.mark.asyncio
    async def test_run_evaluation_basic(self, service):
        """Test basic evaluation run"""
        async def mock_search(query_text, top_k):
            # Mock search returns different results based on query
            if "Query 1" in query_text:
                return ["doc1", "doc2", "doc_x", "doc_y", "doc_z"]
            else:
                return ["doc3", "doc_x", "doc_y"]

        evaluation_run = await service.run_evaluation(mock_search, top_k=5)

        assert evaluation_run.total_queries == 2
        assert len(evaluation_run.query_results) == 2
        assert evaluation_run.avg_precision_at_5 > 0
        assert evaluation_run.pass_rate >= 0

    @pytest.mark.asyncio
    async def test_run_evaluation_calculates_averages(self, service):
        """Test that evaluation calculates correct averages"""
        async def mock_search(query_text, top_k):
            if "Query 1" in query_text:
                return ["doc1", "doc2", "doc_x"]  # 2/3 relevant
            else:
                return ["doc3", "doc_x", "doc_y"]  # 1/3 relevant

        evaluation_run = await service.run_evaluation(mock_search, top_k=3)

        # Average precision should be (2/3 + 1/3) / 2 = 0.5
        assert evaluation_run.avg_precision_at_5 == pytest.approx(0.5, rel=0.01)

    @pytest.mark.asyncio
    async def test_run_evaluation_empty_queries(self, tmp_path):
        """Test evaluation with no gold queries"""
        service = EvaluationService()
        service.results_dir = tmp_path / "results"
        service.results_dir.mkdir(exist_ok=True)

        async def mock_search(query_text, top_k):
            return []

        evaluation_run = await service.run_evaluation(mock_search)

        assert evaluation_run.total_queries == 0
        assert evaluation_run.avg_precision_at_5 == 0.0

    @pytest.mark.asyncio
    async def test_run_evaluation_handles_errors(self, service):
        """Test that evaluation handles search errors gracefully"""
        async def failing_search(query_text, top_k):
            raise Exception("Search failed")

        evaluation_run = await service.run_evaluation(failing_search)

        assert evaluation_run.total_queries == 2
        assert len(evaluation_run.failed_queries) == 2
        assert len(evaluation_run.query_results) == 0


# =============================================================================
# Historical Tracking Tests
# =============================================================================

class TestHistoricalTracking:
    """Test evaluation history management"""

    @pytest.fixture
    def service(self, tmp_path):
        service = EvaluationService()
        service.results_dir = tmp_path / "results"
        service.results_dir.mkdir(exist_ok=True)
        return service

    def test_load_evaluation_history(self, service):
        """Test loading evaluation history"""
        # Create sample evaluation runs
        run1 = EvaluationRun(
            run_id="eval_20250101_120000",
            timestamp="2025-01-01T12:00:00",
            total_queries=5,
            avg_precision_at_5=0.75,
            avg_precision_at_10=0.70,
            avg_recall_at_5=0.80,
            avg_recall_at_10=0.85,
            avg_mrr=0.90,
            pass_rate=0.85
        )

        service._save_evaluation_run(run1)

        # Load history
        history = service.load_evaluation_history()

        assert len(history) == 1
        assert history[0].run_id == "eval_20250101_120000"
        assert history[0].avg_precision_at_5 == 0.75

    def test_compare_runs(self, service):
        """Test comparing two evaluation runs"""
        run1 = EvaluationRun(
            run_id="run1",
            timestamp="2025-01-01T12:00:00",
            total_queries=5,
            avg_precision_at_5=0.70,
            avg_precision_at_10=0.65,
            avg_recall_at_5=0.75,
            avg_recall_at_10=0.80,
            avg_mrr=0.85,
            pass_rate=0.80
        )

        run2 = EvaluationRun(
            run_id="run2",
            timestamp="2025-01-02T12:00:00",
            total_queries=5,
            avg_precision_at_5=0.80,
            avg_precision_at_10=0.75,
            avg_recall_at_5=0.85,
            avg_recall_at_10=0.90,
            avg_mrr=0.95,
            pass_rate=0.90
        )

        comparison = service.compare_runs(run1, run2)

        assert comparison['precision_at_5_delta'] == pytest.approx(0.10)
        assert comparison['precision_at_10_delta'] == pytest.approx(0.10)
        assert comparison['recall_at_5_delta'] == pytest.approx(0.10)
        assert comparison['pass_rate_delta'] == pytest.approx(0.10)


# =============================================================================
# Report Generation Tests
# =============================================================================

class TestReportGeneration:
    """Test evaluation report generation"""

    @pytest.fixture
    def service(self):
        return EvaluationService()

    @pytest.fixture
    def evaluation_run(self):
        query_result = QueryResult(
            query_id="q001",
            query_text="Test query",
            retrieved_doc_ids=["doc1", "doc2"],
            expected_doc_ids=["doc1", "doc2", "doc3"],
            precision_at_5=0.67,
            precision_at_10=0.67,
            recall_at_5=0.67,
            recall_at_10=0.67,
            mrr=1.0,
            found_count=2,
            expected_count=3
        )

        return EvaluationRun(
            run_id="test_run",
            timestamp="2025-01-01T12:00:00",
            total_queries=1,
            avg_precision_at_5=0.67,
            avg_precision_at_10=0.67,
            avg_recall_at_5=0.67,
            avg_recall_at_10=0.67,
            avg_mrr=1.0,
            pass_rate=1.0,
            query_results=[query_result]
        )

    def test_generate_report(self, service, evaluation_run):
        """Test report generation"""
        report = service.generate_report(evaluation_run)

        assert "# Evaluation Report" in report
        assert "test_run" in report
        assert "Precision@5" in report
        assert "0.67" in report or "0.670" in report
        assert "Test query" in report

    def test_generate_report_includes_metrics(self, service, evaluation_run):
        """Test that report includes all key metrics"""
        report = service.generate_report(evaluation_run)

        assert "Precision@5" in report
        assert "Recall@5" in report
        assert "MRR" in report
        assert "Pass Rate" in report

    def test_generate_report_includes_queries(self, service, evaluation_run):
        """Test that report includes individual queries"""
        report = service.generate_report(evaluation_run)

        assert "q001" in report
        assert "Test query" in report
        assert "2/3" in report  # Found 2 out of 3


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def service(self):
        return EvaluationService()

    def test_precision_with_fewer_results_than_k(self, service):
        """Test precision when retrieved < k"""
        retrieved = ["doc1", "doc2"]
        expected = ["doc1", "doc2", "doc3"]

        precision = service.calculate_precision_at_k(retrieved, expected, 5)
        assert precision == 1.0  # 2 relevant out of 2 retrieved

    def test_metrics_with_empty_expected(self, service):
        """Test metrics with empty expected list"""
        retrieved = ["doc1", "doc2"]
        expected = []

        precision = service.calculate_precision_at_k(retrieved, expected, 5)
        recall = service.calculate_recall_at_k(retrieved, expected, 5)
        mrr = service.calculate_mrr(retrieved, expected)

        assert precision == 0.0
        assert recall == 0.0
        assert mrr == 0.0

    def test_add_gold_query_with_defaults(self, service):
        """Test adding query with default parameters"""
        query = service.add_gold_query("Test", ["doc1"])

        assert query.category == "general"
        assert query.min_precision_at_5 == 0.6
        assert query.notes == ""
