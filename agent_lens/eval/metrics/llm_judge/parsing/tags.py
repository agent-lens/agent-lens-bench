from typing import Optional


def _tag_variants(tag: str) -> tuple[str, str]:
    """Return (bol, after_newline) variants for a tag."""
    return tag, f"\n{tag}"


def find_tag_start(content: str, tag: str) -> Optional[int]:
    """Find the content start index *after* a tag.

    Robust to models emitting tags at BOL or after a newline.
    Returns None if tag not present.
    """
    bol, after_nl = _tag_variants(tag)

    if content.count(tag) == 0:
        return None

    # Prefer newline variant if present to avoid matching tag inside other text.
    if content.count(after_nl) > 0:
        return content.find(after_nl) + len(after_nl)

    return content.find(bol) + len(bol)


def extract_section(content: str, *, start_tag: str, end_tag: Optional[str]) -> str:
    """Extract a section between tags.

    If end_tag is None, takes until end-of-content.
    Returns empty string if start_tag is not found.
    """
    start = find_tag_start(content, start_tag)
    if start is None:
        return ""

    if end_tag is None:
        return content[start:].strip()

    end = content.rfind(end_tag, start)
    if end == -1:
        end = len(content)

    return content[start:end].strip()


def parse_alert_flag(content: str, alert_flag_tag: str) -> bool:
    start = find_tag_start(content, alert_flag_tag)
    if start is None:
        return False

    after = content[start:].lower()
    return "true" in after and "false" not in after
