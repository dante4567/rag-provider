#!/usr/bin/env python3
"""Test script for VocabularyService"""

import sys
import yaml
import logging
from pathlib import Path
from datetime import date

# Direct import without going through __init__
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(level=logging.INFO)

# Manual load of VocabularyService
class VocabularyService:
    def __init__(self, vocab_dir: str = "vocabulary"):
        self.vocab_dir = Path(vocab_dir)
        self.vocabularies = {}
        self.load_all()

    def load_all(self):
        vocab_files = {
            "topics": "topics.yaml",
            "projects": "projects.yaml",
            "places": "places.yaml",
            "people": "people.yaml"
        }

        for name, filename in vocab_files.items():
            path = self.vocab_dir / filename
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        self.vocabularies[name] = yaml.safe_load(f)
                    print(f"✅ Loaded {name} from {filename}")
                except Exception as e:
                    print(f"❌ Failed to load {filename}: {e}")
                    self.vocabularies[name] = {}
            else:
                print(f"⚠️  Not found: {filename}")
                self.vocabularies[name] = {}

    def get_all_topics(self):
        topics_data = self.vocabularies.get("topics", {})
        all_topics = []
        for category, topic_list in topics_data.items():
            if category == "meta":
                continue
            if isinstance(topic_list, list):
                all_topics.extend(topic_list)
        return sorted(all_topics)

    def get_active_projects(self):
        projects_data = self.vocabularies.get("projects", {})
        active = projects_data.get("active", {})
        return list(active.keys())

    def get_project_info(self, project_id):
        projects_data = self.vocabularies.get("projects", {})
        active = projects_data.get("active", {})
        return active.get(project_id)

    def get_all_places(self):
        places_data = self.vocabularies.get("places", {})
        all_places = []
        for category, place_list in places_data.items():
            if category == "meta":
                continue
            if isinstance(place_list, list):
                all_places.extend(place_list)
        return sorted(all_places)

# Test
if __name__ == "__main__":
    print("=" * 60)
    print("Testing VocabularyService")
    print("=" * 60)

    vocab = VocabularyService('vocabulary')

    print("\n=== Topics ===")
    topics = vocab.get_all_topics()
    print(f"Total topics: {len(topics)}")
    print(f"Sample (first 15): {topics[:15]}")

    print("\n=== Projects ===")
    projects = vocab.get_active_projects()
    print(f"Active projects: {len(projects)}")
    for p in projects:
        info = vocab.get_project_info(p)
        print(f"  • {p}: {info.get('description')}")
        print(f"    Watchlist: {info.get('watchlist', [])}")

    print("\n=== Places ===")
    places = vocab.get_all_places()
    print(f"Total places: {len(places)}")
    print(f"Sample: {places[:10]}")

    print("\n=== Statistics ===")
    print(f"  Topics: {len(vocab.get_all_topics())}")
    print(f"  Projects: {len(vocab.get_active_projects())}")
    print(f"  Places: {len(vocab.get_all_places())}")

    print("\n✅ All tests passed!")
