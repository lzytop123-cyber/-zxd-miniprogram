"""Compose review-reward carousel V3 — warm photo + organic wave style.

参照暑期双月卡的视觉语言：
- 左侧暖白底承载文案，右侧放实景自习室照片
- 有机波浪形分隔（非矩形面板）
- 绿色药丸标签 + 大标题 + 叶形分隔符副标题 + 虚线 + 三项图标 + 底部票券
- 右上角和左下角叶片点缀
- 120px 安全边距，适配小程序轮播裁切
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


WIDTH, HEIGHT = 1500, 1360
MAX_BYTES = 1_950_000
SAFE_MARGIN = 120  # 安全边距，防止轮播裁切

ROOT = Path(__file__).resolve().parents[1]
# 使用 calm-space 作为右侧实景照片（最安静温暖的那张）
SOURCE = ROOT / "assets" / "marketing" / "home-carousel" / "sources" / "source-02-calm-space.png"
DESTINATION = (
    ROOT / "assets" / "marketing" / "home-carousel"
    / "home-carousel-05-review-reward-v3-1500x1360.jpg"
)

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_FALLBACK = Path(r"C:\Windows\Fonts\simhei.ttf")

# ---------- 色板（参照参考图暖绿调） ----------
BG_WARM = (250, 247, 238)          # 左侧暖白底
BG_WARM_DEEP = (235, 243, 232)    # 底部淡绿晕染
INK_DARK = (38, 88, 62)           # 深绿主文字
INK_MAIN = (72, 165, 120)         # 主绿
INK_DEEP = (45, 106, 79)
INK_LIGHT = (210, 238, 220)       # 浅绿标签底
INK_MID = (100, 148, 120)
INK_MUTED = (128, 142, 132)
INK_DOTTED = (190, 210, 198)      # 虚线颜色
GOLD = (212, 176, 96)
WHITE = (255, 255, 255)
LEAF_GREEN = (58, 130, 86)
LEAF_DARK = (36, 90, 58)
LEAF_LIGHT = (120, 180, 140)
LEAF_VEIN = (42, 100, 68)
TICKET_BG = (246, 250, 244)
TICKET_BORDER = (200, 224, 208)
SHADOW = (40, 80, 55)


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


# ---------- 波浪分隔曲线 ----------
def build_wave_mask(size, wave_cx, wave_amplitude=180):
    """生成右侧照片区的蒙版：左侧是有机波浪形镂空。

    wave_cx: 波浪中线 X 坐标（左侧文字区与右侧照片区分界点）
    返回 L 模式蒙版（白色=保留照片，黑色=遮罩）
    """
    w, h = size
    mask = Image.new("L", (w, h), 0)
    md = ImageDraw.Draw(mask)

    # 用贝塞尔风格的多点曲线模拟 S 形波浪
    # 关键点：从上到下定义控制点
    points = []
    # 顶部从 wave_cx 开始，向外凸
    points.append((wave_cx + 60, 0))
    # 第一波（上方向右凸）
    for y in range(0, h + 1, 4):
        t = y / h
        # 组合两条正弦波，形成有机 S 形
        offset = (
            wave_amplitude * math.sin(t * math.pi * 1.2 - 0.3)
            + wave_amplitude * 0.4 * math.sin(t * math.pi * 2.5 + 0.8)
            + wave_amplitude * 0.15 * math.sin(t * math.pi * 4.2)
        )
        # 从上到下整体略往右移，营造弧形包裹感
        drift = 40 * t
        points.append((wave_cx + offset + drift, y))

    points.append((w, h))
    points.append((w, 0))

    md.polygon(points, fill=255)
    # 对蒙版边缘做轻微模糊，让波浪过渡更柔和
    mask = mask.filter(ImageFilter.GaussianBlur(radius=1.5))
    return mask


# ---------- 叶片绘制 ----------
def draw_single_leaf(draw, cx, cy, length, width, angle, color, vein_color=None):
    """画一片带叶尖和叶脉的叶子。angle 单位度，0=水平向右。"""
    if vein_color is None:
        vein_color = LEAF_VEIN

    # 先画一个椭圆叶身（在本地坐标系），然后旋转
    leaf_w = int(length)
    leaf_h = int(width)
    pad = max(leaf_w, leaf_h) + 20
    leaf_img = Image.new("RGBA", (pad * 2, pad * 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(leaf_img)

    # 叶身（椭圆）
    ld.ellipse(
        (pad - leaf_w, pad - leaf_h // 2, pad + leaf_w, pad + leaf_h // 2),
        fill=color,
    )
    # 叶尖（小三角）
    tip_len = leaf_w // 3
    ld.polygon(
        [(pad + leaf_w, pad - leaf_h // 4),
         (pad + leaf_w + tip_len, pad),
         (pad + leaf_w, pad + leaf_h // 4)],
        fill=color,
    )
    # 叶脉中轴
    ld.line(
        [(pad - leaf_w + 4, pad), (pad + leaf_w + tip_len - 2, pad)],
        fill=vein_color, width=max(1, leaf_h // 12),
    )
    # 侧脉
    n_veins = 3
    for i in range(n_veins):
        t = (i + 1) / (n_veins + 1)
        vx = pad - leaf_w + 4 + t * (leaf_w * 2 + tip_len - 6)
        offset = leaf_h // 3
        ld.line([(vx, pad), (vx + leaf_w // 4, pad - offset)], fill=vein_color, width=1)
        ld.line([(vx, pad), (vx + leaf_w // 4, pad + offset)], fill=vein_color, width=1)

    # 旋转并贴回
    rotated = leaf_img.rotate(angle, resample=Image.Resampling.BICUBIC, center=(pad, pad))
    return rotated, (int(cx - pad), int(cy - pad))


def draw_leaf_branch(layer, anchor_x, anchor_y, direction="top-right"):
    """在指定角落画一枝伸入画面的叶子。"""
    if direction == "top-right":
        leaves = [
            # (相对anchor偏移, 长度, 宽度, 角度, 颜色)
            ((0, 0), 120, 50, -20, LEAF_DARK),
            ((-60, 40), 100, 42, -35, LEAF_GREEN),
            ((60, 30), 110, 48, -5, LEAF_GREEN),
            ((-30, 90), 90, 38, -50, LEAF_LIGHT),
            ((100, 80), 95, 40, 10, LEAF_DARK),
            ((-90, -20), 80, 34, -40, LEAF_LIGHT),
            ((40, -30), 85, 36, -15, LEAF_GREEN),
            ((130, 20), 70, 30, 15, LEAF_LIGHT),
        ]
        # 枝条
        branch = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(branch)
        bd.arc(
            (anchor_x - 200, anchor_y - 200, anchor_x + 200, anchor_y + 300),
            start=200, end=300, fill=LEAF_DARK, width=6,
        )
        layer.alpha_composite(branch)
    elif direction == "bottom-left":
        leaves = [
            ((0, 0), 90, 38, 150, LEAF_GREEN),
            ((50, -40), 80, 34, 130, LEAF_LIGHT),
            ((-30, -50), 85, 36, 170, LEAF_DARK),
            ((80, 10), 70, 30, 120, LEAF_GREEN),
            ((-60, -80), 60, 26, 190, LEAF_LIGHT),
        ]
    else:
        leaves = []

    for (dx, dy), length, width, angle, color in leaves:
        leaf_img, pos = draw_single_leaf(
            None, anchor_x + dx, anchor_y + dy, length, width, angle, color
        )
        layer.alpha_composite(leaf_img, pos)


# ---------- 叶片小图标（用于分隔符和标签） ----------
def leaf_icon(size=24, color=INK_MAIN):
    """生成一个小叶片 RGBA 图像，用于标签和分隔。"""
    img = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size
    d.ellipse((s - s * 0.8, s - s * 0.35, s + s * 0.8, s + s * 0.35), fill=color)
    d.polygon(
        [(s + s * 0.8, s - s * 0.2),
         (s + s * 1.1, s),
         (s + s * 0.8, s + s * 0.2)],
        fill=color,
    )
    d.line([(s - s * 0.6, s), (s + s * 0.9, s)], fill=(255, 255, 255, 180), width=max(1, s // 10))
    return img


def paste_leaf_icon(layer, x, y, size=24, color=INK_MAIN):
    icon = leaf_icon(size, color)
    layer.alpha_composite(icon, (int(x - size), int(y - size)))


# ---------- 圆形图标 ----------
def draw_circle_icon(layer, cx, cy, r, kind):
    """画圆形小图标（用于特性区）。kind: pen / camera / gift"""
    draw = ImageDraw.Draw(layer)
    # 圆背景
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=INK_LIGHT)
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=INK_MAIN, width=2)
    lw = max(2, r // 8)
    if kind == "pen":
        # 笔（简化为斜线+小圆头）
        draw.line(
            [(cx - r * 0.4, cy + r * 0.4), (cx + r * 0.5, cy - r * 0.5)],
            fill=INK_DEEP, width=lw + 1,
        )
        draw.ellipse(
            (cx + r * 0.4, cy - r * 0.6, cx + r * 0.65, cy - r * 0.35),
            fill=GOLD,
        )
    elif kind == "camera":
        # 相机（矩形+圆镜头+小闪光灯）
        bw, bh = r * 1.1, r * 0.75
        draw.rounded_rectangle(
            (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2),
            radius=4, fill=INK_DEEP,
        )
        draw.ellipse(
            (cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3),
            fill=WHITE,
        )
        draw.ellipse(
            (cx - r * 0.15, cy - r * 0.15, cx + r * 0.15, cy + r * 0.15),
            fill=INK_MAIN,
        )
        draw.ellipse(
            (cx + bw / 2 - r * 0.2, cy - bh / 2 - r * 0.05,
             cx + bw / 2 + r * 0.05, cy - bh / 2 + r * 0.2),
            fill=GOLD,
        )
    elif kind == "gift":
        # 礼盒（矩形+丝带十字+蝴蝶结）
        bw, bh = r * 1.2, r * 0.8
        draw.rounded_rectangle(
            (cx - bw / 2, cy - bh / 2 + r * 0.1, cx + bw / 2, cy + bh / 2 + r * 0.1),
            radius=4, fill=INK_MAIN,
        )
        # 丝带竖线
        draw.rectangle(
            (cx - lw, cy - bh / 2 + r * 0.1, cx + lw, cy + bh / 2 + r * 0.1),
            fill=GOLD,
        )
        # 丝带横线
        draw.rectangle(
            (cx - bw / 2, cy - lw + r * 0.1, cx + bw / 2, cy + lw + r * 0.1),
            fill=GOLD,
        )
        # 蝴蝶结（两个小三角/圆）
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


# ---------- 票券形状 ----------
def draw_ticket(layer, x1, y1, x2, y2, notch_r=16, radius=20):
    """画一张左右带半圆缺口的票券，返回 mask 用于裁切内部。"""
    w = x2 - x1
    h = y2 - y1
    ticket = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ticket)
    # 主体圆角矩形
    d.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=TICKET_BG)
    # 左右半圆缺口（挖空）
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
    # 虚线分隔
    dash_len = 10
    gap = 8
    cy = (y1 + y2) // 2
    x = x1 + notch_r + 12
    while x < x2 - notch_r - 12:
        d.line([(x, cy), (x + dash_len, cy)], fill=TICKET_BORDER, width=2)
        x += dash_len + gap
    # 边框
    d.rounded_rectangle((x1, y1, x2, y2), radius=radius, outline=TICKET_BORDER, width=2)
    # 再补缺口处的边
    d.arc(
        (x1 - notch_r, cy - notch_r, x1 + notch_r, cy + notch_r),
        start=90, end=270, fill=TICKET_BORDER, width=2,
    )
    d.arc(
        (x2 - notch_r, cy - notch_r, x2 + notch_r, cy + notch_r),
        start=270, end=90, fill=TICKET_BORDER, width=2,
    )
    layer.alpha_composite(ticket)


# ---------- 主合成 ----------
def compose():
    # 1. 暖白底
    bg = Image.new("RGB", (WIDTH, HEIGHT), BG_WARM)
    # 底部淡绿晕染
    bg_grad = vertical_gradient((WIDTH, HEIGHT), BG_WARM, BG_WARM_DEEP)
    bg = Image.blend(bg, bg_grad, 0.5)
    canvas = bg.convert("RGBA")

    # 2. 右侧实景照片（用波浪蒙版裁切）
    wave_cx = 720  # 波浪分界中线
    if SOURCE.exists():
        with Image.open(SOURCE) as src:
            photo = ImageOps.exif_transpose(src).convert("RGB")
            photo = cover_crop(photo, (WIDTH, HEIGHT))
            photo = ImageEnhance.Color(photo).enhance(1.05)
            photo = ImageEnhance.Brightness(photo).enhance(1.05)
            photo = ImageEnhance.Contrast(photo).enhance(1.02)
            photo_rgba = photo.convert("RGBA")
            # 对照片加一层暖绿调（降低冷感）
            tint = Image.new("RGBA", (WIDTH, HEIGHT), (120, 180, 140, 25))
            photo_rgba = Image.alpha_composite(photo_rgba, tint)
        mask = build_wave_mask((WIDTH, HEIGHT), wave_cx, wave_amplitude=160)
        canvas.paste(photo_rgba, (0, 0), mask)
    else:
        # 无图时画一个占位淡绿块
        placeholder = Image.new("RGBA", (WIDTH, HEIGHT), INK_LIGHT + (255,))
        mask = build_wave_mask((WIDTH, HEIGHT), wave_cx, wave_amplitude=160)
        canvas.paste(placeholder, (0, 0), mask)

    # 3. 叶片装饰（右上角 + 左下角）
    leaves_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_leaf_branch(leaves_layer, WIDTH + 20, -40, direction="top-right")
    draw_leaf_branch(leaves_layer, -40, HEIGHT + 60, direction="bottom-left")
    canvas = Image.alpha_composite(canvas, leaves_layer)

    # 4. 叶影（柔和的半透明叶影投在背景上）
    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_layer)
    # 左上大叶影
    for cx, cy, r, a in [
        (80, 60, 180, 20),
        (200, 120, 120, 15),
        (WIDTH - 200, HEIGHT - 100, 200, 18),
    ]:
        sd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(45, 106, 79, a))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=30))
    canvas = Image.alpha_composite(canvas, shadow_layer)

    # 5. 文案层
    text_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    # 安全区内的左边界
    left = SAFE_MARGIN
    content_right = wave_cx - 40  # 文字区右边界（不碰到波浪）
    content_width = content_right - left

    # ---- 5.1 顶部标签：好评有礼（绿底白字药丸，左带小叶子）----
    tag_font = select_font(28, bold=True)
    tag_text = "好评有礼"
    tag_w, tag_h, _, _ = text_metrics(draw, tag_text, tag_font)
    tag_pill_w = tag_w + 80  # 留叶片位置
    tag_pill_h = 60
    tag_top = 120
    tag_left = left
    # 药丸底
    draw.rounded_rectangle(
        (tag_left, tag_top, tag_left + tag_pill_w, tag_top + tag_pill_h),
        radius=tag_pill_h // 2, fill=INK_MAIN,
    )
    # 左侧小叶子图标（白色，药丸内）
    leaf_icon_img = leaf_icon(14, WHITE)
    text_layer.alpha_composite(leaf_icon_img, (int(tag_left + 22), int(tag_top + tag_pill_h / 2)))
    # 标签文字
    draw_centered(
        draw,
        (tag_left + tag_pill_w / 2 + 10, tag_top + tag_pill_h / 2),
        tag_text, tag_font, WHITE,
    )

    # ---- 5.2 大标题 ----
    headline_font = select_font(118, bold=True)
    line1 = "写好评"
    line2 = "送日卡"
    l1_w, l1_h, _, _ = text_metrics(draw, line1, headline_font)
    l2_w, l2_h, _, _ = text_metrics(draw, line2, headline_font)
    hl_top = tag_top + tag_pill_h + 50
    draw.text((left, hl_top), line1, font=headline_font, fill=INK_DARK)
    l2_top = hl_top + l1_h + 8
    draw.text((left, l2_top), line2, font=headline_font, fill=INK_DARK)

    # ---- 5.3 叶形分隔符副标题 ----
    sub_font = select_font(34)
    sub_text = "15字好评 · 三张真实照片"
    sub_top = l2_top + l2_h + 50
    # 左右小叶子 + 文字
    sub_w, sub_h, _, _ = text_metrics(draw, sub_text, sub_font)
    leaf_gap = 24
    leaf_sz = 16
    total_w = leaf_sz * 2 + leaf_gap * 2 + sub_w
    sub_x = left
    paste_leaf_icon(text_layer, sub_x + leaf_sz, sub_top + sub_h / 2, size=leaf_sz, color=INK_MAIN)
    draw.text(
        (sub_x + leaf_sz + leaf_gap, sub_top),
        sub_text, font=sub_font, fill=INK_MID,
    )
    paste_leaf_icon(
        text_layer,
        sub_x + leaf_sz + leaf_gap + sub_w + leaf_gap + leaf_sz,
        sub_top + sub_h / 2,
        size=leaf_sz, color=INK_MAIN,
    )

    # ---- 5.4 虚线分隔 ----
    dash_top = sub_top + sub_h + 40
    dash_len = 12
    gap = 10
    x = left
    while x < left + content_width - 20:
        draw.line([(x, dash_top), (x + dash_len, dash_top)], fill=INK_DOTTED, width=2)
        x += dash_len + gap

    # ---- 5.5 三个圆形图标+文字：美团 / 大众点评 / 抖音 ----
    feat_top = dash_top + 50
    feat_font = select_font(26)
    icon_r = 38
    gap_between = content_width / 3
    feats = [
        ("美团", "pen"),
        ("大众点评", "camera"),
        ("抖音", "gift"),
    ]
    for i, (label, icon_kind) in enumerate(feats):
        cx = left + gap_between * i + gap_between / 2
        cy = feat_top + icon_r
        draw_circle_icon(text_layer, int(cx), int(cy), icon_r, icon_kind)
        # 文字
        draw_centered(
            draw, (cx, cy + icon_r + 28), label, feat_font, INK_MUTED,
        )

    # ---- 5.6 底部票券 ----
    ticket_top = feat_top + icon_r * 2 + 70
    ticket_h = 160
    ticket_w = content_width - 20
    ticket_x1 = left
    ticket_x2 = left + ticket_w
    ticket_y1 = ticket_top
    ticket_y2 = ticket_top + ticket_h
    draw_ticket(text_layer, ticket_x1, ticket_y1, ticket_x2, ticket_y2, notch_r=14, radius=16)

    # 票券内容
    # 左侧大数字/文字
    big_font = select_font(62, bold=True)
    med_font = select_font(28)
    small_font = select_font(22)

    # "日卡" 大字
    big_text = "日卡"
    draw.text(
        (ticket_x1 + 40, ticket_y1 + 22),
        big_text, font=big_font, fill=INK_DARK,
    )
    # "×1张"
    sub_t = "×1张"
    draw.text(
        (ticket_x1 + 40 + text_metrics(draw, big_text, big_font)[0] + 6, ticket_y1 + 52),
        sub_t, font=med_font, fill=INK_MAIN,
    )
    # 说明小字
    note_lines = ["截图发给管理员", "即可免费兑换"]
    for i, line in enumerate(note_lines):
        draw.text(
            (ticket_x1 + 40, ticket_y1 + 94 + i * 30),
            line, font=small_font, fill=INK_MUTED,
        )

    # 票券右侧：装饰叶子
    leaf_deco = leaf_icon(28, INK_MAIN)
    text_layer.alpha_composite(
        leaf_deco,
        (int(ticket_x2 - 80), int(ticket_y1 + 30)),
    )

    # ---- 5.7 右上角品牌字（放在照片区域上方，避开波浪） ----
    wm_font = select_font(26, bold=True)
    wm_text = "知行岛自习室"
    wm_w, _, _, _ = text_metrics(draw, wm_text, wm_font)
    wm_right = WIDTH - SAFE_MARGIN
    wm_top = SAFE_MARGIN + 10
    # 半透明白底标签让字在照片上可读
    wm_pad_x, wm_pad_y = 18, 10
    draw.rounded_rectangle(
        (wm_right - wm_w - wm_pad_x * 2, wm_top,
         wm_right, wm_top + 26 + wm_pad_y * 2),
        radius=18, fill=(255, 255, 255, 200),
    )
    draw.text(
        (wm_right - wm_w - wm_pad_x, wm_top + wm_pad_y - 2),
        wm_text, font=wm_font, fill=INK_DARK,
    )

    canvas = Image.alpha_composite(canvas, text_layer)
    return canvas.convert("RGB")


def cover_crop(image, size):
    normalized = ImageOps.exif_transpose(image).convert("RGB")
    scale = max(size[0] / normalized.width, size[1] / normalized.height)
    resized = normalized.resize(
        (round(normalized.width * scale), round(normalized.height * scale)),
        Image.Resampling.LANCZOS,
    )
    left = (resized.width - size[0]) // 2
    top = (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


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


def encode_jpeg(image):
    for quality in (92, 88, 84, 80, 76):
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=quality, optimize=True, progressive=True, subsampling="4:2:0")
        payload = buf.getvalue()
        if 0 < len(payload) < MAX_BYTES:
            return payload, quality
    raise RuntimeError(f"JPEG too large ({MAX_BYTES})")


def main():
    final = compose()
    payload, _q = encode_jpeg(final)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(payload)

    with Image.open(DESTINATION) as rendered:
        rendered.load()
        if rendered.size != (WIDTH, HEIGHT):
            raise RuntimeError(f"Unexpected size: {rendered.size}")
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
