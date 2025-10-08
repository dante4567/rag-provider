#!/usr/bin/env python3
"""
Retrieval Quality Evaluation Script

Runs gold query set and calculates:
- Precision@k (quality of results)
- Recall@k (coverage)
- MRR (Mean Reciprocal Rank)
- Any Good Citation Rate (% queries with ≥1 relevant result)

Usage:
    python scripts/evaluate_retrieval.py
    python scripts/evaluate_retrieval.py --gold-set evaluation/custom_queries.yaml
    python scripts/evaluate_retrieval.py --api-url http://localhost:8001
"""

import argparse
import yaml
import requests
import json
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
from collections import defaultdict

class RetrievalEvaluator:
    def __init__(self, api_url: str, gold_queries_path: str):
        self.api_url = api_url
        self.gold_queries_path = Path(gold_queries_path)
        self.results = []
        
    def load_gold_queries(self) -> Dict:
        """Load gold query set from YAML"""
        if not self.gold_queries_path.exists():
            raise FileNotFoundError(
                f"Gold query file not found: {self.gold_queries_path}\n"
                f"Copy evaluation/gold_queries.yaml.example to evaluation/gold_queries.yaml"
            )
        
        with open(self.gold_queries_path, 'r') as f:
            return yaml.safe_load(f)
    
    def query_api(self, query_text: str, top_k: int = 10) -> List[Dict]:
        """Query the RAG API and return results"""
        try:
            response = requests.post(
                f"{self.api_url}/search",
                json={"text": query_text, "top_k": top_k},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            print(f"   ⚠️  API error: {e}")
            return []
    
    def extract_doc_id(self, result: Dict) -> str:
        """Extract document ID/filename from search result metadata"""
        metadata = result.get("metadata", {})
        
        # Try different metadata fields for document ID
        doc_id = (
            metadata.get("filename") or 
            metadata.get("source") or
            metadata.get("doc_id") or
            metadata.get("title", "unknown")
        )
        
        # Normalize: remove path, keep just filename
        if isinstance(doc_id, str):
            return Path(doc_id).name
        return str(doc_id)
    
    def calculate_precision_at_k(
        self, retrieved_docs: List[str], relevant_docs: List[str], k: int
    ) -> float:
        """Precision@k: fraction of retrieved docs (in top k) that are relevant"""
        if k == 0:
            return 0.0
        
        retrieved_k = set(retrieved_docs[:k])
        relevant_set = set(relevant_docs)
        
        intersection = retrieved_k & relevant_set
        return len(intersection) / k if k > 0 else 0.0
    
    def calculate_recall_at_k(
        self, retrieved_docs: List[str], relevant_docs: List[str], k: int
    ) -> float:
        """Recall@k: fraction of relevant docs that appear in top k results"""
        if len(relevant_docs) == 0:
            return 0.0
        
        retrieved_k = set(retrieved_docs[:k])
        relevant_set = set(relevant_docs)
        
        intersection = retrieved_k & relevant_set
        return len(intersection) / len(relevant_docs)
    
    def calculate_reciprocal_rank(
        self, retrieved_docs: List[str], relevant_docs: List[str]
    ) -> float:
        """Reciprocal rank: 1/rank of first relevant document (0 if none found)"""
        relevant_set = set(relevant_docs)
        
        for rank, doc in enumerate(retrieved_docs, start=1):
            if doc in relevant_set:
                return 1.0 / rank
        
        return 0.0  # No relevant doc found
    
    def evaluate_single_query(self, query_data: Dict, k_values: List[int]) -> Dict:
        """Evaluate a single query"""
        query_id = query_data["id"]
        query_text = query_data["query"]
        expected_docs = query_data["expected_docs"]
        
        print(f"\n   Query {query_id}: {query_text}")
        print(f"   Expected docs: {expected_docs}")
        
        # Retrieve results from API
        max_k = max(k_values)
        api_results = self.query_api(query_text, top_k=max_k)
        
        # Extract document IDs from results
        retrieved_docs = [self.extract_doc_id(r) for r in api_results]
        
        print(f"   Retrieved: {retrieved_docs[:5]}...")
        
        # Calculate metrics for each k
        metrics = {
            "query_id": query_id,
            "query_text": query_text,
            "expected_docs": expected_docs,
            "retrieved_docs": retrieved_docs,
            "reciprocal_rank": self.calculate_reciprocal_rank(retrieved_docs, expected_docs),
            "has_relevant": any(doc in expected_docs for doc in retrieved_docs),
        }
        
        for k in k_values:
            metrics[f"precision_at_{k}"] = self.calculate_precision_at_k(
                retrieved_docs, expected_docs, k
            )
            metrics[f"recall_at_{k}"] = self.calculate_recall_at_k(
                retrieved_docs, expected_docs, k
            )
        
        print(f"   RR: {metrics['reciprocal_rank']:.3f} | "
              f"P@5: {metrics.get('precision_at_5', 0):.3f} | "
              f"R@10: {metrics.get('recall_at_10', 0):.3f}")
        
        return metrics
    
    def evaluate_all(self) -> Dict:
        """Run evaluation on all queries and aggregate results"""
        gold_data = self.load_gold_queries()
        queries = gold_data["queries"]
        config = gold_data.get("config", {})
        
        k_values = config.get("k_values", [1, 3, 5, 10])
        
        print(f"\n🔍 Running evaluation on {len(queries)} queries...")
        print(f"   API: {self.api_url}")
        print(f"   k values: {k_values}")
        
        # Evaluate each query
        all_results = []
        for query_data in queries:
            result = self.evaluate_single_query(query_data, k_values)
            all_results.append(result)
        
        # Aggregate metrics
        aggregated = self.aggregate_metrics(all_results, k_values, config)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "num_queries": len(queries),
            "individual_results": all_results,
            "aggregated_metrics": aggregated,
            "config": config
        }
    
    def aggregate_metrics(
        self, results: List[Dict], k_values: List[int], config: Dict
    ) -> Dict:
        """Aggregate metrics across all queries"""
        num_queries = len(results)
        
        aggregated = {
            "mrr": sum(r["reciprocal_rank"] for r in results) / num_queries,
            "any_good_citation_rate": sum(1 for r in results if r["has_relevant"]) / num_queries,
        }
        
        # Aggregate precision@k and recall@k
        for k in k_values:
            precision_key = f"precision_at_{k}"
            recall_key = f"recall_at_{k}"
            
            aggregated[precision_key] = sum(r[precision_key] for r in results) / num_queries
            aggregated[recall_key] = sum(r[recall_key] for r in results) / num_queries
        
        # Check quality gates
        gates = {}
        gates["precision_at_5"] = aggregated.get("precision_at_5", 0) >= config.get("min_precision_at_5", 0.6)
        gates["recall_at_10"] = aggregated.get("recall_at_10", 0) >= config.get("min_recall_at_10", 0.7)
        gates["mrr"] = aggregated["mrr"] >= config.get("min_mrr", 0.5)
        gates["any_good_citation"] = aggregated["any_good_citation_rate"] >= config.get("min_any_good_citation", 0.8)
        
        aggregated["quality_gates"] = gates
        aggregated["all_gates_passed"] = all(gates.values())
        
        return aggregated
    
    def print_report(self, eval_results: Dict):
        """Print formatted evaluation report"""
        agg = eval_results["aggregated_metrics"]
        gates = agg["quality_gates"]
        
        print("\n" + "="*70)
        print("📊 RETRIEVAL QUALITY EVALUATION REPORT")
        print("="*70)
        print(f"\nTimestamp: {eval_results['timestamp']}")
        print(f"Queries evaluated: {eval_results['num_queries']}")
        
        print("\n🎯 AGGREGATED METRICS:")
        print(f"   MRR (Mean Reciprocal Rank): {agg['mrr']:.3f} {'✅' if gates['mrr'] else '❌'}")
        print(f"   Any Good Citation Rate:     {agg['any_good_citation_rate']:.3f} {'✅' if gates['any_good_citation'] else '❌'}")
        
        for k in [1, 3, 5, 10]:
            if f"precision_at_{k}" in agg:
                p = agg[f"precision_at_{k}"]
                r = agg[f"recall_at_{k}"]
                p_status = "✅" if k == 5 and gates.get("precision_at_5") else ""
                r_status = "✅" if k == 10 and gates.get("recall_at_10") else ""
                print(f"   Precision@{k}: {p:.3f} {p_status}    Recall@{k}: {r:.3f} {r_status}")
        
        print("\n🚦 QUALITY GATES:")
        for gate_name, passed in gates.items():
            if gate_name != "all_gates_passed":
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"   {gate_name.replace('_', ' ').title()}: {status}")
        
        overall = "✅ ALL GATES PASSED" if agg["all_gates_passed"] else "❌ SOME GATES FAILED"
        print(f"\n🏁 Overall: {overall}")
        print("="*70 + "\n")
        
        return agg["all_gates_passed"]
    
    def save_results(self, eval_results: Dict, output_path: str):
        """Save detailed results to JSON file"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(eval_results, f, indent=2)
        
        print(f"💾 Detailed results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality")
    parser.add_argument(
        "--gold-set",
        default="evaluation/gold_queries.yaml",
        help="Path to gold query YAML file"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8001",
        help="RAG API base URL"
    )
    parser.add_argument(
        "--output",
        default="evaluation/results/latest.json",
        help="Output path for detailed results JSON"
    )
    parser.add_argument(
        "--fail-on-gates",
        action="store_true",
        help="Exit with error code if quality gates fail"
    )
    
    args = parser.parse_args()
    
    evaluator = RetrievalEvaluator(args.api_url, args.gold_set)
    
    try:
        results = evaluator.evaluate_all()
        all_passed = evaluator.print_report(results)
        evaluator.save_results(results, args.output)
        
        if args.fail_on_gates and not all_passed:
            print("❌ Evaluation failed quality gates")
            exit(1)
        
        print("✅ Evaluation complete")
        exit(0)
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
