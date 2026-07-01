"""Build favicon assets from the transparent site logo (white background)."""
from pathlib import Path

from PIL import Image

IMG_DIR = Path(__file__).resolve().parent.parent / 'static' / 'img'
SOURCE = IMG_DIR / 'logo.png'


def build_icon(size, dest_name, padding_ratio=0.12):
    logo = Image.open(SOURCE).convert('RGBA')
    canvas = Image.new('RGBA', (size, size), (255, 255, 255, 255))
    max_dim = max(1, int(size * (1 - 2 * padding_ratio)))
    fitted = logo.copy()
    fitted.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    offset = ((size - fitted.width) // 2, (size - fitted.height) // 2)
    canvas.paste(fitted, offset, fitted)
    dest = IMG_DIR / dest_name
    canvas.convert('RGB').save(dest, 'PNG', optimize=True)
    print(f'Wrote {dest.name} ({size}x{size})')


if __name__ == '__main__':
    if not SOURCE.exists():
        raise SystemExit(f'Missing source logo: {SOURCE}')
    build_icon(32, 'favicon.png')
    build_icon(180, 'apple-touch-icon.png')
