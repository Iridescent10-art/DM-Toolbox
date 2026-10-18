import os
import math
from PIL import Image, ImageDraw, ImageFilter

def create_app_icon():
    canvas_size = 1024
    img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    
    # 1. Soft Drop Shadow for the squircle
    shadow_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_img)
    margin = 80
    corner_radius = 210
    
    # Draw shadow
    shadow_draw.rounded_rectangle(
        [margin + 10, margin + 40, canvas_size - margin - 10, canvas_size - margin + 20],
        radius=corner_radius,
        fill=(15, 35, 95, 90)
    )
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(35))
    img.paste(shadow_img, (0, 0), shadow_img)
    
    # 2. Main Squircle with Gradient
    base_mask = Image.new("L", (canvas_size, canvas_size), 0)
    mask_draw = ImageDraw.Draw(base_mask)
    mask_draw.rounded_rectangle(
        [margin, margin, canvas_size - margin, canvas_size - margin],
        radius=corner_radius,
        fill=255
    )
    
    # Create Gradient background
    grad_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    # Linear gradient: Top-Left (Vibrant Sky Blue #2563EB) to Bottom-Right (Electric Royal Blue #1D4ED8 to Cyan #0EA5E9)
    for y in range(margin, canvas_size - margin):
        ratio_y = (y - margin) / (canvas_size - 2 * margin)
        for x in range(margin, canvas_size - margin):
            ratio_x = (x - margin) / (canvas_size - 2 * margin)
            diag = (ratio_x + ratio_y) / 2.0
            
            # Color stops:
            # 0.0 -> (37, 99, 235)  #2563EB
            # 0.5 -> (30, 64, 175)  #1E40AF
            # 1.0 -> (14, 165, 233) #0EA5E9
            if diag < 0.5:
                t = diag / 0.5
                r = int(37 * (1 - t) + 30 * t)
                g = int(99 * (1 - t) + 64 * t)
                b = int(235 * (1 - t) + 175 * t)
            else:
                t = (diag - 0.5) / 0.5
                r = int(30 * (1 - t) + 14 * t)
                g = int(64 * (1 - t) + 165 * t)
                b = int(175 * (1 - t) + 233 * t)
            grad_img.putpixel((x, y), (r, g, b, 255))
            
    # Apply squircle mask to gradient
    squircle = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    squircle.paste(grad_img, (0, 0), base_mask)
    
    # Inner rim light / bevel highlight at top
    highlight_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    h_draw = ImageDraw.Draw(highlight_img)
    h_draw.rounded_rectangle(
        [margin + 4, margin + 4, canvas_size - margin - 4, canvas_size - margin - 4],
        radius=corner_radius - 4,
        outline=(255, 255, 255, 70),
        width=6
    )
    h_draw.rounded_rectangle(
        [margin + 8, margin + 8, canvas_size - margin - 8, canvas_size - margin - 8],
        radius=corner_radius - 8,
        outline=(255, 255, 255, 30),
        width=3
    )
    squircle.paste(highlight_img, (0, 0), highlight_img)
    
    # 3. Draw Hardware / Processor Circuit Graphic on Top
    fg = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    fg_draw = ImageDraw.Draw(fg)
    center = canvas_size // 2
    
    # Outer Circuit Tracks (glowing cyan / translucent white)
    track_color = (255, 255, 255, 175)
    dot_color = (56, 189, 248, 255)
    
    # 4 corner diagonal circuits
    for angle in [45, 135, 225, 315]:
        rad = math.radians(angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        
        # Start from chip edge
        x1 = center + int(210 * cos_a)
        y1 = center + int(210 * sin_a)
        x2 = center + int(290 * cos_a)
        y2 = center + int(290 * sin_a)
        fg_draw.line([x1, y1, x2, y2], fill=track_color, width=8)
        fg_draw.ellipse([x2 - 12, y2 - 12, x2 + 12, y2 + 12], fill=dot_color, outline=(255, 255, 255, 220), width=4)

    # 8 Pin connectors on 4 sides
    pin_offsets = [-110, -55, 0, 55, 110]
    for dy in pin_offsets:
        # Left pins
        fg_draw.line([center - 200, center + dy, center - 265, center + dy], fill=track_color, width=7)
        fg_draw.ellipse([center - 275, center + dy - 7, center - 261, center + dy + 7], fill=dot_color)
        # Right pins
        fg_draw.line([center + 200, center + dy, center + 265, center + dy], fill=track_color, width=7)
        fg_draw.ellipse([center + 261, center + dy - 7, center + 275, center + dy + 7], fill=dot_color)

    for dx in pin_offsets:
        # Top pins
        fg_draw.line([center + dx, center - 200, center + dx, center - 265], fill=track_color, width=7)
        fg_draw.ellipse([center + dx - 7, center - 275, center + dx + 7, center - 261], fill=dot_color)
        # Bottom pins
        fg_draw.line([center + dx, center + 200, center + dx, center + 265], fill=track_color, width=7)
        fg_draw.ellipse([center + dx - 7, center + 261, center + dx + 7, center + 275], fill=dot_color)

    # 4. Central Chip Base with 3D Bevel
    chip_w = 360
    chip_r = 50
    chip_box = [center - chip_w // 2, center - chip_w // 2, center + chip_w // 2, center + chip_w // 2]
    
    # Chip shadow
    c_shadow = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    c_s_draw = ImageDraw.Draw(c_shadow)
    c_s_draw.rounded_rectangle(
        [chip_box[0], chip_box[1] + 15, chip_box[2], chip_box[3] + 20],
        radius=chip_r,
        fill=(10, 25, 70, 140)
    )
    c_shadow = c_shadow.filter(ImageFilter.GaussianBlur(16))
    fg.paste(c_shadow, (0, 0), c_shadow)
    
    # Chip body (Clean metallic porcelain white #F8FAFC)
    fg_draw.rounded_rectangle(chip_box, radius=chip_r, fill=(248, 250, 252, 255), outline=(255, 255, 255, 240), width=6)
    
    # Inner silicon die (Silicon reflective metallic dark blue / gold accent)
    die_w = 230
    die_r = 34
    die_box = [center - die_w // 2, center - die_w // 2, center + die_w // 2, center + die_w // 2]
    
    # Die gradient fill
    die_img = Image.new("RGBA", (die_w, die_w), (0, 0, 0, 0))
    d_draw = ImageDraw.Draw(die_img)
    for i in range(die_w):
        r = int(24 + (43 - 24) * (i / die_w))
        g = int(72 + (133 - 72) * (i / die_w))
        b = int(184 + (255 - 184) * (i / die_w))
        d_draw.line([(0, i), (die_w, i)], fill=(r, g, b, 255))
        
    die_mask = Image.new("L", (die_w, die_w), 0)
    ImageDraw.Draw(die_mask).rounded_rectangle([0, 0, die_w, die_w], radius=die_r, fill=255)
    
    fg.paste(die_img, (center - die_w // 2, center - die_w // 2), die_mask)
    
    # Die inner core emblem: Futuristic "H" / Lightning Bolt Hardware Core
    core_draw = ImageDraw.Draw(fg)
    
    # Modern lightning / tech glyph
    poly_pts = [
        (center - 15, center - 80),
        (center + 55, center - 80),
        (center + 10, center - 10),
        (center + 65, center - 10),
        (center - 45, center + 85),
        (center - 15, center + 15),
        (center - 65, center + 15),
    ]
    # Glow around lightning
    glow_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    ImageDraw.Draw(glow_img).polygon(poly_pts, fill=(255, 255, 255, 120))
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(12))
    fg.paste(glow_img, (0, 0), glow_img)
    
    # Crisp white lightning glyph
    core_draw.polygon(poly_pts, fill=(255, 255, 255, 255))
    
    # Subtle circuit dots around die
    for ox, oy in [(-70, -70), (70, -70), (-70, 70), (70, 70)]:
        core_draw.ellipse([center + ox - 6, center + oy - 6, center + ox + 6, center + oy + 6], fill=(125, 211, 252, 220))

    # Compose final icon
    img.paste(squircle, (0, 0), squircle)
    img.paste(fg, (0, 0), fg)
    
    # Resize down with LANCZOS for razor sharp edges
    final_icon = img.resize((512, 512), Image.Resampling.LANCZOS)
    
    os.makedirs(r"D:\AI\自定义配置\assets", exist_ok=True)
    png_path = r"D:\AI\自定义配置\assets\app_icon.png"
    ico_path = r"D:\AI\自定义配置\assets\app_icon.ico"
    
    final_icon.save(png_path, format="PNG")
    
    # Create multi-resolution ICO
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    final_icon.save(ico_path, format="ICO", sizes=sizes)
    print(f"Icon generated: {png_path} and {ico_path}")

create_app_icon()
import os
import math
from PIL import Image, ImageDraw, ImageFilter

def create_hero_graphic():
    w, h = 600, 320
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    cx, cy = 350, 160
    
    # 1. Background soft radial glow
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(glow)
    g_draw.ellipse([cx - 180, cy - 130, cx + 180, cy + 130], fill=(59, 130, 246, 55))
    g_draw.ellipse([cx - 120, cy - 90, cx + 120, cy + 90], fill=(14, 165, 233, 75))
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img.paste(glow, (0, 0), glow)
    
    # 2. Glowing Elliptical Tech Orbit Rings
    for rx, ry, angle, color in [
        (220, 75, -18, (147, 197, 253, 140)),
        (190, 65, 22, (96, 165, 250, 160)),
        (240, 90, 5, (186, 230, 253, 110))
    ]:
        ring = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        r_draw = ImageDraw.Draw(ring)
        r_draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=color, width=3)
        # Add tech dots on ring
        r_draw.ellipse([cx + rx - 8, cy - 8, cx + rx + 8, cy + 8], fill=(37, 99, 235, 255), outline=(255, 255, 255, 240), width=2)
        r_draw.ellipse([cx - rx + 40, cy - ry + 15, cx - rx + 52, cy - ry + 27], fill=(14, 165, 233, 255))
        ring = ring.rotate(angle, center=(cx, cy), resample=Image.Resampling.BICUBIC)
        img.paste(ring, (0, 0), ring)

    # 3. 3D Floating Hardware Elements
    # Center Tech Orb / Hardware Core
    core_r = 85
    core_img = Image.new("RGBA", (core_r * 2 + 40, core_r * 2 + 40), (0, 0, 0, 0))
    cd = ImageDraw.Draw(core_img)
    # Orb shadow
    cd.ellipse([20, 25, 20 + core_r * 2, 25 + core_r * 2], fill=(20, 45, 110, 80))
    core_img = core_img.filter(ImageFilter.GaussianBlur(10))
    cd = ImageDraw.Draw(core_img)
    
    # 3D shaded sphere
    for r in range(core_r, 0, -1):
        ratio = r / core_r
        # Light coming from top-left
        ox = int((1 - ratio) * -22)
        oy = int((1 - ratio) * -22)
        cr = int(30 + 190 * (1 - ratio))
        cg = int(64 + 170 * (1 - ratio))
        cb = int(175 + 80 * (1 - ratio))
        cd.ellipse([20 + core_r - r + ox, 20 + core_r - r + oy, 20 + core_r + r + ox, 20 + core_r + r + oy], fill=(cr, cg, cb, 255))
        
    img.paste(core_img, (cx - core_r - 20, cy - core_r - 20), core_img)
    
    # Specular spot
    draw.ellipse([cx - 45, cy - 45, cx - 15, cy - 15], fill=(255, 255, 255, 220))
    
    # 4. Floating Glassmorphism Badges (like in the reference screenshot)
    # Badge 1: CPU Chip Badge (Top-Left)
    b1_x, b1_y = cx - 165, cy - 75
    b1 = Image.new("RGBA", (110, 65), (0, 0, 0, 0))
    b1_d = ImageDraw.Draw(b1)
    b1_d.rounded_rectangle([2, 5, 108, 62], radius=16, fill=(15, 30, 80, 40))
    b1 = b1.filter(ImageFilter.GaussianBlur(4))
    b1_d = ImageDraw.Draw(b1)
    b1_d.rounded_rectangle([0, 0, 106, 56], radius=16, fill=(255, 255, 255, 230), outline=(220, 235, 255, 255), width=2)
    # CPU Icon inside badge
    b1_d.rounded_rectangle([12, 12, 44, 44], radius=8, fill=(238, 242, 255, 255))
    b1_d.rectangle([20, 20, 36, 36], fill=(79, 70, 229, 255))
    b1_d.text((52, 16), "CPU", fill=(30, 41, 59, 255))
    b1_d.text((52, 32), "9800X3D", fill=(99, 102, 241, 255))
    img.paste(b1, (b1_x, b1_y), b1)
    
    # Badge 2: GPU Card Badge (Top-Right)
    b2_x, b2_y = cx + 85, cy - 85
    b2 = Image.new("RGBA", (120, 65), (0, 0, 0, 0))
    b2_d = ImageDraw.Draw(b2)
    b2_d.rounded_rectangle([2, 5, 118, 62], radius=16, fill=(15, 30, 80, 40))
    b2 = b2.filter(ImageFilter.GaussianBlur(4))
    b2_d = ImageDraw.Draw(b2)
    b2_d.rounded_rectangle([0, 0, 116, 56], radius=16, fill=(255, 255, 255, 235), outline=(225, 230, 255, 255), width=2)
    b2_d.rounded_rectangle([12, 12, 44, 44], radius=8, fill=(243, 232, 255, 255))
    b2_d.ellipse([21, 21, 35, 35], fill=(139, 92, 246, 255))
    b2_d.text((52, 16), "RTX 5090", fill=(30, 41, 59, 255))
    b2_d.text((52, 32), "24GB GDDR7", fill=(147, 51, 234, 255))
    img.paste(b2, (b2_x, b2_y), b2)
    
    # Badge 3: SSS Rank Badge (Bottom-Right)
    b3_x, b3_y = cx + 65, cy + 45
    b3 = Image.new("RGBA", (110, 60), (0, 0, 0, 0))
    b3_d = ImageDraw.Draw(b3)
    b3_d.rounded_rectangle([2, 5, 108, 58], radius=16, fill=(15, 30, 80, 40))
    b3 = b3.filter(ImageFilter.GaussianBlur(4))
    b3_d = ImageDraw.Draw(b3)
    b3_d.rounded_rectangle([0, 0, 106, 52], radius=16, fill=(255, 255, 255, 235), outline=(210, 240, 255, 255), width=2)
    b3_d.rounded_rectangle([10, 10, 42, 42], radius=8, fill=(224, 242, 254, 255))
    b3_d.text((16, 14), "SSS", fill=(2, 132, 199, 255))
    b3_d.text((48, 14), "99.9%", fill=(15, 23, 42, 255))
    b3_d.text((48, 28), "顶级超越", fill=(14, 165, 233, 255))
    img.paste(b3, (b3_x, b3_y), b3)
    
    # Save graphic
    out_p = r"D:\AI\自定义配置\assets\hero_graphic.png"
    img.save(out_p, format="PNG")
    print(f"Hero graphic created: {out_p}")

create_hero_graphic()
