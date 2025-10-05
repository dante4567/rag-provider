"""
Vocabulary Service - Manage controlled vocabularies for enrichment

Loads and manages curated lists of:
- Topics (hierarchical, e.g., school/admin/enrollment)
- Projects (time-bound focus areas)
- Places (locations, institutions)
- People (role-based identifiers)

Enables:
- Controlled tagging (no invented tags)
- Suggested tags for review
- Auto-promotion of frequent suggestions
"""

import yaml
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime, date

logger = logging.getLogger(__name__)


class VocabularyService:
    """Manage controlled vocabularies for document enrichment"""

    def __init__(self, vocab_dir: str = "vocabulary"):
        """
        Initialize vocabulary service

        Args:
            vocab_dir: Path to vocabulary directory
        """
        self.vocab_dir = Path(vocab_dir)
        self.vocabularies = {}
        self.suggested_tags_count = {}  # Track suggestion frequency
        self.load_all()

    def load_all(self):
        """Load all vocabulary files"""
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
                    logger.info(f"✅ Loaded {name} vocabulary from {filename}")
                except Exception as e:
                    logger.error(f"Failed to load {filename}: {e}")
                    self.vocabularies[name] = {}
            else:
                logger.warning(f"Vocabulary file not found: {filename}")
                self.vocabularies[name] = {}

    def reload(self):
        """Reload all vocabularies (useful after updates)"""
        logger.info("Reloading vocabularies...")
        self.load_all()

    # ===== TOPICS =====

    def get_all_topics(self) -> List[str]:
        """Get flat list of all topics"""
        topics_data = self.vocabularies.get("topics", {})
        all_topics = []

        for category, topic_list in topics_data.items():
            if category == "meta":
                continue
            if isinstance(topic_list, list):
                all_topics.extend(topic_list)

        return sorted(all_topics)

    def get_topics_by_category(self, category: str) -> List[str]:
        """Get topics for a specific category"""
        topics_data = self.vocabularies.get("topics", {})
        return topics_data.get(category, [])

    def is_valid_topic(self, topic: str) -> bool:
        """Check if topic exists in vocabulary"""
        return topic in self.get_all_topics()

    def suggest_topic(self, topic: str) -> str:
        """
        Find closest matching topic from vocabulary

        Returns: Best match or original topic if no good match
        """
        from difflib import get_close_matches

        all_topics = self.get_all_topics()
        matches = get_close_matches(topic, all_topics, n=1, cutoff=0.6)

        if matches:
            logger.info(f"Topic suggestion: '{topic}' → '{matches[0]}'")
            return matches[0]

        return topic

    # ===== PROJECTS =====

    def get_active_projects(self) -> List[str]:
        """Get list of active project IDs"""
        projects_data = self.vocabularies.get("projects", {})
        active = projects_data.get("active", {})
        return list(active.keys())

    def get_project_info(self, project_id: str) -> Optional[Dict]:
        """Get project details"""
        projects_data = self.vocabularies.get("projects", {})
        active = projects_data.get("active", {})
        archived = projects_data.get("archived", {})

        if project_id in active:
            return active[project_id]
        elif project_id in archived:
            return archived[project_id]

        return None

    def get_project_watchlist(self, project_id: str) -> List[str]:
        """Get watchlist topics for a project"""
        info = self.get_project_info(project_id)
        return info.get("watchlist", []) if info else []

    def is_project_active(self, project_id: str, check_date: Optional[date] = None) -> bool:
        """Check if project is active on given date"""
        info = self.get_project_info(project_id)
        if not info:
            return False

        check_date = check_date or date.today()

        # Check if date is within project timeframe
        start = info.get("start")
        end = info.get("end")

        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)

        return start <= check_date <= end

    def match_projects_for_doc(self, doc_topics: List[str], doc_date: Optional[date] = None) -> List[str]:
        """
        Find matching projects based on document topics and date

        Args:
            doc_topics: List of topics from document
            doc_date: Document creation date (defaults to today)

        Returns:
            List of matching project IDs
        """
        doc_date = doc_date or date.today()
        matches = []

        for project_id in self.get_active_projects():
            if not self.is_project_active(project_id, doc_date):
                continue

            watchlist = self.get_project_watchlist(project_id)

            # Check if any doc topic matches watchlist
            for topic in doc_topics:
                if topic in watchlist:
                    matches.append(project_id)
                    break

        return matches

    # ===== PLACES =====

    def get_all_places(self) -> List[str]:
        """Get flat list of all places"""
        places_data = self.vocabularies.get("places", {})
        all_places = []

        for category, place_list in places_data.items():
            if category == "meta":
                continue
            if isinstance(place_list, list):
                all_places.extend(place_list)

        return sorted(all_places)

    def is_valid_place(self, place: str) -> bool:
        """Check if place exists in vocabulary"""
        return place in self.get_all_places()

    # ===== PEOPLE =====

    def get_all_people(self) -> List[str]:
        """Get flat list of all people"""
        people_data = self.vocabularies.get("people", {})
        all_people = []

        for category, people_list in people_data.items():
            if category == "meta":
                continue
            if isinstance(people_list, list):
                all_people.extend(people_list)

        return sorted(all_people)

    def is_valid_person(self, person: str) -> bool:
        """Check if person exists in vocabulary"""
        return person in self.get_all_people()

    # ===== SUGGESTED TAGS =====

    def track_suggestion(self, tag: str):
        """Track suggested tag frequency"""
        self.suggested_tags_count[tag] = self.suggested_tags_count.get(tag, 0) + 1

        # Check for auto-promotion
        threshold = self._get_auto_promote_threshold()
        if self.suggested_tags_count[tag] >= threshold:
            logger.info(f"🎯 Tag '{tag}' reached auto-promotion threshold ({threshold})")

    def get_frequent_suggestions(self, min_count: int = 3) -> Dict[str, int]:
        """Get frequently suggested tags"""
        return {
            tag: count
            for tag, count in self.suggested_tags_count.items()
            if count >= min_count
        }

    def _get_auto_promote_threshold(self) -> int:
        """Get auto-promotion threshold from topics config"""
        topics_data = self.vocabularies.get("topics", {})
        meta = topics_data.get("meta", {})
        return meta.get("auto_promote_threshold", 5)

    def add_topic_to_vocabulary(self, topic: str, category: str):
        """
        Add new topic to vocabulary

        Args:
            topic: Topic to add (e.g., "school/new-topic")
            category: Category to add to (e.g., "school")
        """
        topics_path = self.vocab_dir / "topics.yaml"

        if not topics_path.exists():
            logger.error("topics.yaml not found")
            return False

        # Load current topics
        with open(topics_path, 'r') as f:
            topics_data = yaml.safe_load(f)

        # Add topic to category
        if category not in topics_data:
            topics_data[category] = []

        if topic not in topics_data[category]:
            topics_data[category].append(topic)
            topics_data[category].sort()

            # Update metadata
            if "meta" not in topics_data:
                topics_data["meta"] = {}
            topics_data["meta"]["last_updated"] = date.today().isoformat()

            # Write back
            with open(topics_path, 'w') as f:
                yaml.dump(topics_data, f, default_flow_style=False, sort_keys=False)

            logger.info(f"✅ Added '{topic}' to vocabulary under '{category}'")
            self.reload()
            return True

        return False

    # ===== VALIDATION =====

    def validate_metadata(self, metadata: Dict) -> Dict[str, List[str]]:
        """
        Validate metadata against vocabularies

        Returns:
            Dict with keys: valid_topics, valid_places, valid_people,
                           invalid_topics, invalid_places, invalid_people
        """
        result = {
            "valid_topics": [],
            "invalid_topics": [],
            "valid_places": [],
            "invalid_places": [],
            "valid_people": [],
            "invalid_people": []
        }

        # Validate topics
        for topic in metadata.get("topics", []):
            if self.is_valid_topic(topic):
                result["valid_topics"].append(topic)
            else:
                result["invalid_topics"].append(topic)

        # Validate places
        for place in metadata.get("places", []):
            if self.is_valid_place(place):
                result["valid_places"].append(place)
            else:
                result["invalid_places"].append(place)

        # Validate people
        for person in metadata.get("people", []):
            if self.is_valid_person(person):
                result["valid_people"].append(person)
            else:
                result["invalid_people"].append(person)

        return result

    # ===== STATS =====

    def get_stats(self) -> Dict:
        """Get vocabulary statistics"""
        return {
            "topics_count": len(self.get_all_topics()),
            "active_projects_count": len(self.get_active_projects()),
            "places_count": len(self.get_all_places()),
            "people_count": len(self.get_all_people()),
            "suggested_tags_tracked": len(self.suggested_tags_count),
            "frequent_suggestions": len(self.get_frequent_suggestions()),
            "vocabularies_loaded": list(self.vocabularies.keys())
        }


# Singleton instance
_vocabulary_service = None


def get_vocabulary_service(vocab_dir: str = "vocabulary") -> VocabularyService:
    """Get or create singleton vocabulary service"""
    global _vocabulary_service
    if _vocabulary_service is None:
        _vocabulary_service = VocabularyService(vocab_dir)
    return _vocabulary_service
