import os, io, json, time, requests, feedparser
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss.xml",
]
MODEL = "gemini-3.8-flash"
MIN_SCORE = 7
MAX_SCORED = 6
MAX_DRAFTS = 4
MAX_AGE_HOURS = 24

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]
MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
errors = []

PROMPT = """You are the editor of @YoXo_Station, a Web3 news account on X.
Given a news story, do three things.

1) Score 1-10 how likely people are to actually read and share it
(big numbers, big names, hacks, major launches, regulation, surprising facts score high;
routine price commentary, sponsored content, and opinion pieces score low).

2) Write ONE X post in an extended news style, 900-1300 characters total.
FORMAT:
Line 1 (hook): "JUST IN:" or "BREAKING:" + the single most surprising fact, with a number if one exists. ALL CAPS, max 20 words.
Then a blank line, then 4-5 short paragraphs of 1-3 sentences each:
- what happened, with the key numbers and names
- the key details, or a short direct quote from the source
- how it unfolded or the timeline, if the source gives one
- background or context that helps a reader understand it
- closing paragraph: what happens next or what to watch, using only what the source says (reactions, deadlines, next steps, open questions). If the source gives none, close with the most relevant remaining detail. Do not force a crypto or Web3 angle that the source does not have.
Write plainly so anyone gets what the news really means. Use $CASHTAGS for tokens. No hashtags, no emojis, no thread bait.
RULES: Use ONLY facts in the source. Never invent numbers, quotes or names.
Keep words like "reportedly" or "alleged". No price predictions or financial advice.

3) Fill in the text for a bold square social media graphic ("graphic"):
- kicker: 1-3 words naming the topic or project (example: "Near Intents")
- headline: max 8 words, punchy, states the news. Do NOT repeat the big_number in it.
- highlight: ONE word copied exactly from your headline that deserves emphasis.
- big_number: the single most striking figure from the story, short (examples: "$3.8M", "48H", "12%"). Use "" if the story has no strong number.
- number_label: max 7 words saying what the big number is.
- tiles: [] or ONE extra stat {"value": max 6 chars, "label": max 2 words}. Only if the source has it.
- tag: sticker text, max 2 short words (examples: "BREAKING", "JUST IN", "HACK", "RECORD").
- source: the publication name.
- object: pick the ONE object that best matches what the story is about, from exactly this list:
  coin (a specific token, coin or stablecoin), bank (a bank, central bank, government agency, institution, ETF issuer, company),
  shield (security, audits, protection), lock (hacks, exploits, stolen or frozen funds), gavel (lawsuits, courts, regulation, SEC),
  chart_up (prices or flows rising, records), chart_down (prices or flows falling, losses), rocket (launches, mainnet, airdrops, rallies),
  chip (AI, hardware, mining, infrastructure), globe (countries, global adoption), wallet (wallets, payments, custody, accounts),
  swap (exchanges, trading, bridges, mergers).
- object_text: if object is "coin", the token's ticker, max 4 letters (examples: "BTC", "ETH", "SOL", "USDT"). If object is "chip", a 2-3 letter label like "AI" or "GPU". Otherwise "".
Everything in the graphic must come from the source. Never invent anything.

Also give a one-line "verify" note: what the editor should double-check before posting.

Return ONLY JSON:
{"score": int, "post": str, "verify": str, "graphic": {"kicker": str, "headline": str, "highlight": str, "big_number": str, "number_label": str, "tiles": [{"value": str, "label": str}], "tag": str, "source": str, "object": str, "object_text": str}}

STORY:
"""

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
    c.rect((44, 112, 356, 176), 38, fill=LAV)
    c.rect((232, 214, 356, 278), 30, fill=NAVY)
    c.ell((258, 232, 298, 272), fill=LIME)

def obj_swap(c, t):
    c.ell((40, 40, 360, 360), fill=WHITE)
    c.rect((88, 126, 238, 164), 18, fill=NAVY)
    c.poly([(232, 92), (232, 198), (312, 145)], NAVY)
    c.rect((162, 236, 312, 274), 18, fill=INDIGO)
    c.poly([(168, 202), (168, 308), (88, 255)], INDIGO)

OBJECTS = {"coin": obj_coin, "bank": obj_bank, "shield": obj_shield, "lock": obj_lock,
           "chart_up": obj_chart_up, "chart_down": obj_chart_down, "gavel": obj_gavel,
           "rocket": obj_rocket, "chip": obj_chip, "globe": obj_globe, "wallet": obj_wallet, "swap": obj_swap}

def make_object(name, text, fallback_letter="$"):
    c = Cv()
    fn = OBJECTS.get(str(name).lower().strip())
    if fn is None:
        fn, text = obj_coin, (text or fallback_letter)
    fn(c, text)
    return c.im

# ---------- text helpers ----------
def clean(w):
    return "".join(ch for ch in w if ch.isalnum()).lower()

def pick_highlight(words, given):
    g = clean(given or "")
    if g:
        for w in words:
            if clean(w) == g:
                return w
    for w in words:
        if any(ch.isdigit() for ch in w) or "$" in w:
            return w
    return max(words, key=lambda x: len(clean(x))) if words else ""

def layout(d, words, f, max_w, hl, pad):
    sp = tw(d, " ", f)
    lines, cur, cw = [], [], 0
    for w in words:
        ww = tw(d, w, f) + (2 * pad if w == hl else 0)
        add = ww if not cur else sp + ww
        if cur and cw + add > max_w:
            lines.append(cur)
            cur, cw = [w], ww
        else:
            cur.append(w)
            cw += add
    if cur:
        lines.append(cur)
    return lines

def arrow(d, cx, cy, r, bg, fg):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bg)
    a = r * 0.42
    wd = max(2, int(r * 0.16))
    d.line((cx - a, cy + a, cx + a, cy - a), fill=fg, width=wd)
    d.line((cx - a * 0.1, cy - a, cx + a, cy - a), fill=fg, width=wd)
    d.line((cx + a, cy - a, cx + a, cy + a * 0.1), fill=fg, width=wd)

# ---------- main render (1:1) ----------
def render(g, out_path=None):
    img = gradient()
    d = ImageDraw.Draw(img)

    hw = str(g.get("headline", "")).upper().split()
    headline = ""
    for w_ in hw:
        if len((headline + " " + w_).strip()) > 80:
            break
        headline = (headline + " " + w_).strip()
    number = str(g.get("big_number", ""))[:9]
    label = str(g.get("number_label", ""))[:44]
    kicker = str(g.get("kicker", "")).upper()[:24]
    sticker = str(g.get("tag", "BREAKING")).upper()[:14] or "BREAKING"
    tiles = (g.get("tiles") or [])[:1]
    source = str(g.get("source", ""))[:20]

    # lime shapes bleeding off the corners
    d.ellipse((P(W - 200), P(-200), P(W + 200), P(200)), fill=LIME)
    d.ellipse((P(-200), P(800), P(120), P(1120)), fill=(171, 224, 20))

    # top pill
    fp = font(REG, P(22))
    ptxt = kicker if kicker else "WEB3 NEWS"
    ptxt = " ".join(ptxt) if len(ptxt) <= 12 else ptxt
    pw = tw(d, ptxt, fp) + P(44)
    rr(img, (P(64), P(54), P(64) + pw, P(102)), P(24), (255, 255, 255, 46))
    d.rounded_rectangle((P(64), P(54), P(64) + pw, P(102)), radius=P(24), outline=WHITE, width=P(2))
    d.text((P(64) + P(22), P(78)), ptxt, font=fp, fill=WHITE, anchor="lm")

    # sticker
    sz = P(156)
    st = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    sd.ellipse((0, 0, sz - 1, sz - 1), fill=NAVY)
    parts = sticker.split()[:2]
    fs = font(HEAVY, P(30))
    while max(tw(sd, p, fs) for p in parts) > sz * 0.78 and fs.size > P(16):
        fs = font(HEAVY, fs.size - 2)
    lh = fs.size * 1.15
    y0 = sz / 2 - lh * (len(parts) - 1) / 2
    for i, p in enumerate(parts):
        sd.text((sz / 2, y0 + i * lh), p, font=fs, fill=LIME, anchor="mm")
    paste_rot(img, st, P(884), P(112), -12)

    # headline with highlighted word
    words = headline.split()
    hl = pick_highlight(words, g.get("highlight"))
    left, max_w = P(64), P(952)
    top_y, max_h = P(190), P(392)
    size = P(116)
    while True:
        f = font(HEAVY, size)
        pad = size * 0.14
        lines = layout(d, words, f, max_w, hl, pad)
        if (len(lines) <= 4 and len(lines) * size * 1.14 <= max_h) or size <= P(54):
            break
        size -= P(4)
    base = top_y + size * 0.82
    for ln in lines:
        x = left
        for w in ln:
            ww = tw(d, w, f)
            if w == hl:
                cap = -f.getbbox("H", anchor="ls")[1]
                rr(img, (x, base - cap - size * 0.16, x + ww + 2 * pad, base + size * 0.2), int(size * 0.22), LIME + (255,))
                d.text((x + pad, base), w, font=f, fill=NAVY, anchor="ls")
                x += ww + 2 * pad
            else:
                d.text((x, base), w, font=f, fill=WHITE, anchor="ls")
                x += ww
            x += tw(d, " ", f)
        base += size * 1.14

    # hero object on a lime disc (right side, bottom aligned with the card)
    hx, hy = P(812), P(768)
    d.ellipse((hx - P(182), hy - P(182), hx + P(182), hy + P(182)), fill=LIME)
    obj = make_object(g.get("object"), g.get("object_text"), (kicker[:1] or "$"))
    obj = obj.rotate(-5, expand=True, resample=Image.BICUBIC)
    sh = obj.split()[3].point(lambda v: int(v * 0.28)).filter(ImageFilter.GaussianBlur(P(10)))
    ox, oy = hx - obj.width // 2, hy - obj.height // 2
    img.paste(Image.new("RGB", obj.size, NAVY), (ox, oy + P(16)), sh)
    img.paste(obj, (ox, oy), obj)
    d = ImageDraw.Draw(img)

    # number card (left)
    cx0, cx1 = P(64), P(580)
    inner_l = cx0 + P(36)
    max_num_w = (cx1 - cx0) - P(72)
    main = number if number else (kicker if kicker else "LATEST")
    n_size = P(150) if number else P(70)
    while n_size > P(44):
        fn = font(HEAVY, n_size)
        l, t, r, b = d.textbbox((0, 0), main, font=fn)
        if (r - l) <= max_num_w:
            break
        n_size -= P(4)
    fn = font(HEAVY, n_size)
    l, t, r, b = d.textbbox((0, 0), main, font=fn, anchor="ls")
    glyph_h = -t
    sub = label if number else "Latest update" + (f" via {source}" if source else "")
    fl = font(REG, P(28))
    while tw(d, sub, fl) > max_num_w and fl.size > P(16):
        fl = font(REG, fl.size - 2)
    pill_h = P(54)
    card_h = P(34) + glyph_h + P(22) + P(30) + P(22) + pill_h + P(34)
    card_bottom = P(956)
    card_top = card_bottom - card_h
    shadow(img, (cx0, card_top, cx1, card_bottom), P(36), blur=24, dy=16, alpha=95)
    rr(img, (cx0, card_top, cx1, card_bottom), P(36), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    gy = card_top + P(34) + glyph_h
    d.text((inner_l, gy), main, font=fn, fill=NAVY, anchor="ls")
    d.text((inner_l, gy + P(22) + fl.size * 0.8), sub, font=fl, fill=MUTED, anchor="ls")

    # via-source pill
    pt = ("VIA " + source.upper()) if source else "WEB3 NEWS"
    fpl = font(HEAVY, P(22))
    pwid = tw(d, pt, fpl) + P(34) + P(52)
    py0 = card_bottom - P(34) - pill_h
    rr(img, (inner_l, py0, inner_l + pwid, py0 + pill_h), pill_h // 2, LIME + (255,))
    d = ImageDraw.Draw(img)
    d.text((inner_l + P(20), py0 + pill_h / 2), pt, font=fpl, fill=NAVY, anchor="lm")
    arrow(d, inner_l + pwid - P(28), py0 + pill_h / 2, P(17), NAVY, LIME)

    # floating stat chip (optional)
    if tiles:
        v = str(tiles[0].get("value", ""))[:6]
        lb = str(tiles[0].get("label", ""))[:16]
        cw, ch = P(170), P(116)
        chip = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        cd = ImageDraw.Draw(chip)
        cd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=P(26), fill=WHITE)
        fv = font(HEAVY, P(44))
        while tw(cd, v, fv) > cw - P(28) and fv.size > P(20):
            fv = font(HEAVY, fv.size - 2)
        cd.text((cw / 2, ch * 0.40), v, font=fv, fill=NAVY, anchor="mm")
        flb = font(REG, P(18))
        while tw(cd, lb, flb) > cw - P(20) and flb.size > P(11):
            flb = font(REG, flb.size - 1)
        cd.text((cw / 2, ch * 0.78), lb, font=flb, fill=MUTED, anchor="mm")
        cx_, cy_ = P(662), P(890)
        shadow(img, (cx_ - cw // 2, cy_ - ch // 2, cx_ + cw // 2, cy_ + ch // 2), P(26), blur=14, dy=10, alpha=90)
        paste_rot(img, chip, cx_, cy_, 5)
        d = ImageDraw.Draw(img)

    # footer bar
    fy0, fy1 = P(986), P(1040)
    cx0f, cx1f = P(64), P(1016)
    shadow(img, (cx0f, fy0, cx1f, fy1), P(27), blur=12, dy=6, alpha=60)
    rr(img, (cx0f, fy0, cx1f, fy1), P(27), (70, 56, 214, 245))
    d = ImageDraw.Draw(img)
    d.ellipse((cx0f + P(12), fy0 + P(9), cx0f + P(12) + P(36), fy0 + P(9) + P(36)), fill=LIME)
    d.text((cx0f + P(30), fy0 + P(27)), "Y", font=font(HEAVY, P(20)), fill=NAVY, anchor="mm")
    ff = font(REG, P(22))
    d.text
