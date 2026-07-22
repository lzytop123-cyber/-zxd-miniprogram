"""Compose review-reward carousel V5 — desk illustration in reference-2 layout.

按第二张参考图（暖白底+波浪+叶形分隔+票券）的版式，重新呈现第一张图（GLM 原版）
的书桌插画内容：台灯 + 翻开的书 + 咖啡杯 + 绿植。
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH, HEIGHT = 1500, 1360
MAX_BYTES = 1_950_000
SAFE_MARGIN = 120

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = (
    ROOT / "assets" / "marketing" / "home-carousel"
    / "home-carousel-05-review-reward-v5-1500x1360.jpg"
)

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_FALLBACK = Path(r"C:\Windows\Fonts\simhei.ttf")

# ---------- 色板 ----------
BG_TOP = (250, 247, 238)
BG_BOTTOM = (228, 242, 232)
INK_DARK = (38, 88, 62)
INK_MAIN = (72, 165, 120)
INK_DEEP = (45, 106, 79)
INK_LIGHT = (210, 238, 220)
INK_MID = (100, 148, 120)
INK_MUTED = (128, 142, 132)
INK_DOTTED = (190, 210, 198)
GOLD = (212, 176, 96)
CREAM = (254, 250, 242)
WHITE = (255, 255, 255)
WOOD = (222, 198, 164)
WOOD_DARK = (190, 162, 122)
WOOD_EDGE = (170, 140, 100)
COFFEE = (142, 106, 78)
LEAF_DARK = (36, 90, 58)
LEAF_MAIN = (72, 165, 120)
LEAF_LIGHT = (148, 210, 178)
LEAF_PALE = (196, 230, 210)
POT = (228, 180, 140)
POT_DARK = (198, 150, 105)
TICKET_BG = (246, 250, 244)
TICKET_BORDER = (200, 224, 208)
WARM_GLOW = (255, 244, 208)


def select_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    preferred = FONT_BOLD if bold else FONT_REGULAR
    path = preferred if preferred.exists() else FONT_FALLBACK
    if not path.exists():
        raise FileNotFoundError("No required Chinese font is available")
    return ImageFont.truetype(str(path), size)


def text_metrics(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1], box[0], box[1]


def draw_centered(draw, xy, text, font, fill):
    x, y = xy
    w, h, ox, oy = text_metrics(draw, text, font)
    draw.text((x - w / 2 - ox, y - h / 2 - oy), text, font=font, fill=fill)


def vertical_gradient(size, top, bottom, ease=True):
    w, h = size
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        if ease:
            t = t * t * (3.0 - 2.0 * t)
        px[0, y] = (
            round(top[0] * (1 - t) + bottom[0] * t),
            round(top[1] * (1 - t) + bottom[1] * t),
            round(top[2] * (1 - t) + bottom[2] * t),
        )
    return strip.resize((w, h), Image.Resampling.BILINEAR)


# ---------- 有机波浪蒙版 ----------
def build_wave_mask(size, wave_cx, wave_amplitude=130):
    w, h = size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)
    points = [(wave_cx + 40, 0)]
    for y in range(0, h + 1, 4):
        t = y / h
        offset = (
            wave_amplitude * math.sin(t * math.pi * 1.2 - 0.3)
            + wave_amplitude * 0.35 * math.sin(t * math.pi * 2.4 + 0.8)
            + wave_amplitude * 0.12 * math.sin(t * math.pi * 4.0)
        )
        drift = 30 * t
        points.append((wave_cx + offset + drift, y))
    points.extend([(w, h), (w, 0)])
    md.polygon(points, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(radius=1.5))


# ---------- 叶片与枝条 ----------
def draw_leaf(draw_layer_dest, cx, cy, length, width, angle, color, vein=LEAF_DARK):
    """画一片叶子并贴到目标图层。这里直接接收目标图层而非 draw。"""
    pad = max(length, width) + 30
    leaf = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(leaf)
    ld.ellipse(
        (pad - length, pad - width // 2, pad + length, pad + width // 2),
        fill=color,
    )
    tip = length // 3
    ld.polygon(
        [(pad + length, pad - width // 4),
         (pad + length + tip, pad),
         (pad + length, pad + width // 4)],
        fill=color,
    )
    lw = max(1, width // 12)
    ld.line([(pad - length + 4, pad), (pad + length + tip - 2, pad)], fill=vein, width=lw)
    for i in range(3):
        t = (i + 1) / 4
        vx = pad - length + 4 + t * (length * 2 + tip - 6)
        off = width // 3
        ld.line([(vx, pad), (vx + length // 4, pad - off)], fill=vein, width=1)
        ld.line([(vx, pad), (vx + length // 4, pad + off)], fill=vein, width=1)
    rotated = leaf.rotate(angle, resample=Image.Resampling.BICUBIC, center=(pad, pad))
    draw_layer_dest.alpha_composite(rotated, (int(cx - pad), int(cy - pad)))


def draw_branch(layer, anchor_x, anchor_y, direction="top-right"):
    if direction == "top-right":
        leaves = [
            ((0, 0), 120, 50, -20, LEAF_DARK),
            ((-60, 40), 100, 42, -35, LEAF_MAIN),
            ((60, 30), 110, 48, -5, LEAF_MAIN),
            ((-30, 90), 90, 38, -50, LEAF_LIGHT),
            ((100, 80), 95, 40, 10, LEAF_DARK),
            ((-90, -20), 80, 34, -40, LEAF_LIGHT),
            ((40, -30), 85, 36, -15, LEAF_MAIN),
            ((130, 20), 70, 30, 15, LEAF_LIGHT),
        ]
    elif direction == "bottom-left":
        leaves = [
            ((0, 0), 90, 38, 150, LEAF_MAIN),
            ((50, -40), 80, 34, 130, LEAF_LIGHT),
            ((-30, -50), 85, 36, 170, LEAF_DARK),
            ((80, 10), 70, 30, 120, LEAF_MAIN),
            ((-60, -80), 60, 26, 190, LEAF_LIGHT),
        ]
    else:
        leaves = []
    for (dx, dy), length, width, angle, color in leaves:
        draw_leaf(layer, anchor_x + dx, anchor_y + dy, length, width, angle, color)


def leaf_icon(size=24, color=INK_MAIN):
    img = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    d.ellipse((s - s * 0.8, s - s * 0.35, s + s * 0.8, s + s * 0.35), fill=color)
    d.polygon(
        [(s + s * 0.8, s - s * 0.2), (s + s * 1.1, s), (s + s * 0.8, s + s * 0.2)],
        fill=color,
    )
    d.line([(s - s * 0.6, s), (s + s * 0.9, s)], fill=(255, 255, 255, 180), width=max(1, s // 10))
    return img


def paste_leaf_icon(layer, x, y, size=24, color=INK_MAIN):
    icon = leaf_icon(size, color)
    layer.alpha_composite(icon, (int(x - size), int(y - size)))


# ---------- 圆形图标 ----------
def draw_circle_icon(layer, cx, cy, r, kind):
    draw = ImageDraw.Draw(layer)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=INK_LIGHT)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=INK_MAIN, width=2)
    lw = max(2, r // 8)
    if kind == "pen":
        draw.line(
            [(cx - r * 0.4, cy + r * 0.4), (cx + r * 0.5, cy - r * 0.5)],
            fill=INK_DEEP, width=lw + 1,
        )
        draw.ellipse(
            (cx + r * 0.4, cy - r * 0.6, cx + r * 0.65, cy - r * 0.35),
            fill=GOLD,
        )
    elif kind == "camera":
        bw, bh = r * 1.1, r * 0.75
        draw.rounded_rectangle(
            (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2),
            radius=4, fill=INK_DEEP,
        )
        draw.ellipse((cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3), fill=WHITE)
        draw.ellipse((cx - r * 0.15, cy - r * 0.15, cx + r * 0.15, cy + r * 0.15), fill=INK_MAIN)
        draw.ellipse(
            (cx + bw / 2 - r * 0.2, cy - bh / 2 - r * 0.05,
             cx + bw / 2 + r * 0.05, cy - bh / 2 + r * 0.2),
            fill=GOLD,
        )
    elif kind == "gift":
        bw, bh = r * 1.2, r * 0.8
        draw.rounded_rectangle(
            (cx - bw / 2, cy - bh / 2 + r * 0.1, cx + bw / 2, cy + bh / 2 + r * 0.1),
            radius=4, fill=INK_MAIN,
        )
        draw.rectangle(
            (cx - lw, cy - bh / 2 + r * 0.1, cx + lw, cy + bh / 2 + r * 0.1),
            fill=GOLD,
        )
        draw.rectangle(
            (cx - bw / 2, cy - lw + r * 0.1, cx + bw / 2, cy + lw + r * 0.1),
            fill=GOLD,
        )
        draw.ellipse(
            (cx - r * 0.4, cy - bh / 2 - r * 0.15,
             cx - r * 0.05, cy - bh / 2 + r * 0.2),
            fill=GOLD,
        )
        draw.ellipse(
            (cx + r * 0.05, cy - bh / 2 - r * 0.15,
             cx + r * 0.4, cy - bh / 2 + r * 0.2),
            fill=GOLD,
        )


# ---------- 票券 ----------
def draw_ticket(layer, x1, y1, x2, y2, notch_r=14, radius=16):
    ticket = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ticket)
    d.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=TICKET_BG)
    d.ellipse(
        (x1 - notch_r, (y1 + y2) // 2 - notch_r,
         x1 + notch_r, (y1 + y2) // 2 + notch_r),
        fill=(0, 0, 0, 0),
    )
    d.ellipse(
        (x2 - notch_r, (y1 + y2) // 2 - notch_r,
         x2 + notch_r, (y1 + y2) // 2 + notch_r),
        fill=(0, 0, 0, 0),
    )
    dash_len, gap = 10, 8
    cy = (y1 + y2) // 2
    x = x1 + notch_r + 12
    while x < x2 - notch_r - 12:
        d.line([(x, cy), (x + dash_len, cy)], fill=TICKET_BORDER, width=2)
        x += dash_len + gap
    d.rounded_rectangle((x1, y1, x2, y2), radius=radius, outline=TICKET_BORDER, width=2)
    d.arc(
        (x1 - notch_r, cy - notch_r, x1 + notch_r, cy + notch_r),
        start=90, end=270, fill=TICKET_BORDER, width=2,
    )
    d.arc(
        (x2 - notch_r, cy - notch_r, x2 + notch_r, cy + notch_r),
        start=270, end=90, fill=TICKET_BORDER, width=2,
    )
    layer.alpha_composite(ticket)


# ---------- 右侧书桌插画（来自 V1，优化细节） ----------
def draw_right_illustration(layer):
    draw = ImageDraw.Draw(layer)

    # 1. 右侧浅色背景大色块（让插画有"底"）
    blob = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob)
    bd.rounded_rectangle((660, 80, 1420, 1280), radius=80, fill=LEAF_PALE + (120,))
    blob = blob.filter(ImageFilter.GaussianBlur(radius=20))
    layer.alpha_composite(blob)
    draw = ImageDraw.Draw(layer)

    # 2. 顶部柔光（暖黄光晕）
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((900, 100, 1400, 500), fill=WARM_GLOW + (90,))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=50))
    layer.alpha_composite(glow)
    draw = ImageDraw.Draw(layer)

    # 3. 地面投影条
    floor_top = 1180
    carpet = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(carpet)
    cd.rounded_rectangle(
        (760, floor_top, 1420, floor_top + 60),
        radius=30, fill=LEAF_PALE + (180,),
    )
    carpet = carpet.filter(ImageFilter.GaussianBlur(radius=2))
    layer.alpha_composite(carpet)
    draw = ImageDraw.Draw(layer)

    # 4. 桌面
    desk_left, desk_right = 820, 1420
    desk_top = 920
    desk_thick = 22
    # 桌面投影
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (desk_left + 6, desk_top + desk_thick + 2, desk_right + 6, desk_top + desk_thick + 20),
        radius=8, fill=(45, 106, 79, 40),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=6))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)
    # 桌面
    draw.rounded_rectangle(
        (desk_left, desk_top, desk_right, desk_top + desk_thick),
        radius=10, fill=WOOD,
    )
    draw.rectangle(
        (desk_left + 12, desk_top + 3, desk_right - 12, desk_top + 6),
        fill=(236, 216, 186),
    )
    draw.rounded_rectangle(
        (desk_left, desk_top + desk_thick - 4, desk_right, desk_top + desk_thick + 8),
        radius=6, fill=WOOD_DARK,
    )
    # 桌腿
    for leg_x in [desk_left + 50, desk_right - 50]:
        draw.polygon(
            [(leg_x - 10, desk_top + desk_thick + 8),
             (leg_x + 10, desk_top + desk_thick + 8),
             (leg_x + 6, floor_top),
             (leg_x - 6, floor_top)],
            fill=WOOD_DARK,
        )

    # 5. 台灯（左）
    lamp_base_cx = desk_left + 140
    lamp_base_y = desk_top
    # 底座
    draw.ellipse(
        (lamp_base_cx - 36, lamp_base_y - 8, lamp_base_cx + 36, lamp_base_y + 10),
        fill=INK_DEEP,
    )
    draw.ellipse(
        (lamp_base_cx - 30, lamp_base_y - 14, lamp_base_cx + 30, lamp_base_y + 2),
        fill=INK_DARK,
    )
    # 灯柱
    pole_top = lamp_base_y - 200
    draw.line(
        [(lamp_base_cx, lamp_base_y - 6), (lamp_base_cx + 8, pole_top + 30)],
        fill=WOOD_DARK, width=7,
    )
    draw.line(
        [(lamp_base_cx + 8, pole_top + 30), (lamp_base_cx + 4, pole_top + 60)],
        fill=WOOD_DARK, width=7,
    )
    # 灯罩
    shade_top_y = pole_top
    draw.polygon(
        [(lamp_base_cx - 60, shade_top_y + 80),
         (lamp_base_cx + 68, shade_top_y + 80),
         (lamp_base_cx + 36, shade_top_y),
         (lamp_base_cx - 28, shade_top_y)],
        fill=INK_DEEP,
    )
    draw.ellipse(
        (lamp_base_cx - 62, shade_top_y + 76, lamp_base_cx + 70, shade_top_y + 88),
        fill=INK_MAIN,
    )
    draw.ellipse(
        (lamp_base_cx - 58, shade_top_y + 74, lamp_base_cx + 66, shade_top_y + 82),
        fill=(255, 248, 220),
    )
    # 桌面暖光
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        (lamp_base_cx - 100, desk_top - 2, lamp_base_cx + 100, desk_top + 14),
        fill=WARM_GLOW + (150,),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=8))
    layer.alpha_composite(glow)
    draw = ImageDraw.Draw(layer)

    # 6. 翻开的书（中左）
    book_cx = desk_left + 400
    book_top = desk_top - 46
    bw, bh = 110, 50
    # 书阴影
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(
        (book_cx - bw - 8, book_top + bh + 2, book_cx + bw + 8, book_top + bh + 16),
        fill=(45, 106, 79, 40),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=5))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)
    # 封底深绿
    draw.polygon(
        [(book_cx - bw + 4, book_top + bh + 4),
         (book_cx - bw - 2, book_top + 6),
         (book_cx - 8, book_top - 2),
         (book_cx - 2, book_top + bh + 2)],
        fill=INK_DEEP,
    )
    draw.polygon(
        [(book_cx + bw - 4, book_top + bh + 4),
         (book_cx + bw + 2, book_top + 6),
         (book_cx + 8, book_top - 2),
         (book_cx + 2, book_top + bh + 2)],
        fill=INK_DEEP,
    )
    # 左右页
    draw.polygon(
        [(book_cx - bw, book_top + bh),
         (book_cx - bw - 6, book_top + 8),
         (book_cx - 6, book_top),
         (book_cx, book_top + bh)],
        fill=CREAM,
    )
    draw.polygon(
        [(book_cx + bw, book_top + bh),
         (book_cx + bw + 6, book_top + 8),
         (book_cx + 6, book_top),
         (book_cx, book_top + bh)],
        fill=(255, 255, 252),
    )
    draw.line(
        [(book_cx, book_top + 2), (book_cx, book_top + bh - 2)],
        fill=(220, 215, 200), width=2,
    )
    for page_left in [book_cx - bw + 14, book_cx + 14]:
        for i, yoff in enumerate([14, 24, 34]):
            lw = 70 if i != 2 else 48
            draw.line(
                [(page_left, book_top + yoff), (page_left + lw, book_top + yoff)],
                fill=(180, 200, 186), width=2,
            )

    # 7. 咖啡杯（中右）
    cup_cx = desk_left + 760
    cup_top = desk_top - 78
    cup_w, cup_h = 52, 64
    # 杯底阴影
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(
        (cup_cx - cup_w - 6, desk_top - 2, cup_cx + cup_w + 30, desk_top + 10),
        fill=(45, 106, 79, 35),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=4))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)
    # 杯碟
    draw.ellipse(
        (cup_cx - cup_w - 6, cup_top + cup_h - 4, cup_cx + cup_w + 6, cup_top + cup_h + 10),
        fill=(245, 240, 232),
    )
    # 杯身
    draw.polygon(
        [(cup_cx - cup_w + 4, cup_top + cup_h),
         (cup_cx + cup_w - 4, cup_top + cup_h),
         (cup_cx + cup_w - 10, cup_top + 8),
         (cup_cx - cup_w + 10, cup_top + 8)],
        fill=WHITE,
    )
    draw.ellipse(
        (cup_cx - cup_w + 8, cup_top, cup_cx + cup_w - 8, cup_top + 16),
        fill=(250, 248, 244),
    )
    draw.ellipse(
        (cup_cx - cup_w + 12, cup_top + 2, cup_cx + cup_w - 12, cup_top + 14),
        fill=COFFEE,
    )
    draw.arc(
        (cup_cx + cup_w - 14, cup_top + 14, cup_cx + cup_w + 22, cup_top + 52),
        start=300, end=100, fill=(230, 224, 216), width=5,
    )
    # 蒸汽
    for dx, alpha in [(-12, 180), (8, 140), (20, 100)]:
        steam = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        sm = ImageDraw.Draw(steam)
        sx = cup_cx + dx
        sy = cup_top - 4
        for i in range(3):
            phase = 1 if i % 2 == 0 else -1
            sm.arc(
                (sx - 8 + phase * 6, sy - 18 - i * 18,
                 sx + 8 + phase * 6, sy - 2 - i * 18),
                start=200, end=340,
                fill=(200, 210, 204, alpha), width=3,
            )
        steam = steam.filter(ImageFilter.GaussianBlur(radius=1))
        layer.alpha_composite(steam)
    draw = ImageDraw.Draw(layer)

    # 8. 绿植（右）
    plant_cx = desk_right - 120
    plant_top = desk_top - 28
    # 花盆阴影
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(
        (plant_cx - 46, desk_top - 2, plant_cx + 46, desk_top + 10),
        fill=(45, 106, 79, 35),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=4))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)
    # 花盆
    pot_top = plant_top + 80
    draw.polygon(
        [(plant_cx - 42, pot_top),
         (plant_cx + 42, pot_top),
         (plant_cx + 34, plant_top + 26),
         (plant_cx - 34, plant_top + 26)],
        fill=POT_DARK,
    )
    draw.ellipse(
        (plant_cx - 38, plant_top + 20, plant_cx + 38, plant_top + 34),
        fill=POT,
    )
    draw.ellipse(
        (plant_cx - 34, plant_top + 22, plant_cx + 34, plant_top + 32),
        fill=(80, 54, 36),
    )
    # 叶簇
    leaves = [
        (0, -20, 22, 58, LEAF_DARK),
        (-20, 0, 18, 48, LEAF_MAIN),
        (22, -4, 20, 52, LEAF_MAIN),
        (-10, -38, 16, 42, LEAF_LIGHT),
        (14, -34, 17, 44, LEAF_LIGHT),
        (-30, -18, 12, 30, LEAF_PALE),
        (30, -22, 13, 32, LEAF_PALE),
    ]
    for dx, dy, rx, ry, color in leaves:
        cx = plant_cx + dx
        cy = plant_top + dy
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=color)

    # 9. 散落叶片装饰
    decors = [
        (780, 200, 70, 35, -25, LEAF_LIGHT),
        (1340, 280, 80, 38, 20, LEAF_MAIN),
        (760, 580, 55, 28, -40, LEAF_PALE),
        (1380, 720, 65, 32, 30, LEAF_LIGHT),
        (820, 780, 50, 24, -15, LEAF_PALE),
    ]
    for cx, cy, length, width, angle, color in decors:
        draw_leaf(layer, cx, cy, length, width, angle, color)


# ---------- 左侧文案 ----------
def draw_text_layer(layer, wave_cx):
    draw = ImageDraw.Draw(layer)
    left = SAFE_MARGIN
    content_right = wave_cx - 50
    content_width = content_right - left

    # 标签
    tag_font = select_font(28, bold=True)
    tag_text = "好评有礼"
    tag_w, tag_h, _, _ = text_metrics(draw, tag_text, tag_font)
    tag_pill_w = tag_w + 80
    tag_pill_h = 60
    tag_top = 120
    tag_left = left
    draw.rounded_rectangle(
        (tag_left, tag_top, tag_left + tag_pill_w, tag_top + tag_pill_h),
        radius=tag_pill_h // 2, fill=INK_MAIN,
    )
    paste_leaf_icon(layer, tag_left + 28, tag_top + tag_pill_h / 2, size=14, color=WHITE)
    draw_centered(
        draw, (tag_left + tag_pill_w / 2 + 10, tag_top + tag_pill_h / 2),
        tag_text, tag_font, WHITE,
    )

    # 大标题
    headline_font = select_font(118, bold=True)
    l1 = "写好评"
    l2 = "送日卡"
    l1_w, l1_h, _, _ = text_metrics(draw, l1, headline_font)
    l2_w, l2_h, _, _ = text_metrics(draw, l2, headline_font)
    hl_top = tag_top + tag_pill_h + 50
    draw.text((left, hl_top), l1, font=headline_font, fill=INK_DARK)
    l2_top = hl_top + l1_h + 8
    draw.text((left, l2_top), l2, font=headline_font, fill=INK_DARK)

    # 叶形分隔符副标题
    sub_font = select_font(34)
    sub_text = "15字好评 · 三张真实照片"
    sub_top = l2_top + l2_h + 50
    sub_w, sub_h, _, _ = text_metrics(draw, sub_text, sub_font)
    leaf_sz = 16
    leaf_gap = 22
    sub_x = left
    paste_leaf_icon(layer, sub_x + leaf_sz, sub_top + sub_h / 2, size=leaf_sz, color=INK_MAIN)
    draw.text(
        (sub_x + leaf_sz + leaf_gap, sub_top),
        sub_text, font=sub_font, fill=INK_MID,
    )
    paste_leaf_icon(
        layer,
        sub_x + leaf_sz + leaf_gap + sub_w + leaf_gap + leaf_sz,
        sub_top + sub_h / 2,
        size=leaf_sz, color=INK_MAIN,
    )

    # 虚线
    dash_top = sub_top + sub_h + 40
    dash_len, gap = 12, 10
    x = left
    while x < left + content_width - 20:
        draw.line([(x, dash_top), (x + dash_len, dash_top)], fill=INK_DOTTED, width=2)
        x += dash_len + gap

    # 三图标
    feat_top = dash_top + 50
    feat_font = select_font(26)
    icon_r = 38
    gap_between = content_width / 3
    feats = [("美团", "pen"), ("大众点评", "camera"), ("抖音", "gift")]
    for i, (label, kind) in enumerate(feats):
        cx = left + gap_between * i + gap_between / 2
        cy = feat_top + icon_r
        draw_circle_icon(layer, int(cx), int(cy), icon_r, kind)
        draw_centered(draw, (cx, cy + icon_r + 28), label, feat_font, INK_MUTED)

    # 票券
    ticket_top = feat_top + icon_r * 2 + 70
    ticket_h = 160
    ticket_w = content_width - 20
    ticket_x1 = left
    ticket_x2 = left + ticket_w
    ticket_y1 = ticket_top
    ticket_y2 = ticket_top + ticket_h
    draw_ticket(layer, ticket_x1, ticket_y1, ticket_x2, ticket_y2)

    big_font = select_font(62, bold=True)
    med_font = select_font(28)
    small_font = select_font(22)
    big_text = "日卡"
    draw.text((ticket_x1 + 40, ticket_y1 + 22), big_text, font=big_font, fill=INK_DARK)
    draw.text(
        (ticket_x1 + 40 + text_metrics(draw, big_text, big_font)[0] + 6, ticket_y1 + 52),
        "×1张", font=med_font, fill=INK_MAIN,
    )
    note_lines = ["截图发给管理员", "即可免费兑换"]
    for i, line in enumerate(note_lines):
        draw.text(
            (ticket_x1 + 40, ticket_y1 + 94 + i * 30),
            line, font=small_font, fill=INK_MUTED,
        )
    leaf_deco = leaf_icon(28, INK_MAIN)
    layer.alpha_composite(leaf_deco, (int(ticket_x2 - 80), int(ticket_y1 + 30)))

    # 品牌角标
    wm_font = select_font(26, bold=True)
    wm_text = "知行岛自习室"
    wm_w, _, _, _ = text_metrics(draw, wm_text, wm_font)
    wm_right = WIDTH - SAFE_MARGIN
    wm_top = SAFE_MARGIN + 10
    draw.rounded_rectangle(
        (wm_right - wm_w - 40, wm_top, wm_right, wm_top + 46),
        radius=23, fill=(255, 255, 255, 200),
    )
    draw.text(
        (wm_right - wm_w - 20, wm_top + 10),
        wm_text, font=wm_font, fill=INK_DARK,
    )


def encode_jpeg(image):
    for quality in (92, 88, 84, 80, 76):
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=quality, optimize=True, progressive=True, subsampling="4:2:0")
        payload = buf.getvalue()
        if 0 < len(payload) < MAX_BYTES:
            return payload, quality
    raise RuntimeError("JPEG too large")


def main():
    bg = Image.new("RGB", (WIDTH, HEIGHT), BG_TOP)
    bg_grad = vertical_gradient((WIDTH, HEIGHT), BG_TOP, BG_BOTTOM)
    bg = Image.blend(bg, bg_grad, 0.5)
    canvas = bg.convert("RGBA")

    wave_cx = 700
    wave_mask = build_wave_mask((WIDTH, HEIGHT), wave_cx, wave_amplitude=130)
    right_bg = Image.new("RGBA", (WIDTH, HEIGHT), (240, 250, 240, 255))
    canvas.paste(right_bg, (0, 0), wave_mask)

    leaves_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_branch(leaves_layer, WIDTH + 20, -40, "top-right")
    draw_branch(leaves_layer, -40, HEIGHT + 60, "bottom-left")
    canvas = Image.alpha_composite(canvas, leaves_layer)

    illust = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_right_illustration(illust)
    canvas = Image.alpha_composite(canvas, illust)

    text_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_text_layer(text_layer, wave_cx)
    canvas = Image.alpha_composite(canvas, text_layer)

    final = canvas.convert("RGB")
    payload, _q = encode_jpeg(final)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(payload)

    with Image.open(DESTINATION) as rendered:
        rendered.load()
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
