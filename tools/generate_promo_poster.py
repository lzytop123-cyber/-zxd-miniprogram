"""Create a QR-safe 1080x1350 WeChat Moments poster."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "marketing" / "zhixingdao-ai-moments-1080x1350.png"
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


def rounded_photo(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *image.size), radius=radius, fill=255)
    image.putalpha(mask)
    return image


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (1080, 1350), "#F8F7F2")
    draw = ImageDraw.Draw(canvas)
    source = Image.open(CODE).convert("RGBA")

    # Header uses the supplied official 搜一搜 mark and a precise text baseline.
    mark = source.crop((890, 86, 1140, 332)).resize((82, 80), Image.Resampling.LANCZOS)
    canvas.paste(mark, (70, 70), mark)
    draw.text((170, 81), "微信搜一搜", font=f(43), fill="#36383A")

    draw.rounded_rectangle((70, 186, 1010, 296), radius=24, fill="#08B957")
    draw.ellipse((111, 220, 151, 260), outline="#FFFFFF", width=5)
    draw.line((144, 253, 167, 276), fill="#FFFFFF", width=5)
    draw.text((204, 209), "知行岛自习空间", font=f(40, True), fill="#FFFFFF")

    room = cover(Image.open(PHOTO).convert("RGB"), 940, 360)
    room = ImageEnhance.Color(room).enhance(0.76)
    room = ImageEnhance.Brightness(room).enhance(1.05)
    room_tile = rounded_photo(room, 30)
    canvas.paste(room_tile, (70, 344), room_tile)

    # Original mini-program code is intentionally retained as an image, not generated.
    qr = source.crop((48, 38, 745, 765)).resize((370, 386), Image.Resampling.LANCZOS)
    canvas.paste(qr, (70, 765), qr)

    # One clean feature grid: no supporting copy repeats the AI message.
    draw.line((495, 798, 965, 798), fill="#D3E4D7", width=2)
    draw.line((725, 830, 725, 1035), fill="#E0E8E1", width=2)
    draw.line((495, 932, 965, 932), fill="#E0E8E1", width=2)
    draw.text((520, 853), "AI 学习助手", font=f(31, True), fill="#267353")
    draw.text((755, 853), "智能蓝牙", font=f(29, True), fill="#4F5D55")
    draw.text((520, 972), "静心学习", font=f(29, True), fill="#4F5D55")
    draw.text((755, 972), "在线选座", font=f(29, True), fill="#4F5D55")

    canvas.save(OUT, quality=95)
    print(OUT)


if __name__ == "__main__":
    main()
