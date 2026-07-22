from PIL import Image, ImageDraw, ImageFont
import os

SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

RES_DIR = "android/app/src/main/res"


def draw_icon(size, round_bg=False):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bg_color = (220, 38, 38)
    if round_bg:
        draw.ellipse([0, 0, size - 1, size - 1], fill=bg_color)
    else:
        draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=bg_color)

    cx, cy = size // 2, size // 2

    sw = int(size * 0.52)
    sh = int(size * 0.58)
    sx1 = cx - sw // 2
    sy1 = cy - sh // 2 + int(size * 0.02)
    sx2 = cx + sw // 2
    sy2 = cy + sh // 2 + int(size * 0.02)

    shield_pts = []
    shield_pts.append((cx, sy1 - int(size * 0.04)))
    shield_pts.append((sx2 + int(size * 0.01), sy1 + int(sh * 0.15)))
    shield_pts.append((sx2, cy + int(sh * 0.05)))
    shield_pts.append((cx, sy2))
    shield_pts.append((sx1, cy + int(sh * 0.05)))
    shield_pts.append((sx1 - int(size * 0.01), sy1 + int(sh * 0.15)))

    draw.polygon(shield_pts, fill=(255, 255, 255, 240))

    bw = int(size * 0.06)
    inner_pts = []
    inner_pts.append((cx, sy1 - int(size * 0.04) + bw))
    inner_pts.append((sx2 + int(size * 0.01) - bw, sy1 + int(sh * 0.15) + bw))
    inner_pts.append((sx2 - bw, cy + int(sh * 0.05)))
    inner_pts.append((cx, sy2 - bw))
    inner_pts.append((sx1 + bw, cy + int(sh * 0.05)))
    inner_pts.append((sx1 - int(size * 0.01) + bw, sy1 + int(sh * 0.15) + bw))
    draw.polygon(inner_pts, fill=bg_color)

    ex = cx
    ey = int(size * 0.42)
    tri_h = int(size * 0.2)
    tri_w = int(size * 0.12)
    draw.polygon([
        (ex - tri_w, ey - tri_h // 2),
        (ex + tri_w, ey - tri_h // 2),
        (ex, ey + tri_h // 2),
    ], fill=(255, 255, 255, 240))

    dot_y = int(size * 0.56)
    dot_r = max(int(size * 0.03), 2)
    draw.ellipse([
        ex - dot_r, dot_y - dot_r,
        ex + dot_r, dot_y + dot_r,
    ], fill=(255, 255, 255, 240))

    line_y = int(size * 0.63)
    line_h = int(size * 0.06)
    lw = max(int(size * 0.02), 1)
    draw.rounded_rectangle([
        ex - lw, line_y,
        ex + lw, line_y + line_h,
    ], radius=lw, fill=(255, 255, 255, 240))

    return img


def main():
    for folder, size in SIZES.items():
        out_dir = os.path.join(RES_DIR, folder)
        os.makedirs(out_dir, exist_ok=True)

        icon = draw_icon(size, round_bg=False)
        icon.save(os.path.join(out_dir, "ic_launcher.png"))
        print(f"  {folder}/ic_launcher.png ({size}x{size})")

        icon_round = draw_icon(size, round_bg=True)
        icon_round.save(os.path.join(out_dir, "ic_launcher_round.png"))
        print(f"  {folder}/ic_launcher_round.png ({size}x{size})")

    fg_dir = os.path.join(RES_DIR, "mipmap-anydpi-v26")
    os.makedirs(fg_dir, exist_ok=True)

    for name in ["ic_launcher.xml", "ic_launcher_round.xml"]:
        path = os.path.join(fg_dir, name)
        with open(path, "w") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            f.write('<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n')
            f.write('    <background android:drawable="@color/ic_launcher_background"/>\n')
            f.write('    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n')
            f.write('</adaptive-icon>\n')
        print(f"  {fg_dir}/{name}")

    for folder in SIZES:
        fg_path = os.path.join(RES_DIR, folder, "ic_launcher_foreground.png")
        if not os.path.exists(fg_path):
            size = SIZES[folder]
            fg = draw_icon(int(size * 1.08), round_bg=False)
            fg.save(fg_path)
            print(f"  {folder}/ic_launcher_foreground.png ({int(size * 1.08)}x{int(size * 1.08)})")

    colors_dir = os.path.join(RES_DIR, "values")
    os.makedirs(colors_dir, exist_ok=True)
    colors_path = os.path.join(colors_dir, "ic_launcher_background.xml")
    with open(colors_path, "w") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write('<resources>\n')
        f.write('    <color name="ic_launcher_background">#DC2626</color>\n')
        f.write('</resources>\n')
    print(f"  {colors_path}")

    print("\nDone! App icons generated.")


if __name__ == "__main__":
    main()
