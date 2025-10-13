#!/usr/bin/env python3
"""
Batch Ingestion Test Script

Ingests a representative sample of the corpus for real-world performance testing.
Measures ingestion speed, success rate, and tracks failures.
"""

import sys
import os
import requests
import time
from pathlib import Path
from typing import List, Dict
import json

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8001")
DATA_DIR = Path(__file__).parent.parent / "data"
MAX_FILES_PER_TYPE = 50  # Limit per file type to avoid overwhelming the system


def find_sample_files() -> Dict[str, List[Path]]:
    """
    Find a representative sample of files from each type

    Returns:
        Dictionary mapping file type to list of file paths
    """
    samples = {
        "contacts": list((DATA_DIR / "contacts").glob("*.vcf"))[:MAX_FILES_PER_TYPE],
        "calendar": list((DATA_DIR / "calendar").glob("*.ics"))[:MAX_FILES_PER_TYPE],
        "pdfs": list((DATA_DIR / "processed_originals").glob("*.pdf"))[:20],  # PDFs are slow
        "markdown": list((DATA_DIR / "obsidian").glob("*.md"))[:MAX_FILES_PER_TYPE],
        "input_files": list((DATA_DIR / "input").glob("*.*"))[:30],  # Mixed types
    }

    return samples


def ingest_file(file_path: Path) -> Dict:
    """
    Ingest a single file via API

    Returns:
        Result dictionary with success, duration, and response
    """
    start_time = time.time()

    try:
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f)}
            response = requests.post(
                f"{API_URL}/ingest/file",
                files=files,
                timeout=60
            )

        duration = time.time() - start_time

        if response.status_code == 200:
            return {
                "success": True,
                "file": file_path.name,
                "duration": duration,
                "response": response.json()
            }
        else:
            return {
                "success": False,
                "file": file_path.name,
                "duration": duration,
                "error": f"HTTP {response.status_code}: {response.text[:200]}"
            }

    except Exception as e:
        duration = time.time() - start_time
        return {
            "success": False,
            "file": file_path.name,
            "duration": duration,
            "error": str(e)
        }


def main():
    """Run batch ingestion test"""

    print("=" * 80)
    print("BATCH INGESTION TEST")
    print("=" * 80)

    # Check API health
    print(f"\n🔍 Checking API health at {API_URL}...")
    try:
        health = requests.get(f"{API_URL}/health", timeout=5).json()
        print(f"✅ API Status: {health.get('status')}")
        print(f"📊 ChromaDB: {health.get('chromadb')}")
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        sys.exit(1)

    # Find files to ingest
    print("\n🔍 Finding sample files...")
    samples = find_sample_files()

    total_files = sum(len(files) for files in samples.values())
    print(f"\n📁 Found {total_files} files to ingest:")
    for file_type, files in samples.items():
        print(f"   - {file_type}: {len(files)} files")

    # Ingest files
    print(f"\n⏳ Starting ingestion (may take several minutes)...\n")

    results = {
        "successes": [],
        "failures": [],
        "total_duration": 0,
        "by_type": {}
    }

    for file_type, files in samples.items():
        print(f"📂 Ingesting {file_type} ({len(files)} files)...")
        type_results = {
            "success_count": 0,
            "failure_count": 0,
            "total_duration": 0
        }

        for i, file_path in enumerate(files, 1):
            result = ingest_file(file_path)

            if result["success"]:
                results["successes"].append(result)
                type_results["success_count"] += 1
                print(f"   ✅ [{i}/{len(files)}] {result['file']} ({result['duration']:.2f}s)")
            else:
                results["failures"].append(result)
                type_results["failure_count"] += 1
                print(f"   ❌ [{i}/{len(files)}] {result['file']}: {result['error']}")

            type_results["total_duration"] += result["duration"]
            results["total_duration"] += result["duration"]

        results["by_type"][file_type] = type_results
        print(f"   ✓ {file_type}: {type_results['success_count']}/{len(files)} succeeded "
              f"({type_results['total_duration']:.2f}s total)\n")

    # Final statistics
    print("\n" + "=" * 80)
    print("INGESTION RESULTS")
    print("=" * 80)

    success_count = len(results["successes"])
    failure_count = len(results["failures"])
    success_rate = (success_count / total_files * 100) if total_files > 0 else 0

    print(f"\n📊 Overall Statistics:")
    print(f"   Total files:      {total_files}")
    print(f"   ✅ Successes:     {success_count} ({success_rate:.1f}%)")
    print(f"   ❌ Failures:      {failure_count}")
    print(f"   ⏱️  Total time:    {results['total_duration']:.2f}s")
    print(f"   ⚡ Avg per file:   {results['total_duration']/total_files:.2f}s")

    print(f"\n📂 By File Type:")
    for file_type, stats in results["by_type"].items():
        total = stats["success_count"] + stats["failure_count"]
        rate = (stats["success_count"] / total * 100) if total > 0 else 0
        avg_time = stats["total_duration"] / total if total > 0 else 0
        print(f"   {file_type}:")
        print(f"      Success: {stats['success_count']}/{total} ({rate:.1f}%)")
        print(f"      Avg time: {avg_time:.2f}s per file")

    # Check final corpus size
    print(f"\n🔍 Checking final corpus size...")
    try:
        stats_response = requests.get(f"{API_URL}/stats", timeout=5).json()
        doc_count = stats_response.get("total_documents", 0)
        chunk_count = stats_response.get("total_chunks", 0)
        print(f"   📚 Total documents indexed: {doc_count}")
        print(f"   🧩 Total chunks:            {chunk_count}")
        if doc_count > 0:
            print(f"   📊 Avg chunks per doc:      {chunk_count/doc_count:.1f}")
    except Exception as e:
        print(f"   ⚠️  Could not fetch stats: {e}")

    # Save results to file
    results_file = Path(__file__).parent.parent / "test_results" / "ingestion_test.json"
    results_file.parent.mkdir(exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_files": total_files,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_rate,
            "total_duration": results["total_duration"],
            "avg_duration_per_file": results["total_duration"] / total_files if total_files > 0 else 0,
            "by_type": results["by_type"],
            "failures": [{"file": f["file"], "error": f["error"]} for f in results["failures"]]
        }, f, indent=2)

    print(f"\n💾 Results saved to: {results_file}")

    print("\n" + "=" * 80)
    print("✅ BATCH INGESTION TEST COMPLETE")
    print("=" * 80)

    # Exit with appropriate code
    sys.exit(0 if failure_count == 0 else 1)


if __name__ == "__main__":
    main()
