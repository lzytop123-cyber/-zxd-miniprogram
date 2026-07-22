"""Compose four ready-to-upload homepage carousel images for 知行岛.

The input images are generated, text-free background visuals. This script crops
them to the mini-program hero ratio, adds deterministic Chinese typography, and
keeps every JPEG below the admin upload limit.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


WIDTH = 1500
HEIGHT = 1360
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "assets" / "marketing" / "home-carousel"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
MAX_BYTES = 1_950_000


@dataclass(frozen=True)
class Slide:
    filename: str
    ribbon: str
    title: str
    subtitle: str
    cta: str
    ribbon_fill: str = "#D8F3DC"
    ribbon_text: str = "#205B43"


SLIDES = (
    Slide(
        filename="home-carousel-01-retention-1500x1360.jpg",
        ribbon="专注周报",
        title="每一次坚持\n都算数",
        subtitle="回看学习轨迹，继续积累专注时光",
        cta="查看学习报告",
    ),
    Slide(
        filename="home-carousel-02-calm-space-1500x1360.jpg",
        ribbon="安静发生",
        title="把喧闹\n留在门外",
        subtitle="自然光、独立座位与恰到好处的安静",
        cta="探索学习空间",
    ),
    Slide(
        filename="home-carousel-03-booking-1500x1360.jpg",
        ribbon="即刻开座",
        title="为今晚\n留一个位置",
        subtitle="在线选座，到店即可进入专注状态",
        cta="立即预约",
    ),
    Slide(
        filename="home-carousel-04-focus-challenge-1500x1360.jpg",
        ribbon="本月专注挑战",
        title="累计 40 小时\n解锁专注奖励",
        subtitle="把大目标，拆成每天的一小步",
        cta="参加挑战",
        ribbon_fill="#FFE3A3",
        ribbon_text="#6F4800",
    ),
)


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    requested = FONT_BOLD if bold and FONT_BOLD.exists() else FONT_REGULAR
    if not requested.exists():
        requested = Path(r"C:\Windows\Fonts\simhei.ttf")
    return ImageFont.truetype(str(requested), size)


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = ImageOps.exif_transpose(image).convert("RGB")
    scale = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize(
        (round(image.width * scale), round(image.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def add_readability_gradient(image: Image.Image) -> Image.Image:
    base = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    pixels = overlay.load()

    for x in range(WIDTH):
        horizontal = x / max(WIDTH - 1, 1)
        left_alpha = round(205 * (1 - horizontal) ** 1.55 + 12)
        for y in range(HEIGHT):
            edge = min(y / 260, (HEIGHT - 1 - y) / 240, 1)
            edge_alpha = round(48 * (1 - max(0, edge)))
            pixels[x, y] = (10, 35, 24, min(232, left_alpha + edge_alpha))

    return Image.alpha_composite(base, overlay).convert("RGB")


def text_width(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), value, font=face)
    return box[2] - box[0]


def compose(background: Path, slide: Slide, destination: Path) -> None:
    image = cover(Image.open(background), (WIDTH, HEIGHT))
    image = ImageEnhance.Color(image).enhance(0.90)
    image = ImageEnhance.Contrast(image).enhance(1.04)
    image = ImageEnhance.Brightness(image).enhance(0.97)
    image = add_readability_gradient(image)
    draw = ImageDraw.Draw(image, "RGBA")

    x = 92
    ribbon_y = 382
    ribbon_font = font(39, bold=True)
    ribbon_w = text_width(draw, slide.ribbon, ribbon_font) + 58
    draw.rounded_rectangle(
        (x, ribbon_y, x + ribbon_w, ribbon_y + 72),
        radius=36,
        fill=slide.ribbon_fill,
    )
    draw.text(
        (x + 29, ribbon_y + 12),
        slide.ribbon,
        font=ribbon_font,
        fill=slide.ribbon_text,
    )

    title_y = ribbon_y + 112
    title_font = font(82, bold=True)
    draw.multiline_text(
        (x, title_y),
        slide.title,
        font=title_font,
        fill="#FFFFFF",
        spacing=15,
        stroke_width=1,
        stroke_fill=(20, 55, 40, 80),
    )
    title_box = draw.multiline_textbbox(
        (x, title_y), slide.title, font=title_font, spacing=15, stroke_width=1
    )

    accent_y = title_box[3] + 34
    draw.rounded_rectangle((x, accent_y, x + 84, accent_y + 8), radius=4, fill="#7FD6A7")
    subtitle_y = accent_y + 35
    subtitle_font = font(37)
    draw.text(
        (x, subtitle_y),
        slide.subtitle,
        font=subtitle_font,
        fill=(244, 249, 246, 235),
    )

    cta_y = subtitle_y + 92
    cta_font = font(39, bold=True)
    cta_w = text_width(draw, slide.cta, cta_font) + 88
    draw.rounded_rectangle(
        (x, cta_y, x + cta_w, cta_y + 94),
        radius=47,
        fill=(255, 255, 255, 248),
    )
    draw.text((x + 44, cta_y + 20), slide.cta, font=cta_font, fill="#2D6A4F")
    arrow_x = x + cta_w + 25
    arrow_y = cta_y + 47
    draw.line((arrow_x, arrow_y, arrow_x + 38, arrow_y), fill="#FFFFFF", width=5)
    draw.line((arrow_x + 24, arrow_y - 14, arrow_x + 38, arrow_y), fill="#FFFFFF", width=5)
    draw.line((arrow_x + 24, arrow_y + 14, arrow_x + 38, arrow_y), fill="#FFFFFF", width=5)

    destination.parent.mkdir(parents=True, exist_ok=True)
    for quality in (90, 86, 82, 78):
        image.save(destination, "JPEG", quality=quality, optimize=True, progressive=True)
        if destination.stat().st_size <= MAX_BYTES:
            break
    if destination.stat().st_size > MAX_BYTES:
        raise RuntimeError(f"{destination.name} exceeds the 2MB upload limit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("backgrounds", nargs=4, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    missing = [str(path) for path in args.backgrounds if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing background(s): {', '.join(missing)}")

    results = []
    for background, slide in zip(args.backgrounds, SLIDES, strict=True):
        destination = OUTPUT_DIR / slide.filename
        compose(background, slide, destination)
        with Image.open(destination) as image:
            results.append(
                {
                    "path": str(destination),
                    "width": image.width,
                    "height": image.height,
                    "bytes": destination.stat().st_size,
                }
            )

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
