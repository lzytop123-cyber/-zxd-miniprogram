"""Create the clean landscape layout selected by the user."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "marketing" / "zhixingdao-wechat-search-2048x1024.png"
CODE = Path(r"D:\Downloads\搜一搜小程序推广物料图片-png\扫码_搜索联合传播样式-标准色版.png")
PHOTO = Path(r"F:\lzy\知行岛抖音\fc8a52fa50a445bb65e311cf6ac706381380015.webp")
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")


def f(size: int, bold: bool = False):
    return ImageFont.truetype(str(BOLD if bold and BOLD.exists() else FONT), size)


def cover(image: Image.Image, width: int, height: int) -> Image.Image:
    scale = max(width / image.width, height / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left = (image.width - width) // 2
    top = (image.height - height) // 2
    return image.crop((left, top, left + width, top + height))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (2048, 1024), "#F8F7F2")
    draw = ImageDraw.Draw(canvas)
    source = Image.open(CODE).convert("RGBA")

    room = cover(Image.open(PHOTO).convert("RGB"), 1390, 1024)
    room = ImageEnhance.Color(room).enhance(0.76)
    room = ImageEnhance.Brightness(room).enhance(1.05)
    canvas.paste(room, (658, 0))
    # Light veil creates the same calm transition from typography to the real room image.
    veil = Image.new("RGBA", (340, 1024))
    pixels = veil.load()
    for x in range(340):
        alpha = max(0, 238 - round(x / 340 * 238))
        for y in range(1024):
            pixels[x, y] = (248, 247, 242, alpha)
    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(veil, dest=(600, 0))
    canvas = canvas.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    mark = source.crop((890, 86, 1140, 332)).resize((86, 84), Image.Resampling.LANCZOS)
    canvas.paste(mark, (76, 86), mark)
    draw.text((180, 94), "微信搜一搜", font=f(49), fill="#333537")

    draw.rounded_rectangle((76, 205, 650, 312), radius=23, fill="#08B957")
    draw.ellipse((112, 237, 152, 277), outline="#FFFFFF", width=5)
    draw.line((145, 270, 169, 293), fill="#FFFFFF", width=5)
    draw.text((204, 228), "知行岛自习空间", font=f(37, True), fill="#FFFFFF")

    qr = source.crop((48, 38, 745, 765)).resize((455, 475), Image.Resampling.LANCZOS)
    canvas.paste(qr, (97, 354), qr)

    # Exactly four benefits, with no duplicate AI supporting copy.
    draw.text((76, 921), "在线选座", font=f(27), fill="#39433D")
    draw.text((218, 921), "·", font=f(29), fill="#B7862E")
    draw.text((270, 921), "静心学习", font=f(27), fill="#39433D")
    draw.text((412, 921), "·", font=f(29), fill="#B7862E")
    draw.text((464, 921), "智能蓝牙", font=f(27), fill="#39433D")
    draw.text((606, 921), "·", font=f(29), fill="#B7862E")
    draw.text((658, 909), "AI 学习助手", font=f(34, True), fill="#2B7655")
    draw.line((656, 958, 848, 958), fill="#2B7655", width=2)

    canvas.save(OUT, quality=95)
    print(OUT)


if __name__ == "__main__":
    main()
