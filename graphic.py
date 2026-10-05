import io
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from objects import *

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
    d.text((cx0f + P(62), fy0 + P(27)), "@YoXo_Station", font=ff, fill=WHITE, anchor="lm")
    d.text((cx1f - P(26), fy0 + P(27)), "WEB3 NEWS", font=ff, fill=WHITE, anchor="rm")

    out = img.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    if out_path:
        open(out_path, "wb").write(data)
    return data
