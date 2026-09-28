import re

URL_PATTERN = re.compile(r"https?://\S+")
def might_have_content_to_gather(text: str) -> bool:
    """Check if the text might contain a URL or file path."""
    return bool(URL_PATTERN.search(text)) or "/" in text  # crude file-path heuristic
