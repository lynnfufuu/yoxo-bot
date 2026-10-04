import os, io, json, time, requests, feedparser
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont

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

3) Fill in the text for a clean editorial graphic ("graphic"):
- kicker: 1-3 words naming the topic or project (example: "Near Intents")
- headline: max 9 words, punchy, states the news. Do NOT repeat the big_number in it.
- big_number: the single most striking figure from the story, short (examples: "$3.8M", "48H", "12%"). Use "" if the story has no strong number.
- number_label: max 8 words saying what the big number is.
- tiles: 0 to 2 extra stats, each {"value": max 6 chars, "label": max 3 words}. Only if the source has them.
- tag: a short casual phrase (max 4 words) or a very short quote from the story, shown rotated in a corner.
- accent: "teal" for neutral or good news, "coral" for hacks, losses or bad news, "gold" for money milestones or records.
- source: the publication name.
Everything in the graphic must come from the source. Never invent anything.

Also give a one-line "verify" note: what the editor should double-check before posting.

Return ONLY JSON:
{"score": int, "post": str, "verify": str, "graphic": {"kicker": str, "headline": str, "big_number": str, "number_label": str, "tiles": [{"value": str, "label": str}], "tag": str, "accent": str, "source": str}}

STORY:
"""

BG = (245, 244, 240)
INK = (17, 17, 17)
MUTED = (110, 110, 105)
LINE = (214, 212, 205)
ACCENTS = {"teal": (20, 150, 140), "coral": (240, 100, 80), "gold": (214, 160, 40)}

HEAVY = ["fonts/heavy.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
LIGHT = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]

def font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

def text_w(d, s, f):
    return d.textlength(s, font=f)

def wrap(d, s, f, max_w):
    lines, cur = [], ""
    for w in s.split():
        t = (cur + " " + w).strip()
        if text_w(d, t, f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def fit_headline(d, s, max_w, max_h, start, minimum):
    size = start
    while size >= minimum:
        f = font(HEAVY, size)
        lines = wrap(d, s, f, max_w) or [""]
        h = len(lines) * int(size * 1.02)
        widest = max(text_w(d, l, f) for l in lines)
        if h <= max_h and widest <= max_w:
            return f, lines, size
        size -= 4
    f = font(HEAVY, minimum)
    return f, (wrap(d, s, f, max_w) or [""]), minimum

def rotated_text(img, s, f, xy, angle, fill):
    d = ImageDraw.Draw(img)
    w = int(text_w(d, s, f)) + 20
    h = int(f.size * 1.5)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((10, 4), s, font=f, fill=fill)
    layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
    img.paste(layer, xy, layer)

def render(g, out_path=None):
    W, H = 1600, 900
    S = 2
    img = Image.new("RGB", (W * S, H * S), BG)
    d = ImageDraw.Draw(img)
    accent = ACCENTS.get(str(g.get("accent", "teal")).lower(), ACCENTS["teal"])
    m = 96 * S

    headline = str(g.get("headline", "")).upper()[:90]
    number = str(g.get("big_number", ""))[:9]
    number_label = str(g.get("number_label", ""))[:56]
    kicker = str(g.get("kicker", "")).upper()[:40]
    tag = str(g.get("tag", ""))[:34]
    tiles = (g.get("tiles") or [])[:2]
    source = str(g.get("source", ""))[:30]

    # decorative texture fragment bleeding off the bottom-right edge
    frag = Image.new("RGBA", (420 * S, 300 * S), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frag)
    fd.rectangle((0, 0, 420 * S, 300 * S), fill=(232, 230, 222, 255))
    for i in range(-300, 420, 26):
        fd.line((i * S, 300 * S, (i + 300) * S, 0), fill=(214, 211, 202, 255), width=3 * S)
    frag = frag.rotate(7, expand=True, resample=Image.BICUBIC)
    img.paste(frag, ((W - 250) * S, (H - 170) * S), frag)

    # kicker
    y = m - 10 * S
    if kicker:
        fk = font(LIGHT, 26 * S)
        spaced = " ".join(kicker)
        d.text((m, y), spaced if len(spaced) < 60 else kicker, font=fk, fill=MUTED)
    y += 54 * S

    # headline
    has_tiles = len(tiles) > 0
    max_w = (1010 if has_tiles else 1280) * S
    start = 108 if number else 150
    max_h = 340 if number else 600
    fh, lines, size = fit_headline(d, headline, max_w, max_h * S, start * S, 52 * S)
    lh = int(size * 1.02)
    for l in lines:
        d.text((m, y), l, font=fh, fill=INK)
        y += lh

    # big number (placed from the bottom, shrinks to fit the free space)
    if number:
        bottom = H * S - 200 * S
        avail = bottom - y - 56 * S
        size_n = 240 * S
        while size_n > 110 * S:
            fn = font(HEAVY, size_n)
            l, t, r, b = d.textbbox((0, 0), number, font=fn)
            if (b - t) <= avail and (r - l) <= 900 * S:
                break
            size_n -= 8 * S
        fn = font(HEAVY, size_n)
        l, t, r, b = d.textbbox((0, 0), number, font=fn)
        d.text((m - l, bottom - b), number, font=fn, fill=INK)
        ub = bottom + 18 * S
        d.rectangle((m, ub, m + int((r - l) * 0.4), ub + 14 * S), fill=accent)
        if number_label:
            fl = font(LIGHT, 30 * S)
            while text_w(d, number_label, fl) > 1000 * S and fl.size > 20 * S:
                fl = font(LIGHT, fl.size - 2 * S)
            d.text((m, ub + 36 * S), number_label, font=fl, fill=MUTED)

    # tiles (rounded squares with generous padding)
    if has_tiles:
        ts = 190 * S
        gap = 54 * S
        tx = W * S - m - ts - 40 * S
        total = len(tiles) * ts + (len(tiles) - 1) * gap + len(tiles) * 44 * S
        ty = max(m + 130 * S, int((H * S - total) / 2) + 30 * S)
        for t in tiles:
            val = str(t.get("value", ""))[:6]
            lab = str(t.get("label", ""))[:22]
            d.rounded_rectangle((tx, ty, tx + ts, ty + ts), radius=40 * S, fill=(255, 255, 255), outline=LINE, width=2 * S)
            fv = font(HEAVY, 70 * S)
            vw = text_w(d, val, fv)
            if vw > ts - 40 * S:
                fv = font(HEAVY, int(70 * S * (ts - 40 * S) / vw))
                vw = text_w(d, val, fv)
            d.text((tx + (ts - vw) / 2, ty + (ts - fv.size) / 2 - 8 * S), val, font=fv, fill=INK)
            fl = font(LIGHT, 24 * S)
            lw = text_w(d, lab, fl)
            d.text((tx + (ts - lw) / 2, ty + ts + 14 * S), lab, font=fl, fill=MUTED)
            ty += ts + gap + 44 * S

    # rotated hand-placed phrase, top-right
    if tag:
        ft = font(LIGHT, 30 * S)
        tw = int(text_w(d, tag, ft)) + 40 * S
        rotated_text(img, tag, ft, (W * S - m - tw, 64 * S), 6, ACCENTS.get(str(g.get("accent", "teal")).lower(), ACCENTS["teal"]))

    # footer
    ff = font(LIGHT, 22 * S)
    foot = "@YoXo_Station" + (f"   /   {source}" if source else "")
    d.text((m, H * S - 52 * S), foot, font=ff, fill=MUTED)

    img = img.resize((W, H), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    data = buf.getvalue()
    if out_path:
        open(out_path, "wb").write(data)
    return data

def list_flash_models():
    try:
        r = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?pageSize=200&key={GEMINI_KEY}",
            timeout=30,
        )
        names = []
        for m in r.json().get("models", []):
            n = m["name"].split("/")[-1]
            ok = "generateContent" in m.get("supportedGenerationMethods", [])
            bad = any(x in n for x in ("image", "tts", "audio", "live", "native", "embedding"))
            if ok and "flash" in n and not bad:
                names.append(n)
        return names
    except Exception:
        return []

MODELS = [MODEL] + [n for n in list_flash_models() if n != MODEL][:3]

def load_seen():
    try:
        data = json.load(open("seen.json"))
        if isinstance(data, dict):
            return set(data.get("links", []))
    except Exception:
        pass
    return set()

def save_seen(seen):
    json.dump({"v": 2, "links": sorted(seen)[-2000:]}, open("seen.json", "w"))

def recent(entry):
    t = entry.get("published_parsed")
    if not t:
        return True
    dt = datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt < timedelta(hours=MAX_AGE_HOURS)

def ask_gemini(title, summary, link):
    story = f"Title: {title}\nSummary: {summary[:2500]}\nLink: {link}"
    body = {
        "contents": [{"parts": [{"text": PROMPT + story}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    last = ""
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        for attempt in range(2):
            try:
                r = requests.post(url, json=body, timeout=60)
                data = r.json()
            except Exception as ex:
                last = f"{model} request error: {str(ex)[:80]}"
                time.sleep(3)
                continue
            if "candidates" in data:
                try:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    return json.loads(text)
                except Exception as ex:
                    last = f"{model} bad output: {str(ex)[:80]}"
                    break
            last = f"{model} {r.status_code}"
            if r.status_code in (429, 500, 503):
                time.sleep(4)
                continue
            break
    raise Exception(last)

def send(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True},
            timeout=30,
        )
        if not r.ok:
            msg = f"Telegram {r.status_code}: {r.text[:150]}"
            errors.append(msg)
            print(msg)
            return False
        return True
    except Exception as ex:
        errors.append(f"Telegram error: {str(ex)[:100]}")
        print("Telegram error:", ex)
        return False

def send_photo(png):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto",
            data={"chat_id": TG_CHAT},
            files={"photo": ("graphic.png", png, "image/png")},
            timeout=60,
        )
        if not r.ok:
            errors.append(f"Photo {r.status_code}: {r.text[:100]}")
        return r.ok
    except Exception as ex:
        errors.append(f"Photo error: {str(ex)[:100]}")
        return False

def main():
    if MANUAL:
        send("Bot started. Checking news...")

    seen = load_seen()
    new = []
    for feed in FEEDS:
        for e in feedparser.parse(feed).entries:
            link = e.get("link")
            if link and link not in seen and recent(e):
                new.append(e)
    new.sort(key=lambda e: tuple(e.get("published_parsed") or ()), reverse=True)

    drafts = 0
    scores = []
    fails = 0
    for e in new[:MAX_SCORED]:
        link = e.link
        try:
            res = ask_gemini(e.get("title", ""), e.get("summary", ""), link)
            fails = 0
            scores.append(res["score"])
            if res["score"] >= MIN_SCORE and drafts < MAX_DRAFTS:
                try:
                    png = render(res.get("graphic") or {})
                    send_photo(png)
                except Exception as ex:
                    errors.append(f"Graphic error: {str(ex)[:100]}")
                ok = send(
                    f"Score {res['score']}/10\n\n{res['post']}\n\n"
                    f"Verify: {res['verify']}\n\nSource: {link}"
                )
                if ok:
                    drafts += 1
                    seen.add(link)
            else:
                seen.add(link)
        except Exception as ex:
            fails += 1
            errors.append(str(ex)[:120])
            print("error:", ex)
            if fails >= 2:
                errors.append("Stopped early, Gemini busy. Will retry next run.")
                break
        time.sleep(3)

    save_seen(seen)

    if MANUAL:
        send(
            f"Run done. New stories: {len(new)}. Scored: {len(scores)}. "
            f"Scores: {scores}. Drafts sent: {drafts}. "
            f"Errors: {errors[:3] if errors else 'none'}"
        )

main()
