import io, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W = H = 1080
S = 2
WHITE = (255, 255, 255)
# palette-driven colors (graphic.py calls set_colors for every post)
NAVY = (14, 11, 74)
LIME = (201, 243, 29)
RIM = (34, 28, 130)
INDIGO = (88, 72, 228)
LAV = (226, 222, 255)
LAV2 = (190, 184, 248)

def set_colors(ink, pop, rim, mid, tint, tint2):
    global NAVY, LIME, RIM, INDIGO, LAV, LAV2
    NAVY, LIME, RIM, INDIGO, LAV, LAV2 = ink, pop, rim, mid, tint, tint2

HEAVY = ["fonts/heavy.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
REG = ["fonts/regular.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
       "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]

def P(v):
    return int(v * S)

def font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, int(size))
        except Exception:
            continue
    return ImageFont.load_default()

def tw(d, s, f):
    return d.textlength(s, font=f)

def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

def shadow(img, box, r, blur=20, dy=12, alpha=80, color=(14, 11, 74)):
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = int(blur * 3)
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((pad, pad + dy, pad + x1 - x0, pad + y1 - y0 + dy), radius=r, fill=alpha)
    m = m.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.new("RGB", (w, h), color), (x0 - pad, y0 - pad), m)

def rr(img, box, r, fill):
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=fill)
    img.paste(layer, (x0, y0), layer)

def paste_rot(img, layer, cx, cy, angle):
    layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)

# ---------- objects (drawn in a 400x400 box) ----------
class Cv:
    def __init__(self):
        self.im = Image.new("RGBA", (P(400), P(400)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
    def ell(self, b, fill=None, outline=None, w=0):
        self.d.ellipse([P(v) for v in b], fill=fill, outline=outline, width=P(w))
    def rect(self, b, r=0, fill=None, outline=None, w=0):
        self.d.rounded_rectangle([P(v) for v in b], radius=P(r), fill=fill, outline=outline, width=P(w))
    def poly(self, pts, fill):
        self.d.polygon([(P(x), P(y)) for x, y in pts], fill=fill)
    def line(self, pts, fill, w):
        self.d.line([(P(x), P(y)) for x, y in pts], fill=fill, width=P(w), joint="curve")
    def pie(self, b, a0, a1, fill):
        self.d.pieslice([P(v) for v in b], a0, a1, fill=fill)
    def arc(self, b, a0, a1, fill, w):
        self.d.arc([P(v) for v in b], a0, a1, fill=fill, width=P(w))
    def text(self, xy, s, size, fill):
        self.d.text((P(xy[0]), P(xy[1])), s, font=font(HEAVY, P(size)), fill=fill, anchor="mm")

def obj_coin(c, t):
    t = (t or "$")[:4].upper()
    c.ell((44, 70, 356, 382), fill=RIM)
    c.ell((44, 46, 356, 358), fill=NAVY)
    c.ell((80, 82, 320, 322), outline=LIME, w=10)
    size = {1: 110, 2: 88, 3: 70, 4: 56}[len(t)]
    c.text((200, 206), t, size, LIME)
    c.arc((58, 60, 342, 344), 198, 262, (255, 255, 255, 200), 12)

def obj_bank(c, t):
    c.poly([(200, 34), (44, 138), (356, 138)], WHITE)
    c.poly([(200, 34), (356, 138), (200, 138)], LAV)
    c.ell((180, 82, 220, 122), fill=LIME)
    c.rect((36, 138, 364, 174), 8, fill=WHITE)
    for i in range(5):
        x = 64 + i * 62
        c.rect((x, 182, x + 38, 302), 8, fill=WHITE)
        c.rect((x + 22, 182, x + 38, 302), 8, fill=LAV)
    c.rect((26, 308, 374, 338), 8, fill=WHITE)
    c.rect((10, 342, 390, 372), 8, fill=LAV2)

def obj_shield(c, t):
    c.poly([(200, 28), (338, 80), (330, 214), (200, 372), (70, 214), (62, 80)], WHITE)
    c.poly([(200, 28), (338, 80), (330, 214), (200, 372)], LAV)
    c.poly([(200, 62), (306, 102), (300, 208), (200, 330), (100, 208), (94, 102)], INDIGO)
    c.line([(148, 200), (192, 244), (262, 152)], LIME, 26)

def obj_lock(c, t):
    c.rect((122, 44, 278, 270), 78, outline=NAVY, w=32)
    c.rect((70, 170, 330, 362), 40, fill=WHITE)
    c.rect((200, 170, 330, 362), 40, fill=LAV)
    c.rect((70, 170, 200, 362), 40, fill=WHITE)
    c.rect((150, 170, 250, 362), 0, fill=WHITE)
    c.ell((172, 232, 228, 288), fill=NAVY)
    c.poly([(188, 276), (212, 276), (220, 330), (180, 330)], NAVY)

def obj_chart_up(c, t):
    for b, col in zip([(52, 270, 112, 360), (132, 220, 192, 360), (212, 160, 272, 360), (292, 100, 352, 360)], [WHITE, LAV, WHITE, INDIGO]):
        c.rect(b, 12, fill=col)
    c.line([(56, 214), (150, 154), (210, 184), (304, 82)], NAVY, 14)
    c.poly([(342, 38), (319, 100), (282, 66)], NAVY)

def obj_chart_down(c, t):
    for b, col in zip([(52, 100, 112, 360), (132, 160, 192, 360), (212, 220, 272, 360), (292, 280, 352, 360)], [WHITE, LAV, WHITE, LAV2]):
        c.rect(b, 12, fill=col)
    c.line([(56, 64), (140, 120), (200, 94), (298, 192)], NAVY, 14)
    c.poly([(338, 238), (278, 210), (316, 176)], NAVY)

def obj_gavel(c, t):
    g = Cv()
    g.rect((116, 60, 284, 166), 28, fill=NAVY)
    g.rect((146, 60, 172, 166), 0, fill=LIME)
    g.rect((228, 60, 254, 166), 0, fill=LIME)
    g.rect((186, 166, 214, 330), 12, fill=WHITE)
    c.im.alpha_composite(g.im.rotate(32, resample=Image.BICUBIC))
    c.rect((150, 326, 372, 372), 16, fill=WHITE)
    c.rect((150, 352, 372, 380), 14, fill=LAV2)

def obj_rocket(c, t):
    c.poly([(150, 220), (84, 322), (150, 298)], INDIGO)
    c.poly([(250, 220), (316, 322), (250, 298)], INDIGO)
    c.poly([(166, 316), (234, 316), (200, 386)], WHITE)
    c.poly([(182, 316), (218, 316), (200, 350)], LAV2)
    c.rect((146, 96, 254, 318), 40, fill=WHITE)
    c.rect((206, 96, 254, 318), 24, fill=LAV)
    c.poly([(200, 24), (254, 114), (146, 114)], NAVY)
    c.ell((168, 150, 232, 214), fill=NAVY)
    c.ell((182, 164, 218, 200), fill=LAV2)

def obj_chip(c, t):
    for i in range(4):
        x = 128 + i * 46
        c.rect((x, 56, x + 20, 112), 6, fill=LAV2)
        c.rect((x, 288, x + 20, 344), 6, fill=LAV2)
        c.rect((56, x, 112, x + 20), 6, fill=LAV2)
        c.rect((288, x, 344, x + 20), 6, fill=LAV2)
    c.rect((92, 92, 308, 308), 30, fill=NAVY)
    c.rect((136, 136, 264, 264), 20, fill=WHITE)
    t = (t or "").upper()[:3]
    if t:
        c.text((200, 202), t, 62 if len(t) < 3 else 50, NAVY)
    else:
        c.ell((172, 172, 228, 228), fill=LIME)

def obj_globe(c, t):
    c.ell((50, 50, 350, 350), fill=WHITE)
    c.ell((120, 50, 280, 350), outline=LAV2, w=8)
    c.ell((176, 50, 224, 350), outline=LAV2, w=8)
    for y in (130, 200, 270):
        c.line([(70 if y != 200 else 52, y), (330 if y != 200 else 348, y)], LAV2, 8)
    c.ell((50, 50, 350, 350), outline=NAVY, w=10)
    c.ell((244, 96, 292, 144), fill=NAVY)

def obj_wallet(c, t):
    c.rect((96, 60, 276, 160), 16, fill=INDIGO)
    c.rect((44, 112, 356, 336), 38, fill=WHITE)
    c.rect((44, 112, 356, 176), 38, fill=LAV)
    c.rect((232, 214, 356, 278), 30, fill=NAVY)
    c.ell((258, 232, 298, 272), fill=LIME)

def obj_swap(c, t):
    c.ell((40, 40, 360, 360), fill=WHITE)
    c.rect((88, 126, 238, 164), 18, fill=NAVY)
    c.poly([(232, 92), (232, 198), (312, 145)], NAVY)
    c.rect((162, 236, 312, 274), 18, fill=INDIGO)
    c.poly([(168, 202), (168, 308), (88, 255)], INDIGO)

# ----- new objects -----
def obj_listing(c, t):
    t = (t or "NEW").upper()[:5]
    c.rect((50, 50, 350, 350), 36, fill=WHITE)
    c.rect((50, 50, 350, 140), 36, fill=NAVY)
    c.rect((50, 100, 350, 140), 0, fill=NAVY)
    c.text((200, 96), t, 46, LIME)
    for i, y in enumerate((166, 230, 294)):
        c.ell((78, y, 122, y + 44), fill=LIME if i == 0 else LAV2)
        c.rect((138, y + 6, 258, y + 20), 7, fill=LAV2)
        c.rect((138, y + 28, 206, y + 38), 5, fill=LAV)
        c.rect((272, y + 4, 326, y + 40), 16, fill=NAVY if i == 0 else LAV)
        if i == 0:
            c.poly([(299, y + 10), (314, y + 28), (284, y + 28)], LIME)

def obj_candles(c, t):
    spec = [(70, 150, 290, 190, 260, 0), (135, 120, 270, 160, 240, 1), (200, 170, 320, 210, 290, 0),
            (265, 110, 280, 140, 240, 1), (330, 60, 230, 90, 200, 1)]
    for x, wt, wb, bt, bb, up in spec:
        c.line([(x, wt), (x, wb)], NAVY, 8)
        c.rect((x - 24, bt, x + 24, bb), 8, fill=WHITE if up else NAVY)
    c.line([(40, 340), (360, 340)], NAVY, 8)
    t = (t or "").upper()[:4]
    if t:
        c.rect((24, 330, 120, 380), 22, fill=INDIGO)
        c.text((72, 355), t, 34, WHITE)

def obj_blocks(c, t):
    c.rect((30, 140, 130, 240), 20, fill=WHITE)
    c.rect((150, 140, 250, 240), 20, fill=LAV)
    c.rect((270, 140, 370, 240), 20, outline=NAVY, w=9)
    c.rect((130, 182, 150, 198), 0, fill=NAVY)
    for x in (230, 250):
        c.rect((x, 182, x + 20, 198), 0, fill=NAVY)
    c.ell((60, 170, 100, 210), fill=LIME)
    c.line([(172, 192), (192, 214), (228, 168)], NAVY, 12)
    c.text((320, 190), "?", 70, NAVY)
    t = (t or "").upper()[:6]
    if t:
        c.text((200, 90), t, 52, NAVY)
    for x in (80, 200, 320):
        c.rect((x - 4, 250, x + 4, 330), 4, fill=LAV2)
    c.rect((60, 330, 340, 350), 10, fill=LAV2)

def obj_nft(c, t):
    rnd = random.Random(sum(ord(ch) * (i + 3) for i, ch in enumerate(t or "nft")))
    c.rect((50, 40, 350, 340), 34, fill=WHITE)
    c.rect((74, 64, 326, 316), 22, fill=LAV)
    cols = [NAVY, INDIGO, LIME, NAVY]
    cell = 36
    ox, oy = 200 - 3.5 * cell, 190 - 3.5 * cell
    for r in range(7):
        for k in range(4):
            if rnd.random() < 0.58:
                col = cols[rnd.randrange(len(cols))]
                for kk in {k, 6 - k}:
                    c.rect((ox + kk * cell, oy + r * cell, ox + (kk + 1) * cell - 2, oy + (r + 1) * cell - 2), 4, fill=col)
    c.rect((220, 322, 350, 378), 26, fill=NAVY)
    c.text((285, 351), "NFT", 36, LIME)

def obj_calendar(c, t):
    t = (t or "").upper()[:6]
    c.rect((50, 70, 350, 350), 30, fill=WHITE)
    c.rect((50, 70, 350, 160), 30, fill=NAVY)
    c.rect((50, 120, 350, 160), 0, fill=NAVY)
    c.rect((110, 40, 134, 100), 12, fill=LAV2)
    c.rect((266, 40, 290, 100), 12, fill=LAV2)
    for i in range(4):
        c.ell((100 + i * 66, 108, 124 + i * 66, 132), fill=LIME if i == 1 else LAV2)
    if t:
        size = 120 if len(t) <= 2 else 84 if len(t) <= 3 else 56
        c.text((200, 252), t, size, NAVY)
    else:
        for r in range(3):
            for k in range(5):
                c.ell((82 + k * 52, 188 + r * 44, 106 + k * 52, 212 + r * 44), fill=INDIGO if (r, k) == (1, 2) else LAV)

def obj_ticket(c, t):
    t = (t or "MINT").upper()[:5]
    c.rect((30, 100, 370, 300), 30, fill=WHITE)
    c.ell((10, 170, 70, 230), fill=(0, 0, 0, 0))
    c.ell((330, 170, 390, 230), fill=(0, 0, 0, 0))
    for y in range(118, 290, 26):
        c.rect((284, y, 292, y + 14), 3, fill=LAV2)
    c.rect((30, 100, 280, 300), 30, fill=WHITE)
    c.text((156, 200), t, 64 if len(t) <= 4 else 52, NAVY)
    c.ell((314, 172, 354, 212), fill=LIME)
    c.rect((306, 232, 362, 246), 7, fill=LAV2)
    c.rect((54, 130, 130, 142), 6, fill=LAV2)

def obj_meme(c, t):
    c.ell((50, 50, 350, 350), fill=WHITE)
    c.ell((78, 214, 138, 264), fill=LAV2)
    c.ell((262, 214, 322, 264), fill=LAV2)
    c.rect((88, 128, 184, 202), 30, fill=NAVY)
    c.rect((216, 128, 312, 202), 30, fill=NAVY)
    c.rect((176, 146, 224, 160), 6, fill=NAVY)
    c.ell((104, 140, 130, 160), fill=(255, 255, 255, 150))
    c.ell((232, 140, 258, 160), fill=(255, 255, 255, 150))
    c.arc((110, 190, 290, 320), 15, 165, NAVY, 16)
    c.ell((176, 276, 224, 322), fill=INDIGO)

def obj_dog(c, t):
    c.poly([(66, 110), (150, 56), (170, 170), (98, 214)], NAVY)
    c.poly([(334, 110), (250, 56), (230, 170), (302, 214)], NAVY)
    c.ell((78, 84, 322, 330), fill=WHITE)
    c.ell((130, 196, 270, 322), fill=LAV)
    c.ell((140, 140, 172, 180), fill=NAVY)
    c.ell((228, 140, 260, 180), fill=NAVY)
    c.ell((148, 146, 160, 158), fill=WHITE)
    c.ell((236, 146, 248, 158), fill=WHITE)
    c.ell((172, 206, 228, 246), fill=NAVY)
    c.line([(200, 246), (200, 272)], NAVY, 9)
    c.arc((166, 252, 200, 292), 0, 180, NAVY, 8)
    c.arc((200, 252, 234, 292), 0, 180, NAVY, 8)
    c.ell((186, 282, 216, 318), fill=LIME)

def obj_frog(c, t):
    c.ell((70, 70, 170, 170), fill=INDIGO)
    c.ell((230, 70, 330, 170), fill=INDIGO)
    c.ell((40, 110, 360, 350), fill=INDIGO)
    c.ell((84, 84, 156, 156), fill=WHITE)
    c.ell((244, 84, 316, 156), fill=WHITE)
    c.ell((106, 100, 142, 140), fill=NAVY)
    c.ell((258, 100, 294, 140), fill=NAVY)
    c.arc((90, 150, 310, 330), 20, 160, NAVY, 14)
    c.ell((80, 236, 124, 270), fill=LAV2)
    c.ell((276, 236, 320, 270), fill=LAV2)
    c.ell((176, 190, 188, 202), fill=NAVY)
    c.ell((212, 190, 224, 202), fill=NAVY)

def obj_warning(c, t):
    c.poly([(200, 30), (372, 336), (28, 336)], NAVY)
    c.poly([(200, 78), (326, 304), (74, 304)], WHITE)
    c.rect((184, 138, 216, 242), 14, fill=NAVY)
    c.ell((182, 256, 218, 292), fill=NAVY)

def obj_magnifier(c, t):
    c.line([(250, 250), (350, 350)], NAVY, 44)
    c.ell((40, 40, 280, 280), fill=LAV)
    c.ell((40, 40, 280, 280), outline=NAVY, w=26)
    for i, h in enumerate((60, 100, 80, 130)):
        c.rect((84 + i * 36, 230 - h, 112 + i * 36, 230), 6, fill=INDIGO if i % 2 else LAV2)
    c.arc((70, 70, 250, 250), 200, 250, (255, 255, 255, 220), 12)

def obj_capitol(c, t):
    c.line([(200, 20), (200, 72)], NAVY, 7)
    c.poly([(204, 20), (258, 36), (204, 52)], LIME)
    c.pie((112, 70, 288, 300), 180, 360, WHITE)
    c.pie((112, 70, 288, 300), 270, 360, LAV)
    c.ell((176, 108, 224, 146), fill=LAV2)
    c.rect((132, 176, 268, 214), 6, fill=WHITE)
    c.rect((200, 176, 268, 214), 6, fill=LAV)
    c.rect((40, 220, 360, 256), 8, fill=WHITE)
    for i in range(6):
        x = 56 + i * 54
        c.rect((x, 262, x + 32, 338), 6, fill=WHITE)
        c.rect((x + 20, 262, x + 32, 338), 6, fill=LAV)
    c.rect((24, 342, 376, 376), 8, fill=LAV2)

def obj_document(c, t):
    c.rect((84, 36, 316, 366), 26, fill=WHITE)
    c.poly([(250, 30), (322, 30), (322, 104)], (0, 0, 0, 0))
    c.poly([(250, 36), (316, 102), (250, 102)], LAV2)
    c.rect((124, 130, 218, 156), 10, fill=NAVY)
    for i, w in enumerate((230, 230, 200, 230, 160)):
        c.rect((124, 184 + i * 32, w + 40, 198 + i * 32), 7, fill=LAV2)
    c.ell((222, 290, 304, 364), fill=LIME)
    c.line([(240, 328), (258, 344), (288, 308)], NAVY, 10)

def obj_vault(c, t):
    c.rect((46, 50, 354, 346), 36, fill=WHITE)
    c.rect((76, 80, 324, 316), 24, fill=LAV)
    c.ell((120, 118, 280, 278), fill=NAVY)
    c.ell((140, 138, 260, 258), fill=LAV2)
    for ang in range(4):
        import math
        a = math.radians(45 + ang * 90)
        c.line([(200, 198), (200 + 78 * math.cos(a) * 0.9, 198 + 78 * math.sin(a) * 0.9)], NAVY, 12)
    c.ell((178, 176, 222, 220), fill=LIME)
    c.rect((36, 120, 62, 168), 6, fill=NAVY)
    c.rect((36, 228, 62, 276), 6, fill=NAVY)
    c.rect((110, 338, 150, 366), 6, fill=NAVY)
    c.rect((250, 338, 290, 366), 6, fill=NAVY)

def obj_bag(c, t):
    t = (t or "$")[:4]
    c.ell((60, 120, 340, 372), fill=WHITE)
    c.poly([(150, 140), (250, 140), (284, 66), (116, 66)], LAV)
    c.rect((140, 56, 260, 92), 14, fill=NAVY)
    c.ell((60, 120, 340, 372), fill=WHITE)
    c.poly([(150, 140), (250, 140), (276, 78), (124, 78)], WHITE)
    c.rect((136, 54, 264, 94), 14, fill=NAVY)
    c.ell((60, 160, 340, 372), fill=WHITE)
    c.text((200, 262), t, 130 if len(t) == 1 else 88 if len(t) <= 3 else 66, NAVY)

def obj_flame(c, t):
    outer = [(200, 24), (252, 100), (316, 176), (322, 262), (270, 346), (200, 376), (130, 346), (78, 262), (90, 190), (140, 130), (160, 80)]
    c.poly(outer, WHITE)
    c.ell((78, 190, 322, 376), fill=WHITE)
    c.poly([(200, 110), (240, 170), (278, 238), (252, 312), (200, 346), (148, 312), (122, 240), (160, 178)], LAV2)
    c.ell((122, 226, 278, 346), fill=LAV2)
    c.poly([(200, 206), (226, 256), (236, 306), (200, 338), (164, 306), (174, 256)], LIME)
    c.ell((164, 290, 236, 340), fill=LIME)

def obj_bolt(c, t):
    pts = [(236, 24), (96, 214), (184, 214), (150, 376), (312, 158), (224, 158)]
    c.poly([(x + 10, y + 12) for x, y in pts], NAVY)
    c.poly(pts, WHITE)
    c.poly([(236, 24), (224, 158), (312, 158)], LAV)

def obj_gamepad(c, t):
    c.rect((90, 96, 170, 136), 18, fill=LAV2)
    c.rect((230, 96, 310, 136), 18, fill=LAV2)
    c.ell((30, 190, 140, 338), fill=WHITE)
    c.ell((260, 190, 370, 338), fill=WHITE)
    c.rect((40, 120, 360, 300), 80, fill=WHITE)
    c.rect((92, 204, 150, 224), 8, fill=NAVY)
    c.rect((111, 185, 131, 243), 8, fill=NAVY)
    for (x, y, col) in ((268, 172, LIME), (312, 204, INDIGO), (268, 236, NAVY), (224, 204, LAV2)):
        c.ell((x - 20, y - 20, x + 20, y + 20), fill=col)
    c.rect((176, 196, 226, 212), 8, fill=LAV2)

def obj_robot(c, t):
    t = (t or "").upper()[:3]
    c.line([(200, 100), (200, 52)], NAVY, 10)
    c.ell((178, 24, 222, 68), fill=INDIGO)
    c.rect((40, 170, 82, 270), 14, fill=LAV2)
    c.rect((318, 170, 360, 270), 14, fill=LAV2)
    c.rect((70, 100, 330, 340), 64, fill=WHITE)
    c.rect((110, 160, 290, 260), 38, fill=NAVY)
    c.ell((140, 188, 180, 232), fill=LIME)
    c.ell((220, 188, 260, 232), fill=LIME)
    if t:
        c.text((200, 304), t, 40, NAVY)
    else:
        c.rect((150, 292, 250, 312), 10, fill=NAVY)

def obj_gift(c, t):
    c.rect((70, 170, 330, 366), 18, fill=WHITE)
    c.rect((50, 128, 350, 196), 18, fill=LAV)
    c.rect((178, 128, 222, 366), 0, fill=INDIGO)
    c.arc((108, 40, 204, 140), 90, 360, INDIGO, 22)
    c.arc((196, 40, 292, 140), 180, 450, INDIGO, 22)
    c.ell((180, 104, 220, 144), fill=INDIGO)

def obj_server(c, t):
    for i, y in enumerate((50, 150, 250)):
        c.rect((50, y, 350, y + 86), 24, fill=WHITE if i != 1 else LAV)
        c.ell((80, y + 28, 110, y + 58), fill=LIME)
        c.rect((130, y + 30, 270, y + 44), 7, fill=LAV2)
        c.rect((130, y + 52, 220, y + 62), 5, fill=LAV2)
        for k in range(3):
            c.ell((290 + k * 18, y + 34, 302 + k * 18, y + 46), fill=NAVY if k == 0 else LAV2)
    c.rect((170, 336, 230, 366), 8, fill=NAVY)
    c.rect((90, 360, 310, 376), 8, fill=NAVY)

def obj_bridge(c, t):
    c.rect((10, 190, 390, 224), 10, fill=WHITE)
    for x in (70, 200, 330):
        c.rect((x - 12, 224, x + 12, 330), 4, fill=WHITE)
    for x0 in (10, 140, 270):
        c.arc((x0 + 6, 224, x0 + 118, 340), 180, 360, LAV2, 18)
    c.rect((10, 330, 390, 370), 10, fill=LAV2)
    c.line([(30, 190), (70, 80), (200, 150), (330, 80), (370, 190)], NAVY, 8)
    for x in (70, 330):
        c.rect((x - 10, 70, x + 10, 190), 4, fill=NAVY)
    c.ell((176, 126, 224, 174), fill=LIME)

def obj_monogram(c, t):
    t = "".join(ch for ch in (t or "W3").upper() if ch.isalnum())[:3] or "W3"
    c.rect((50, 50, 350, 350), 76, fill=WHITE)
    c.rect((50, 200, 350, 350), 76, fill=LAV)
    c.rect((50, 200, 350, 270), 0, fill=LAV)
    c.rect((50, 50, 350, 350), 76, outline=WHITE, w=4)
    c.rect((84, 84, 316, 316), 54, fill=NAVY)
    size = {1: 170, 2: 130, 3: 98}[len(t)]
    c.text((200, 206), t, size, LIME)
    c.ell((282, 62, 338, 118), fill=LIME)
    c.line([(298, 92), (308, 102), (324, 80)], NAVY, 8)

OBJECTS = {"monogram": obj_monogram, "coin": obj_coin, "bank": obj_bank, "shield": obj_shield, "lock": obj_lock,
           "chart_up": obj_chart_up, "chart_down": obj_chart_down, "gavel": obj_gavel,
           "rocket": obj_rocket, "chip": obj_chip, "globe": obj_globe, "wallet": obj_wallet, "swap": obj_swap,
           "listing": obj_listing, "candles": obj_candles, "blocks": obj_blocks, "nft": obj_nft,
           "calendar": obj_calendar, "ticket": obj_ticket, "meme": obj_meme, "dog": obj_dog, "frog": obj_frog,
           "warning": obj_warning, "magnifier": obj_magnifier, "capitol": obj_capitol, "document": obj_document,
           "vault": obj_vault, "bag": obj_bag, "flame": obj_flame, "bolt": obj_bolt, "gamepad": obj_gamepad,
           "robot": obj_robot, "gift": obj_gift, "server": obj_server, "bridge": obj_bridge}

def make_object(name, text, fallback_letter="$"):
    c = Cv()
    fn = OBJECTS.get(str(name).lower().strip())
    if fn is None:
        fn, text = obj_monogram, (fallback_letter or "W3")
    fn(c, text)
    return c.im
