"""Create one 3:4 promotion layout for WeChat Moments and Xiaohongshu."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "marketing"
CODE = Path(r"D:\Downloads\搜一搜小程序推广物料图片-png\扫码_搜索联合传播样式-标准色版.png")
PHOTO = Path(r"F:\lzy\知行岛抖音\fc8a52fa50a445bb65e311cf6ac706381380015.webp")
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")
WIDTH, HEIGHT = 1242, 1660


def f(size: int, bold: bool = False):
    return ImageFont.truetype(str(BOLD if bold and BOLD.exists() else FONT), size)


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = (image.width - width) // 2
    top = (image.height - height) // 2
    return image.crop((left, top, left + width, top + height))


def paste_rounded(canvas: Image.Image, image: Image.Image, xy: tuple[int, int], radius: int) -> None:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius=radius, fill=255)
    canvas.paste(image, xy, mask)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "#F8F7F2")
    draw = ImageDraw.Draw(canvas)
    source = Image.open(CODE).convert("RGBA")

    mark = source.crop((890, 86, 1140, 332)).resize((86, 84), Image.Resampling.LANCZOS)
    canvas.paste(mark, (96, 84), mark)
    draw.text((200, 96), "微信搜一搜", font=f(50), fill="#333537")

    draw.rounded_rectangle((96, 212, 1146, 332), radius=26, fill="#08B957")
    draw.ellipse((139, 248, 181, 290), outline="#FFFFFF", width=5)
    draw.line((174, 283, 199, 308), fill="#FFFFFF", width=5)
    draw.text((246, 238), "知行岛自习空间", font=f(43, True), fill="#FFFFFF")

    room = cover(Image.open(PHOTO).convert("RGB"), 1050, 560)
    room = ImageEnhance.Color(room).enhance(0.76)
    room = ImageEnhance.Brightness(room).enhance(1.05)
    paste_rounded(canvas, room, (96, 394), 34)

    # The original mini-program code remains unmodified inside the composed poster.
    qr = source.crop((48, 38, 745, 765)).resize((430, 449), Image.Resampling.LANCZOS)
    canvas.paste(qr, (406, 1012), qr)

    draw.line((158, 1488, 1084, 1488), fill="#D6E5D8", width=2)
    # Two centered feature rows use the selected reference's restrained one-line treatment.
    draw.text((202, 1521), "在线选座", font=f(31), fill="#404A43")
    draw.text((390, 1520), "·", font=f(33), fill="#B6872E")
    draw.text((458, 1521), "静心学习", font=f(31), fill="#404A43")
    draw.text((646, 1520), "·", font=f(33), fill="#B6872E")
    draw.text((714, 1521), "智能蓝牙", font=f(31), fill="#404A43")
    draw.text((380, 1573), "AI 学习助手", font=f(38, True), fill="#277554")
    draw.line((376, 1620, 616, 1620), fill="#277554", width=2)

    xhs = ASSETS / "zhixingdao-social-xiaohongshu-1242x1660.png"
    wx = ASSETS / "zhixingdao-social-wechat-1080x1440.png"
    canvas.save(xhs, quality=95)
    canvas.resize((1080, 1440), Image.Resampling.LANCZOS).save(wx, quality=95)
    print(xhs)
    print(wx)


if __name__ == "__main__":
    main()
