"""Platform resolver from URL."""

from urllib.parse import urlparse

def resolve_platform(url: str) -> str:
    """Detect platform from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        if 'youtube.com' in domain or 'youtu.be' in domain:
            return 'youtube'
        if 'instagram.com' in domain:
            return 'instagram'
            
        return 'unsupported'
    except Exception:
        return 'invalid'
