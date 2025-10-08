"""
Contact Service - Generate vCards from extracted people

Automatically creates vCard files for people mentioned in documents.
"""

from pathlib import Path
from typing import List, Dict, Optional, Union
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


class ContactService:
    """Generate vCard files for people extracted from documents"""

    def __init__(self, output_dir: Path = None):
        """
        Initialize contact service

        Args:
            output_dir: Directory for vCard files (default: data/contacts)
        """
        self.output_dir = output_dir or Path("/data/contacts")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_name(self, name: str) -> str:
        """Sanitize name for filename"""
        # Remove special characters, keep letters, numbers, spaces, hyphens
        safe = re.sub(r'[^a-zA-Z0-9\s\-äöüÄÖÜß]', '', name)
        # Replace spaces with hyphens
        safe = re.sub(r'\s+', '-', safe).strip('-')
        return safe.lower()

    def create_vcard(
        self,
        name: str,
        role: Optional[str] = None,
        organization: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        document_sources: List[str] = None,
        notes: Optional[str] = None
    ) -> Path:
        """
        Create vCard file for a person

        Args:
            name: Full name
            role: Job title or role (e.g., "Rechtsanwalt", "Richterin")
            organization: Organization name
            email: Email address
            phone: Phone number
            address: Physical address
            document_sources: List of documents where person was mentioned
            notes: Additional notes

        Returns:
            Path to created vCard file
        """
        safe_name = self.sanitize_name(name)
        filename = f"{safe_name}.vcf"
        file_path = self.output_dir / filename

        # Parse name into components
        name_parts = name.split()
        given_name = name_parts[0] if len(name_parts) > 0 else ""
        family_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        # Build vCard (vCard 3.0 format for compatibility)
        vcard_lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"FN:{name}",
            f"N:{family_name};{given_name};;;",
        ]

        if role:
            vcard_lines.append(f"TITLE:{role}")

        if organization:
            vcard_lines.append(f"ORG:{organization}")

        if email:
            vcard_lines.append(f"EMAIL;TYPE=INTERNET:{email}")

        if phone:
            vcard_lines.append(f"TEL;TYPE=CELL:{phone}")

        if address:
            # vCard 3.0 ADR format: ;;street;city;state;postalcode;country
            # Simple format: just use the full address in street field
            vcard_lines.append(f"ADR;TYPE=WORK:;;{address};;;;")

        # Add notes with document sources
        note_parts = []
        if notes:
            note_parts.append(notes)

        if document_sources:
            sources_text = "Mentioned in: " + ", ".join(document_sources[:3])
            if len(document_sources) > 3:
                sources_text += f" (+{len(document_sources) - 3} more)"
            note_parts.append(sources_text)

        if note_parts:
            combined_notes = " | ".join(note_parts)
            # Escape special characters in notes
            combined_notes = combined_notes.replace(',', '\\,').replace(';', '\\;')
            vcard_lines.append(f"NOTE:{combined_notes}")

        # Add metadata
        vcard_lines.append(f"REV:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}")
        vcard_lines.append("PRODID:-//RAG Provider//Contact Service//EN")

        # Add categories for filtering
        categories = ["RAG-Extracted"]
        if role:
            categories.append(role)
        vcard_lines.append(f"CATEGORIES:{','.join(categories)}")

        vcard_lines.append("END:VCARD")

        # Write vCard file
        vcard_content = "\n".join(vcard_lines) + "\n"
        file_path.write_text(vcard_content, encoding='utf-8')

        logger.info(f"Created vCard for {name}: {file_path}")
        return file_path

    def update_or_create_vcard(
        self,
        name: str,
        role: Optional[str] = None,
        organization: Optional[str] = None,
        document_source: Optional[str] = None,
        **kwargs
    ) -> Path:
        """
        Update existing vCard or create new one

        This merges information from multiple documents about the same person.

        Args:
            name: Person's name
            role: Role/title
            organization: Organization
            document_source: Document where mentioned
            **kwargs: Additional vCard fields

        Returns:
            Path to vCard file
        """
        safe_name = self.sanitize_name(name)
        filename = f"{safe_name}.vcf"
        file_path = self.output_dir / filename

        # Load existing vCard if it exists
        existing_data = {}
        if file_path.exists():
            existing_data = self._parse_vcard(file_path)

        # Merge data
        merged_role = role or existing_data.get('TITLE')
        merged_org = organization or existing_data.get('ORG')

        # Merge document sources
        existing_sources = existing_data.get('document_sources', [])
        if document_source and document_source not in existing_sources:
            existing_sources.append(document_source)

        # Create/update vCard
        return self.create_vcard(
            name=name,
            role=merged_role,
            organization=merged_org,
            document_sources=existing_sources,
            **kwargs
        )

    def _parse_vcard(self, file_path: Path) -> Dict:
        """
        Parse existing vCard file

        Args:
            file_path: Path to vCard file

        Returns:
            Dictionary with vCard fields
        """
        content = file_path.read_text(encoding='utf-8')
        data = {}

        for line in content.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                if key == 'NOTE':
                    # Extract document sources from notes
                    if 'Mentioned in:' in value:
                        sources_part = value.split('Mentioned in:')[1].strip()
                        # Remove " (+X more)" suffix
                        sources_part = re.sub(r'\s+\(\+\d+ more\)', '', sources_part)
                        data['document_sources'] = [s.strip() for s in sources_part.split(',')]
                else:
                    data[key] = value

        return data

    def create_vcards_from_metadata(
        self,
        people: List[Union[str, Dict]],  # Accept both strings and person objects
        organizations: List[str] = None,
        document_title: str = None,
        document_id: str = None
    ) -> List[Path]:
        """
        Create vCards from document metadata

        Args:
            people: List of people (strings or person objects with contact details)
            organizations: List of organizations
            document_title: Source document title
            document_id: Source document ID

        Returns:
            List of created vCard file paths
        """
        vcards = []

        # Create mapping of people to organizations (if mentioned together)
        # (only for string format, person objects have their own org field)
        org_mapping = self._infer_organization_mapping(
            [p if isinstance(p, str) else p.get('name', '') for p in people],
            organizations
        )

        for person in people:
            # Handle both formats: string or dict
            if isinstance(person, dict):
                # New format: person object with contact details
                name = person.get('name', '')
                if not name:
                    continue  # Skip entries without names

                role = person.get('role')
                org = person.get('organization')
                email = person.get('email')
                phone = person.get('phone')
                address = person.get('address')
                bank_account = person.get('bank_account')

                # If no explicit role, try to infer from name
                if not role:
                    role = self._infer_role(name)

                # If no explicit org, use mapping
                if not org:
                    org = org_mapping.get(name)

            else:
                # Old format: simple string name
                name = person
                role = self._infer_role(name)
                org = org_mapping.get(name)
                email = None
                phone = None
                address = None
                bank_account = None

            # Create source reference
            source = document_title or document_id

            # Build kwargs for additional contact fields
            extra_fields = {}
            if email:
                extra_fields['email'] = email
            if phone:
                extra_fields['phone'] = phone
            if address:
                extra_fields['address'] = address
            if bank_account:
                extra_fields['notes'] = f"Bank account: {bank_account}"  # Add to notes

            vcard_path = self.update_or_create_vcard(
                name=name,
                role=role,
                organization=org,
                document_source=source,
                **extra_fields
            )

            vcards.append(vcard_path)

        logger.info(f"Created {len(vcards)} vCards from metadata")
        return vcards

    def _infer_role(self, name: str) -> Optional[str]:
        """
        Infer role from name

        Args:
            name: Person name (may include role)

        Returns:
            Role if found, None otherwise
        """
        role_keywords = {
            'Richterin': 'Judge',
            'Richter': 'Judge',
            'Rechtsanwalt': 'Lawyer',
            'Rechtsanwältin': 'Lawyer',
            'Verfahrensbevollmächtigter': 'Legal Representative',
            'Anwalt': 'Lawyer',
            'Dr.': 'Doctor',
            'Prof.': 'Professor'
        }

        for keyword, role in role_keywords.items():
            if keyword in name:
                return role

        return None

    def _infer_organization_mapping(
        self,
        people: List[str],
        organizations: List[str] = None
    ) -> Dict[str, str]:
        """
        Infer which people belong to which organizations

        Simple heuristic: If name contains organization keywords, map them.

        Args:
            people: List of people
            organizations: List of organizations

        Returns:
            Mapping of person -> organization
        """
        if not organizations:
            return {}

        mapping = {}

        for person in people:
            for org in organizations:
                # Simple match: if org name appears in context near person
                # For now, just return empty mapping
                # TODO: Use context from document to infer relationships
                pass

        return mapping

    def export_all_vcards(self, output_file: Path = None) -> Path:
        """
        Export all vCards to a single .vcf file

        This creates a single file that can be imported into contacts apps.

        Args:
            output_file: Output file path (default: contacts/all_contacts.vcf)

        Returns:
            Path to combined vCard file
        """
        output_file = output_file or self.output_dir / "all_contacts.vcf"

        # Collect all vCard files
        vcard_files = list(self.output_dir.glob("*.vcf"))

        combined_content = []
        for vcard_file in vcard_files:
            if vcard_file != output_file:  # Don't include the combined file itself
                content = vcard_file.read_text(encoding='utf-8')
                combined_content.append(content.strip())

        # Write combined file
        output_file.write_text("\n".join(combined_content) + "\n", encoding='utf-8')

        logger.info(f"Exported {len(combined_content)} vCards to {output_file}")
        return output_file


def get_contact_service(output_dir: Path = None) -> ContactService:
    """Get ContactService instance"""
    return ContactService(output_dir=output_dir)
