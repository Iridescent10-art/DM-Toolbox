# -*- coding: utf-8 -*-
"""
Generate the DM-Toolbox DLSS 5 icon (PNG + multi-size ICO).

Design: three offset "frame" outlines (multi-frame generation) over a dark
teal rounded tile, with the DLSS 5 wordmark. Rendered at 1024px and downscaled
with LANCZOS so 16/24/32px taskbar sizes stay legible.

Usage:  python apps/app6_dlss5/assets/create_dlss5_icon.py
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 1024
HERE = Path(__file__).resolve().parent
COMMON_ASSETS = HERE.parent.parent.parent / "common" / "assets"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _vertical_gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        for x in range(size):
            px[x, y] = color
    return img


def build_icon() -> Image.Image:
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Rounded tile with a soft green glow behind the frame stack
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((32, 32, S - 32, S - 32), radius=210, fill=255)

    tile = _vertical_gradient(S, (10, 20, 34), (5, 52, 40)).convert("RGBA")
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((190, 360, 850, 980), fill=(16, 185, 129, 90))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    tile = Image.alpha_composite(tile, glow)
    canvas.paste(tile, (0, 0), mask)

    draw = ImageDraw.Draw(canvas)

    # Inner hairline border
    draw.rounded_rectangle((44, 44, S - 44, S - 44), radius=198, outline=(52, 211, 153, 110), width=5)

    # Back frames (multi-frame generation motif)
    draw.rounded_rectangle((392, 168, 892, 668), radius=92, outline=(16, 185, 129, 90), width=18)
    draw.rounded_rectangle((348, 214, 848, 714), radius=96, outline=(52, 211, 153, 150), width=20)

    # Front frame
    draw.rounded_rectangle(
        (300, 270, 800, 770), radius=104,
        fill=(9, 26, 32, 255), outline=(52, 211, 153, 255), width=24,
    )

    # Wordmark
    f_dlss = _font(104)
    f_five = _font(318)
    f_sub = _font(64)
    frame_center_x = 550

    def centered(text, font, top, fill):
        box = draw.textbbox((0, 0), text, font=font)
        draw.text((frame_center_x - (box[2] - box[0]) / 2 - box[0], top), text, font=font, fill=fill)

    centered("DLSS", f_dlss, 338, (167, 243, 208, 255))
    centered("5", f_five, 442, (255, 255, 255, 255))
    centered("NEURAL  RENDER", f_sub, 800, (110, 231, 183, 230))

    # Neural dots accents on the front frame corners
    for (cx, cy), r in (((338, 308), 13), ((762, 308), 13), ((338, 732), 13), ((762, 732), 13)):
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(52, 211, 153, 230))

    return canvas


def main():
    master = build_icon()

    png_512 = master.resize((512, 512), Image.LANCZOS)
    png_256 = master.resize((256, 256), Image.LANCZOS)

    targets = [
        HERE / "dlss5_icon.png",
        COMMON_ASSETS / "dlss5_icon.png",
    ]
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        png_512.save(path, "PNG", optimize=True)
        print("wrote", path)

    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    for ico_path in (HERE / "dlss5_icon.ico", COMMON_ASSETS / "dlss5_icon.ico"):
        master.save(ico_path, format="ICO", sizes=ico_sizes)
        print("wrote", ico_path)

    # Small preview strip for quick visual verification
    preview = Image.new("RGBA", (512 + 256 + 128 + 64 + 48, 256), (245, 245, 245, 255))
    x = 0
    for size in (256, 128, 64, 48, 32, 16):
        icon = master.resize((size, size), Image.LANCZOS)
        preview.alpha_composite(icon, (x, 0))
        x += size + 8
    preview.save(HERE / "_icon_preview.png")
    print("preview:", HERE / "_icon_preview.png")


if __name__ == "__main__":
    main()
