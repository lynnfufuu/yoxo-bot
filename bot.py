import os, json, time, re, html, requests, feedparser
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from graphic import render

FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("The Block", "https://www.theblock.co/rss.xml"),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed"),
    ("CryptoSlate", "https://cryptoslate.com/feed/"),
    ("U.Today", "https://u.today/rss"),
    ("BeInCrypto", "https://beincrypto.com/feed/"),
    ("CryptoPotato", "https://cryptopotato.com/feed/"),
    ("NewsBTC", "https://www.newsbtc.com/feed/"),
    ("Bitcoinist", "https://bitcoinist.com/feed/"),
    ("AMBCrypto", "https://ambcrypto.com/feed/"),
    ("Blockworks", "https://blockworks.co/feed"),
    ("Crypto Briefing", "https://cryptobriefing.com/feed/"),
    ("CoinGape", "https://coingape.com/feed/"),
    ("Cryptonews", "https://cryptonews.com/news/feed/"),
    ("Protos", "https://protos.com/feed/"),
    ("Unchained", "https://unchainedcrypto.com/feed/"),
    ("crypto.news", "https://crypto.news/feed/"),
    ("DL News", "https://www.dlnews.com/arc/outboundfeeds/rss/"),
    ("NFT Evening", "https://nftevening.com/feed/"),
    ("NFT Now", "https://nftnow.com/feed/"),
    ("Ethereum Foundation", "https://blog.ethereum.org/feed.xml"),
]
MODEL = "gemini-3.8-flash"
MIN_SCORE = 6
MAX_CANDIDATES = 24
MAX_DRAFTS = 3
MAX_AGE_HOURS = 24
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]
MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
errors = []

SCORE_PROMPT = """You are the news editor of @YoXo_Station, an X account about Web3: crypto, blockchain, NFTs, DeFi, stablecoins, exchanges, tokenization, Web3 gaming, AI x crypto, and regulation that affects them.
You get NEW STORIES (id | source | title | snippet) and RECENT POSTS that were already sent.

For EVERY story return:
- "score" 1-10 = how likely people are to read and share it as a Web3 post.
  8-10: hacks or exploits with big numbers, major launches, big institutions moving in or out, regulation decisions, record numbers, big names, surprising facts.
  5-7: solid news with moderate impact.
  1-4: routine price commentary, sponsored or promoted content, opinion pieces, how-to guides, listicles, or anything NOT related to Web3.
- "dup" = true if the story reports the same news event as any RECENT POST, or as another story earlier in the list. If several stories cover one event, keep dup=false only on the best one.

Return ONLY JSON: [{"id": int, "score": int, "dup": bool}, ...] with one item per story.

"""

WRITE_PROMPT = """You are the editor of @YoXo_Station, a Web3 news account on X.
Given a news story, do three things.

1) Write ONE X post, 450-750 characters total, built to be skimmed in seconds.
FORMAT:
Line 1 (hook): "JUST IN:" or "BREAKING:" + the single most surprising fact, with a number if one exists. ALL CAPS, max 18 words.
Then a blank line, then 3-4 short lines, one sentence each (max 22 words), separated by blank lines:
- the key stat or number, with the names involved
- the most important detail, or a short direct quote from the source
- one more detail that adds context (skip it if the source has none)
- last line: what happens next or what to watch, only if the source says it; otherwise a sharp one-line takeaway built only from facts in the source.
Plain words, no filler. Use $CASHTAGS for tokens. No hashtags, no emojis, no thread bait.
RULES: Use ONLY facts in the source. Never invent numbers, quotes or names.
Keep words like "reportedly" or "alleged". No price predictions or financial advice.

2) Fill in the text for a bold square social media graphic ("graphic"):
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

3) Give a one-line "verify" note: what the editor should double-check before posting.

Return ONLY JSON:
{"post": str, "verify": str, "graphic": {"kicker": str, "headline": str, "highlight": str, "big_number": str, "number_label": str, "tiles": [{"value": str, "label": str}], "tag": str, "source": str, "object": str, "object_text": str}}

STORY:
"""

STOP = set("a an the of to in on for and or as at by with from is are be after before over into new says say report reports will its it this that than more".split())

def toks(s):
    return set(w for w in re.findall(r"[a-z0-9$%.]+", s.lower()) if w not in STOP and len(w) > 2)

def similar(a, b):
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.5

def clean_html(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def mm_time(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return ""
    dt = datetime(*t[:6], tzinfo=timezone.utc) + timedelta(hours=6, minutes=30)
    h = dt.hour % 12 or 12
    ap = "AM" if dt.hour < 12 else "PM"
    return "Published: " + str(dt.day) + " " + dt.strftime("%b %Y") + ", " + str(h) + ":" + format(dt.minute, "02d") + " " + ap + " (Myanmar time)"

def load_state():
    try:
        data = json.load(open("seen.json"))
        if isinstance(data, dict):
            return (set(data.get("links", [])), int(data.get("n", 0)),
                    list(data.get("titles", [])), list(data.get("sent", [])))
    except Exception:
        pass
    return set(), 0, [], []

def save_state(seen, n, titles, sent):
    json.dump({"v": 4, "n": n, "links": sorted(seen)[-3000:], "titles": titles[-250:], "sent": sent[-30:]},
              open("seen.json", "w"))

def recent(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return True
    dt = datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt < timedelta(hours=MAX_AGE_HOURS)

def fetch_feed(item):
    name, url = item
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.ok:
            return name, feedparser.parse(r.content).entries
    except Exception:
        pass
    return name, []

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

def gemini(text):
    body = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    last = ""
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
        for attempt in range(2):
            try:
                r = requests.post(url, json=body, timeout=90)
                data = r.json()
            except Exception as ex:
                last = f"{model} request error: {str(ex)[:80]}"
                time.sleep(3)
                continue
            if "candidates" in data:
                try:
                    return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
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
            json={"chat_id": TG_CHAT, "text": text[:4000], "disable_web_page_preview": True},
            timeout=30,
        )
        if not r.ok:
            errors.append(f"Telegram {r.status_code}: {r.text[:150]}")
            return False
        return True
    except Exception as ex:
        errors.append(f"Telegram error: {str(ex)[:100]}")
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

    seen, n, titles, sent = load_state()

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_feed, FEEDS))
    ok_feeds = [name for name, ents in results if ents]
    broken = [name for name, ents in results if not ents]

    pool = []
    for name, ents in results:
        for e in ents:
            link = e.get("link")
            title = clean_html(e.get("title", ""))
            if link and title and link not in seen and recent(e):
                pool.append({"source": name, "title": title, "link": link,
                             "summary": clean_html(e.get("summary", "")), "entry": e})
    pool.sort(key=lambda c: tuple(c["entry"].get("published_parsed") or c["entry"].get("updated_parsed") or ()), reverse=True)

    # cheap duplicate filter: same story already processed, or covered by another outlet in this batch
    cands, skipped_dups = [], 0
    for c in pool:
        if any(similar(c["title"], t) for t in titles) or any(similar(c["title"], k["title"]) for k in cands):
            seen.add(c["link"])
            skipped_dups += 1
            continue
        if len(cands) < MAX_CANDIDATES:
            cands.append(c)

    drafts, picked, dups, scores = 0, [], 0, []
    if cands:
        try:
            lines = [f"{i} | {c['source']} | {c['title']} | {c['summary'][:220]}" for i, c in enumerate(cands)]
            recent_txt = "\n".join("- " + t for t in sent[-15:]) or "(none)"
            res = gemini(SCORE_PROMPT + "RECENT POSTS ALREADY SENT:\n" + recent_txt + "\n\nNEW STORIES:\n" + "\n".join(lines))
            if isinstance(res, dict):
                res = next((v for v in res.values() if isinstance(v, list)), [])
            by_id = {int(r["id"]): r for r in res if isinstance(r, dict) and "id" in r}
        except Exception as ex:
            errors.append("Scoring failed: " + str(ex)[:120])
            by_id = None

        if by_id is not None:
            for i, c in enumerate(cands):
                r = by_id.get(i, {})
                c["score"] = int(r.get("score", 0) or 0)
                c["dup"] = bool(r.get("dup", False))
                scores.append(c["score"])
                dups += 1 if c["dup"] else 0
            picked = [c for c in cands if c["score"] >= MIN_SCORE and not c["dup"]]
            picked.sort(key=lambda c: -c["score"])
            picked = picked[:MAX_DRAFTS]
            unsent = set(c["link"] for c in picked)
            fails = 0
            for c in picked:
                try:
                    out = gemini(WRITE_PROMPT + f"Source: {c['source']}\nTitle: {c['title']}\nSummary: {c['summary'][:2500]}\nLink: {c['link']}")
                    fails = 0
                    g = out.get("graphic") or {}
                    try:
                        png = render(g, variant=n)
                        n += 1
                        send_photo(png)
                    except Exception as ex:
                        errors.append("Graphic error: " + str(ex)[:100])
                    post = str(out.get("post", "")).rstrip()
                    stamp = mm_time(c["entry"])
                    if stamp:
                        post = post + "\n\n" + stamp
                    if send(f"Score {c['score']}/10\n\n{post}\n\nVerify: {out.get('verify', '')}\n\nSource: {c['link']}"):
                        drafts += 1
                        unsent.discard(c["link"])
                        sent.append(str(g.get("headline") or c["title"]))
                except Exception as ex:
                    errors.append(str(ex)[:120])
                    fails += 1
                    if fails >= 2:
                        errors.append("Stopped early, Gemini busy. Will retry next run.")
                        break
                time.sleep(2)
            for c in cands:
                if c["link"] not in unsent:
                    seen.add(c["link"])
                    titles.append(c["title"])

    save_state(seen, n, titles, sent)

    if MANUAL:
        send(
            f"Run done. Feeds working: {len(ok_feeds)}/{len(FEEDS)}. Not working: {', '.join(broken) if broken else 'none'}. "
            f"New stories: {len(pool)}. Duplicates skipped: {skipped_dups + dups}. Scored: {len(scores)}. "
            f"Scores: {scores}. Sent: {drafts}. Errors: {errors[:3] if errors else 'none'}"
        )

main()
