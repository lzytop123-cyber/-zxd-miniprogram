"""Compose the review-reward homepage carousel as a deterministic JPEG."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


WIDTH = 1500
HEIGHT = 1360
MAX_BYTES = 1_950_000
ROOT = Path(__file__).resolve().parents[1]
SOURCE = (
    ROOT
    / "assets"
    / "marketing"
    / "home-carousel"
    / "sources"
    / "source-05-review-reward.png"
)
DESTINATION = (
    ROOT
    / "assets"
    / "marketing"
    / "home-carousel"
    / "home-carousel-05-review-reward-1500x1360.jpg"
)

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_FALLBACK = Path(r"C:\Windows\Fonts\simhei.ttf")

TAG = "好评有礼"
HEADLINE = "写好评\n送日卡"
SUBTITLE = "美团 · 大众点评 · 抖音｜15字+3张照片"
CTA = "截图领日卡"
WORDMARK = "知行岛自习室"


def select_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Return the requested Microsoft YaHei face, with SimHei as fallback."""
    preferred = FONT_BOLD if bold else FONT_REGULAR
    path = preferred if preferred.exists() else FONT_FALLBACK
    if not path.exists():
        raise FileNotFoundError("No required Chinese font is available")
    return ImageFont.truetype(str(path), size)


def text_width(
    draw: ImageDraw.ImageDraw,
    value: str,
    face: ImageFont.FreeTypeFont,
) -> int:
    """Measure rendered text width in pixels."""
    left, _, right, _ = draw.textbbox((0, 0), value, font=face)
    return right - left


def cover_crop(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Apply an orientation-safe centered cover crop with deterministic rounding."""
    normalized = ImageOps.exif_transpose(image).convert("RGB")
    scale = max(size[0] / normalized.width, size[1] / normalized.height)
    resized = normalized.resize(
        (round(normalized.width * scale), round(normalized.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def left_to_right_alpha_gradient(
    size: tuple[int, int],
    *,
    start_alpha: int = 174,
    solid_fraction: float = 0.48,
    fade_end_fraction: float = 0.84,
) -> Image.Image:
    """Build a broad left-side alpha field with a smooth rightward fade."""
    width, height = size
    if width < 1 or height < 1:
        raise ValueError("Gradient dimensions must be positive")
    if not 0.0 <= solid_fraction < fade_end_fraction <= 1.0:
        raise ValueError("Gradient fractions must be ordered within 0..1")

    values: list[int] = []
    for x in range(width):
        position = x / max(width - 1, 1)
        if position <= solid_fraction:
            alpha = start_alpha
        elif position >= fade_end_fraction:
            alpha = 0
        else:
            progress = (position - solid_fraction) / (
                fade_end_fraction - solid_fraction
            )
            smooth = progress * progress * (3.0 - 2.0 * progress)
            alpha = round(start_alpha * (1.0 - smooth))
        values.append(alpha)

    row = Image.new("L", (width, 1))
    row.putdata(values)
    return row.resize((width, height))


def compose(source: Image.Image) -> Image.Image:
    """Create the final RGB carousel image without writing to disk."""
    image = cover_crop(source, (WIDTH, HEIGHT))
    image = ImageEnhance.Color(image).enhance(0.94)
    image = ImageEnhance.Contrast(image).enhance(1.02)
    image = ImageEnhance.Brightness(image).enhance(0.98)

    overlay = Image.new("RGBA", image.size, (11, 45, 32, 0))
    overlay.putalpha(left_to_right_alpha_gradient(image.size))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")

    left = 92

    tag_font = select_font(38, bold=True)
    tag_top = 238
    tag_height = 76
    tag_width = text_width(draw, TAG, tag_font) + 60
    draw.rounded_rectangle(
        (left, tag_top, left + tag_width, tag_top + tag_height),
        radius=tag_height // 2,
        fill="#D8F3DC",
    )
    tag_box = draw.textbbox((0, 0), TAG, font=tag_font)
    tag_x = left + (tag_width - (tag_box[2] - tag_box[0])) / 2 - tag_box[0]
    tag_y = tag_top + (tag_height - (tag_box[3] - tag_box[1])) / 2 - tag_box[1]
    draw.text((tag_x, tag_y), TAG, font=tag_font, fill="#205B43")

    headline_font = select_font(126, bold=True)
    headline_top = 350
    draw.multiline_text(
        (left, headline_top),
        HEADLINE,
        font=headline_font,
        fill="#FFFFFF",
        spacing=8,
    )
    headline_box = draw.multiline_textbbox(
        (left, headline_top),
        HEADLINE,
        font=headline_font,
        spacing=8,
    )

    subtitle_font = select_font(36)
    subtitle_top = headline_box[3] + 46
    subtitle_right = left + text_width(draw, SUBTITLE, subtitle_font)
    if subtitle_right > 830:
        raise RuntimeError("Subtitle crosses the protected left-copy boundary")
    draw.text(
        (left, subtitle_top),
        SUBTITLE,
        font=subtitle_font,
        fill="#F7F1E7",
    )

    cta_font = select_font(44, bold=True)
    cta_top = subtitle_top + 92
    cta_height = 104
    cta_width = text_width(draw, CTA, cta_font) + 96
    draw.rounded_rectangle(
        (left, cta_top, left + cta_width, cta_top + cta_height),
        radius=cta_height // 2,
        fill="#FFFFFF",
    )
    cta_box = draw.textbbox((0, 0), CTA, font=cta_font)
    cta_x = left + (cta_width - (cta_box[2] - cta_box[0])) / 2 - cta_box[0]
    cta_y = cta_top + (cta_height - (cta_box[3] - cta_box[1])) / 2 - cta_box[1]
    draw.text((cta_x, cta_y), CTA, font=cta_font, fill="#205B43")

    wordmark_font = select_font(31, bold=True)
    wordmark_right = WIDTH - 92
    wordmark_top = 86
    wordmark_x = wordmark_right - text_width(draw, WORDMARK, wordmark_font)
    draw.text(
        (wordmark_x, wordmark_top),
        WORDMARK,
        font=wordmark_font,
        fill="#205B43",
    )

    return image


def encode_jpeg(image: Image.Image) -> tuple[bytes, int]:
    """Encode progressively at descending quality until the upload limit is met."""
    for quality in (92, 88, 84, 80, 76):
        buffer = io.BytesIO()
        image.save(
            buffer,
            "JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling="4:2:0",
        )
        payload = buffer.getvalue()
        if 0 < len(payload) < MAX_BYTES:
            return payload, quality
    raise RuntimeError(f"JPEG remains at or above {MAX_BYTES:,} bytes")


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing source image: {SOURCE}")
    if DESTINATION.exists():
        raise FileExistsError(f"Refusing to overwrite existing carousel: {DESTINATION}")

    with Image.open(SOURCE) as source:
        image = compose(source)
    payload, _quality = encode_jpeg(image)
    DESTINATION.write_bytes(payload)

    with Image.open(DESTINATION) as rendered:
        rendered.load()
        if rendered.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"Unexpected output size: {rendered.size}")
        if rendered.mode != "RGB":
            raise RuntimeError(f"Unexpected output mode: {rendered.mode}")
        if rendered.format != "JPEG":
            raise RuntimeError(f"Unexpected output format: {rendered.format}")
        result = {
            "output_path": str(DESTINATION),
            "width": rendered.width,
            "height": rendered.height,
            "format": rendered.format,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
