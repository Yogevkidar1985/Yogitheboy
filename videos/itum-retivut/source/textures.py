import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy.ndimage import gaussian_filter
rng = np.random.default_rng(11)
W, H = 1080, 1000
def noise(h, w, s, amp=1.0):
    n = gaussian_filter(rng.standard_normal((h, w)), s); return n / (np.abs(n).max() + 1e-9) * amp

# ---------- room ----------
img = np.zeros((H, W, 3), np.float32)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
BW_R, TOP, BOT = 800, 170, 860
def poly_mask(pts):
    m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).polygon(pts, fill=255); return np.asarray(m, np.float32) / 255
back = poly_mask([(0, TOP), (BW_R, TOP), (BW_R, BOT), (0, BOT)])
ceil = poly_mask([(0, 0), (W, 0), (W, 40), (BW_R, TOP), (0, TOP)])
side = poly_mask([(BW_R, TOP), (W, 40), (W, H), (BW_R, BOT)])
floor = poly_mask([(0, BOT), (BW_R, BOT), (W, H), (0, H)])
plaster = noise(H, W, 1.2, 0.012) + noise(H, W, 6, 0.018) + noise(H, W, 40, 0.02)
# back wall: warm off-white, lit from the window at right
light = 0.90 + 0.08 * (xx / BW_R) - 0.05 * ((yy - TOP) / (BOT - TOP))
wallc = np.array([0.93, 0.925, 0.905])
img += back[..., None] * (wallc * (light + plaster)[..., None])
# ceiling slightly darker/cooler
img += ceil[..., None] * (np.array([0.86, 0.87, 0.88]) * (0.95 + plaster * 0.5 - 0.06 * (1 - yy / TOP))[..., None])
# side wall in shade
img += side[..., None] * (np.array([0.80, 0.80, 0.78]) * (0.92 + plaster - 0.06 * ((xx - BW_R) / (W - BW_R)))[..., None])
# floor: light oak planks in perspective
vx, vy = 400, -600  # vanishing-ish
plank = np.sin((xx - 400) / (1 + np.clip(yy - BOT, 0, None) * 0.012) * 0.06) * 0.5 + 0.5
wood = np.array([0.72, 0.60, 0.46]) * (0.85 + 0.1 * plank + noise(H, W, 2, 0.05) + 0.12 * (yy - BOT) / (H - BOT))[..., None]
img += floor[..., None] * wood
# ambient occlusion along edges
def line_ao(p0, p1, width, strength):
    m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).line([p0, p1], fill=255, width=width)
    a = gaussian_filter(np.asarray(m, np.float32) / 255, width / 2); return a / max(a.max(), 1e-6) * strength
ao = line_ao((0, TOP), (BW_R, TOP), 40, 0.10) + line_ao((BW_R, TOP), (BW_R, BOT), 50, 0.14) + line_ao((0, BOT), (BW_R, BOT), 30, 0.10) + line_ao((BW_R, TOP), (W, 40), 30, 0.08)
img *= (1 - ao)[..., None]
img = np.clip(img, 0, 1)
im = Image.fromarray((img * 255).astype(np.uint8))
d = ImageDraw.Draw(im, 'RGBA')
# cornice
d.polygon([(0, TOP - 4), (BW_R, TOP - 4), (BW_R, TOP + 14), (0, TOP + 14)], fill=(246, 246, 244, 255))
d.line([(0, TOP + 14), (BW_R, TOP + 14)], fill=(200, 200, 196, 255), width=3)
d.polygon([(BW_R, TOP - 4), (W, 36), (W, 56), (BW_R, TOP + 14)], fill=(226, 226, 222, 255))
# skirting
d.polygon([(0, BOT - 34), (BW_R, BOT - 34), (BW_R, BOT), (0, BOT)], fill=(245, 245, 242, 255))
d.line([(0, BOT - 34), (BW_R, BOT - 34)], fill=(205, 205, 200, 255), width=3)
d.polygon([(BW_R, BOT - 34), (W, BOT - 34 + 70 - 10), (W, H), (BW_R, BOT)], fill=(222, 222, 218, 255))
# window on side wall (perspective quad) with sky
win = [(865, 300), (1040, 230), (1040, 700), (865, 660)]
d.polygon(win, fill=(250, 250, 248, 255))
inner = [(880, 312), (1026, 254), (1026, 684), (880, 648)]
d.polygon(inner, fill=(176, 212, 232, 255))
d.line([(953, 283), (953, 668)], fill=(250, 250, 248, 255), width=10)
d.polygon([(865, 660), (1040, 700), (1040, 716), (858, 674)], fill=(236, 236, 232, 255))
# socket on back wall
d.rounded_rectangle([120, 740, 176, 796], 8, fill=(250, 250, 248, 255), outline=(190, 190, 186, 255), width=2)
d.ellipse([136, 758, 146, 768], fill=(150, 150, 146, 255)); d.ellipse([150, 758, 160, 768], fill=(150, 150, 146, 255))
im = im.filter(ImageFilter.GaussianBlur(0.6))
# window light spill on floor and wall
spill = Image.new('RGBA', (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(spill)
sd.polygon([(640, BOT + 10), (900, 840), (1080, 1000), (700, 1000)], fill=(255, 244, 214, 70))
spill = spill.filter(ImageFilter.GaussianBlur(30)); im = Image.alpha_composite(im.convert('RGBA'), spill)
im.convert('RGB').save('www/room.jpg', quality=93)

# ---------- stains ----------
S = 640
y, x = np.mgrid[0:S, 0:S].astype(np.float32)
cx, cy = S / 2, S * 0.36
r = np.sqrt(((x - cx) / 1.0) ** 2 + ((y - cy) / 0.92) ** 2) / (S * 0.34)
field = 1 - r + noise(S, S, 18, 0.32) + noise(S, S, 6, 0.08)
# drips: downward lobes
for dx, L in ((-90, 210), (40, 260), (120, 160)):
    lobe = np.exp(-((x - cx - dx) ** 2) / (2 * 14 ** 2)) * np.clip((y - cy) / L, 0, 1) * (y < cy + L + 60) * (1 - np.clip((y - cy - L) / 60, 0, 1))
    field += 0.55 * lobe
m = np.clip((field - 0.05) * 6, 0, 1)
edge = np.clip(1 - np.abs(field - 0.08) * 10, 0, 1)  # tide line
ring2 = np.clip(1 - np.abs(field - 0.32) * 14, 0, 1) * 0.6
mott = noise(S, S, 3, 1) * 0.5 + 0.5
def rgba(rgb, a):
    out = np.zeros((S, S, 4), np.float32); out[..., :3] = rgb; out[..., 3] = np.clip(a, 0, 1); return out
wet_rgb = np.stack([0.48 + 0.08 * mott, 0.40 + 0.06 * mott, 0.27 + 0.04 * mott], -1)
wet_rgb = wet_rgb * (1 - 0.35 * edge[..., None]) * (1 - 0.15 * ring2[..., None])
inner = np.clip(field * 2.2, 0, 1)
wet_a = m * (0.22 + 0.22 * mott) * (1 - 0.35 * inner) + edge * 0.5 + ring2 * 0.2
# mold specks near top edge
spk = np.zeros((S, S), np.float32)
for _ in range(110):
    px = rng.normal(cx, 130); py = rng.normal(cy - 120, 40)
    if 0 <= px < S and 0 <= py < S: spk[int(py), int(px)] = rng.uniform(0.6, 1)
spk = np.clip(gaussian_filter(spk, 1.4) * 22, 0, 1) * (field > 0.1) * 0.45
wet_rgb = wet_rgb * (1 - 0.6 * spk[..., None]); wet_a = np.clip(wet_a + spk * 0.6, 0, 0.95)
Image.fromarray((rgba(wet_rgb, wet_a) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)).save('www/stain_wet.png')
dry_rgb = np.stack([0.62 + 0.0 * mott, 0.54 + 0 * mott, 0.36 + 0 * mott], -1)
dry_a = edge * 0.38 + ring2 * 0.12 + m * 0.07
Image.fromarray((rgba(dry_rgb, dry_a) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5)).save('www/stain_dry.png')
# bleed-through (yellowish ghost under paint)
bl_rgb = np.stack([0.70 + 0 * mott, 0.60 + 0 * mott, 0.38 + 0 * mott], -1)
bl_a = (m * 0.28 + edge * 0.45) * (0.7 + 0.3 * mott)
Image.fromarray((rgba(bl_rgb, bl_a) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)).save('www/stain_bleed.png')
# fresh paint texture (bright, with vertical roller streaks)
PW, PH = 1080, 1000
streak = gaussian_filter(rng.standard_normal((1, PW)), (0, 3)).repeat(PH, 0) * 0.012 + noise(PH, PW, 1.0, 0.006)
paint = np.clip(np.array([0.975, 0.972, 0.958]) * (1 + streak)[..., None], 0, 1)
Image.fromarray((paint * 255).astype(np.uint8)).save('www/paint.jpg', quality=95)
print('ok')
