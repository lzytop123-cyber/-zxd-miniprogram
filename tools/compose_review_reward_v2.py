"""Compose review-reward carousel V2 — polished fresh illustration style.

改进点：
- 左上柔光窗景代替大太阳；漂浮装饰改为少量几何圆点+弧线
- 文案面板：细色条+礼品卡小图标；平台名改为药丸标签；更均衡的留白
- 桌面：台灯带底座、书有立体感、咖啡杯更精致、加绿植/小物件、所有物品带投影
- 地面地毯条，整体更有"空间感"
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
ROOT = Path(__file__).resolve().parents[1]
DESTINATION = (
    ROOT
    / "assets"
    / "marketing"
    / "home-carousel"
    / "home-carousel-05-review-reward-v2-1500x1360.jpg"
)

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
FONT_FALLBACK = Path(r"C:\Windows\Fonts\simhei.ttf")

# ---------- 色板 ----------
BG_TOP = (248, 250, 244)
BG_BOTTOM = (230, 244, 233)

INK_DARK = (35, 82, 60)         # 深绿主文字
INK_MAIN = (82, 183, 136)       # 主绿
INK_DEEP = (45, 106, 79)
INK_LIGHT = (216, 243, 220)
INK_MID = (103, 155, 126)
INK_MUTED = (120, 138, 126)
INK_SOFT = (180, 200, 186)

WOOD = (222, 198, 164)
WOOD_DARK = (190, 162, 122)
WOOD_EDGE = (170, 140, 100)
COFFEE = (142, 106, 78)
COFFEE_MILK = (210, 190, 168)
CREAM = (252, 248, 240)

LEAF_DEEP = (45, 106, 79)
LEAF_MAIN = (82, 183, 136)
LEAF_SOFT = (148, 210, 178)
LEAF_PALE = (196, 230, 210)
POT = (232, 180, 140)
POT_DARK = (204, 150, 108)

SKY_TOP = (220, 238, 248)
SKY_BOTTOM = (245, 250, 252)
WINDOW_FRAME = (232, 226, 216)

WARM = (252, 236, 178)
WARM_GLOW = (255, 244, 208)
GOLD = (232, 196, 112)

CARD_ACCENT = (82, 183, 136)
CARD_TEXT = (45, 106, 79)

TAG = "好评有礼"
HEADLINE_LINE1 = "写好评"
HEADLINE_LINE2 = "送日卡"
PLATFORMS = ["美团", "大众点评", "抖音"]
PLATFORM_SEP = "·"
NOTE = "截图发给管理员，即可兑换日卡一张"
WORDMARK = "知行岛自习室"


# ---------- 字体 ----------
def select_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    preferred = FONT_BOLD if bold else FONT_REGULAR
    path = preferred if preferred.exists() else FONT_FALLBACK
    if not path.exists():
        raise FileNotFoundError("No required Chinese font is available")
    return ImageFont.truetype(str(path), size)


def text_metrics(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    w = box[2] - box[0]
    h = box[3] - box[1]
    ox, oy = box[0], box[1]
    return w, h, ox, oy


def draw_centered_text(draw, xy, text, font, fill):
    x, y = xy
    w, h, ox, oy = text_metrics(draw, text, font)
    draw.text((x - w / 2 - ox, y - h / 2 - oy), text, font=font, fill=fill)


# ---------- 背景渐变 ----------
def vertical_gradient(size, top, bottom, ease=True):
    w, h = size
    strip = Image.new("RGB", (1, h))
    px = strip.load()
    for y in range(h):
        t = y / max(h - 1, 1)
        if ease:
            t = t * t * (3.0 - 2.0 * t)
        r = round(top[0] * (1 - t) + bottom[0] * t)
        g = round(top[1] * (1 - t) + bottom[1] * t)
        b = round(top[2] * (1 - t) + bottom[2] * t)
        px[0, y] = (r, g, b)
    return strip.resize((w, h), Image.Resampling.BILINEAR)


# ---------- 圆角矩形（抗锯齿友好） ----------
def rounded_rect(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


# ---------- 主绘制 ----------
def draw_background_decor(layer):
    """背景装饰：窗景+柔光+少量几何装饰。"""
    draw = ImageDraw.Draw(layer)

    # 1. 右上窗景
    win_left, win_top = 980, 140
    win_right, win_bottom = 1420, 540
    win_r = 28
    # 窗框底色
    rounded_rect(draw, (win_left - 14, win_top - 14, win_right + 14, win_bottom + 14),
                 win_r + 8, fill=(240, 236, 228))
    # 窗玻璃（天渐变）
    win_glass = vertical_gradient(
        (win_right - win_left, win_bottom - win_top), SKY_TOP, SKY_BOTTOM, ease=True
    )
    win_glass_rgba = win_glass.convert("RGBA")
    # 用圆角蒙版裁切玻璃
    mask = Image.new("L", (win_right - win_left, win_bottom - win_top), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, win_right - win_left, win_bottom - win_top),
                         radius=win_r, fill=255)
    layer.paste(win_glass_rgba, (win_left, win_top), mask)

    # 窗框十字分格
    draw.line(
        [(win_left - 14, (win_top + win_bottom) // 2),
         (win_right + 14, (win_top + win_bottom) // 2)],
        fill=(240, 236, 228), width=8,
    )
    draw.line(
        [((win_left + win_right) // 2, win_top - 14),
         ((win_left + win_right) // 2, win_bottom + 14)],
        fill=(240, 236, 228), width=8,
    )

    # 窗外小太阳（小而柔）
    sun_cx, sun_cy = 1300, 260
    for r, a in [(90, 40), (70, 70), (50, 110)]:
        glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((sun_cx - r, sun_cy - r, sun_cx + r, sun_cy + r),
                   fill=WARM + (a,))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=18 if r > 70 else 8))
        layer.alpha_composite(glow)

    # 窗外云（两朵）
    for cx, cy, scale in [(1120, 340, 1.0), (1250, 420, 0.7)]:
        for dx, dy, r in [(-30, 0, 26), (0, -8, 32), (30, 0, 26), (0, 10, 22)]:
            draw.ellipse(
                (cx + dx * scale - r * scale, cy + dy * scale - r * scale,
                 cx + dx * scale + r * scale, cy + dy * scale + r * scale),
                fill=(255, 255, 255, 200),
            )

    draw = ImageDraw.Draw(layer)

    # 2. 柔和大色块（营造氛围，左下、右下淡色圆）
    soft_blobs = [
        (220, 1180, 360, LEAF_PALE + (70,)),
        (1320, 1200, 420, INK_LIGHT + (60,)),
        (640, 140, 180, WARM_GLOW + (60,)),
    ]
    for cx, cy, r, color in soft_blobs:
        blob = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(blob)
        bd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)
        blob = blob.filter(ImageFilter.GaussianBlur(radius=50))
        layer.alpha_composite(blob)

    draw = ImageDraw.Draw(layer)

    # 3. 少量装饰圆点+弧线（替代之前的散落叶）
    dots = [
        (820, 200, 6, GOLD),
        (720, 320, 4, LEAF_MAIN),
        (920, 680, 5, LEAF_SOFT),
        (1440, 700, 7, GOLD),
        (860, 860, 4, LEAF_MAIN),
    ]
    for cx, cy, r, color in dots:
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color)

    # 4. 细弧线装饰
    for box, start, end, color, w in [
        ((760, 560, 880, 680), 200, 340, LEAF_SOFT, 3),
        ((1380, 560, 1480, 660), 20, 160, LEAF_SOFT, 3),
    ]:
        draw.arc(box, start=start, end=end, fill=color, width=w)


def draw_desk_scene(layer):
    """更有生活感的桌面场景。"""
    draw = ImageDraw.Draw(layer)

    # ---- 地面/地毯 ----
    floor_top = 1170
    carpet = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(carpet)
    cd.rounded_rectangle(
        (660, floor_top, 1470, floor_top + 60),
        radius=30, fill=LEAF_PALE + (180,),
    )
    carpet = carpet.filter(ImageFilter.GaussianBlur(radius=2))
    layer.alpha_composite(carpet)
    draw = ImageDraw.Draw(layer)

    # ---- 桌面 ----
    desk_left, desk_right = 720, 1460
    desk_top = 920
    desk_thick = 22
    # 桌面投影（在桌面上方向下的软阴影）
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
    rounded_rect(draw, (desk_left, desk_top, desk_right, desk_top + desk_thick),
                 radius=10, fill=WOOD)
    # 桌面木纹高光
    draw.rectangle(
        (desk_left + 12, desk_top + 3, desk_right - 12, desk_top + 6),
        fill=(236, 216, 186),
    )
    # 桌沿深色
    rounded_rect(draw,
                 (desk_left, desk_top + desk_thick - 4, desk_right, desk_top + desk_thick + 8),
                 radius=6, fill=WOOD_DARK)

    # 桌腿
    for leg_x in [desk_left + 50, desk_right - 50]:
        draw.polygon(
            [(leg_x - 10, desk_top + desk_thick + 8),
             (leg_x + 10, desk_top + desk_thick + 8),
             (leg_x + 6, floor_top),
             (leg_x - 6, floor_top)],
            fill=WOOD_DARK,
        )

    # ---- 台灯（左） ----
    lamp_base_cx = desk_left + 140
    lamp_base_y = desk_top
    # 底座（椭圆）
    draw.ellipse(
        (lamp_base_cx - 36, lamp_base_y - 8, lamp_base_cx + 36, lamp_base_y + 10),
        fill=INK_DEEP,
    )
    draw.ellipse(
        (lamp_base_cx - 30, lamp_base_y - 14, lamp_base_cx + 30, lamp_base_y + 2),
        fill=INK_DARK,
    )
    # 灯柱（稍弯，这里用竖线+小弧简化）
    pole_top = lamp_base_y - 200
    draw.line(
        [(lamp_base_cx, lamp_base_y - 6), (lamp_base_cx + 8, pole_top + 30)],
        fill=WOOD_DARK, width=7,
    )
    draw.line(
        [(lamp_base_cx + 8, pole_top + 30), (lamp_base_cx + 4, pole_top + 60)],
        fill=WOOD_DARK, width=7,
    )
    # 灯罩（梯形，深绿+浅绿底沿）
    shade_top_y = pole_top
    draw.polygon(
        [(lamp_base_cx - 60, shade_top_y + 80),
         (lamp_base_cx + 68, shade_top_y + 80),
         (lamp_base_cx + 36, shade_top_y),
         (lamp_base_cx - 28, shade_top_y)],
        fill=INK_DEEP,
    )
    # 灯罩底沿（主绿）
    draw.ellipse(
        (lamp_base_cx - 62, shade_top_y + 76, lamp_base_cx + 70, shade_top_y + 88),
        fill=INK_MAIN,
    )
    draw.ellipse(
        (lamp_base_cx - 58, shade_top_y + 74, lamp_base_cx + 66, shade_top_y + 82),
        fill=(255, 248, 220),
    )
    # 灯光投影（桌面暖光椭圆）
    glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse(
        (lamp_base_cx - 100, desk_top - 2, lamp_base_cx + 100, desk_top + 14),
        fill=WARM_GLOW + (150,),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=8))
    layer.alpha_composite(glow)
    draw = ImageDraw.Draw(layer)

    # ---- 翻开的书（中左） ----
    book_cx = desk_left + 400
    book_top = desk_top - 46
    bw, bh = 110, 50
    # 书底阴影
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(
        (book_cx - bw - 8, book_top + bh + 2, book_cx + bw + 8, book_top + bh + 16),
        fill=(45, 106, 79, 40),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=5))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)

    # 左页（稍倾斜：用梯形）
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
    # 左页白
    draw.polygon(
        [(book_cx - bw, book_top + bh),
         (book_cx - bw - 6, book_top + 8),
         (book_cx - 6, book_top),
         (book_cx, book_top + bh)],
        fill=CREAM,
    )
    # 右页白
    draw.polygon(
        [(book_cx + bw, book_top + bh),
         (book_cx + bw + 6, book_top + 8),
         (book_cx + 6, book_top),
         (book_cx, book_top + bh)],
        fill=(255, 255, 252),
    )
    # 书脊中缝阴影
    draw.line(
        [(book_cx, book_top + 2), (book_cx, book_top + bh - 2)],
        fill=(220, 215, 200), width=2,
    )
    # 文字线
    for page_left in [book_cx - bw + 14, book_cx + 14]:
        for i, yoff in enumerate([14, 24, 34]):
            lw = 70 if i != 2 else 48
            draw.line(
                [(page_left, book_top + yoff), (page_left + lw, book_top + yoff)],
                fill=INK_SOFT, width=2,
            )

    # ---- 小笔记本+笔（书旁边，在书右侧靠后） ----
    nb_cx = book_cx + 160
    nb_top = book_top + 12
    nb_w, nb_h = 50, 36
    # 笔记本
    rounded_rect(draw,
                 (nb_cx - nb_w, nb_top, nb_cx + nb_w, nb_top + nb_h * 2),
                 radius=4, fill=(255, 248, 232))
    # 绑带
    draw.rectangle(
        (nb_cx - nb_w, nb_top + nb_h - 2, nb_cx + nb_w, nb_top + nb_h + 2),
        fill=INK_MAIN,
    )
    # 笔
    pen_x = nb_cx + nb_w + 10
    draw.line(
        [(pen_x, nb_top - 4), (pen_x + 40, nb_top + nb_h * 2 + 4)],
        fill=INK_DARK, width=4,
    )
    draw.polygon(
        [(pen_x + 40, nb_top + nb_h * 2 + 4),
         (pen_x + 46, nb_top + nb_h * 2 + 10),
         (pen_x + 38, nb_top + nb_h * 2 + 12)],
        fill=WOOD_DARK,
    )

    # ---- 咖啡杯（中右） ----
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
    # 杯身（梯形，上宽下窄）
    draw.polygon(
        [(cup_cx - cup_w + 4, cup_top + cup_h),
         (cup_cx + cup_w - 4, cup_top + cup_h),
         (cup_cx + cup_w - 10, cup_top + 8),
         (cup_cx - cup_w + 10, cup_top + 8)],
        fill=(255, 255, 255),
    )
    # 杯口
    draw.ellipse(
        (cup_cx - cup_w + 8, cup_top, cup_cx + cup_w - 8, cup_top + 16),
        fill=(250, 248, 244),
    )
    # 咖啡
    draw.ellipse(
        (cup_cx - cup_w + 12, cup_top + 2, cup_cx + cup_w - 12, cup_top + 14),
        fill=COFFEE,
    )
    # 杯把
    draw.arc(
        (cup_cx + cup_w - 14, cup_top + 14, cup_cx + cup_w + 22, cup_top + 52),
        start=300, end=100, fill=(230, 224, 216), width=5,
    )
    # 蒸汽（柔曲线，用多段弧）
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

    # ---- 小绿植（右） ----
    plant_cx = desk_right - 120
    plant_top = desk_top - 28
    # 花盆投影
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse(
        (plant_cx - 46, desk_top - 2, plant_cx + 46, desk_top + 10),
        fill=(45, 106, 79, 35),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=4))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)
    # 花盆（梯形）
    pot_top = plant_top + 80
    draw.polygon(
        [(plant_cx - 42, pot_top),
         (plant_cx + 42, pot_top),
         (plant_cx + 34, plant_top + 26),
         (plant_cx - 34, plant_top + 26)],
        fill=POT_DARK,
    )
    # 盆沿
    draw.ellipse(
        (plant_cx - 38, plant_top + 20, plant_cx + 38, plant_top + 34),
        fill=POT,
    )
    draw.ellipse(
        (plant_cx - 34, plant_top + 22, plant_cx + 34, plant_top + 32),
        fill=(80, 54, 36),
    )
    # 土
    draw.ellipse(
        (plant_cx - 32, plant_top + 24, plant_cx + 32, plant_top + 32),
        fill=(80, 58, 40),
    )
    # 叶簇（更丰富的层次）
    leaves = [
        # (cx_offset, cy_offset, rx, ry, color)
        (0, -20, 22, 58, LEAF_DEEP),
        (-20, 0, 18, 48, LEAF_MAIN),
        (22, -4, 20, 52, LEAF_MAIN),
        (-10, -38, 16, 42, LEAF_SOFT),
        (14, -34, 17, 44, LEAF_SOFT),
        (-30, -18, 12, 30, LEAF_PALE),
        (30, -22, 13, 32, LEAF_PALE),
    ]
    for dx, dy, rx, ry, color in leaves:
        cx = plant_cx + dx
        cy = plant_top + dy
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=color)


def draw_panel(layer):
    """左侧文案面板。"""
    draw = ImageDraw.Draw(layer)

    panel_left, panel_top = 76, 200
    panel_right, panel_bottom = 720, 1160
    panel_r = 40

    # 面板大阴影
    shadow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (panel_left + 10, panel_top + 16, panel_right + 10, panel_bottom + 16),
        radius=panel_r, fill=(45, 106, 79, 28),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=22))
    layer.alpha_composite(shadow)
    draw = ImageDraw.Draw(layer)

    # 面板白底
    rounded_rect(draw,
                 (panel_left, panel_top, panel_right, panel_bottom),
                 radius=panel_r, fill=(255, 255, 255, 240))

    # 顶部细主绿条（比之前更细，位置缩进）
    bar_left = panel_left + 40
    bar_right = panel_left + 110
    rounded_rect(draw,
                 (bar_left, panel_top + 32, bar_right, panel_top + 40),
                 radius=4, fill=INK_MAIN)

    inner_left = panel_left + 56

    # ---- 标签：好评有礼 ----
    tag_font = select_font(34, bold=True)
    tag_top = panel_top + 80
    tag_w, tag_h, _, _ = text_metrics(draw, TAG, tag_font)
    tag_pill_w = tag_w + 48
    tag_pill_h = 64
    rounded_rect(draw,
                 (inner_left, tag_top, inner_left + tag_pill_w, tag_top + tag_pill_h),
                 radius=tag_pill_h // 2, fill=INK_LIGHT)
    draw_centered_text(
        draw,
        (inner_left + tag_pill_w / 2, tag_top + tag_pill_h / 2),
        TAG, tag_font, INK_DEEP,
    )

    # ---- 主标题 ----
    headline_font = select_font(108, bold=True)
    h1 = HEADLINE_LINE1
    h2 = HEADLINE_LINE2
    h1_w, h1_h, h1_ox, h1_oy = text_metrics(draw, h1, headline_font)
    h2_w, h2_h, h2_ox, h2_oy = text_metrics(draw, h2, headline_font)
    h1_top = tag_top + tag_pill_h + 60
    line_gap = 6
    draw.text((inner_left - h1_ox, h1_top - h1_oy), h1, font=headline_font, fill=INK_DARK)
    h2_top = h1_top + h1_h + line_gap
    draw.text((inner_left - h2_ox, h2_top - h2_oy), h2, font=headline_font, fill=INK_DARK)
    headline_bottom = h2_top + h2_h

    # 在"送日卡"右侧画一个小小的日卡图标
    card_ix = inner_left + h2_w + 28
    card_iy = h2_top + 6
    card_w, card_h = 70, 50
    # 卡阴影
    cs = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    csd = ImageDraw.Draw(cs)
    csd.rounded_rectangle(
        (card_ix + 2, card_iy + 3, card_ix + card_w + 2, card_iy + card_h + 3),
        radius=8, fill=(45, 106, 79, 40),
    )
    layer.alpha_composite(cs)
    draw = ImageDraw.Draw(layer)
    # 卡片
    rounded_rect(draw,
                 (card_ix, card_iy, card_ix + card_w, card_iy + card_h),
                 radius=8, fill=CARD_ACCENT)
    # 卡内白块（芯片）
    rounded_rect(draw,
                 (card_ix + 8, card_iy + 10, card_ix + 28, card_iy + 24),
                 radius=3, fill=(255, 255, 255, 220))
    # 卡面线
    draw.line(
        [(card_ix + 8, card_iy + 34), (card_ix + card_w - 8, card_iy + 34)],
        fill=(255, 255, 255, 200), width=2,
    )
    draw.line(
        [(card_ix + 8, card_iy + 42), (card_ix + 40, card_iy + 42)],
        fill=(255, 255, 255, 160), width=2,
    )
    # "DAY" 字
    day_font = select_font(14, bold=True)
    draw.text((card_ix + card_w - 28, card_iy + card_h - 20),
              "DAY", font=day_font, fill=(255, 255, 255))

    # ---- 平台药丸 ----
    sub_top = headline_bottom + 48
    pill_font = select_font(24, bold=True)
    pill_h = 44
    pill_gap = 12
    x_cursor = inner_left
    for i, name in enumerate(PLATFORMS):
        if i > 0:
            # 分隔点
            dot_r = 4
            dot_y = sub_top + pill_h / 2
            draw.ellipse(
                (x_cursor + 4 - dot_r, dot_y - dot_r,
                 x_cursor + 4 + dot_r, dot_y + dot_r),
                fill=INK_SOFT,
            )
            x_cursor += 8 + dot_r * 2 + 8
        pw, _, _, _ = text_metrics(draw, name, pill_font)
        pill_w = pw + 28
        pill_color = [GOLD, LEAF_MAIN, INK_MID][i]
        rounded_rect(draw,
                     (x_cursor, sub_top, x_cursor + pill_w, sub_top + pill_h),
                     radius=pill_h // 2, fill=pill_color)
        draw_centered_text(
            draw, (x_cursor + pill_w / 2, sub_top + pill_h / 2),
            name, pill_font, (255, 255, 255),
        )
        x_cursor += pill_w

    # "|15字+3张照片" 灰字紧跟其后
    cond_font = select_font(26)
    cond_text = " 15字+3张照片"
    draw.text((x_cursor, sub_top + (pill_h - 26) / 2 - 2),
              cond_text, font=cond_font, fill=INK_MUTED)

    # ---- 说明行：截图发给管理员...（带小图标） ----
    note_top = sub_top + pill_h + 46
    # 小礼品图标（方框 + 丝带）
    icon_x = inner_left
    icon_y = note_top + 2
    icon_s = 26
    rounded_rect(draw,
                 (icon_x, icon_y, icon_x + icon_s, icon_y + icon_s),
                 radius=4, fill=INK_LIGHT)
    draw.line(
        [(icon_x - 2, icon_y - 4), (icon_x + icon_s / 2, icon_y + icon_s / 2)],
        fill=INK_MAIN, width=3,
    )
    draw.line(
        [(icon_x + icon_s + 2, icon_y - 4),
         (icon_x + icon_s / 2, icon_y + icon_s / 2)],
        fill=INK_MAIN, width=3,
    )
    # 说明文字
    note_font = select_font(26)
    draw.text(
        (icon_x + icon_s + 14, note_top),
        NOTE, font=note_font, fill=INK_DARK,
    )

    # ---- 底部小装饰：一排主绿圆点 + 文字"期待你的真实评价" ----
    tip_font = select_font(20)
    tip_text = "✦ 期待你的真实评价 ✦"
    tip_top = panel_bottom - 70
    draw_centered_text(
        draw, ((panel_left + panel_right) / 2, tip_top),
        tip_text, tip_font, INK_SOFT,
    )


def draw_wordmark(layer):
    draw = ImageDraw.Draw(layer)
    font = select_font(28, bold=True)
    w, h, ox, oy = text_metrics(draw, WORDMARK, font)
    # 放到右上角但避开窗户：窗户右上是 1420,140，放在右上角窗外侧
    right = WIDTH - 56
    top = 60
    draw.text((right - w - ox, top - oy), WORDMARK, font=font, fill=INK_DEEP)


def encode_jpeg(image):
    for quality in (92, 88, 84, 80, 76):
        buffer = io.BytesIO()
        image.save(
            buffer, "JPEG",
            quality=quality, optimize=True, progressive=True, subsampling="4:2:0",
        )
        payload = buffer.getvalue()
        if 0 < len(payload) < MAX_BYTES:
            return payload, quality
    raise RuntimeError(f"JPEG remains at or above {MAX_BYTES:,} bytes")


def main():
    background = vertical_gradient((WIDTH, HEIGHT), BG_TOP, BG_BOTTOM)
    canvas = background.convert("RGBA")

    decor = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_background_decor(decor)
    canvas = Image.alpha_composite(canvas, decor)

    desk = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_desk_scene(desk)
    canvas = Image.alpha_composite(canvas, desk)

    panel = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_panel(panel)
    canvas = Image.alpha_composite(canvas, panel)

    wm = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw_wordmark(wm)
    canvas = Image.alpha_composite(canvas, wm)

    final = canvas.convert("RGB")
    payload, _quality = encode_jpeg(final)
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_bytes(payload)

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
