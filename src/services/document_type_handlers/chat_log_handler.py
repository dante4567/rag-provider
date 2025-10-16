"""
ChatLogHandler - Preprocessing for LLM conversation exports (ChatGPT, Claude, etc.)

Key challenges:
- Multi-turn conversations spanning hours/days
- User/assistant role distinction
- Session detection (when does one topic end, another begin?)
- Code blocks and technical content preservation
- Summary should focus on: questions asked, solutions provided, decisions made

Strategy:
- Detect session boundaries (timestamp gaps >30min = new session)
- Preserve code blocks verbatim (RAG:PRESERVE markers)
- Remove boilerplate (system messages, disclaimers)
- Extract key Q&A pairs
- Identify main topics discussed
"""

import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

from .base_handler import DocumentTypeHandler

logger = logging.getLogger(__name__)


class ChatLogHandler(DocumentTypeHandler):
    """Handler for LLM conversation exports and chat logs"""

    # Session boundary detection
    SESSION_GAP_MINUTES = 30  # >30min gap = new session

    # Boilerplate patterns to remove
    BOILERPLATE_PATTERNS = [
        r'^I\'m (Claude|ChatGPT|an AI assistant).*?\.[ \n]',
        r'^As an AI language model.*?\.[ \n]',
        r'^I don\'t have personal (opinions|experiences|feelings).*?\.[ \n]',
        r'^\[System message:.*?\][ \n]',
        r'^This conversation may be reviewed.*?\.[ \n]',
        r'^I cannot (help with|assist with|provide).*?(illegal|harmful|unethical).*?\.[ \n]',
    ]

    # Turn markers (user/assistant alternation)
    TURN_PATTERNS = [
        r'^(User|Human|You):\s*',
        r'^(Assistant|Claude|ChatGPT|AI):\s*',
        r'^\*\*User\*\*:\s*',
        r'^\*\*Assistant\*\*:\s*',
    ]

    def preprocess(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Clean chat log content:
        1. Remove boilerplate AI disclaimers
        2. Preserve code blocks
        3. Detect session boundaries
        4. Clean redundant turn markers
        """
        original_length = len(text)

        # Preserve code blocks (mark them so they're not touched)
        code_blocks = []
        def preserve_code(match):
            code_blocks.append(match.group(0))
            return f"<<<CODE_BLOCK_{len(code_blocks)-1}>>>"

        # Preserve markdown code blocks
        text = re.sub(r'```[\s\S]*?```', preserve_code, text)
        # Preserve inline code
        text = re.sub(r'`[^`]+`', preserve_code, text)

        # Remove boilerplate
        for pattern in self.BOILERPLATE_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)

        # Clean excessive turn markers (keep first occurrence, remove duplicates)
        lines = text.split('\n')
        cleaned_lines = []
        prev_was_turn_marker = False

        for line in lines:
            is_turn_marker = any(re.match(pattern, line, re.IGNORECASE) for pattern in self.TURN_PATTERNS)

            # Skip duplicate turn markers
            if is_turn_marker and prev_was_turn_marker:
                continue

            cleaned_lines.append(line)
            prev_was_turn_marker = is_turn_marker

        text = '\n'.join(cleaned_lines)

        # Restore code blocks
        for i, code in enumerate(code_blocks):
            text = text.replace(f"<<<CODE_BLOCK_{i}>>>", code)

        # Clean excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        cleaned_length = len(text)
        retention_pct = (cleaned_length / original_length * 100) if original_length > 0 else 0

        logger.info(f"💬 Chat log cleaned: {original_length} → {cleaned_length} chars ({retention_pct:.1f}% retained)")

        if retention_pct < 30:
            logger.warning(f"⚠️  Low retention ({retention_pct:.1f}%) - may have removed too much content")

        return text

    def extract_metadata(self, text: str, existing_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract chat-specific metadata:
        - Turn count (how many exchanges)
        - Has code blocks
        - Session count (detected topic shifts)
        - Main question/topic
        - Languages/technologies mentioned
        """
        metadata = {}

        # Count turns (user/assistant exchanges)
        turn_count = 0
        for pattern in self.TURN_PATTERNS:
            turn_count += len(re.findall(pattern, text, re.MULTILINE | re.IGNORECASE))
        metadata['turn_count'] = turn_count

        # Detect code blocks
        code_blocks = re.findall(r'```[\s\S]*?```', text)
        metadata['has_code'] = len(code_blocks) > 0
        metadata['code_block_count'] = len(code_blocks)

        # Extract programming languages from code fences
        languages = set()
        for block in code_blocks:
            match = re.match(r'```(\w+)', block)
            if match:
                languages.add(match.group(1))
        metadata['programming_languages'] = list(languages)

        # Detect technical terms (simplified)
        tech_patterns = [
            r'\b(Python|JavaScript|TypeScript|Java|Go|Rust|C\+\+|Ruby|PHP)\b',
            r'\b(Docker|Kubernetes|AWS|Azure|GCP)\b',
            r'\b(React|Vue|Angular|Django|Flask|FastAPI|Express)\b',
            r'\b(SQL|PostgreSQL|MongoDB|Redis|Elasticsearch)\b',
        ]
        technologies = set()
        for pattern in tech_patterns:
            technologies.update(re.findall(pattern, text, re.IGNORECASE))
        metadata['technologies_mentioned'] = list(technologies)[:10]  # Limit to 10

        # Estimate session count (timestamp-based would be better, but we work with what we have)
        # For now, use turn count as proxy (every 10 turns ≈ 1 session)
        metadata['estimated_sessions'] = max(1, turn_count // 10)

        # Check for actionable content
        has_todo = bool(re.search(r'\b(TODO|FIXME|Action item|Next step)', text, re.IGNORECASE))
        has_question = bool(re.search(r'\?', text))
        metadata['has_questions'] = has_question
        metadata['has_todos'] = has_todo

        return metadata

    def get_chunking_strategy(self, metadata: Dict[str, Any]) -> str:
        """
        Chat logs should be chunked by session or topic shift.
        Long conversations: split by session
        Short conversations: keep whole
        """
        turn_count = metadata.get('turn_count', 0)

        if turn_count < 10:
            return 'whole'  # Short conversation, keep intact
        elif turn_count < 50:
            return 'session'  # Split by detected sessions
        else:
            return 'semantic'  # Long conversation, use semantic chunking

    def get_summary_prompt(self, text: str, metadata: Dict[str, Any]) -> str:
        """
        Chat logs need summaries focused on:
        1. What questions were asked
        2. What solutions/answers were provided
        3. What code/examples were generated
        4. What decisions were made
        5. What technologies were discussed
        """
        has_code = metadata.get('has_code', False)
        turn_count = metadata.get('turn_count', 0)
        technologies = metadata.get('technologies_mentioned', [])

        base_prompt = """2-3 sentence summary focusing on:
   - The main question(s) or problem being solved
   - The solution or approach discussed"""

        if has_code:
            base_prompt += "\n   - Key code examples or implementations provided"

        if technologies:
            base_prompt += f"\n   - Technologies discussed: {', '.join(technologies[:3])}"

        if turn_count > 20:
            base_prompt += "\n   - Main topics covered in this extended conversation"

        base_prompt += "\n   - Be specific about outcomes and actionable insights"

        return base_prompt
