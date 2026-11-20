"""
Topic research module for the Video Agent pipeline.

Generates structured research summaries from a topic string using
template-based content generation. Produces educational key points,
code examples, and takeaway messages.
"""

from __future__ import annotations

import re
import textwrap
from typing import Dict, List

from video_agent.models import CodeSnippetSpec, ResearchResult


# ---------------------------------------------------------------------------
# Internal helpers & public normalizers
# ---------------------------------------------------------------------------


def normalize_topic(topic: str) -> str:
    """Strip and normalize whitespace in a topic string."""
    return re.sub(r"\s+", " ", topic.strip())


_normalize_topic = normalize_topic


def validate_topic(topic: str) -> str:
    """Validate topic string, rejecting empty or whitespace-only queries.

    Raises:
        ValueError: If topic is None, empty, or whitespace-only.
    """
    if not topic or not topic.strip():
        raise ValueError("Topic query cannot be empty or whitespace.")
    return normalize_topic(topic)


def extract_key_points(topic: str) -> List[str]:
    """Extract substantive educational key points for a topic."""
    clean = normalize_topic(topic)
    keywords = _extract_keywords(clean)
    return _generate_key_points(clean, keywords)


def _extract_keywords(topic: str) -> List[str]:
    """Extract meaningful keywords from a topic string.

    Filters out common stop-words and returns unique, lowercased keywords
    in their original order.
    """
    stop_words = {
        "a", "an", "the", "in", "on", "at", "to", "for", "of", "with",
        "and", "or", "but", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "it", "its", "this", "that", "these", "those", "how", "what",
        "why", "when", "where", "which", "who", "whom", "about", "into",
        "through", "during", "before", "after", "above", "below",
        "from", "up", "down", "out", "off", "over", "under", "again",
        "further", "then", "once", "using", "vs", "versus",
    }
    words = re.findall(r"[A-Za-z0-9_#+]+", topic)
    seen: set[str] = set()
    keywords: List[str] = []
    for w in words:
        low = w.lower()
        if low not in stop_words and low not in seen and len(low) > 1:
            seen.add(low)
            keywords.append(w)
    return keywords


def _generate_summary(topic: str, keywords: List[str]) -> str:
    """Create a concise educational summary paragraph."""
    kw_list = ", ".join(keywords[:5]) if keywords else topic
    return (
        f"{topic} is a critical area in modern software development. "
        f"Understanding the core concepts — {kw_list} — enables developers "
        f"to write more efficient, maintainable, and scalable code. "
        f"This topic encompasses both foundational theory and practical "
        f"techniques that can be applied immediately in real-world projects."
    )


def _generate_key_points(topic: str, keywords: List[str]) -> List[str]:
    """Generate 4-6 substantive educational key points."""
    points: List[str] = []
    clean = _normalize_topic(topic)

    points.append(
        f"{clean} fundamentals: core architectural principles enable reliable scalability and performance."
    )

    if keywords:
        points.append(
            f"Key concept — {keywords[0]}: this forms the backbone of {clean} "
            f"and is the first thing every practitioner should master."
        )

    if len(keywords) > 1:
        points.append(
            f"The relationship between {keywords[0]} and {keywords[1]} is "
            f"often misunderstood; clarifying it unlocks deeper understanding."
        )

    points.append(
        f"Performance considerations: when implementing {clean}, always "
        f"measure before optimizing — profiling reveals the real bottlenecks."
    )

    points.append(
        f"Common pitfalls include ignoring edge cases and not testing "
        f"thoroughly — defensive coding practices prevent production failures."
    )

    if len(keywords) > 2:
        points.append(
            f"Advanced pattern — combining {keywords[1]} with {keywords[2]}: "
            f"this technique is used in production systems to achieve both "
            f"reliability and speed."
        )
    else:
        points.append(
            f"Best practices for {clean} include writing clear documentation, "
            f"using type hints, and following established design patterns."
        )

    return points


def _generate_code_examples(
    topic: str, keywords: List[str]
) -> List[Dict[str, str]]:
    """Generate 1-2 code examples relevant to the topic."""
    examples: List[Dict[str, str]] = []
    clean = _normalize_topic(topic)

    # Primary example — always generated
    primary_kw = keywords[0] if keywords else clean.replace(" ", "_").lower()
    safe_var = re.sub(r"[^a-z0-9_]", "_", primary_kw.lower())[:30]

    primary_code = textwrap.dedent(f"""\
        # {clean} — basic demonstration
        def demonstrate_{safe_var}():
            \"\"\"Show the core concept of {clean}.\"\"\"
            print(f"Starting {clean} demonstration...")

            # Core logic placeholder
            result = {{
                "topic": "{clean}",
                "status": "success",
                "detail": "Core concept demonstrated",
            }}
            return result

        if __name__ == "__main__":
            output = demonstrate_{safe_var}()
            print(f"Result: {{output}}")
    """)

    examples.append({
        "title": f"{clean} — Basic Example",
        "language": "python",
        "code": primary_code,
    })

    # Secondary example — generated when there are enough keywords
    if len(keywords) >= 2:
        secondary_kw = keywords[1]
        safe_var2 = re.sub(r"[^a-z0-9_]", "_", secondary_kw.lower())[:30]
        secondary_code = textwrap.dedent(f"""\
            # {clean} — practical application with {secondary_kw}
            import time

            class {safe_var2.title().replace("_", "")}Handler:
                \"\"\"Handle {secondary_kw} operations for {clean}.\"\"\"

                def __init__(self):
                    self.data = []

                def process(self, item):
                    \"\"\"Process a single item.\"\"\"
                    start = time.perf_counter()
                    self.data.append(item)
                    elapsed = time.perf_counter() - start
                    return {{"item": item, "elapsed_ms": elapsed * 1000}}

            handler = {safe_var2.title().replace("_", "")}Handler()
            print(handler.process("example_input"))
        """)

        examples.append({
            "title": f"{clean} — Practical {secondary_kw} Pattern",
            "language": "python",
            "code": secondary_code,
        })

    return examples


def _generate_takeaway(topic: str, keywords: List[str]) -> str:
    """Generate a memorable closing takeaway message."""
    clean = _normalize_topic(topic)
    if keywords:
        return (
            f"Mastering {clean} starts with understanding {keywords[0]}. "
            f"Start small, iterate often, and measure your results."
        )
    return (
        f"Mastering {clean} unlocks compounding returns in software quality and productivity."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def research_topic(topic: str) -> ResearchResult:
    """Generate a structured research summary for a given topic.

    Uses template-based content generation to produce substantive,
    educational material including key points, code examples, and a
    takeaway message.

    Args:
        topic: The subject to research (e.g. "Python async programming").

    Returns:
        A fully populated ``ResearchResult`` instance.

    Raises:
        ValueError: If the topic string is empty or whitespace-only.
    """
    if not topic or not topic.strip():
        raise ValueError("Topic must be a non-empty string.")

    clean_topic = validate_topic(topic)
    keywords = _extract_keywords(clean_topic)

    code_examples = _generate_code_examples(clean_topic, keywords)
    code_snippets = [
        CodeSnippetSpec(
            language=ex.get("language", "python"),
            code=ex.get("code", ""),
            description=ex.get("title", ""),
            command="python main.py",
        )
        for ex in code_examples
    ]
    takeaway_str = _generate_takeaway(clean_topic, keywords)

    return ResearchResult(
        topic=clean_topic,
        title=f"Mastering {clean_topic}",
        summary=_generate_summary(clean_topic, keywords),
        key_points=_generate_key_points(clean_topic, keywords),
        code_snippets=code_snippets,
        code_examples=code_examples,
        takeaway=takeaway_str,
        takeaways=[takeaway_str],
    )
