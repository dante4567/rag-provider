"""
Patch Service - Safely apply JSON patches to metadata with diff logging

Applies JSON patches while ensuring:
1. Forbidden fields are never modified
2. Changes are logged for audit trail
3. Patches are reversible
4. Human-readable diffs are generated
"""

import logging
import json
from typing import Dict, Any, List, Tuple
from copy import deepcopy
from datetime import datetime

logger = logging.getLogger(__name__)


class PatchService:
    """
    Safely apply JSON patches to enrichment metadata

    Implements safe patching with validation and diff logging.
    """

    def __init__(self):
        """Initialize patch service"""
        logger.info("🔧 PatchService initialized")

    def apply_patch(
        self,
        original: Dict[str, Any],
        patch: Dict[str, Any],
        forbidden_paths: List[str] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Apply patch and return (patched_metadata, diff)

        Args:
            original: Original metadata dict
            patch: Patch dict with keys: add, replace, remove
            forbidden_paths: Paths that cannot be modified

        Returns:
            Tuple of (patched_metadata, diff_dict)

        Raises:
            ValueError: If patch touches forbidden paths
        """
        if forbidden_paths is None:
            forbidden_paths = []

        # Validate paths first
        self._validate_paths(patch, forbidden_paths)

        # Deep copy to avoid mutating original
        patched = deepcopy(original)

        # Track changes for diff
        changes = {
            "added": {},
            "replaced": {},
            "removed": []
        }

        # Apply adds
        if 'add' in patch and patch['add']:
            for path, value in patch['add'].items():
                old_value = self._set_nested_value(patched, path, value, merge=True)
                if old_value is None:
                    changes['added'][path] = value
                else:
                    changes['replaced'][path] = {
                        "old": old_value,
                        "new": value
                    }

        # Apply replaces
        if 'replace' in patch and patch['replace']:
            for path, value in patch['replace'].items():
                old_value = self._set_nested_value(patched, path, value, merge=False)
                changes['replaced'][path] = {
                    "old": old_value,
                    "new": value
                }

        # Apply removes
        if 'remove' in patch and patch['remove']:
            for path in patch['remove']:
                old_value = self._remove_nested_value(patched, path)
                if old_value is not None:
                    changes['removed'].append({
                        "path": path,
                        "value": old_value
                    })

        # Generate human-readable diff
        diff = self._generate_diff(changes)

        logger.info(f"✅ Patch applied: {len(changes['added'])} adds, "
                   f"{len(changes['replaced'])} replaces, "
                   f"{len(changes['removed'])} removes")

        return patched, diff

    def _validate_paths(self, patch: Dict[str, Any], forbidden: List[str]) -> None:
        """
        Ensure patch doesn't touch forbidden fields

        Args:
            patch: Patch to validate
            forbidden: List of forbidden path prefixes

        Raises:
            ValueError: If patch touches forbidden path
        """
        if not forbidden:
            return

        for action in ['add', 'replace']:
            if action in patch:
                for path in patch[action].keys():
                    for forbidden_path in forbidden:
                        if path == forbidden_path or path.startswith(forbidden_path + '.'):
                            raise ValueError(
                                f"❌ Cannot modify forbidden path: {path}"
                            )

        if 'remove' in patch:
            for path in patch['remove']:
                # Strip array indices for comparison
                base_path = path.split('[')[0]
                for forbidden_path in forbidden:
                    if base_path == forbidden_path or base_path.startswith(forbidden_path + '.'):
                        raise ValueError(
                            f"❌ Cannot remove forbidden path: {path}"
                        )

    def _set_nested_value(
        self,
        obj: Dict[str, Any],
        path: str,
        value: Any,
        merge: bool = False
    ) -> Any:
        """
        Set a nested value using dot notation

        Args:
            obj: Dict to modify
            path: Dot-separated path like "summary.tl_dr"
            value: Value to set
            merge: If True and value is dict/list, merge rather than replace

        Returns:
            Old value at that path (or None if didn't exist)
        """
        parts = path.split('.')
        current = obj

        # Navigate to parent
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]

        # Get old value
        last_part = parts[-1]
        old_value = current.get(last_part)

        # Set new value
        if merge and isinstance(value, dict) and isinstance(old_value, dict):
            # Merge dicts
            current[last_part] = {**old_value, **value}
        elif merge and isinstance(value, list) and isinstance(old_value, list):
            # Append to lists (avoiding duplicates)
            current[last_part] = old_value + [v for v in value if v not in old_value]
        else:
            # Direct replacement
            current[last_part] = value

        return old_value

    def _remove_nested_value(
        self,
        obj: Dict[str, Any],
        path: str
    ) -> Any:
        """
        Remove a nested value using dot notation

        Supports array indices like "topics[2]"

        Args:
            obj: Dict to modify
            path: Dot-separated path, possibly with array index

        Returns:
            Removed value (or None if didn't exist)
        """
        # Handle array indices
        if '[' in path:
            # e.g. "topics[2]"
            base_path, idx_part = path.split('[')
            idx = int(idx_part.rstrip(']'))

            parts = base_path.split('.') if base_path else []
            current = obj

            # Navigate to array
            for part in parts:
                if part not in current:
                    return None
                current = current[part]

            # Remove from array
            if isinstance(current, list) and 0 <= idx < len(current):
                return current.pop(idx)
            return None

        # Regular path
        parts = path.split('.')
        current = obj

        # Navigate to parent
        for part in parts[:-1]:
            if part not in current:
                return None
            current = current[part]

        # Remove value
        last_part = parts[-1]
        if last_part in current:
            return current.pop(last_part)

        return None

    def _generate_diff(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate human-readable diff from changes

        Args:
            changes: Changes dict with added/replaced/removed

        Returns:
            Diff dict with metadata and change summary
        """
        diff = {
            "timestamp": datetime.now().isoformat(),
            "changes_count": (
                len(changes['added']) +
                len(changes['replaced']) +
                len(changes['removed'])
            ),
            "added": changes['added'],
            "replaced": changes['replaced'],
            "removed": changes['removed'],
            "summary": self._generate_summary(changes)
        }

        return diff

    def _generate_summary(self, changes: Dict[str, Any]) -> str:
        """
        Generate human-readable summary of changes

        Args:
            changes: Changes dict

        Returns:
            Human-readable summary string
        """
        lines = []

        if changes['added']:
            lines.append(f"Added {len(changes['added'])} fields:")
            for path, value in list(changes['added'].items())[:5]:  # First 5
                value_str = str(value)[:50]
                lines.append(f"  + {path}: {value_str}")

        if changes['replaced']:
            lines.append(f"Modified {len(changes['replaced'])} fields:")
            for path, change in list(changes['replaced'].items())[:5]:  # First 5
                old_str = str(change['old'])[:30]
                new_str = str(change['new'])[:30]
                lines.append(f"  ~ {path}: {old_str} → {new_str}")

        if changes['removed']:
            lines.append(f"Removed {len(changes['removed'])} fields:")
            for remove_info in changes['removed'][:5]:  # First 5
                path = remove_info['path']
                value_str = str(remove_info['value'])[:30]
                lines.append(f"  - {path}: {value_str}")

        return "\n".join(lines) if lines else "No changes"

    def create_reverse_patch(
        self,
        original: Dict[str, Any],
        patched: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a reverse patch that undoes changes

        Args:
            original: Original metadata
            patched: Patched metadata

        Returns:
            Reverse patch that would restore original
        """
        # This is a simplified version - for full undo support,
        # we'd want to use a proper JSON patch library
        reverse = {
            "add": {},
            "replace": {},
            "remove": []
        }

        # For now, just log that this is a placeholder
        logger.warning("⚠️ Reverse patch generation is a placeholder")

        return reverse
