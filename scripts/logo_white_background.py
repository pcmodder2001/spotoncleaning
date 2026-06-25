"""Replace cream/beige logo background with pure white."""
from collections import deque
from pathlib import Path

from PIL import Image

IMG_DIR = Path(__file__).resolve().parent.parent / 'static' / 'img'
TOLERANCE = 38


def color_dist(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def is_background_pixel(rgb, ref):
    return color_dist(rgb[:3], ref) <= TOLERANCE


def cream_to_white(path):
    img = Image.open(path).convert('RGBA')
    width, height = img.size
    pixels = img.load()

    ref = pixels[0, 0][:3]
    visited = [[False] * width for _ in range(height)]
    queue = deque()

    for x, y in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        if not visited[y][x] and is_background_pixel(pixels[x, y], ref):
            visited[y][x] = True
            queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        pixels[x, y] = (255, 255, 255, pixels[x, y][3])
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height and not visited[ny][nx]:
                if is_background_pixel(pixels[nx, ny], ref):
                    visited[ny][nx] = True
                    queue.append((nx, ny))

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if color_dist((r, g, b), ref) <= TOLERANCE - 8:
                pixels[x, y] = (255, 255, 255, a)
            else:
                # Light warm cream fills inside the artwork (gloves, oven body, etc.)
                total = r + g + b
                if total > 480 and r >= g - 3 and g >= b - 20 and total < 765:
                    pixels[x, y] = (255, 255, 255, a)

    img.save(path, 'PNG')
    print(f'Updated {path.name}')


if __name__ == '__main__':
    for name in ('logo.png', 'logo-alt.png'):
        cream_to_white(IMG_DIR / name)
