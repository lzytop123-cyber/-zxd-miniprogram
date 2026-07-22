"""Create the portrait layout selected by the user for WeChat and Xiaohongshu."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "marketing"
CODE = Path(r"D:\Downloads\搜一搜小程序推广物料图片-png\扫码_搜索联合传播样式-标准色版.png")
PHOTO = Path(r"F:\lzy\知行岛抖音\fc8a52fa50a445bb65e311cf6ac706381380015.webp")
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
W, H = 1242, 1660


def f(size: int, bold: bool = False):
    return ImageFont.truetype(str(BOLD if bold and BOLD.exists() else FONT), size)


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = (image.width - width) // 2
    top = (image.height - height) // 2
    return image.crop((left, top, left + width, top + height))


def rounded_paste(canvas: Image.Image, image: Image.Image, xy: tuple[int, int], radius: int) -> None:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius=radius, fill=255)
    canvas.paste(image, xy, mask)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (W, H), "#F8F7F2")
    draw = ImageDraw.Draw(canvas)
    source = Image.open(CODE).convert("RGBA")

    # Centered, compact search header as in the chosen reference layout.
    mark = source.crop((890, 86, 1140, 332)).resize((72, 70), Image.Resampling.LANCZOS)
    canvas.paste(mark, (267, 72), mark)
    draw.text((358, 78), "微信搜一搜", font=f(44), fill="#333537")
    draw.rounded_rectangle((258, 178, 984, 288), radius=23, fill="#08B957")
    draw.ellipse((302, 211, 342, 251), outline="#FFFFFF", width=5)
    draw.line((335, 244, 359, 268), fill="#FFFFFF", width=5)
    draw.text((400, 204), "知行岛自习空间", font=f(37, True), fill="#FFFFFF")

    room = cover(Image.open(PHOTO).convert("RGB"), 1242, 730)
    room = ImageEnhance.Color(room).enhance(0.75)
    room = ImageEnhance.Brightness(room).enhance(1.05)
    rounded_paste(canvas, room, (0, 350), 34)

    # Original code overlaps the photo/bottom boundary for a lively but QR-safe composition.
    qr = source.crop((48, 38, 745, 765)).resize((415, 433), Image.Resampling.LANCZOS)
    qr_mask = Image.new("L", qr.size, 0)
    ImageDraw.Draw(qr_mask).ellipse((0, 0, qr.width, qr.height), fill=255)
    canvas.paste(qr, (84, 915), qr_mask)

    # All four core functions appear once, in the requested reading order.
    y = 1334
    draw.text((101, y), "在线选座", font=f(28), fill="#3B4740")
    draw.text((252, y - 2), "·", font=f(31), fill="#B6872E")
    draw.text((307, y), "蓝牙智能入座", font=f(28), fill="#3B4740")
    draw.text((510, y - 2), "·", font=f(31), fill="#B6872E")
    draw.text((565, y - 5), "AI 学习助手", font=f(32, True), fill="#2B7756")
    draw.text((754, y - 2), "·", font=f(31), fill="#B6872E")
    draw.text((809, y), "知行合一", font=f(28), fill="#3B4740")
    draw.line((562, 1380, 740, 1380), fill="#2B7756", width=2)

    xhs = ASSETS / "zhixingdao-layout-xiaohongshu-1242x1660.png"
    wx = ASSETS / "zhixingdao-layout-wechat-1080x1440.png"
    canvas.save(xhs, quality=95)
    canvas.resize((1080, 1440), Image.Resampling.LANCZOS).save(wx, quality=95)
    print(xhs)
    print(wx)


if __name__ == "__main__":
    main()
