"""
Tạo bộ sticker trong suốt (Transparent PNG Stickers) độ phân giải cao cho 1998 TEAM Photobooth.
Bao gồm các chủ đề:
- Wedding: Trái tim, Nhẫn cưới, Hoa hồng/Vòng hoa, Ly champagne, Nơ tình yêu.
- Birthday: Bánh kem, Bóng bay, Mũ sinh nhật, Ngôi sao lấp lánh, Hộp quà.
- Fun: Kính mát tiệc tùng, Vương miện hoàng gia, Ria mép quý ông, Nơ cổ, Ngôi sao vàng.
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Assets", "Stickers"))

def get_canvas(size=512):
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))

def finalize(img, out_path, target_size=256):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    downscaled = img.resize((target_size, target_size), Image.Resampling.LANCZOS)
    downscaled.save(out_path, "PNG")

def draw_heart(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Double heart: large gold heart + rose red inner
    # Parametric heart: x = 16 sin^3(t), y = 13 cos(t) - 5 cos(2t) - 2 cos(3t) - cos(4t)
    points = []
    for step in range(360):
        t = math.radians(step)
        x = 16 * (math.sin(t) ** 3)
        y = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
        # scale & center (center at 256, 260)
        px = 256 + x * 13.5
        py = 250 + y * 13.5
        points.append((px, py))
    
    # Outer gold glow border
    d.polygon(points, fill=(212, 175, 55, 230), outline=(247, 231, 206, 255))
    
    # Inner rose red heart
    inner_points = []
    for step in range(360):
        t = math.radians(step)
        x = 16 * (math.sin(t) ** 3)
        y = -(13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t))
        px = 256 + x * 11
        py = 250 + y * 11
        inner_points.append((px, py))
    d.polygon(inner_points, fill=(225, 29, 72, 240), outline=(255, 228, 230, 220))
    
    # Highlight reflection curve
    d.arc([160, 160, 260, 260], start=200, end=290, fill=(255, 255, 255, 200), width=12)
    finalize(img, path)

def draw_rings(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Two interlocking golden rings
    # Ring 1
    d.ellipse([90, 150, 310, 370], outline=(212, 175, 55, 255), width=32)
    d.ellipse([106, 166, 294, 354], outline=(245, 222, 136, 255), width=10)
    # Ring 2 (interlocked)
    d.ellipse([200, 150, 420, 370], outline=(229, 193, 88, 255), width=32)
    d.ellipse([216, 166, 404, 354], outline=(255, 248, 220, 255), width=10)
    # Diamond on top of Ring 1
    diamond = [(200, 130), (225, 100), (200, 70), (175, 100)]
    d.polygon(diamond, fill=(224, 242, 254, 255), outline=(56, 189, 248, 255))
    d.line([(175, 100), (225, 100)], fill=(255, 255, 255, 255), width=4)
    d.line([(200, 70), (200, 130)], fill=(255, 255, 255, 255), width=4)
    finalize(img, path)

def draw_champagne(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Two champagne flutes clinking
    # Glass 1 (left tilted)
    d.polygon([(180, 140), (230, 230), (200, 245), (150, 155)], fill=(253, 230, 138, 200), outline=(212, 175, 55, 255))
    d.line([(215, 237), (250, 340)], fill=(212, 175, 55, 255), width=10)
    d.ellipse([220, 330, 280, 360], fill=(212, 175, 55, 255))
    # Glass 2 (right tilted)
    d.polygon([(332, 140), (282, 230), (312, 245), (362, 155)], fill=(253, 230, 138, 200), outline=(212, 175, 55, 255))
    d.line([(297, 237), (262, 340)], fill=(212, 175, 55, 255), width=10)
    d.ellipse([232, 330, 292, 360], fill=(212, 175, 55, 255))
    # Clink spark
    d.ellipse([246, 170, 266, 190], fill=(255, 255, 255, 255))
    d.line([(256, 145), (256, 215)], fill=(245, 222, 136, 255), width=5)
    d.line([(220, 180), (292, 180)], fill=(245, 222, 136, 255), width=5)
    finalize(img, path)

def draw_flower(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Rose / floral blossom
    cx, cy = 256, 256
    petals = 8
    for i in range(petals):
        angle = math.radians(i * (360 / petals))
        px = cx + math.cos(angle) * 75
        py = cy + math.sin(angle) * 75
        d.ellipse([px - 60, py - 60, px + 60, py + 60], fill=(244, 63, 94, 210), outline=(251, 113, 133, 255))
    # Inner petals
    for i in range(6):
        angle = math.radians(i * (360 / 6) + 30)
        px = cx + math.cos(angle) * 45
        py = cy + math.sin(angle) * 45
        d.ellipse([px - 45, py - 45, px + 45, py + 45], fill=(225, 29, 72, 230), outline=(253, 164, 175, 255))
    # Center core
    d.ellipse([cx - 35, cy - 35, cx + 35, cy + 35], fill=(212, 175, 55, 255), outline=(254, 240, 138, 255))
    finalize(img, path)

def draw_cake(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Birthday cake
    # Plate
    d.ellipse([70, 400, 442, 450], fill=(226, 232, 240, 255), outline=(148, 163, 184, 255))
    # Bottom layer
    d.rectangle([110, 300, 402, 410], fill=(251, 113, 133, 255), outline=(225, 29, 72, 255))
    d.ellipse([110, 280, 402, 320], fill=(254, 205, 211, 255), outline=(225, 29, 72, 255))
    # Top layer
    d.rectangle([160, 210, 352, 295], fill=(253, 164, 175, 255), outline=(225, 29, 72, 255))
    d.ellipse([160, 195, 352, 230], fill=(255, 228, 230, 255), outline=(225, 29, 72, 255))
    # Candles
    for cx in [210, 256, 302]:
        d.rectangle([cx - 6, 140, cx + 6, 205], fill=(56, 189, 248, 255), outline=(14, 165, 233, 255))
        # Flame
        d.polygon([(cx, 105), (cx + 8, 130), (cx, 138), (cx - 8, 130)], fill=(245, 158, 11, 255))
        d.polygon([(cx, 115), (cx + 4, 130), (cx, 135), (cx - 4, 130)], fill=(254, 240, 138, 255))
    finalize(img, path)

def draw_balloons(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # 3 colorful party balloons
    # Balloon 1 (pink left)
    d.ellipse([90, 80, 250, 270], fill=(244, 63, 94, 230), outline=(251, 113, 133, 255))
    d.polygon([(160, 270), (180, 270), (170, 285)], fill=(244, 63, 94, 255))
    d.line([(170, 285), (256, 440)], fill=(203, 213, 225, 255), width=4)
    # Balloon 2 (gold right)
    d.ellipse([262, 90, 422, 280], fill=(234, 179, 8, 230), outline=(250, 204, 21, 255))
    d.polygon([(332, 280), (352, 280), (342, 295)], fill=(234, 179, 8, 255))
    d.line([(342, 295), (256, 440)], fill=(203, 213, 225, 255), width=4)
    # Balloon 3 (cyan center front)
    d.ellipse([176, 130, 336, 320], fill=(14, 165, 233, 235), outline=(56, 189, 248, 255))
    d.polygon([(246, 320), (266, 320), (256, 335)], fill=(14, 165, 233, 255))
    d.line([(256, 335), (256, 440)], fill=(203, 213, 225, 255), width=5)
    finalize(img, path)

def draw_hat(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Party cone hat
    d.polygon([(256, 70), (120, 410), (392, 410)], fill=(147, 51, 234, 240), outline=(192, 132, 252, 255))
    # Colorful stripes
    d.line([(155, 330), (357, 330)], fill=(234, 179, 8, 255), width=18)
    d.line([(190, 240), (322, 240)], fill=(236, 72, 153, 255), width=18)
    d.line([(225, 150), (287, 150)], fill=(14, 165, 233, 255), width=18)
    # Pom-pom top
    d.ellipse([230, 44, 282, 96], fill=(245, 158, 11, 255), outline=(254, 240, 138, 255))
    # Base pom-poms
    for bx in range(120, 400, 36):
        d.ellipse([bx - 12, 400, bx + 12, 424], fill=(251, 191, 36, 255))
    finalize(img, path)

def draw_crown(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Royal golden crown
    crown_poly = [
        (80, 370), (432, 370), (410, 180), (330, 260),
        (256, 130), (182, 260), (102, 180)
    ]
    d.polygon(crown_poly, fill=(212, 175, 55, 250), outline=(254, 240, 138, 255))
    # Jewels on tips
    for px, py in [(102, 175), (256, 125), (410, 175)]:
        d.ellipse([px - 16, py - 16, px + 16, py + 16], fill=(225, 29, 72, 255), outline=(255, 255, 255, 255))
    # Base band jewels
    d.rectangle([80, 345, 432, 385], fill=(180, 140, 30, 255), outline=(254, 240, 138, 255))
    for jx in range(130, 400, 60):
        d.ellipse([jx - 10, 355, jx + 10, 375], fill=(56, 189, 248, 255))
    finalize(img, path)

def draw_glasses(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Cool sunglasses
    # Left lens
    d.rounded_rectangle([60, 200, 230, 300], radius=35, fill=(15, 23, 42, 250), outline=(212, 175, 55, 255), width=10)
    # Right lens
    d.rounded_rectangle([282, 200, 452, 300], radius=35, fill=(15, 23, 42, 250), outline=(212, 175, 55, 255), width=10)
    # Bridge
    d.arc([220, 210, 292, 260], start=180, end=360, fill=(212, 175, 55, 255), width=10)
    # Left & right temples
    d.line([(60, 220), (20, 205)], fill=(212, 175, 55, 255), width=10)
    d.line([(452, 220), (492, 205)], fill=(212, 175, 55, 255), width=10)
    # Glare lines on lenses
    d.line([(90, 280), (130, 220)], fill=(255, 255, 255, 140), width=8)
    d.line([(312, 280), (352, 220)], fill=(255, 255, 255, 140), width=8)
    finalize(img, path)

def draw_star(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Golden 5-point star
    cx, cy = 256, 256
    points = []
    for i in range(10):
        r = 180 if i % 2 == 0 else 75
        angle = math.radians(i * 36 - 90)
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    d.polygon(points, fill=(245, 158, 11, 245), outline=(254, 240, 138, 255))
    # Inner star
    inner_pts = []
    for i in range(10):
        r = 135 if i % 2 == 0 else 55
        angle = math.radians(i * 36 - 90)
        inner_pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    d.polygon(inner_pts, fill=(251, 191, 36, 255))
    finalize(img, path)

def draw_mustache(path):
    img = get_canvas(512)
    d = ImageDraw.Draw(img)
    # Dapper gentleman moustache
    # Left curl
    d.pieslice([80, 220, 260, 340], start=180, end=360, fill=(26, 32, 44, 255))
    d.pieslice([120, 200, 256, 300], start=0, end=180, fill=(26, 32, 44, 255))
    # Right curl
    d.pieslice([252, 220, 432, 340], start=180, end=360, fill=(26, 32, 44, 255))
    d.pieslice([256, 200, 392, 300], start=0, end=180, fill=(26, 32, 44, 255))
    finalize(img, path)

def main():
    wedding_dir = os.path.join(BASE_DIR, "wedding")
    birthday_dir = os.path.join(BASE_DIR, "birthday")
    fun_dir = os.path.join(BASE_DIR, "fun")

    draw_heart(os.path.join(wedding_dir, "heart.png"))
    draw_rings(os.path.join(wedding_dir, "rings.png"))
    draw_champagne(os.path.join(wedding_dir, "champagne.png"))
    draw_flower(os.path.join(wedding_dir, "flower.png"))

    draw_cake(os.path.join(birthday_dir, "cake.png"))
    draw_balloons(os.path.join(birthday_dir, "balloons.png"))
    draw_hat(os.path.join(birthday_dir, "hat.png"))

    draw_crown(os.path.join(fun_dir, "crown.png"))
    draw_glasses(os.path.join(fun_dir, "glasses.png"))
    draw_star(os.path.join(fun_dir, "star.png"))
    draw_mustache(os.path.join(fun_dir, "mustache.png"))

    print("Generated all stickers successfully.")

if __name__ == "__main__":
    main()
