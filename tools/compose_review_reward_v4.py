"""Compose review-reward carousel V4 — warm illustration with photo-frame motif.

融合参考元素：
- 左侧文案区：绿标签 + 大标题 + 叶形分隔 + 三平台图标 + 票券
- 右侧插画：木质相框（内写"你今天真棒"）、绿植、礼物盒/日卡
- 暖白浅绿背景，有机曲线过渡，120px 安全边距
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
    / "home-carousel-05-review-reward-v4-1500x1360.jpg"
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
FRAME_WOOD = (220, 180, 130)
FRAME_DARK = (180, 140, 92)
WHITE = (255, 255, 255)
LEAF_DARK = (36, 90, 58)
LEAF_MAIN = (72, 165, 120)
LEAF_LIGHT = (148, 210, 178)
LEAF_PALE = (196, 230, 210)
POT = (228, 180, 140)
POT_DARK = (198, 150, 105)
TICKET_BG = (246, 250, 244)
TICKET_BORDER = (200, 224, 208)


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


# ---------- 有机波浪蒙版（右侧插画区） ----------
def build_wave_mask(size, wave_cx, wave_amplitude=150):
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
def draw_leaf(draw, cx, cy, length, width, angle, color, vein=LEAF_DARK):
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
    return rotated, (int(cx - pad), int(cy - pad))


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
        leaf_img, pos = draw_leaf(None, anchor_x + dx, anchor_y + dy, length, width, angle, color)
        layer.alpha_composite(leaf_img, pos)


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


# ---------- 右侧核心插画：相框 + 绿植 + 礼物 ----------
def draw_right_illustration(layer):
    draw = ImageDraw.Draw(layer)

    # 1. 右侧背景色块（浅薄荷圆角大色块，让插画有"底"）
    blob = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob)
    bd.rounded_rectangle(
        (660, 80, 1420, 1280), radius=80, fill=LEAF_PALE + (120,)
    )
    blob = blob.filter(ImageFilter.GaussianBlur(radius=20))
    layer.alpha_composite(blob)
    draw = ImageDraw.Draw(layer)

    # 2. 木质相框
    frame_cx, frame_cy = 1110, 520
    frame_w, frame_h = 460, 560
    frame_thick = 22
    # 外框阴影
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (frame_cx - frame_w / 2 + 12, frame_cy - frame_h / 2 + 18,
         frame_cx + frame_w / 2 + 12, frame_cy + frame_h / 2 + 18),
        radius=8, fill=(40, 60, 45, 45),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=16))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)
    # 外框
    draw.rounded_rectangle(
        (frame_cx - frame_w / 2, frame_cy - frame_h / 2,
         frame_cx + frame_w / 2, frame_cy + frame_h / 2),
        radius=8, fill=FRAME_WOOD, outline=FRAME_DARK, width=3,
    )
    # 内框白底
    inner_pad = 28
    draw.rounded_rectangle(
        (frame_cx - frame_w / 2 + inner_pad, frame_cy - frame_h / 2 + inner_pad,
         frame_cx + frame_w / 2 - inner_pad, frame_cy + frame_h / 2 - inner_pad),
        radius=4, fill=CREAM,
    )
    # 相框内文字 "你今天真棒" — 手写感
    phrase_font = select_font(56, bold=True)
    chars = ["你", "今", "天", "真", "棒"]
    # 竖排或横排都可以；这里用活泼的错落排列
    start_y = frame_cy - frame_h / 2 + 80
    positions = [
        (frame_cx - 80, start_y),
        (frame_cx + 40, start_y + 70),
        (frame_cx - 20, start_y + 140),
        (frame_cx - 90, start_y + 210),
        (frame_cx + 50, start_y + 280),
    ]
    for i, ch in enumerate(chars):
        x, y = positions[i]
        # 轻微旋转营造手写感
        ch_img = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
        cd = ImageDraw.Draw(ch_img)
        cd.text((60, 60), ch, font=phrase_font, fill=INK_DARK, anchor="mm")
        angle = (-6, 4, -3, 5, -2)[i]
        ch_img = ch_img.rotate(angle, resample=Image.Resampling.BICUBIC)
        layer.alpha_composite(ch_img, (int(x - 60), int(y - 60)))

    # 小装饰：相框内底部画两片小叶子
    draw.ellipse((frame_cx - 100, frame_cy + 180, frame_cx - 30, frame_cy + 220), fill=LEAF_LIGHT)
    draw.ellipse((frame_cx + 50, frame_cy + 170, frame_cx + 120, frame_cy + 210), fill=LEAF_PALE)

    # 3. 相框下方绿植（大盆植物）
    plant_cx = frame_cx - 40
    plant_base_y = frame_cy + frame_h / 2 + 140
    # 花盆
    pot_w, pot_h = 120, 90
    draw.polygon(
        [(plant_cx - pot_w / 2, plant_base_y),
         (plant_cx + pot_w / 2, plant_base_y),
         (plant_cx + pot_w / 2 - 16, plant_base_y - pot_h),
         (plant_cx - pot_w / 2 + 16, plant_base_y - pot_h)],
        fill=POT_DARK,
    )
    draw.ellipse(
        (plant_cx - pot_w / 2 - 4, plant_base_y - pot_h - 10,
         plant_cx + pot_w / 2 + 4, plant_base_y - pot_h + 10),
        fill=POT,
    )
    # 土
    draw.ellipse(
        (plant_cx - pot_w / 2 + 6, plant_base_y - pot_h - 8,
         plant_cx + pot_w / 2 - 6, plant_base_y - pot_h + 4),
        fill=(80, 58, 40),
    )
    # 叶簇
    leaves = [
        (0, -40, 34, 80, LEAF_DARK),
        (-28, -20, 28, 68, LEAF_MAIN),
        (28, -24, 30, 72, LEAF_MAIN),
        (-12, -70, 22, 56, LEAF_LIGHT),
        (16, -64, 24, 58, LEAF_LIGHT),
        (-44, -10, 18, 42, LEAF_PALE),
        (44, -16, 20, 46, LEAF_PALE),
    ]
    for dx, dy, rx, ry, color in leaves:
        cx = plant_cx + dx
        cy = plant_base_y - pot_h + dy
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=color)
    # 叶脉
    draw.line(
        [(plant_cx, plant_base_y - pot_h - 90), (plant_cx, plant_base_y - pot_h - 10)],
        fill=LEAF_DARK, width=2,
    )

    # 4. 礼物盒/日卡（相框右下方）
    gift_cx = frame_cx + 220
    gift_cy = plant_base_y - 20
    gift_w, gift_h = 120, 90
    # 盒子
    draw.rounded_rectangle(
        (gift_cx - gift_w / 2, gift_cy - gift_h / 2,
         gift_cx + gift_w / 2, gift_cy + gift_h / 2),
        radius=10, fill=INK_MAIN,
    )
    # 丝带十字
    rib = 14
    draw.rectangle(
        (gift_cx - rib, gift_cy - gift_h / 2, gift_cx + rib, gift_cy + gift_h / 2),
        fill=GOLD,
    )
    draw.rectangle(
        (gift_cx - gift_w / 2, gift_cy - rib / 2, gift_cx + gift_w / 2, gift_cy + rib / 2),
        fill=GOLD,
    )
    # 蝴蝶结
    draw.ellipse(
        (gift_cx - gift_w / 2 - 14, gift_cy - gift_h / 2 - 18,
         gift_cx - gift_w / 2 + 14, gift_cy - gift_h / 2 + 4),
        fill=GOLD,
    )
    draw.ellipse(
        (gift_cx + gift_w / 2 - 14, gift_cy - gift_h / 2 - 18,
         gift_cx + gift_w / 2 + 14, gift_cy - gift_h / 2 + 4),
        fill=GOLD,
    )
    # "日卡" 字
    day_font = select_font(24, bold=True)
    draw.text((gift_cx - 22, gift_cy - 14), "日卡", font=day_font, fill=WHITE)

    # 5. 散落叶片装饰
    decors = [
        (820, 200, 70, 35, -25, LEAF_LIGHT),
        (1340, 280, 80, 38, 20, LEAF_MAIN),
        (780, 780, 55, 28, -40, LEAF_PALE),
        (1380, 920, 65, 32, 30, LEAF_LIGHT),
        (940, 1120, 50, 24, -15, LEAF_PALE),
    ]
    for cx, cy, length, width, angle, color in decors:
        leaf_img, pos = draw_leaf(None, cx, cy, length, width, angle, color)
        layer.alpha_composite(leaf_img, pos)

    # 6. 光斑
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((1300, 120, 1480, 300), fill=(252, 244, 200, 100))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=40))
    layer.alpha_composite(glow)


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

    # 票券右侧装饰叶
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
