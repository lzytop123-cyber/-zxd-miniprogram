"""Create a 2048x800 WeChat Search banner using the original code and room photo."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "marketing" / "zhixingdao-ai-wechat-search-2048x800.png"
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
    return image.crop((left, 0, left + width, height))


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (2048, 800), "#F9F8F4")

    room = cover(Image.open(PHOTO).convert("RGB"), 1040, 800)
    room = ImageEnhance.Color(room).enhance(0.72)
    room = ImageEnhance.Brightness(room).enhance(1.06)
    canvas.paste(room, (1008, 0))
    # White-to-transparent veil: photograph remains real but never competes with the message.
    veil = Image.new("RGBA", (1040, 800))
    veil_px = veil.load()
    for x in range(1040):
        alpha = max(0, 232 - round(x / 1040 * 232))
        for y in range(800):
            veil_px[x, y] = (250, 249, 245, alpha)
    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(veil, dest=(1008, 0))
    canvas = canvas.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    source = Image.open(CODE).convert("RGBA")
    qr = source.crop((48, 38, 745, 765)).resize((570, 594), Image.Resampling.LANCZOS)
    canvas.paste(qr, (54, 102), qr)

    # Use the genuine Search mark, while typesetting all copy to an exact baseline grid.
    mark = source.crop((890, 86, 1140, 332)).resize((95, 93), Image.Resampling.LANCZOS)
    canvas.paste(mark, (714, 114), mark)
    draw.text((827, 123), "微信搜一搜", font=f(48), fill="#343638")

    draw.rounded_rectangle((714, 258, 1644, 378), radius=24, fill="#08B957")
    draw.ellipse((758, 293, 800, 335), outline="#FFFFFF", width=5)
    draw.line((792, 327, 817, 351), fill="#FFFFFF", width=5)
    draw.text((851, 283), "知行岛自习空间", font=f(45, True), fill="#FFFFFF")

    draw.line((714, 434, 1568, 434), fill="#D6E4D8", width=2)
    draw.text((714, 467), "全新 AI 学习助手", font=f(48, True), fill="#257052")
    draw.text((714, 537), "专属计划  ·  目标拆解  ·  学习复盘", font=f(29), fill="#55635A")
    draw.text((714, 594), "在线选座  ·  静心学习  ·  智能入座", font=f(26), fill="#707B73")
    draw.text((714, 659), "让每一次学习，都更有方向", font=f(25), fill="#34775A")

    canvas.save(OUT, quality=95)
    print(OUT)


if __name__ == "__main__":
    main()
