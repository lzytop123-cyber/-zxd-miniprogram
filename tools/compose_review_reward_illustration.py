"""Compose a fresh modern-illustration review-reward carousel (no photo).

纯 Pillow 矢量绘制：清新扁平插画风格，不依赖任何照片素材。
输出：assets/marketing/home-carousel/home-carousel-05-review-reward-illustration-1500x1360.jpg
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH, HEIGHT = 1500, 1360
MAX_BYTES = 1_950_000
ROOT = Path(__file__).resolve().parents[1]
DESTINATION = (
    ROOT
    / "assets"
    / "marketing"
    / "home-carousel"
    / "home-carousel-05-review-reward-illustration-1500x1360.jpg"
)

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_FALLBACK = Path(r"C:\Windows\Fonts\simhei.ttf")

# 知行岛配色（与 DESIGN.md 一致）
BG_TOP = (250, 251, 246)        # 暖白偏亮
BG_BOTTOM = (216, 243, 220)     # 浅薄荷
PANEL_FILL = (255, 255, 255, 210)
PANEL_SHADOW = (45, 106, 79, 28)

INK_DARK = (45, 106, 79)        # #2D6A4F 深绿
INK_MAIN = (82, 183, 136)       # #52B788 主绿
INK_LIGHT = (216, 243, 220)     # #D8F3DC 浅绿
INK_MID = (82, 124, 100)
INK_MUTED = (111, 125, 115)

WOOD = (232, 213, 183)
WOOD_DARK = (201, 175, 138)
COFFEE = (165, 140, 110)
LEAF_DEEP = (45, 106, 79)
LEAF_MID = (82, 183, 136)
LEAF_SOFT = (143, 198, 173)
SUN_CORE = (252, 232, 168)
SUN_RING = (244, 218, 130)
STEM = (120, 158, 110)

TAG = "好评有礼"
HEADLINE = "写好评\n送日卡"
SUBTITLE = "美团 · 大众点评 · 抖音｜15字+3张照片"
NOTE = "截图发给管理员，即可兑换日卡一张"
WORDMARK = "知行岛自习室"


def select_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    preferred = FONT_BOLD if bold else FONT_REGULAR
    path = preferred if preferred.exists() else FONT_FALLBACK
    if not path.exists():
        raise FileNotFoundError("No required Chinese font is available")
    return ImageFont.truetype(str(path), size)


def text_width(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.FreeTypeFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), value, font=face)
    return right - left


def vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    """上到下的线性 RGB 渐变。"""
    w, h = size
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        # 用 ease-in-out 让中间过渡更柔和
        s = t * t * (3.0 - 2.0 * t)
        r = round(top[0] * (1 - s) + bottom[0] * s)
        g = round(top[1] * (1 - s) + bottom[1] * s)
        b = round(top[2] * (1 - s) + bottom[2] * s)
        px[0, y] = (r, g, b)
    return strip.resize((w, h), Image.Resampling.BILINEAR)


def draw_leaf(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, angle_deg: float, color: tuple[int, int, int]) -> None:
    """画一片绕 (cx, cy) 旋转的椭圆叶片。"""
    leaf = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(leaf)
    ld.ellipse((0, size // 3, size * 2, size - size // 3), fill=color + (255,))
    leaf = leaf.rotate(angle_deg, resample=Image.Resampling.BICUBIC, expand=False)
    # paste 回主画布
    # 这里直接用 draw.image 不行，需要返回图给上层 paste
    # 简化：用 chord / ellipse 直接画
    # 退化为画一个倾斜椭圆
    draw.ellipse(
        (cx - size, cy - size // 3, cx + size, cy + size // 3),
        fill=color,
    )


def draw_scene(base: Image.Image) -> Image.Image:
    """在背景上绘制插画场景，返回 RGBA 图层（含场景）。"""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # 1. 右上太阳光晕（多层同心圆）
    sun_cx, sun_cy = 1280, 260
    for i, (r, color) in enumerate([
        (260, SUN_CORE + (0,)),
        (230, SUN_CORE + (0,)),
        (200, SUN_RING + (0,)),
    ]):
        # 用 RGBA 但 alpha 渐变
        alpha = [60, 90, 160][i]
        draw.ellipse(
            (sun_cx - r, sun_cy - r, sun_cx + r, sun_cy + r),
            fill=color[:3] + (alpha,),
        )

    # 太阳本体（实心）
    draw.ellipse(
        (sun_cx - 130, sun_cy - 130, sun_cx + 130, sun_cy + 130),
        fill=SUN_CORE + (220,),
    )

    # 2. 漂浮叶片（散落在右上和右侧空白处）
    floaters = [
        (820, 240, 70, 35, LEAF_SOFT),
        (1080, 180, 90, 40, LEAF_MID),
        (1380, 520, 60, 28, LEAF_SOFT),
        (760, 480, 50, 24, LEAF_MID),
        (1180, 540, 75, 34, LEAF_DEEP),
        (900, 380, 55, 26, LEAF_SOFT),
        (1320, 720, 65, 30, LEAF_MID),
    ]
    for cx, cy, w, h, color in floaters:
        draw.ellipse((cx - w, cy - h, cx + w, cy + h), fill=color + (200,))

    # 3. 地面阴影线（底部弱阴影）
    draw.rounded_rectangle(
        (640, 1180, 1480, 1230),
        radius=25,
        fill=(45, 106, 79, 30),
    )

    # 4. 书桌主体（右下区域）
    desk_left, desk_right = 760, 1440
    desk_top = 950
    desk_thick = 26
    # 桌面
    draw.rounded_rectangle(
        (desk_left, desk_top, desk_right, desk_top + desk_thick),
        radius=12,
        fill=WOOD,
    )
    # 桌面下沿深色
    draw.rounded_rectangle(
        (desk_left, desk_top + desk_thick, desk_right, desk_top + desk_thick + 6),
        radius=6,
        fill=WOOD_DARK,
    )
    # 桌腿（两根斜柱）
    draw.polygon(
        [(desk_left + 40, desk_top + desk_thick + 6),
         (desk_left + 30, 1180),
         (desk_left + 60, 1180),
         (desk_left + 70, desk_top + desk_thick + 6)],
        fill=WOOD_DARK,
    )
    draw.polygon(
        [(desk_right - 70, desk_top + desk_thick + 6),
         (desk_right - 60, 1180),
         (desk_right - 30, 1180),
         (desk_right - 40, desk_top + desk_thick + 6)],
        fill=WOOD_DARK,
    )

    # 5. 桌上物品：台灯、书、咖啡、绿植（从左到右）

    # 5.1 台灯（左侧）
    lamp_base_x = desk_left + 110
    lamp_top_y = desk_top - 220
    # 灯柱
    draw.line(
        [(lamp_base_x, desk_top), (lamp_base_x, lamp_top_y + 40)],
        fill=WOOD_DARK, width=10,
    )
    # 灯罩（梯形）
    draw.polygon(
        [(lamp_base_x - 70, lamp_top_y + 90),
         (lamp_base_x + 70, lamp_top_y + 90),
         (lamp_base_x + 40, lamp_top_y),
         (lamp_base_x - 40, lamp_top_y)],
        fill=INK_DARK,
    )
    # 灯罩底沿
    draw.rectangle(
        (lamp_base_x - 70, lamp_top_y + 85, lamp_base_x + 70, lamp_top_y + 95),
        fill=INK_MAIN,
    )
    # 灯光（浅黄椭圆投在桌面）
    draw.ellipse(
        (lamp_base_x - 90, desk_top - 4, lamp_base_x + 90, desk_top + 8),
        fill=(252, 232, 168, 120),
    )

    # 5.2 翻开的书（中间偏左）
    book_cx = desk_left + 360
    book_top = desk_top - 50
    # 书页底（浅色）
    draw.polygon(
        [(book_cx - 110, book_top + 50),
         (book_cx + 110, book_top + 50),
         (book_cx + 100, book_top + 10),
         (book_cx - 100, book_top + 10)],
        fill=(245, 247, 240),
    )
    # 书脊中线
    draw.line(
        [(book_cx, book_top + 10), (book_cx, book_top + 50)],
        fill=WOOD_DARK, width=3,
    )
    # 文字线（左页）
    for i, y in enumerate([book_top + 20, book_top + 28, book_top + 36]):
        draw.line(
            [(book_cx - 90, y), (book_cx - 20, y)],
            fill=INK_MUTED + (180,) if False else INK_MUTED, width=2,
        )
    # 文字线（右页）
    for y in [book_top + 20, book_top + 28, book_top + 36]:
        draw.line(
            [(book_cx + 20, y), (book_cx + 90, y)],
            fill=INK_MUTED, width=2,
        )
    # 书封底（深绿，露出一点边）
    draw.polygon(
        [(book_cx - 110, book_top + 50),
         (book_cx - 100, book_top + 10),
         (book_cx - 105, book_top + 8),
         (book_cx - 115, book_top + 48)],
        fill=INK_DARK,
    )
    draw.polygon(
        [(book_cx + 110, book_top + 50),
         (book_cx + 100, book_top + 10),
         (book_cx + 105, book_top + 8),
         (book_cx + 115, book_top + 48)],
        fill=INK_DARK,
    )

    # 5.3 咖啡杯（中间偏右）
    cup_cx = desk_left + 600
    cup_top = desk_top - 70
    cup_w, cup_h = 70, 80
    # 杯身
    draw.rounded_rectangle(
        (cup_cx - cup_w // 2, cup_top, cup_cx + cup_w // 2, cup_top + cup_h),
        radius=10,
        fill=(255, 255, 255),
    )
    # 咖啡液面
    draw.ellipse(
        (cup_cx - cup_w // 2, cup_top - 6, cup_cx + cup_w // 2, cup_top + 10),
        fill=COFFEE,
    )
    # 把手
    draw.arc(
        (cup_cx + cup_w // 2 - 4, cup_top + 12, cup_cx + cup_w // 2 + 40, cup_top + 60),
        start=300, end=90,
        fill=WOOD_DARK, width=8,
    )
    # 蒸汽（两条曲线）
    for offset in (-12, 12):
        draw.arc(
            (cup_cx + offset - 20, cup_top - 60, cup_cx + offset + 20, cup_top - 10),
            start=200, end=340,
            fill=(200, 210, 200, 120) if False else (200, 210, 200),
            width=4,
        )

    # 5.4 绿植（右侧）
    plant_cx = desk_left + 860
    plant_top = desk_top - 30
    # 花盆
    draw.polygon(
        [(plant_cx - 55, plant_top + 90),
         (plant_cx + 55, plant_top + 90),
         (plant_cx + 45, plant_top + 30),
         (plant_cx - 45, plant_top + 30)],
        fill=WOOD_DARK,
    )
    draw.rectangle(
        (plant_cx - 50, plant_top + 24, plant_cx + 50, plant_top + 38),
        fill=WOOD,
    )
    # 叶簇（多片椭圆叠加）
    leaves = [
        (plant_cx, plant_top - 10, 45, 60, LEAF_DEEP),
        (plant_cx - 35, plant_top + 10, 38, 50, LEAF_MID),
        (plant_cx + 35, plant_top + 5, 40, 55, LEAF_MID),
        (plant_cx - 15, plant_top - 30, 32, 45, LEAF_SOFT),
        (plant_cx + 20, plant_top - 25, 35, 48, LEAF_SOFT),
    ]
    for cx, cy, w, h, color in leaves:
        draw.ellipse((cx - w, cy - h, cx + w, cy + h), fill=color)
    # 叶脉（中心线）
    draw.line(
        [(plant_cx, plant_top - 60), (plant_cx, plant_top + 20)],
        fill=LEAF_DEEP, width=2,
    )

    # 6. 右上小装饰：星星 / 圆点
    dots = [
        (920, 120, 8, SUN_RING),
        (1150, 320, 6, LEAF_MID),
        (700, 180, 5, INK_MAIN),
        (1380, 380, 7, SUN_RING),
    ]
    for cx, cy, r, color in dots:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color + (200,))

    return layer


def draw_copy(base: Image.Image) -> Image.Image:
    """绘制左侧文案面板与文字。"""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    # 文案面板（白色圆角，弱阴影）
    panel_left, panel_top = 80, 220
    panel_right, panel_bottom = 720, 1140
    # 阴影
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (panel_left + 8, panel_top + 12, panel_right + 8, panel_bottom + 12),
        radius=44,
        fill=(45, 106, 79, 35),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=16))
    layer = Image.alpha_composite(layer, shadow)
    draw = ImageDraw.Draw(layer)
    # 面板
    draw.rounded_rectangle(
        (panel_left, panel_top, panel_right, panel_bottom),
        radius=44,
        fill=PANEL_FILL,
    )
    # 顶部主绿细色条（DESIGN.md 允许）
    draw.rounded_rectangle(
        (panel_left, panel_top, panel_right, panel_top + 8),
        radius=4,
        fill=INK_MAIN,
    )

    inner_left = panel_left + 56

    # 标签：好评有礼
    tag_font = select_font(36, bold=True)
    tag_top = panel_top + 70
    tag_height = 72
    tag_width = text_width(draw, TAG, tag_font) + 56
    draw.rounded_rectangle(
        (inner_left, tag_top, inner_left + tag_width, tag_top + tag_height),
        radius=tag_height // 2,
        fill=INK_LIGHT,
    )
    tag_box = draw.textbbox((0, 0), TAG, font=tag_font)
    tag_x = inner_left + (tag_width - (tag_box[2] - tag_box[0])) / 2 - tag_box[0]
    tag_y = tag_top + (tag_height - (tag_box[3] - tag_box[1])) / 2 - tag_box[1]
    draw.text((tag_x, tag_y), TAG, font=tag_font, fill=INK_DARK)

    # 主标题：写好评 / 送日卡
    headline_font = select_font(112, bold=True)
    headline_top = tag_top + tag_height + 56
    draw.multiline_text(
        (inner_left, headline_top),
        HEADLINE,
        font=headline_font,
        fill=INK_DARK,
        spacing=10,
    )
    headline_box = draw.multiline_textbbox(
        (inner_left, headline_top),
        HEADLINE,
        font=headline_font,
        spacing=10,
    )

    # 副标题
    subtitle_font = select_font(30)
    subtitle_top = headline_box[3] + 44
    draw.text(
        (inner_left, subtitle_top),
        SUBTITLE,
        font=subtitle_font,
        fill=INK_MUTED,
    )

    # 底部小字（活动说明，原 CTA 位置）
    note_font = select_font(26)
    note_top = subtitle_top + 80
    draw.text(
        (inner_left, note_top),
        NOTE,
        font=note_font,
        fill=INK_DARK,
    )

    return layer


def draw_wordmark(base: Image.Image) -> Image.Image:
    """右上角品牌字标。"""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    font = select_font(30, bold=True)
    right = WIDTH - 80
    top = 80
    w = text_width(draw, WORDMARK, font)
    draw.text((right - w, top), WORDMARK, font=font, fill=INK_DARK)
    return layer


def encode_jpeg(image: Image.Image) -> tuple[bytes, int]:
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
    # 1. 背景渐变
    background = vertical_gradient((WIDTH, HEIGHT), BG_TOP, BG_BOTTOM)

    # 2. 场景插画
    scene = draw_scene(background)

    # 3. 文案面板
    copy_layer = draw_copy(background)

    # 4. 角标
    wordmark = draw_wordmark(background)

    # 5. 合成
    canvas = background.convert("RGBA")
    canvas = Image.alpha_composite(canvas, scene)
    canvas = Image.alpha_composite(canvas, copy_layer)
    canvas = Image.alpha_composite(canvas, wordmark)
    final = canvas.convert("RGB")

    # 6. 编码
    payload, _quality = encode_jpeg(final)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(payload)

    # 7. 校验
    with Image.open(DESTINATION) as rendered:
        rendered.load()
        if rendered.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"Unexpected size: {rendered.size}")
        if rendered.mode != "RGB":
            raise RuntimeError(f"Unexpected mode: {rendered.mode}")
        if rendered.format != "JPEG":
            raise RuntimeError(f"Unexpected format: {rendered.format}")
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
