import hashlib
from pathlib import Path

from django.conf import settings


def static_file_path(relative_path: str) -> Path:
    """Path to the static asset that is actually served (collected copy in production)."""
    rel = relative_path.lstrip('/')
    collected = Path(settings.STATIC_ROOT) / rel
    if collected.exists():
        return collected
    return Path(settings.BASE_DIR) / 'static' / rel


def static_cache_version(relative_path: str) -> str:
    path = static_file_path(relative_path)
    if not path.exists():
        return '0'
    return hashlib.md5(path.read_bytes()).hexdigest()[:10]


def build_static_cache_versions(*paths: str) -> dict[str, str]:
    return {path: static_cache_version(path) for path in paths}


def versioned_static_url(relative_path: str, *, absolute: bool = False) -> str:
    version = settings.STATIC_CACHE_VERSIONS.get(
        relative_path,
        static_cache_version(relative_path),
    )
    static_url = f'{settings.STATIC_URL.rstrip("/")}/{relative_path.lstrip("/")}'
    url = f'/{static_url}?v={version}' if not absolute else (
        f'{settings.SITE_URL.rstrip("/")}/{static_url}?v={version}'
    )
    return url
