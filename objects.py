import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W = H = 1080
S = 2
NAVY = (14, 11, 74)
LIME = (201, 243, 29)
DLIME = (150, 205, 12)
WHITE = (255, 255, 255)
LAV = (226, 222, 255)
LAV2 = (190, 184, 248)
INDIGO = (88, 72, 228)
MUTED = (84, 78, 150)
TOP, MID, BOT = (56, 44, 210), (88, 72, 228), (224, 220, 252)

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

def gradient():
    img = Image.new("RGB", (P(W), P(H)))
    d = ImageDraw.Draw(img)
    for y in range(P(H)):
        t = y / (P(H) - 1)
        c = lerp(TOP, MID, t / 0.5) if t < 0.5 else lerp(MID, BOT, ((t - 0.5) / 0.5) ** 1.1)
        d.line((0, y, P(W), y), fill=c)
    return img

def shadow(img, box, r, blur=20, dy=12, alpha=80):
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = int(blur * 3)
    w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((pad, pad + dy, pad + x1 - x0, pad + y1 - y0 + dy), radius=r, fill=alpha)
    m = m.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.new("RGB", (w, h), NAVY), (x0 - pad, y0 - pad), m)

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
    def arc(self, b, a0, a1, fill, w):
        self.d.arc([P(v) for v in b], a0, a1, fill=fill, width=P(w))
    def text(self, xy, s, size, fill):
        self.d.text((P(xy[0]), P(xy[1])), s, font=font(HEAVY, P(size)), fill=fill, anchor="mm")

def obj_coin(c, t):
    t = (t or "$")[:4].upper()
    c.ell((44, 70, 356, 382), fill=(34, 28, 130))
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
    pts = [(200, 28), (338, 80), (330, 214), (200, 372), (70, 214), (62, 80)]
    c.poly(pts, WHITE)
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
    rot = g.im.rotate(32, resample=Image.BICUBIC)
    c.im.alpha_composite(rot)
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
    c.rect((44, 112, 356,
