import re
from dataclasses import dataclass


@dataclass
class WordGateResult:
    """Result of a wordgate check."""

    matched: bool
    matches: dict[str, int]


def _normalize_text(text: str) -> str:
    """
    Normalize text for word matching.

    Applies:
    - Lowercase conversion
    - Punctuation removal (replaced with spaces)
    - Whitespace normalization (collapse to single spaces)
    """
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def check_words(text: str, target_words: set[str]) -> WordGateResult:
    """
    Check for presence of target words in normalized text.

    Args:
        text: Input text to search
        target_words: Set of words to look for (will be normalized internally)

    Returns:
        WordGateResult with match status and word counts
    """
    normalized_text = _normalize_text(text)
    words = normalized_text.split()

    normalized_targets = {_normalize_text(w) for w in target_words}

    matches: dict[str, int] = {}
    for word in words:
        if word in normalized_targets:
            matches[word] = matches.get(word, 0) + 1

    return WordGateResult(
        matched=len(matches) > 0,
        matches=matches,
    )
