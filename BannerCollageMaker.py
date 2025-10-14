"""
generate_banners_v5.py (FIXED for File Size)
Creates 4 YouTube banner versions (2560x1440 JPGs, max 6 MB) with a seamless, unified grid.

The center 7x2 block of the grid will feature photos from the "Favs" folder.
The rest of the banner will be a shuffled collage of all other photos.

Requires:
  pip install pillow
Files/Folders required in same folder:
  - Archive.zip  (contains all photos)
  - Favs/        (a folder containing your 14 favorite photos)
  - Logo horizontal light.png
  - Logo horizontal dark.png
"""

import os, zipfile, math, random
from PIL import Image, ImageOps, ImageDraw, ImageFilter

# ---------------- CONFIG ---------------- #
ARCHIVE_PATH = "Archive.zip"
FAVS_FOLDER = "Favs"
LOGO_LIGHT = "Logo horizontal light.png"
LOGO_DARK = "Logo horizontal dark.png"

W, H = 2560, 1440
# --- Changed output filenames to .jpg ---
OUTPUTS = [
    ("banner_v5_cinematic_light_natural.jpg", "cinematic", "light"),
    ("banner_v5_cinematic_light_vivid.jpg", "cinematic", "light"),
    ("banner_v5_clean_dark_natural.jpg", "clean", "dark"),
    ("banner_v5_clean_dark_vivid.jpg", "clean", "dark"),
]
# ---------------------------------------- #

print("📦 Extracting photos...")
workdir = "banner_photos_v5"
os.makedirs(workdir, exist_ok=True)
with zipfile.ZipFile(ARCHIVE_PATH, "r") as z:
    z.extractall(workdir)

def is_image(f):
    f = f.lower()
    return f.endswith((".jpg", ".jpeg", ".png", ".webp")) and not os.path.basename(f).startswith("._")

all_imgs = [os.path.join(root, f) for root, _, files in os.walk(workdir) for f in files if is_image(f) and "__MACOSX" not in root]
print(f"✅ Found {len(all_imgs)} photos in archive.")

# ---- helper functions ---- #
def fit_crop(img, tw, th):
    iw, ih = img.size
    target_aspect = tw / th
    img_aspect = iw / ih
    if img_aspect > target_aspect:
        new_width = int(target_aspect * ih)
        offset = (iw - new_width) // 2
        img = img.crop((offset, 0, iw - offset, ih))
    else:
        new_height = int(iw / target_aspect)
        offset = (ih - new_height) // 2
        img = img.crop((0, offset, iw, ih - offset))
    return img.resize((tw, th), Image.Resampling.LANCZOS)

def add_vignette(im, strength=0.4):
    w, h = im.size
    vignette = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(vignette)
    max_radius = math.hypot(w / 2, h / 2)
    for i in range(100):
        radius = int(max_radius * i / 100)
        alpha = int(255 * (i / 100) ** 2)
        draw.ellipse((w/2 - radius, h/2 - radius, w/2 + radius, h/2 + radius), fill=alpha)
    vignette = ImageOps.invert(vignette.filter(ImageFilter.GaussianBlur(80)))
    dark_overlay = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(dark_overlay, im, vignette.point(lambda p: int(p * strength)))

def paste_logo(im, logo_path, width_ratio=0.38, opacity=160):
    logo = Image.open(logo_path).convert("RGBA")
    w, h = im.size
    safe_w = 1546
    lw, lh = logo.size
    target_w = int(safe_w * width_ratio)
    scale = target_w / lw
    target_h = int(lh * scale)
    logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)

    if logo.mode == 'RGBA':
        r, g, b, a = logo.split()
        a = a.point(lambda p: int(p * (opacity / 255)))
        logo = Image.merge('RGBA', (r, g, b, a))
    
    cx, cy = w // 2, h // 2
    im.alpha_composite(logo, (cx - target_w // 2, cy - target_h // 2))
    return im

# ---- generation ---- #
def make_banner(style, tone, out_name):
    print(f"🧩 Generating {out_name} ...")

    if not os.path.isdir(FAVS_FOLDER):
        raise FileNotFoundError(f"The '{FAVS_FOLDER}' folder was not found.")
    
    favs = [os.path.join(FAVS_FOLDER, f) for f in os.listdir(FAVS_FOLDER) if is_image(os.path.join(FAVS_FOLDER, f))]
    fav_names = {os.path.basename(f) for f in favs}
    others = [p for p in all_imgs if os.path.basename(p) not in fav_names]

    if not favs: raise ValueError("'Favs' folder is empty.")
    if not others: raise ValueError("No other photos found in archive for the background.")
    
    total_cols, total_rows = 15, 6
    center_cols, center_rows = 7, 2
    
    base = Image.new("RGB", (W, H), (0, 0, 0))
    grid_w = 6 if style == "cinematic" else 16
    
    tile_w = (W - (total_cols + 1) * grid_w) // total_cols
    tile_h = (H - (total_rows + 1) * grid_w) // total_rows

    center_slots = center_cols * center_rows
    outer_slots = (total_cols * total_rows) - center_slots
    
    favs_to_place = (favs * (center_slots // len(favs) + 1))[:center_slots]
    others_to_place = (others * (outer_slots // len(others) + 1))[:outer_slots]
    random.shuffle(favs_to_place)
    random.shuffle(others_to_place)

    start_col = (total_cols - center_cols) // 2
    end_col = start_col + center_cols
    start_row = (total_rows - center_rows) // 2
    end_row = start_row + center_rows
    
    fav_idx, other_idx = 0, 0
    for r in range(total_rows):
        for c in range(total_cols):
            if start_row <= r < end_row and start_col <= c < end_col:
                img_path = favs_to_place[fav_idx]
                fav_idx += 1
            else:
                img_path = others_to_place[other_idx]
                other_idx += 1
            
            try:
                with Image.open(img_path) as im:
                    im = im.convert("RGB")
                    tile = fit_crop(im, tile_w, tile_h)
                    x = grid_w + c * (tile_w + grid_w)
                    y = grid_w + r * (tile_h + grid_w)
                    base.paste(tile, (x, y))
            except Exception as e:
                print(f"⚠️ Could not process image {img_path}: {e}")

    final_banner = add_vignette(base, strength=0.4)
    final_banner = final_banner.convert("RGBA")
    
    logo_path = LOGO_LIGHT if tone == "light" else LOGO_DARK
    final_banner = paste_logo(final_banner, logo_path, opacity=160)
    
    # --- SAVE AS OPTIMIZED JPEG ---
    # Convert back to RGB (JPEG doesn't support transparency) and save with high quality.
    final_banner.convert("RGB").save(out_name, "JPEG", quality=95, optimize=True)
    
    print(f"✅ Saved {out_name}.")

# ---- create banners ---- #
for fname, style, tone in OUTPUTS:
    make_banner(style, tone, fname)

print("\n✅ Done! Your 4 JPG banners are ready in this folder.")
