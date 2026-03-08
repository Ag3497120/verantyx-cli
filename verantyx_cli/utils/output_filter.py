"""
Output Filter - Filter LLM output to extract actual responses

Filters out:
- ANSI escape sequences
- TUI/UI drawing characters
- Control characters
- Prompt markers
- Status messages

Extracts only:
- Actual LLM responses to user queries
"""

import re
from typing import Optional


class OutputFilter:
    """Filter LLM PTY output to extract actual responses"""

    # Patterns to skip
    SKIP_PATTERNS = [
        # ANSI escape sequences
        r'^\x1b\[',
        r'^\033\[',

        # Box drawing characters (only)
        r'^[╭╰│─┌┐└┘▗▖▘▝█░▒▓\s]+$',

        # Claude welcome screen
        r'Welcome back',
        r'Tips for getting started',
        r'Recent activity',
        r'No recent activity',

        # Model info
        r'Sonnet \d+\.\d+',
        r'Claude API',
        r'Claude Code v\d+',

        # Status/UI elements
        r'Thinking (on|off)',
        r'tab to toggle',
        r'~/[a-zA-Z0-9_/]+',  # Path display

        # Prompt markers (without content)
        r'^>\s*$',
        r'^────+$',

        # Very short (likely control)
        r'^\s{0,3}$',
    ]

    # Patterns that indicate actual LLM response
    RESPONSE_INDICATORS = [
        # Common Japanese greetings/responses
        r'こんにちは',
        r'ありがとう',
        r'はい',
        r'いいえ',
        r'です',
        r'ます',

        # Common English responses
        r'\b(Hello|Hi|Yes|No|Sure|Okay|I)\b',
        r'\b(can|will|would|should|could)\b',
        r'\b(is|are|was|were|be|been)\b',

        # Question marks
        r'[?？]',

        # Code blocks
        r'```',
        r'`[^`]+`',

        # Explanations
        r'\b(this|that|these|those)\b',
        r'\b(because|since|as|so)\b',
    ]

    @classmethod
    def is_likely_response(cls, text: str) -> bool:
        """
        Check if text is likely an actual LLM response

        Args:
            text: Text to check

        Returns:
            True if likely a response, False if likely UI/control
        """
        if not text or not text.strip():
            return False

        text_lower = text.lower()

        # Check skip patterns
        for pattern in cls.SKIP_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False

        # Check response indicators
        for pattern in cls.RESPONSE_INDICATORS:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        # If text is long enough (>20 chars) and has no UI chars, likely response
        if len(text.strip()) > 20:
            ui_char_ratio = sum(1 for c in text if c in '╭╰│─┌┐└┘▗▖▘▝█░▒▓') / len(text)
            if ui_char_ratio < 0.1:  # Less than 10% UI chars
                return True

        return False

    @classmethod
    def clean_output(cls, text: str) -> Optional[str]:
        """
        Clean output text by removing ANSI codes and control chars

        Args:
            text: Raw text

        Returns:
            Cleaned text, or None if should be skipped
        """
        if not cls.is_likely_response(text):
            return None

        # Remove ANSI escape sequences
        cleaned = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
        cleaned = re.sub(r'\033\[[0-9;]*[a-zA-Z]', '', cleaned)

        # Remove other control characters
        cleaned = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', cleaned)

        # Strip whitespace
        cleaned = cleaned.strip()

        return cleaned if cleaned else None


def filter_llm_output(text: str) -> Optional[str]:
    """
    Convenience function to filter LLM output

    Args:
        text: Raw output from LLM PTY

    Returns:
        Cleaned text if it's a response, None otherwise
    """
    return OutputFilter.clean_output(text)
