from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

out = r"C:\Users\17547\Desktop\DLSS显示开关\src\app.ico"
sizes = [16, 24, 32, 48, 64, 128, 256]
imgs = []
font_path = r"C:\Windows\Fonts\seguibl.ttf"
if not os.path.exists(font_path):
    font_path = r"C:\Windows\Fonts\msyhbd.ttc"

for s in sizes:
    big = max(s * 4, 64)
    im = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = int(big * 0.035)

    # Rounded dark badge with a subtle diagonal gradient.
    badge = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.rounded_rectangle((m, m, big-m-1, big-m-1), radius=int(big*0.22), fill=(15, 20, 27, 255))
    grad = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(big):
        t = y / max(1, big - 1)
        color = (int(18 + 10*t), int(29 + 48*t), int(35 + 12*t), 145)
        gd.line((0, y, big, y), fill=color)
    mask = Image.new("L", (big, big), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((m, m, big-m-1, big-m-1), radius=int(big*0.22), fill=255)
    badge.paste(grad, (0, 0), Image.composite(grad.getchannel("A"), Image.new("L", (big, big), 0), mask))
    im.alpha_composite(badge)
    d = ImageDraw.Draw(im)

    # Outer edge.
    d.rounded_rectangle((m, m, big-m-1, big-m-1), radius=int(big*0.22),
                        outline=(76, 94, 105, 255), width=max(1, int(big*0.025)))

    # Bold "D" mark.
    try:
        font = ImageFont.truetype(font_path, int(big * 0.57))
    except Exception:
        font = ImageFont.load_default()
    text = "D"
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = int(big*0.49 - tw/2) - bbox[0]
    ty = int(big*0.51 - th/2) - bbox[1]

    # Soft glow.
    glow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow)
    gd2.text((tx, ty), text, font=font, fill=(116, 230, 0, 170))
    glow = glow.filter(ImageFilter.GaussianBlur(max(1, big//32)))
    im.alpha_composite(glow)
    d = ImageDraw.Draw(im)
    d.text((tx, ty), text, font=font, fill=(221, 255, 169, 255))

    # AI sparkle in the upper-right.
    cx, cy, r = int(big*0.76), int(big*0.24), max(2, int(big*0.105))
    points = [
        (cx, cy-r), (cx+r*0.28, cy-r*0.28), (cx+r, cy),
        (cx+r*0.28, cy+r*0.28), (cx, cy+r),
        (cx-r*0.28, cy+r*0.28), (cx-r, cy),
        (cx-r*0.28, cy-r*0.28)
    ]
    d.polygon(points, fill=(146, 242, 35, 255))

    im = im.resize((s, s), Image.Resampling.LANCZOS)
    imgs.append(im)

imgs[-1].save(out, format="ICO", sizes=[(x, x) for x in imgs[-1].size], append_images=imgs[:-1])
print(out, os.path.getsize(out))
