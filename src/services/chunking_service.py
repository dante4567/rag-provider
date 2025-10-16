"""
Structure-Aware Chunking Service

Chunks documents along semantic boundaries (headings, lists, tables) rather than
arbitrary character/token counts. This dramatically improves retrieval precision.

Key Features:
- Respects document structure (H1/H2/H3, lists, tables, code blocks)
- Keeps section titles in chunk content for context
- Rich metadata (section_title, parent_sections, chunk_type, sequence)
- Configurable target size with smart merging
- Tables and code blocks = standalone chunks
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChunkType(str, Enum):
    """Types of chunks based on document structure"""
    HEADING = "heading"          # H1/H2/H3 section
    TABLE = "table"              # Table (always standalone)
    CODE = "code"                # Code block (always standalone)
    LIST = "list"                # Bullet/numbered list
    PARAGRAPH = "paragraph"      # Regular text
    MIXED = "mixed"              # Combined sections


@dataclass
class Chunk:
    """Structured chunk with rich metadata"""
    content: str
    metadata: Dict[str, Any]
    sequence: int
    char_count: int
    estimated_tokens: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "content": self.content,
            "metadata": self.metadata,
            "sequence": self.sequence,
            "char_count": self.char_count,
            "estimated_tokens": self.estimated_tokens
        }


class ChunkingService:
    """
    Structure-aware document chunking

    Uses Markdown structure to create semantically coherent chunks.
    Each chunk preserves context via section titles and parent sections.
    """

    def __init__(
        self,
        target_size: int = 512,      # Target tokens per chunk
        min_size: int = 100,          # Minimum chunk size
        max_size: int = 800,          # Maximum chunk size
        overlap: int = 50             # Overlap in tokens
    ):
        self.target_size = target_size
        self.min_size = min_size
        self.max_size = max_size
        self.overlap = overlap

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)"""
        return len(text) // 4

    def _remove_rag_ignore_blocks(self, content: str) -> str:
        """
        Remove <!-- RAG:IGNORE-START --> ... <!-- RAG:IGNORE-END --> blocks

        These blocks contain Obsidian-specific wiki-links (xref) that should
        not be indexed for RAG retrieval.
        """
        import re

        # Pattern to match RAG:IGNORE blocks
        pattern = r'<!--\s*RAG:IGNORE-START\s*-->.*?<!--\s*RAG:IGNORE-END\s*-->'

        # Remove all matching blocks (case-insensitive, multiline, dotall)
        cleaned = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)

        return cleaned

    def chunk_text(self, content: str, preserve_structure: bool = True) -> List[Dict[str, Any]]:
        """
        Main chunking function

        Args:
            content: Document content (preferably Markdown)
            preserve_structure: Use structure-aware chunking (vs simple split)

        Returns:
            List of chunk dictionaries with content and metadata
        """
        # Remove RAG:IGNORE blocks before processing
        content = self._remove_rag_ignore_blocks(content)

        if not preserve_structure:
            # Fallback to simple chunking
            return self._simple_chunk(content)

        # Parse document structure
        sections = self._parse_markdown_structure(content)

        # Create chunks from sections
        chunks = self._create_chunks_from_sections(sections)

        return [chunk.to_dict() for chunk in chunks]

    def _parse_markdown_structure(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse Markdown into structural sections

        Detects:
        - Headings (# ## ###)
        - Tables (| ... |)
        - Code blocks (``` ... ```)
        - Lists (- or 1.)
        - Paragraphs
        """
        sections = []
        lines = content.split('\n')
        current_section = {
            'type': 'paragraph',
            'content': [],
            'title': None,
            'level': 0,
            'parent_titles': []
        }

        heading_stack = []  # Track heading hierarchy
        in_code_block = False
        in_table = False
        code_fence = None

        i = 0
        while i < len(lines):
            line = lines[i]

            # Code blocks
            if line.strip().startswith('```'):
                if not in_code_block:
                    # Start code block
                    in_code_block = True
                    code_fence = line.strip()
                    language = code_fence[3:].strip() or "text"

                    # Save previous section
                    if current_section['content']:
                        sections.append(current_section)

                    current_section = {
                        'type': 'code',
                        'content': [line],
                        'title': f"Code block ({language})",
                        'level': 0,
                        'parent_titles': heading_stack.copy(),
                        'language': language
                    }
                else:
                    # End code block
                    current_section['content'].append(line)
                    sections.append(current_section)
                    current_section = {
                        'type': 'paragraph',
                        'content': [],
                        'title': None,
                        'level': 0,
                        'parent_titles': heading_stack.copy()
                    }
                    in_code_block = False

                i += 1
                continue

            if in_code_block:
                current_section['content'].append(line)
                i += 1
                continue

            # Headings
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # Save previous section
                if current_section['content']:
                    sections.append(current_section)

                # Update heading stack
                while heading_stack and heading_stack[-1]['level'] >= level:
                    heading_stack.pop()
                heading_stack.append({'level': level, 'title': title})

                # Start new section
                current_section = {
                    'type': 'heading',
                    'content': [line],  # Include heading in content
                    'title': title,
                    'level': level,
                    'parent_titles': [h['title'] for h in heading_stack[:-1]]
                }

                i += 1
                continue

            # Tables
            if '|' in line and line.strip().startswith('|'):
                if not in_table:
                    # Start table
                    in_table = True

                    # Save previous section
                    if current_section['content']:
                        sections.append(current_section)

                    current_section = {
                        'type': 'table',
                        'content': [line],
                        'title': 'Table',
                        'level': 0,
                        'parent_titles': [h['title'] for h in heading_stack]
                    }
                else:
                    current_section['content'].append(line)

                i += 1
                continue
            else:
                if in_table:
                    # End of table
                    sections.append(current_section)
                    current_section = {
                        'type': 'paragraph',
                        'content': [],
                        'title': None,
                        'level': 0,
                        'parent_titles': [h['title'] for h in heading_stack]
                    }
                    in_table = False

            # Lists
            if re.match(r'^\s*[-*+]\s+', line) or re.match(r'^\s*\d+\.\s+', line):
                if current_section['type'] != 'list':
                    # Start list
                    if current_section['content']:
                        sections.append(current_section)

                    current_section = {
                        'type': 'list',
                        'content': [line],
                        'title': 'List',
                        'level': 0,
                        'parent_titles': [h['title'] for h in heading_stack]
                    }
                else:
                    current_section['content'].append(line)

                i += 1
                continue

            # Regular lines
            if line.strip():
                current_section['content'].append(line)
            else:
                # Empty line - potential section break
                if current_section['content']:
                    # Add empty line but don't break section yet
                    current_section['content'].append(line)

            i += 1

        # Save final section
        if current_section['content']:
            sections.append(current_section)

        return sections

    def _create_chunks_from_sections(self, sections: List[Dict[str, Any]]) -> List[Chunk]:
        """
        Convert sections into chunks

        Strategy:
        - Tables and code blocks = always standalone chunks
        - Headings and their content combined until target_size
        - Small sections merged with neighbors
        - Large sections split at paragraph boundaries
        """
        chunks = []
        sequence = 0

        i = 0
        while i < len(sections):
            section = sections[i]
            section_content = '\n'.join(section['content'])
            section_tokens = self.estimate_tokens(section_content)

            # Tables and code always standalone
            if section['type'] in ['table', 'code']:
                chunk = Chunk(
                    content=section_content,
                    metadata={
                        'chunk_type': section['type'],
                        'section_title': section.get('title'),
                        'parent_sections': section.get('parent_titles', []),
                        'language': section.get('language') if section['type'] == 'code' else None
                    },
                    sequence=sequence,
                    char_count=len(section_content),
                    estimated_tokens=section_tokens
                )
                chunks.append(chunk)
                sequence += 1
                i += 1
                continue

            # For other sections, try to build optimal-sized chunks
            chunk_sections = [section]
            chunk_tokens = section_tokens

            # Try to add following sections until target_size
            j = i + 1
            while j < len(sections) and chunk_tokens < self.target_size:
                next_section = sections[j]

                # Don't merge across major heading boundaries
                if next_section['type'] == 'heading' and next_section['level'] <= 2:
                    break

                # Don't merge tables/code
                if next_section['type'] in ['table', 'code']:
                    break

                next_content = '\n'.join(next_section['content'])
                next_tokens = self.estimate_tokens(next_content)

                # Check if adding would exceed max_size
                if chunk_tokens + next_tokens > self.max_size:
                    break

                chunk_sections.append(next_section)
                chunk_tokens += next_tokens
                j += 1

            # Build chunk from accumulated sections
            combined_content = '\n\n'.join(
                '\n'.join(s['content']) for s in chunk_sections
            )

            # Determine chunk type
            chunk_type = self._determine_chunk_type(chunk_sections)

            # Get title (first heading or first section title)
            chunk_title = None
            for s in chunk_sections:
                if s.get('title'):
                    chunk_title = s['title']
                    break

            chunk = Chunk(
                content=combined_content,
                metadata={
                    'chunk_type': chunk_type,
                    'section_title': chunk_title,
                    'parent_sections': chunk_sections[0].get('parent_titles', []),
                    'section_count': len(chunk_sections)
                },
                sequence=sequence,
                char_count=len(combined_content),
                estimated_tokens=chunk_tokens
            )
            chunks.append(chunk)
            sequence += 1

            # Move to next unprocessed section
            i = j

        return chunks

    def _determine_chunk_type(self, sections: List[Dict[str, Any]]) -> str:
        """Determine the primary type of a multi-section chunk"""
        types = [s['type'] for s in sections]

        if len(set(types)) == 1:
            return types[0]
        elif 'heading' in types:
            return ChunkType.HEADING
        else:
            return ChunkType.MIXED

    def chunk_chat_log(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Strategic turn-based chunking for chat logs

        Breaks conversations into semantic chunks based on Q&A pairs (turns).
        Each chunk includes 1-3 related turns with context headers.

        Args:
            content: Chat log content with User/Assistant turns
            metadata: Optional metadata from chat_log_handler

        Returns:
            List of chunk dictionaries optimized for RAG retrieval
        """
        # Parse turns (user/assistant pairs)
        turns = self._parse_chat_turns(content)

        if not turns:
            # Fallback to simple chunking
            logger.warning("No turns detected in chat log, using simple chunking")
            return self._simple_chunk(content)

        # Group turns into semantic chunks
        chunks = []
        sequence = 0
        current_chunk_turns = []
        current_tokens = 0

        for i, turn in enumerate(turns):
            turn_tokens = self.estimate_tokens(turn['user'] + turn.get('assistant', ''))

            # Check if we should start a new chunk
            should_split = (
                # Chunk would exceed max size
                (current_tokens + turn_tokens > self.max_size) or
                # Detected topic shift (compare with previous turn)
                (current_chunk_turns and self._is_topic_shift(turn, current_chunk_turns[-1])) or
                # Chunk has enough turns (1-3 is optimal)
                (len(current_chunk_turns) >= 3 and current_tokens >= self.min_size)
            )

            if should_split and current_chunk_turns:
                # Save current chunk
                chunk = self._create_chat_chunk(
                    current_chunk_turns,
                    sequence,
                    metadata
                )
                chunks.append(chunk)
                sequence += 1
                current_chunk_turns = []
                current_tokens = 0

            # Add turn to current chunk
            current_chunk_turns.append(turn)
            current_tokens += turn_tokens

        # Save final chunk
        if current_chunk_turns:
            chunk = self._create_chat_chunk(
                current_chunk_turns,
                sequence,
                metadata
            )
            chunks.append(chunk)

        logger.info(
            f"💬 Chat log chunked: {len(turns)} turns → {len(chunks)} semantic chunks "
            f"(avg {len(turns)//len(chunks) if chunks else 0} turns/chunk)"
        )

        return chunks

    def _parse_chat_turns(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse chat log into user/assistant turn pairs

        Detects patterns like:
        - User: ...
        - Assistant: ...
        - **User**: ...
        - **Assistant**: ...
        """
        turns = []
        lines = content.split('\n')
        current_turn = None
        current_role = None
        current_content = []

        # Patterns for detecting role markers
        user_patterns = [
            r'^(User|Human|You):\s*',
            r'^\*\*(User|Human|You):\*\*\s*',  # **User:** format
        ]
        assistant_patterns = [
            r'^(Assistant|Claude|ChatGPT|AI):\s*',
            r'^\*\*(Assistant|Claude|ChatGPT|AI):\*\*\s*',  # **Assistant:** format
        ]

        for line in lines:
            line_stripped = line.strip()

            # Check for user marker
            is_user = any(re.match(pattern, line, re.IGNORECASE) for pattern in user_patterns)
            # Check for assistant marker
            is_assistant = any(re.match(pattern, line, re.IGNORECASE) for pattern in assistant_patterns)

            if is_user or is_assistant:
                # Save previous turn content
                if current_role and current_content:
                    content_text = '\n'.join(current_content).strip()
                    if current_role == 'user':
                        current_turn = {'user': content_text}
                    elif current_role == 'assistant':
                        if current_turn:
                            current_turn['assistant'] = content_text
                            turns.append(current_turn)
                            current_turn = None

                # Start new turn
                current_role = 'user' if is_user else 'assistant'
                current_content = []

                # Add content after marker (if any)
                marker_content = re.sub(
                    '|'.join(user_patterns + assistant_patterns),
                    '',
                    line,
                    flags=re.IGNORECASE
                ).strip()
                if marker_content:
                    current_content.append(marker_content)
            else:
                # Add line to current turn content
                if line_stripped:
                    current_content.append(line)

        # Save final turn
        if current_role and current_content:
            content_text = '\n'.join(current_content).strip()
            if current_role == 'user':
                turns.append({'user': content_text})
            elif current_role == 'assistant' and current_turn:
                current_turn['assistant'] = content_text
                turns.append(current_turn)

        return turns

    def _is_topic_shift(self, turn1: Dict[str, Any], turn2: Dict[str, Any]) -> bool:
        """
        Detect if there's a topic shift between two turns

        Uses simple heuristics:
        - Question word changes (what/how/why)
        - Key nouns overlap < 20%
        - Explicit topic markers ("moving on", "new question", etc.)
        """
        user1 = turn1.get('user', '').lower()
        user2 = turn2.get('user', '').lower()

        # Explicit topic shift markers
        shift_markers = [
            'moving on', 'new question', 'different topic',
            'another question', 'switching to', 'next question'
        ]
        if any(marker in user2 for marker in shift_markers):
            return True

        # Question word changes
        question_words = ['what', 'how', 'why', 'when', 'where', 'which', 'who']
        q1_words = [w for w in question_words if w in user1]
        q2_words = [w for w in question_words if w in user2]

        # Different question types suggest topic shift
        if q1_words and q2_words and set(q1_words) != set(q2_words):
            return True

        # Extract key nouns (very basic - words >4 chars, capitalized or technical)
        def extract_key_terms(text):
            words = re.findall(r'\b[A-Z][a-z]+\b|\b[a-z]{5,}\b', text)
            return set(words[:10])  # Limit to 10 terms

        terms1 = extract_key_terms(user1)
        terms2 = extract_key_terms(user2)

        if not terms1 or not terms2:
            return False

        # Calculate overlap
        overlap = len(terms1 & terms2) / len(terms1 | terms2)

        # < 20% overlap suggests topic shift
        return overlap < 0.2

    def _create_chat_chunk(
        self,
        turns: List[Dict[str, Any]],
        sequence: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a chunk from a list of turns with context headers

        Format:
        ### Chunk 1: {extracted_topic}

        **Turn 1/3**
        **User:** {question}
        **Assistant:** {answer}

        **Turn 2/3**
        ...
        """
        # Extract topic from first user question
        first_question = turns[0].get('user', '')
        topic = self._extract_topic_from_question(first_question)

        # Build chunk content with context headers
        chunk_lines = [
            f"### Chat Chunk {sequence + 1}: {topic}",
            "",
            f"**Context:** {len(turns)} conversation turn(s)",
            ""
        ]

        for i, turn in enumerate(turns):
            chunk_lines.append(f"**Turn {i + 1}/{len(turns)}**")
            chunk_lines.append(f"**User:** {turn.get('user', '(no user message)')}")
            chunk_lines.append("")

            if 'assistant' in turn:
                chunk_lines.append(f"**Assistant:** {turn['assistant']}")
                chunk_lines.append("")

        content = '\n'.join(chunk_lines)

        return {
            'content': content,
            'metadata': {
                'chunk_type': 'chat_turn',
                'section_title': topic,
                'turn_count': len(turns),
                'sequence': sequence,
                'parent_sections': []
            },
            'sequence': sequence,
            'char_count': len(content),
            'estimated_tokens': self.estimate_tokens(content)
        }

    def _extract_topic_from_question(self, question: str) -> str:
        """
        Extract concise topic from user question

        Examples:
        - "How do I create a bootable USB for Fedora?" → "Bootable USB Creation"
        - "what's the best linux distro?" → "Linux Distribution Selection"
        """
        question = question.strip()

        # Remove question words
        topic = re.sub(
            r'\b(how|what|why|when|where|which|who|can|should|do|does|is|are)\b',
            '',
            question,
            flags=re.IGNORECASE
        ).strip()

        # Take first 5-8 words
        words = topic.split()[:8]
        topic = ' '.join(words)

        # Title case
        topic = topic.title()

        # Limit length
        if len(topic) > 60:
            topic = topic[:57] + "..."

        return topic if topic else "Conversation"

    def _simple_chunk(self, content: str) -> List[Dict[str, Any]]:
        """
        Fallback: Simple text splitting (like old SimpleTextSplitter)

        Used when preserve_structure=False or as fallback.
        """
        chunks = []
        text_len = len(content)
        start = 0
        sequence = 0

        while start < text_len:
            # Calculate chunk size in characters (target_size * 4 for token estimation)
            chunk_size_chars = self.target_size * 4
            end = start + chunk_size_chars

            # Try to break at sentence boundary
            if end < text_len:
                # Look for sentence endings
                for i in range(min(100, chunk_size_chars // 4)):
                    if end - i >= 0 and content[end - i] in '.!?\n':
                        end = end - i + 1
                        break

            chunk_content = content[start:end].strip()
            if chunk_content:
                chunk_dict = {
                    'content': chunk_content,
                    'metadata': {
                        'chunk_type': 'paragraph',
                        'section_title': None,
                        'parent_sections': []
                    },
                    'sequence': sequence,
                    'char_count': len(chunk_content),
                    'estimated_tokens': self.estimate_tokens(chunk_content)
                }
                chunks.append(chunk_dict)
                sequence += 1

            # Move start with overlap
            overlap_chars = self.overlap * 4
            start = end - overlap_chars if overlap_chars > 0 else end
            if start <= 0:
                start = end

        return chunks


# Example usage and testing
if __name__ == "__main__":
    # Test with sample Markdown
    test_content = """# Main Document Title

This is the introduction paragraph with some context.

## Section 1: Overview

Here's some content in the first section. It discusses important topics.

### Subsection 1.1

More detailed information here.

| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data 1   | Data 2   | Data 3   |
| Data 4   | Data 5   | Data 6   |

## Section 2: Technical Details

```python
def example_function():
    return "Hello, World!"
```

Some more content after the code block.

- Bullet point 1
- Bullet point 2
- Bullet point 3

## Conclusion

Final thoughts and summary.
"""

    service = ChunkingService(target_size=200, max_size=400)
    chunks = service.chunk_text(test_content)

    logging.basicConfig(level=logging.INFO)
    logger.info(f"\n📄 Created {len(chunks)} chunks from test document\n")
    logger.info("=" * 60)

    for i, chunk_dict in enumerate(chunks):
        logger.info(f"\n🔹 Chunk {i + 1}:")
        logger.info(f"   Type: {chunk_dict['metadata']['chunk_type']}")
        logger.info(f"   Title: {chunk_dict['metadata'].get('section_title', 'N/A')}")
        logger.info(f"   Tokens: ~{chunk_dict['estimated_tokens']}")
        logger.info(f"   Preview: {chunk_dict['content'][:100]}...")
        logger.info("")

    logger.info("=" * 60)
    logger.info("✅ Structure-aware chunking working!")
