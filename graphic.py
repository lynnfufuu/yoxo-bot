import io, colorsys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from objects import *

def hls(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h % 1.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return (int(r * 255), int(g * 255), int(b * 255))

def lum(c):
    def f(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])

def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

def best_text(bgc, ink):
    return WHITE if contrast(WHITE, bgc) >= contrast(ink, bgc) else ink

OFFS = [0.5, 0.333, 0.667, 0.417, 0.583, 0.25]

def pick_pop(ha, ink):
    for L in (0.58, 0.64, 0.70, 0.76, 0.82):
        c = hls(ha, L, 1.0)
        if contrast(ink, c) >= 6.0:
            return c
    return hls(ha, 0.82, 1.0)

def pick_disc(ha, bgbot):
    fallback = None
    for L in (0.50, 0.44, 0.56, 0.38, 0.62, 0.32, 0.68):
        c = hls(ha, L, 0.95)
        if 0.20 <= lum(c) <= 0.42:
            if contrast(c, bgbot) >= 1.25:
                return c
            if fallback is None:
                fallback = c
    return fallback or hls(ha, 0.5, 0.95)

def make_palette(k):
    h = (0.07 + k * 0.381966) % 1.0
    ha = (h + OFFS[(k // 3 + k) % len(OFFS)]) % 1.0
    mode = ["dark", "light", "vivid"][k % 3]
    ink, rim = hls(h, 0.12, 0.55), hls(h, 0.22, 0.6)
    mid, tint, tint2 = hls(h, 0.40, 0.72), hls(h, 0.93, 0.75), hls(h, 0.80, 0.65)
    pop = pick_pop(ha, ink)
    muted = hls(h, 0.40, 0.45)
    if mode == "vivid":
        bgs = [hls(h, 0.44, 0.85), hls(h, 0.50, 0.88), hls(h, 0.58, 0.85)]
        tw_ = min(contrast(WHITE, b) for b in bgs)
        ti_ = min(contrast(ink, b) for b in bgs)
        if max(tw_, ti_) < 3.4:
            mode = "dark"
    if mode == "dark":
        bgs = [hls(h, 0.10, 0.65), hls(h, 0.19, 0.7), hls(h, 0.32, 0.7)]
    elif mode == "light":
        bgs = [hls(h, 0.97, 0.7), hls(h, 0.93, 0.7), hls(h, 0.85, 0.6)]
    if mode == "vivid":
        head = WHITE if min(contrast(WHITE, b) for b in bgs) >= min(contrast(ink, b) for b in bgs) else ink
    else:
        head = WHITE if mode == "dark" else ink
    disc = pick_disc(ha, bgs[2])
    p = {"mode": mode, "bg": bgs, "head": head, "ink": ink, "rim": rim, "mid": mid, "tint": tint, "tint2": tint2,
         "pop": pop, "disc": disc, "muted": muted, "hl_fill": pop, "hl_text": best_text(pop, ink)}
    if mode == "light":
        L = 0.36
        card = hls(h, L, 0.75)
        while contrast(WHITE, card) < 5.0 and L > 0.16:
            L -= 0.02
            card = hls(h, L, 0.75)
        p.update(card=card, card_text=WHITE, card_muted=tint, via_fill=pop, via_text=best_text(pop, ink),
                 blob1=pop, blob2=tint2, pill_text=ink, pill_line=ink, pill_fill=(255, 255, 255, 120),
                 st_fill=ink, st_text=pop, foot=ink, foot_text=WHITE, logo_fill=pop, logo_text=best_text(pop, ink),
                 num=card, label=muted)
    elif mode == "dark":
        p.update(card=WHITE, card_text=ink, card_muted=muted, via_fill=pop, via_text=best_text(pop, ink),
                 blob1=hls(h, 0.45, 0.75), blob2=pop, pill_text=WHITE, pill_line=tint2, pill_fill=(255, 255, 255, 30),
                 st_fill=pop, st_text=best_text(pop, ink), foot=WHITE, foot_text=ink, logo_fill=ink, logo_text=pop,
                 num=pop, label=tint2)
    else:
        p.update(card=WHITE, card_text=ink, card_muted=muted, via_fill=ink, via_text=pop,
                 blob1=hls(h, 0.30, 0.8), blob2=pop, pill_text=head, pill_line=head, pill_fill=(255, 255, 255, 40),
                 hl_fill=ink, hl_text=pop,
                 st_fill=ink, st_text=pop, foot=ink, foot_text=WHITE, logo_fill=pop, logo_text=best_text(pop, ink),
                 num=head, label=head)
    return p

CUR = {"ink": (14, 11, 74)}

def sh(img, box, r, **kw):
    shadow(img, box, r, color=CUR["ink"], **kw)

def bg(pal):
    a, b, c = pal["bg"]
    img = Image.new("RGB", (P(W), P(H)))
    d = ImageDraw.Draw(img)
    for y in range(P(H)):
        t = y / (P(H) - 1)
        col = lerp(a, b, t / 0.5) if t < 0.5 else lerp(b, c, ((t - 0.5) / 0.5) ** 1.1)
        d.line((0, y, P(W), y), fill=col)
    return img

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

def wrap_words(d, words, f, max_w, hl, pad):
    sp = tw(d, " ", f)
    lines, cur, cw = [], [], 0
    for w in words:
        ww = tw(d, w, f) + (2 * pad if w == hl else 0)
        add = ww if not cur else sp + ww
        if cur and cw + add > max_w:
            lines.append((cur, cw))
            cur, cw = [w], ww
        else:
            cur.append(w)
            cw += add
    if cur:
        lines.append((cur, cw))
    return lines

def headline(img, words, hl, x, y, w, h, start, minsz, pal, align="left", max_lines=4, valign="top"):
    d = ImageDraw.Draw(img)
    size = P(start)
    while True:
        f = font(HEAVY, size)
        pad = size * 0.14
        lines = wrap_words(d, words, f, P(w), hl, pad)
        if (len(lines) <= max_lines and len(lines) * size * 1.14 <= P(h)) or size <= P(minsz):
            break
        size -= P(4)
    y0 = P(y)
    if valign == "middle":
        y0 += max(0, (P(h) - len(lines) * size * 1.14) / 2)
    base = y0 + size * 0.82
    for ln, lw in lines:
        cx = P(x) if align == "left" else P(x) + (P(w) - lw) / 2
        for wd in ln:
            ww = tw(d, wd, f)
            if wd == hl:
                cap = -f.getbbox("H", anchor="ls")[1]
                rr(img, (cx, base - cap - size * 0.16, cx + ww + 2 * pad, base + size * 0.2), int(size * 0.22), pal["hl_fill"] + (255,))
                d.text((cx + pad, base), wd, font=f, fill=pal["hl_text"], anchor="ls")
                cx += ww + 2 * pad
            else:
                d.text((cx, base), wd, font=f, fill=pal["head"], anchor="ls")
                cx += ww
            cx += tw(d, " ", f)
        base += size * 1.14
    return base / S

def arrow_icon(d, cx, cy, r, bgc, fgc):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bgc)
    a = r * 0.42
    wd = max(2, int(r * 0.16))
    d.line((cx - a, cy + a, cx + a, cy - a), fill=fgc, width=wd)
    d.line((cx - a * 0.1, cy - a, cx + a, cy - a), fill=fgc, width=wd)
    d.line((cx + a, cy - a, cx + a, cy + a * 0.1), fill=fgc, width=wd)

def pill_top(img, text, pal, x=64, y=54):
    d = ImageDraw.Draw(img)
    fp = font(REG, P(22))
    t = text if text else "WEB3 NEWS"
    t = " ".join(t) if len(t) <= 12 else t
    pw = tw(d, t, fp) + P(44)
    rr(img, (P(x), P(y), P(x) + pw, P(y + 48)), P(24), pal["pill_fill"])
    d.rounded_rectangle((P(x), P(y), P(x) + pw, P(y + 48)), radius=P(24), outline=pal["pill_line"], width=P(2))
    d.text((P(x) + P(22), P(y + 24)), t, font=fp, fill=pal["pill_text"], anchor="lm")

def sticker(img, text, cx, cy, r, angle, pal):
    sz = P(2 * r)
    st = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    sd = ImageDraw.Draw(st)
    sd.ellipse((0, 0, sz - 1, sz - 1), fill=pal["st_fill"])
    parts = text.split()[:2] or ["NEWS"]
    fs = font(HEAVY, P(r * 0.40))
    while max(tw(sd, p, fs) for p in parts) > sz * 0.78 and fs.size > P(14):
        fs = font(HEAVY, fs.size - 2)
    lh = fs.size * 1.15
    y0 = sz / 2 - lh * (len(parts) - 1) / 2
    for i, p in enumerate(parts):
        sd.text((sz / 2, y0 + i * lh), p, font=fs, fill=pal["st_text"], anchor="mm")
    paste_rot(img, st, P(cx), P(cy), angle)

def footer(img, pal):
    fy0, fy1, x0, x1 = P(986), P(1040), P(64), P(1016)
    sh(img, (x0, fy0, x1, fy1), P(27), blur=12, dy=6, alpha=60)
    rr(img, (x0, fy0, x1, fy1), P(27), pal["foot"] + (245,))
    d = ImageDraw.Draw(img)
    d.ellipse((x0 + P(12), fy0 + P(9), x0 + P(48), fy0 + P(45)), fill=pal["logo_fill"])
    d.text((x0 + P(30), fy0 + P(27)), "Y", font=font(HEAVY, P(20)), fill=pal["logo_text"], anchor="mm")
    ff = font(REG, P(22))
    d.text((x0 + P(62), fy0 + P(27)), "@YoXo_Station", font=ff, fill=pal["foot_text"], anchor="lm")
    d.text((x1 - P(26), fy0 + P(27)), "WEB3 NEWS", font=ff, fill=pal["foot_text"], anchor="rm")

def blob(img, pal, cx, cy, r, key):
    ImageDraw.Draw(img).ellipse((P(cx - r), P(cy - r), P(cx + r), P(cy + r)), fill=pal[key])

def initials(s):
    words = [w for w in "".join(ch if ch.isalnum() else " " for ch in (s or "")).split() if w]
    if not words:
        return "W3"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()

def hero(img, g, kicker, cx, cy, rd, pal, angle=-5):
    d = ImageDraw.Draw(img)
    d.ellipse((P(cx - rd), P(cy - rd), P(cx + rd), P(cy + rd)), fill=pal["disc"])
    obj = make_object(g.get("object"), g.get("object_text"), initials(kicker))
    k = (2 * rd * 1.04) / 400.0
    obj = obj.resize((int(obj.width * k), int(obj.height * k)), Image.LANCZOS)
    obj = obj.rotate(angle, expand=True, resample=Image.BICUBIC)
    shd = obj.split()[3].point(lambda v: int(v * 0.28)).filter(ImageFilter.GaussianBlur(P(10) * k))
    ox, oy = P(cx) - obj.width // 2, P(cy) - obj.height // 2
    img.paste(Image.new("RGB", obj.size, CUR["ink"]), (ox, oy + P(14)), shd)
    img.paste(obj, (ox, oy), obj)

def via_pill(img, x, y, source, pal):
    d = ImageDraw.Draw(img)
    pt = ("VIA " + source.upper()) if source else "WEB3 NEWS"
    fpl = font(HEAVY, P(22))
    pw = tw(d, pt, fpl) + P(34) + P(52)
    h = P(54)
    rr(img, (P(x), P(y), P(x) + pw, P(y) + h), h // 2, pal["via_fill"] + (255,))
    d = ImageDraw.Draw(img)
    d.text((P(x) + P(20), P(y) + h / 2), pt, font=fpl, fill=pal["via_text"], anchor="lm")
    arrow_icon(d, P(x) + pw - P(28), P(y) + h / 2, P(17), pal["via_text"], pal["via_fill"])
    return pw / S

def stat_chip(img, cx, cy, tile, pal, angle=5):
    v = str(tile.get("value", ""))[:6]
    lb = str(tile.get("label", ""))[:16]
    cw, ch = P(170), P(116)
    chip = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    cd = ImageDraw.Draw(chip)
    cd.rounded_rectangle((0, 0, cw - 1, ch - 1), radius=P(26), fill=WHITE)
    fv = font(HEAVY, P(44))
    while tw(cd, v, fv) > cw - P(28) and fv.size > P(20):
        fv = font(HEAVY, fv.size - 2)
    cd.text((cw / 2, ch * 0.40), v, font=fv, fill=pal["ink"], anchor="mm")
    flb = font(REG, P(18))
    while tw(cd, lb, flb) > cw - P(20) and flb.size > P(11):
        flb = font(REG, flb.size - 1)
    cd.text((cw / 2, ch * 0.78), lb, font=flb, fill=pal["muted"], anchor="mm")
    sh(img, (P(cx) - cw // 2, P(cy) - ch // 2, P(cx) + cw // 2, P(cy) + ch // 2), P(26), blur=14, dy=10, alpha=90)
    paste_rot(img, chip, P(cx), P(cy), angle)

def fit_text(d, s, paths, start, max_w, minimum):
    size = P(start)
    while size > P(minimum):
        f = font(paths, size)
        l, t, r, b = d.textbbox((0, 0), s, font=f, anchor="ls")
        if (r - l) <= P(max_w):
            break
        size -= P(4)
    f = font(paths, size)
    l, t, r, b = d.textbbox((0, 0), s, font=f, anchor="ls")
    return f, -t, max(0, b), r - l

def stat_card(img, x0, x1, bottom, number, label, kicker, source, pal, with_via=True):
    d = ImageDraw.Draw(img)
    main = number if number else (kicker if kicker else "LATEST")
    f, asc, desc, wid = fit_text(d, main, HEAVY, 150 if number else 70, (x1 - x0) - 72, 44)
    sub = label if number else "Latest update" + (f" via {source}" if source else "")
    fl = font(REG, P(28))
    while tw(d, sub, fl) > P((x1 - x0) - 72) and fl.size > P(16):
        fl = font(REG, fl.size - 2)
    pill_h = P(54) if with_via else 0
    gap = P(24) if with_via else 0
    h = P(34) + asc + desc + P(20) + int(fl.size * 0.9) + gap + pill_h + P(34)
    top = P(bottom) - h
    sh(img, (P(x0), top, P(x1), P(bottom)), P(36), blur=24, dy=16, alpha=95)
    rr(img, (P(x0), top, P(x1), P(bottom)), P(36), pal["card"] + (255,))
    d = ImageDraw.Draw(img)
    gy = top + P(34) + asc
    d.text((P(x0) + P(36), gy), main, font=f, fill=pal["card_text"], anchor="ls")
    d.text((P(x0) + P(36), gy + desc + P(20) + fl.size * 0.8), sub, font=fl, fill=pal["card_muted"], anchor="ls")
    if with_via:
        via_pill(img, x0 / 1 + 36, (top + h - P(34) - pill_h) / S, source, pal)
    return top / S

# ---------------- layouts ----------------
def layout_stack(img, g, c, pal, mirror=False):
    words, hl = c["words"], c["hl"]
    blob(img, pal, 1080, 0, 190, "blob1")
    blob(img, pal, 0 if not mirror else 1080, 1010, 170, "blob2")
    pill_top(img, c["kicker"], pal)
    sticker(img, c["sticker"], 902, 104, 62, -12, pal)
    headline(img, words, hl, 64, 200, 952, 344, 112, 54, pal)
    if not mirror:
        hero(img, g, c["kicker"], 815, 772, 182, pal)
        stat_card(img, 64, 580, 956, c["number"], c["label"], c["kicker"], c["source"], pal)
        if c["tile"]:
            stat_chip(img, 662, 892, c["tile"], pal, 5)
    else:
        hero(img, g, c["kicker"], 265, 772, 182, pal, 5)
        stat_card(img, 500, 1016, 956, c["number"], c["label"], c["kicker"], c["source"], pal)
        if c["tile"]:
            stat_chip(img, 418, 892, c["tile"], pal, -5)

def layout_number(img, g, c, pal):
    d = ImageDraw.Draw(img)
    blob(img, pal, 1080, 1080, 230, "blob1")
    blob(img, pal, 0, 0, 150, "blob2")
    pill_top(img, c["kicker"], pal)
    hero(img, g, c["kicker"], 836, 380, 170, pal, 6)
    sticker(img, c["sticker"], 936, 96, 54, 12, pal)
    f, asc, desc, wid = fit_text(d, c["number"], HEAVY, 300, 590, 120)
    top = P(130)
    d.text((P(64), top + asc), c["number"], font=f, fill=pal["num"], anchor="ls")
    lab = c["label"] or ""
    fl = font(REG, P(34))
    while tw(d, lab, fl) > P(590) and fl.size > P(18):
        fl = font(REG, fl.size - 2)
    ly = top + asc + desc + P(16) + fl.size
    d.text((P(64), ly), lab, font=fl, fill=pal["label"], anchor="ls")
    hy = max(600, ly / S + 46)
    headline(img, c["words"], c["hl"], 64, hy, 952, 905 - hy, 92, 50, pal, max_lines=3)
    via_pill(img, 64, 916, c["source"], pal)
    if c["tile"]:
        stat_chip(img, 880, 900, c["tile"], pal, 5)

def layout_poster(img, g, c, pal):
    blob(img, pal, 0, 1080, 200, "blob1")
    blob(img, pal, 1080, 0, 190, "blob2")
    pill_top(img, c["kicker"], pal)
    hero(img, g, c["kicker"], 540, 352, 212, pal, -4)
    sticker(img, c["sticker"], 912, 128, 64, 12, pal)
    d = ImageDraw.Draw(img)
    # number badge
    bw, bh = P(300), P(170)
    badge = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=P(34), fill=pal["card"])
    main = c["number"] if c["number"] else (c["kicker"] or "LATEST")
    f, asc, desc, wid = fit_text(bd, main, HEAVY, 84, 252, 34)
    lab = c["label"] if c["number"] else ("via " + c["source"] if c["source"] else "")
    fl = font(REG, P(22))
    while tw(bd, lab, fl) > bw - P(30) and fl.size > P(12):
        fl = font(REG, fl.size - 1)
    total = asc + desc + P(10) + fl.size
    y0 = (bh - total) / 2
    bd.text((bw / 2 - wid / 2, y0 + asc), main, font=f, fill=pal["card_text"], anchor="ls")
    bd.text((bw / 2, y0 + asc + desc + P(10) + fl.size * 0.8), lab, font=fl, fill=pal["card_muted"], anchor="mm")
    sh(img, (P(110), P(500), P(110) + bw, P(500) + bh), P(34), blur=18, dy=12, alpha=90)
    paste_rot(img, badge, P(262), P(585), 6)
    if c["tile"]:
        stat_chip(img, 836, 598, c["tile"], pal, -6)
    else:
        via_pill(img, 700, 570, c["source"], pal)
    headline(img, c["words"], c["hl"], 64, 700, 952, 272, 92, 50, pal, align="center", max_lines=3, valign="middle")

def render(g, variant=0, out_path=None):
    lay = variant % 4
    pal = make_palette(variant)
    CUR["ink"] = pal["ink"]
    set_colors(pal["ink"], pal["pop"], pal["rim"], pal["mid"], pal["tint"], pal["tint2"])
    hw = str(g.get("headline", "")).upper().split()
    hs = ""
    for w_ in hw:
        if len((hs + " " + w_).strip()) > 80:
            break
        hs = (hs + " " + w_).strip()
    words = hs.split()
    tiles = (g.get("tiles") or [])[:1]
    c = {
        "words": words, "hl": pick_highlight(words, g.get("highlight")),
        "number": str(g.get("big_number", ""))[:9],
        "label": str(g.get("number_label", ""))[:44],
        "kicker": str(g.get("kicker", "")).upper()[:24],
        "sticker": str(g.get("tag", "BREAKING")).upper()[:14] or "BREAKING",
        "tile": tiles[0] if tiles else None,
        "source": str(g.get("source", ""))[:20],
    }
    if lay == 2 and not c["number"]:
        lay = 0
    img = bg(pal)
    if lay == 0:
        layout_stack(img, g, c, pal)
    elif lay == 1:
        layout_stack(img, g, c, pal, mirror=True)
    elif lay == 2:
        layout_number(img, g, c, pal)
    else:
        layout_poster(img, g, c, pal)
    footer(img, pal)
    out = img.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    if out_path:
        open(out_path, "wb").write(data)
    return data
