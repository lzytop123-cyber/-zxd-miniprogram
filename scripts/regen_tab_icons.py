from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

out = Path(r'f:\zxd-pro\miniprogram\assets')

def make_ticket(color):
    img = Image.new('RGBA', (81, 81), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 23, 28, 58, 53  # ~35x25
    w = 3
    d.rounded_rectangle([x0, y0, x1, y1], radius=4, outline=color, width=w)
    cy = (y0 + y1) // 2
    r = 4
    punch = Image.new('L', img.size, 0)
    pd = ImageDraw.Draw(punch)
    pd.ellipse([x0 - r, cy - r, x0 + r, cy + r], fill=255)
    pd.ellipse([x1 - r, cy - r, x1 + r, cy + r], fill=255)
    rr, gg, bb, aa = img.split()
    aa = ImageChops.subtract(aa, punch)
    img = Image.merge('RGBA', (rr, gg, bb, aa))
    d = ImageDraw.Draw(img)
    d.arc([x0 - r, cy - r, x0 + r, cy + r], start=270, end=90, fill=color, width=w)
    d.arc([x1 - r, cy - r, x1 + r, cy + r], start=90, end=270, fill=color, width=w)
    cx = 35
    for y in range(y0 + 5, y1 - 3, 7):
        d.line([(cx, y), (cx, y + 3)], fill=color, width=w)
    return img

def bbox(im):
    px = im.load()
    xs, ys = [], []
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if a > 20 and r + g + b > 40:
                xs.append(x); ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None

for name, color in [
    ('tab-packages.png', (140, 155, 165, 255)),
    ('tab-packages-active.png', (45, 106, 79, 255)),
]:
    make_ticket(color).save(out / name)
    print('saved', name, bbox(Image.open(out / name).convert('RGBA')))

# First restore checkin from git so we don't double-nudge
import subprocess
subprocess.run(['git', 'checkout', '--', 'miniprogram/assets/tab-checkin.png', 'miniprogram/assets/tab-checkin-active.png'], cwd=r'f:\zxd-pro')

for name in ('tab-checkin.png', 'tab-checkin-active.png'):
    im = Image.open(out / name).convert('RGBA')
    shifted = Image.new('RGBA', im.size, (0, 0, 0, 0))
    shifted.alpha_composite(im, (0, 3))
    shifted.save(out / name)
    b = bbox(shifted)
    print('nudged', name, b, 'cy', (b[1]+b[3])/2)
