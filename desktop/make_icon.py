"""Generate desktop/icon.ico (emerald→cyan rounded square with "FI")."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
grad = Image.new("RGBA", (SIZE, SIZE))
top, bottom = (16, 185, 129), (34, 211, 238)
for y in range(SIZE):
    t = y / (SIZE - 1)
    color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,)
    ImageDraw.Draw(grad).line([(0, y), (SIZE, y)], fill=color)
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=56, fill=255)
img.paste(grad, (0, 0), mask)
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("segoeuib.ttf", 120)
except OSError:
    font = ImageFont.load_default()
box = draw.textbbox((0, 0), "FI", font=font)
w, h = box[2] - box[0], box[3] - box[1]
draw.text(((SIZE - w) / 2 - box[0], (SIZE - h) / 2 - box[1]), "FI", font=font, fill=(4, 17, 12, 255))
out = Path(__file__).resolve().parent / "icon.ico"
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
