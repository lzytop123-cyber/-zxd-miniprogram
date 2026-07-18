"""Create the WeChat Moments promotion banner without regenerating its QR code."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageFilter


WIDTH, HEIGHT = 1920, 1080
LEFT_WIDTH = 760
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "marketing" / "zhixingdao-wechat-search-1920x1080.png"
SOURCE_CODE = Path(r"D:\Downloads\搜一搜小程序推广物料图片-png\扫码_搜索联合传播样式-标准色版.png")
SOURCE_PHOTO = Path(r"F:\lzy\知行岛抖音\fc8a52fa50a445bb65e311cf6ac706381380015.webp")

FONT = Path(r"C:\Windows\Fonts\msyh.ttc")


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    # msyhbd exists on standard Windows installations; use it only for headlines.
    face = Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else FONT
    return ImageFont.truetype(str(face if face.exists() else FONT), size)


def contain(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image.thumbnail(size, Image.Resampling.LANCZOS)
    return image


def cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    scale = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    x = (resized.width - size[0]) // 2
    y = (resized.height - size[1]) // 2
    return resized.crop((x, y, x + size[0], y + size[1]))


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def main() -> None:
    if not SOURCE_CODE.exists() or not SOURCE_PHOTO.exists():
        raise FileNotFoundError("The supplied mini-program code or room photo was not found.")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), "#F8F7F2")

    # Fresh but restrained room treatment: retain the real space while cooling the strong yellow cast.
    room = cover(Image.open(SOURCE_PHOTO).convert("RGB"), (WIDTH - LEFT_WIDTH, HEIGHT))
    room = ImageEnhance.Color(room).enhance(0.76)
    room = ImageEnhance.Brightness(room).enhance(1.05)
    room = ImageEnhance.Contrast(room).enhance(0.94)
    canvas.paste(room, (LEFT_WIDTH, 0))
    photo_overlay = Image.new("RGBA", (WIDTH - LEFT_WIDTH, HEIGHT), (248, 251, 246, 38))
    canvas.paste(Image.alpha_composite(room.convert("RGBA"), photo_overlay).convert("RGB"), (LEFT_WIDTH, 0))

    # A soft separation lets the left-side grid remain quiet and readable.
    shade = Image.new("RGBA", (190, HEIGHT), (248, 247, 242, 235))
    shade = shade.filter(ImageFilter.GaussianBlur(18))
    canvas.paste(shade, (LEFT_WIDTH - 75, 0), shade)
    left = Image.new("RGB", (LEFT_WIDTH, HEIGHT), "#F9F8F4")
    canvas.paste(left, (0, 0))
    draw = ImageDraw.Draw(canvas)

    x = 84
    # Crop only the official red 搜一搜 mark from the supplied promotion asset.
    official = Image.open(SOURCE_CODE).convert("RGBA")
    search_mark = official.crop((890, 86, 1140, 332))
    search_mark = contain(search_mark, (112, 92))
    canvas.alpha_composite(search_mark, (x, 91)) if canvas.mode == "RGBA" else canvas.paste(search_mark, (x, 91), search_mark)
    draw.text((x + 126, 107), "微信搜一搜", font=font(54), fill="#333537")

    bar = (x, 228, 676, 330)
    rounded(draw, bar, 22, "#08B957")
    # Magnifying-glass icon.
    draw.ellipse((x + 33, 253, x + 73, 293), outline="#FFFFFF", width=5)
    draw.line((x + 66, 286, x + 87, 307), fill="#FFFFFF", width=5)
    draw.text((x + 112, 245), "知行岛自习空间", font=font(39, bold=True), fill="#FFFFFF")

    # This crop preserves the original mini-program code rather than asking an image model to redraw it.
    qr = official.crop((48, 38, 745, 765))
    qr = contain(qr, (438, 458))
    canvas.paste(qr, (x, 365), qr)

    # Three-level hierarchy: the distinct AI value is the only headline here;
    # supporting features stay on their own consistent baselines below.
    draw.line((x, 862, 676, 862), fill="#DDE7DE", width=2)
    draw.text((x, 894), "AI 学习助手", font=font(44, bold=True), fill="#267252")
    draw.text((x, 952), "让每一次学习，都更有方向", font=font(27), fill="#52615A")
    draw.text((x, 1002), "专属计划   ·   目标拆解   ·   学习复盘", font=font(23), fill="#6A756D")
    draw.text((x, 1030), "在线选座   ·   静心学习   ·   智能入座", font=font(21), fill="#748078")

    canvas.save(OUTPUT, quality=95)
    print(OUTPUT)
    print(canvas.size)


if __name__ == "__main__":
    main()
