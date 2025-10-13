"""
Entity Name Filter Service - Filter Generic Roles from Specific People

Distinguishes between:
- Generic roles: "Richterin", "Verfahrensbeistand" → Don't create entities
- Specific people: "Richterin Meyer", "Rechtsanwalt Dr. Schmidt" → Create entities

This prevents clutter from generic role mentions.
"""

from typing import List, Set
import logging
import re

logger = logging.getLogger(__name__)


class EntityNameFilterService:
    """Filter generic roles from specific named people"""

    # German legal/professional roles (single words that aren't names)
    GERMAN_ROLES = {
        # Legal roles
        'richterin', 'richter', 'staatsanwalt', 'staatsanwältin',
        'rechtsanwalt', 'rechtsanwältin', 'anwalt', 'anwältin',
        'verfahrensbeistand', 'verfahrensbevollmächtigter',
        'sachverständiger', 'sachverständige', 'notar', 'notarin',
        'prozessbevollmächtigter', 'kläger', 'klägerin',
        'beklagter', 'beklagte', 'angeklagter', 'angeklagte',
        'zeuge', 'zeugin', 'geschädigter', 'geschädigte',

        # Education roles
        'lehrer', 'lehrerin', 'lehrkraft', 'schulleiter', 'schulleiterin',
        'erzieher', 'erzieherin', 'direktor', 'direktorin',
        'klassenlehrer', 'klassenlehrerin', 'rektor', 'rektorin',

        # Medical roles
        'arzt', 'ärztin', 'doktor', 'doktorin', 'therapeut', 'therapeutin',
        'facharzt', 'fachärztin', 'kinderarzt', 'kinderärztin',

        # Business roles
        'geschäftsführer', 'geschäftsführerin', 'vorstand', 'vorständin',
        'manager', 'managerin', 'direktor', 'direktorin',
        'mitarbeiter', 'mitarbeiterin', 'kollege', 'kollegin',

        # Government roles
        'beamter', 'beamtin', 'sachbearbeiter', 'sachbearbeiterin',
        'referent', 'referentin', 'minister', 'ministerin',

        # Generic
        'herr', 'frau', 'person', 'antragsteller', 'antragstellerin'
    }

    # English roles
    ENGLISH_ROLES = {
        'judge', 'lawyer', 'attorney', 'counsel', 'prosecutor',
        'teacher', 'principal', 'doctor', 'manager', 'director',
        'employee', 'colleague', 'representative', 'guardian',
        'witness', 'defendant', 'plaintiff', 'clerk'
    }

    # Titles that indicate a specific person (not just a role)
    SPECIFIC_TITLES = {
        'dr.', 'dr', 'prof.', 'prof', 'dipl.-ing.', 'ing.',
        'mag.', 'msc.', 'ba.', 'ma.', 'phd', 'jr.', 'sr.'
    }

    def __init__(self):
        self.generic_roles = self.GERMAN_ROLES | self.ENGLISH_ROLES

    def filter_people(self, people: List) -> List:
        """
        Filter out generic roles, keep specific named people

        Args:
            people: List of extracted people/roles (strings or person objects)

        Returns:
            List of specific people (generic roles removed)
        """
        if not people:
            return []

        filtered = []
        for person in people:
            # Handle both formats: string or dict
            if isinstance(person, dict):
                name = person.get('name', '')
                if self.is_specific_person(name):
                    filtered.append(person)  # Keep the whole object
                else:
                    logger.debug(f"Filtered out generic role: {name}")
            else:
                # String format
                if self.is_specific_person(person):
                    filtered.append(person)
                else:
                    logger.debug(f"Filtered out generic role: {person}")

        logger.info(f"Filtered {len(people)} people → {len(filtered)} specific people")
        return filtered

    def is_specific_person(self, name: str) -> bool:
        """
        Determine if name is a specific person or just a generic role

        Rules:
        1. Single word that matches known role → Generic (filter out)
        2. Multiple words → Specific person (keep)
        3. Contains title (Dr., Prof.) → Specific person (keep)
        4. Contains family name pattern → Specific person (keep)
        5. All uppercase (except initials) → Generic (filter out)

        Args:
            name: Person name or role

        Returns:
            True if specific person, False if generic role
        """
        if not name or not name.strip():
            return False

        name_clean = name.strip()
        name_lower = name_clean.lower()

        # Check for specific titles (Dr., Prof., etc.)
        for title in self.SPECIFIC_TITLES:
            if title in name_lower:
                logger.debug(f"✓ Specific (has title): {name}")
                return True

        # Split into words
        words = name_clean.split()

        # Single word check
        if len(words) == 1:
            word_lower = words[0].lower()

            # Check if it's a known generic role
            if word_lower in self.generic_roles:
                logger.debug(f"✗ Generic role (single word): {name}")
                return False

            # Single word, but not a known role - might be a last name
            # Keep if it's capitalized and looks like a name (not all caps)
            if words[0][0].isupper() and not words[0].isupper():
                # Could be a surname, keep it
                logger.debug(f"✓ Specific (capitalized surname): {name}")
                return True
            else:
                logger.debug(f"✗ Generic (all caps or lowercase single word): {name}")
                return False

        # Multiple words - check if first word is a generic role
        first_word_lower = words[0].lower()

        # If first word is a known role, check if there's a name after it
        if first_word_lower in self.generic_roles:
            # Check if subsequent words look like a name
            # (capitalized, not another generic word)
            if len(words) > 1:
                second_word_lower = words[1].lower()
                if second_word_lower not in self.generic_roles:
                    # Has role + name → specific person
                    logger.debug(f"✓ Specific (role + name): {name}")
                    return True
                else:
                    # Role + another role → generic
                    logger.debug(f"✗ Generic (role + role): {name}")
                    return False

        # Multiple words, first word not a role → likely a specific person
        logger.debug(f"✓ Specific (multiple words): {name}")
        return True

    def filter_dates(self, dates: List[str]) -> List[str]:
        """
        Filter dates (currently no filtering, but can add logic)

        Future: Filter out past dates beyond certain threshold,
        or dates mentioned in non-actionable contexts.

        Args:
            dates: List of extracted dates

        Returns:
            Filtered list of dates
        """
        # For now, keep all dates
        # Future: Filter based on age, context, etc.
        return dates

    def add_custom_role(self, role: str):
        """
        Add a custom generic role to filter

        Args:
            role: Generic role name to filter out
        """
        self.generic_roles.add(role.lower())
        logger.info(f"Added custom generic role: {role}")

    def add_custom_roles(self, roles: List[str]):
        """
        Add multiple custom generic roles

        Args:
            roles: List of generic role names to filter out
        """
        for role in roles:
            self.add_custom_role(role)


def get_entity_name_filter_service() -> EntityNameFilterService:
    """Get EntityNameFilterService instance"""
    return EntityNameFilterService()


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    service = EntityNameFilterService()

    test_cases = [
        # Generic roles (should be filtered out)
        ("Richterin", False),
        ("Rechtsanwalt", False),
        ("Verfahrensbeistand", False),
        ("Richter", False),
        ("Lehrer", False),

        # Specific people (should be kept)
        ("Richterin Meyer", True),
        ("Rechtsanwalt Dr. Schmidt", True),
        ("Dr. Müller", True),
        ("Prof. Dr. Weber", True),
        ("Verfahrensbeistand Hofmann", True),
        ("Meyer", True),  # Surname
        ("Schmidt", True),  # Surname

        # Edge cases
        ("RECHTSANWALT", False),  # All caps generic
        ("Rechtsanwältin Staatsanwältin", False),  # Role + role
    ]

    logging.basicConfig(level=logging.INFO)
    logger.info("\n=== Entity Name Filter Tests ===\n")
    for name, expected_keep in test_cases:
        result = service.is_specific_person(name)
        status = "✓" if result == expected_keep else "✗"
        action = "KEEP" if result else "FILTER"
        logger.info(f"{status} {action}: '{name}' (expected: {'KEEP' if expected_keep else 'FILTER'})")
