#!/usr/bin/env python3
"""
Collect suggested_topics from all enriched documents
and recommend which to promote to the controlled vocabulary.
"""
import requests
from collections import Counter

BASE_URL = "http://localhost:8001"

def collect_suggested_topics():
    """Query ChromaDB for all documents and collect suggested_topics"""

    print("🔍 Collecting suggested_topics from all documents...\n")

    # Get all documents via stats endpoint (or search with empty query)
    response = requests.post(
        f"{BASE_URL}/search",
        json={"text": "", "top_k": 10000}  # Get all docs
    )

    if response.status_code != 200:
        print(f"❌ Failed to query documents: {response.status_code}")
        return

    results = response.json().get("results", [])
    print(f"📊 Found {len(results)} documents\n")

    # Collect all suggested_topics
    suggested_topics = []
    for doc in results:
        metadata = doc.get("metadata", {})
        topics = metadata.get("suggested_topics", [])
        if isinstance(topics, list):
            suggested_topics.extend(topics)

    # Count frequency
    topic_counts = Counter(suggested_topics)

    print("📈 Suggested Topics (frequency count):\n")
    print("=" * 60)

    # Sort by frequency
    for topic, count in topic_counts.most_common():
        status = "⭐ PROMOTE" if count >= 5 else "  "
        print(f"{status} {topic:40s} ({count:3d} docs)")

    print("=" * 60)
    print(f"\n✅ Total unique suggestions: {len(topic_counts)}")
    print(f"⭐ Topics to promote (5+ mentions): {sum(1 for c in topic_counts.values() if c >= 5)}")
    print("\n💡 Add high-frequency topics to vocabulary/topics.yaml")

if __name__ == "__main__":
    collect_suggested_topics()
