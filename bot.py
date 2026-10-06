import os, json, time, re, html, requests, feedparser
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from graphic import render

def gn(q):
    return "https://news.google.com/rss/search?q=" + quote(q + " when:1d") + "&hl=en-US&gl=US&ceid=US:en"

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
    ("Cryptopolitan", "https://www.cryptopolitan.com/feed/"),
    ("Protos", "https://protos.com/feed/"),
    ("Unchained", "https://unchainedcrypto.com/feed/"),
    ("crypto.news", "https://crypto.news/feed/"),
    ("DL News", "https://www.dlnews.com/arc/outboundfeeds/rss/"),
    ("Ethereum Foundation", "https://blog.ethereum.org/feed.xml"),
    ("NFT Evening", "https://nftevening.com/feed/"),
    ("NFT Now", "https://nftnow.com/feed/"),
    ("NFT Plazas", "https://nftplazas.com/feed/"),
    ("NFTgators", "https://nftgators.com/feed/"),
    ("DappRadar", "https://dappradar.com/blog/feed"),
    ("Meme Insider", "https://memeinsider.com/feed"),
    ("Rekt News", "https://rekt.news/rss.xml"),
    ("Web3 Is Going Great", "https://www.web3isgoinggreat.com/feed"),
    ("SlowMist", "https://slowmist.medium.com/feed"),
    ("GN:listing", gn("(Binance OR Coinbase OR Upbit OR Bybit OR OKX) new token listing")),
    ("GN:launch", gn("crypto launchpad OR launchpool OR IDO OR token generation event")),
    ("GN:perp", gn("perp DEX OR perpetual DEX launch OR points airdrop")),
    ("GN:chain", gn("testnet OR mainnet launch blockchain")),
    ("GN:nft", gn("upcoming NFT collection mint")),
    ("GN:nft2", gn("NFT news collection sale")),
    ("GN:meme", gn("memecoin")),
    ("GN:scam", gn("crypto rug pull OR exploit OR scam OR drained")),
]
NFT_FEEDS = {"NFT Evening", "NFT Now", "NFT Plazas", "NFTgators", "DappRadar", "GN:nft", "GN:nft2"}
MODEL = "gemini-3.8-flash"
MIN_SCORE = 6
MAX_CANDIDATES = 30
MAX_DRAFTS = 3
MAX_AGE_HOURS = 24
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]
MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
errors = []

SCORE_PROMPT = """You are the news editor of @YoXo_Station, an X account about Web3: crypto, blockchain, NFTs, DeFi, stablecoins, exchanges, tokenization, memecoins, Web3 gaming, AI x crypto, and regulation that affects them.
You get NEW STORIES (id | source | title | snippet) and RECENT POSTS that were already sent.

For EVERY story return:
- "score" 1-10 = how likely people are to read and share it as a Web3 post.
  8-10: hacks, exploits, rug pulls or scams with big numbers; major exchange listings (Binance, Coinbase, Upbit, Bybit, OKX); big launches (launchpads, perp DEXs, testnet or mainnet going live, airdrops); hyped NFT collections or mints; trending memecoins; big institutions moving in or out; regulation decisions; record numbers; big names.
  5-7: solid news with moderate impact, smaller listings or launches, NFT or memecoin news with some traction.
  1-4: routine price commentary, sponsored or promoted content, opinion pieces, how-to guides, listicles, or anything NOT related to Web3.
- "dup" = true if the story reports the same news event as any RECENT POST, or as another story earlier in the list. If several stories cover one event, keep dup=false only on the best one.

Return ONLY JSON: [{"id": int, "score": int, "dup": bool}, ...] with one item per story.

"""

GRAPHIC_SPEC = """Fill in the text for a bold square social media graphic ("graphic"):
- kicker: 1-3 words naming the topic or project (example: "Near Intents")
- headline: max 8 words, punchy, states the news. Do NOT repeat the big_number in it.
- highlight: ONE word copied exactly from your headline that deserves emphasis.
- big_number: the single most striking figure from the story, short (examples: "$3.8M", "48H", "12%"). Use "" if the story has no strong number.
- number_label: max 7 words saying what the big number is.
- tiles: [] or ONE extra stat {"value": max 6 chars, "label": max 2 words}. Only if the source has it.
- tag: sticker text, max 2 short words (examples: "BREAKING", "JUST IN", "HACK", "RECORD").
- source: the publication name.
- objects: 1 to 3 picks, best first, each as {"name": ..., "text": ...}. The FIRST pick must directly show what the story is actually about (its real subject), never just decoration. Every pick must clearly relate to this story. Self-check: would a reader see the object and instantly connect it to this news? If not, do not use it. If the story is about one specific project, company, exchange or person and no object fits well, use monogram with its initials.
  Names (use exactly these), when to use them, and what "text" should be:
  coin (a specific token or stablecoin; text = its ticker, required), monogram (one specific project, company or person; text = 2-3 letter initials), bank (banks, central banks, institutions, ETF issuers), capitol (laws, bills, politics, government), document (regulation text, filings, reports, proposals), gavel (court cases, lawsuits, verdicts ONLY),
  shield (security, audits), lock (hacks, exploits, frozen or stolen funds), warning (scams, rug pulls, phishing, alerts), magnifier (investigations, on-chain sleuthing, analytics),
  chart_up (prices or flows rising, records), chart_down (falling prices, losses), candles (trading, perps, leverage; text like "50X"), rocket (launches, launchpads, rallies), flame (token burns), bolt (speed, L2s, upgrades),
  listing (new exchange listings; text = the listed token's ticker), blocks (testnet, mainnet, network upgrades; text "TEST" or "MAIN"), nft (NFT collections and sales; text = collection name), calendar (dates, mint schedules; text = day number like "12"), ticket (mints, allowlists, presales; text "MINT"),
  meme (memecoins in general), dog (dog-themed memecoins), frog (frog-themed memecoins), gift (airdrops, rewards), bag (funding rounds, raises, treasuries; text like "$5M"), vault (custody, staking, reserves), wallet (wallets, payments), swap (DEXs, exchanges, swaps, mergers), bridge (cross-chain bridges), chip (AI hardware, mining; text "AI" or "GPU"), robot (AI agents; text "AI"), server (nodes, validators, infrastructure), gamepad (Web3 gaming), globe (countries, global adoption).
Everything in the graphic must come from the source. Never invent anything."""

GRAPHIC_JSON = '"graphic": {"kicker": str, "headline": str, "highlight": str, "big_number": str, "number_label": str, "tiles": [{"value": str, "label": str}], "tag": str, "source": str, "objects": [{"name": str, "text": str}]}'

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
If the snippet is only a headline, write a shorter post (hook plus 2 lines) from the facts in it.

2) """ + GRAPHIC_SPEC + """

3) Give a one-line "verify" note: what the editor should double-check before posting.

Return ONLY JSON:
{"post": str, "verify": str, """ + GRAPHIC_JSON + """}

"""

MINT_PROMPT = """You are the editor of @YoXo_Station, a Web3 news account on X.
Below are NFT news items from the last 36 hours (title | source | snippet). Build today's NFT MINT LIST post using ONLY mints, drops or collections mentioned in these items: the name, the chain, and the mint date, time or price ONLY if the items state them.

FORMAT: line 1: "TODAY'S NFT MINT LIST:" plus a short teaser (ALL CAPS, max 14 words). Blank line. Then 4-6 lines, one per collection: "- Name (Chain): date or time, price" (leave out anything the items do not say). Last line: one short note on the hottest drop, using only facts from the items. Under 700 characters. No hashtags, no emojis.
If fewer than 3 real upcoming or live mints are mentioned, return {"skip": true}.

Also fill in the graphic. """ + GRAPHIC_SPEC + """ For this post the objects must be from: calendar (text = today's day number), ticket or nft.
Also give a one-line "verify" note.

Return ONLY JSON: {"skip": false, "post": str, "verify": str, """ + GRAPHIC_JSON + """} or {"skip": true}

ITEMS:
"""

VALID = set("coin monogram bank capitol document gavel shield lock warning magnifier chart_up chart_down candles rocket flame bolt listing blocks nft calendar ticket meme dog frog gift bag vault wallet swap bridge chip robot server gamepad globe".split())

def choose_object(g, recent, kicker=""):
    opts = g.get("objects")
    if not isinstance(opts, list) or not opts:
        opts = [{"name": g.get("object", ""), "text": g.get("object_text", "")}]
    clean = []
    for o in opts:
        if isinstance(o, dict):
            name, text = str(o.get("name", "")).lower().strip(), str(o.get("text", "") or "")
        else:
            name, text = str(o).lower().strip(), ""
        if name == "coin" and not text.strip():
            name = "monogram"
        if name in VALID:
            clean.append((name, text))
    if not clean:
        clean = [("monogram", "")]
    for name, text in clean:
        if name not in recent[-3:]:
            g["object"], g["object_text"] = name, text
            return name
    g["object"], g["object_text"] = clean[0]
    return clean[0][0]

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

def mm_now():
    return datetime.now(timezone.utc) + timedelta(hours=6, minutes=30)

def fmt_mm(dt):
    h = dt.hour % 12 or 12
    ap = "AM" if dt.hour < 12 else "PM"
    return str(dt.day) + " " + dt.strftime("%b %Y") + ", " + str(h) + ":" + format(dt.minute, "02d") + " " + ap + " (Myanmar time)"

def mm_time(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return ""
    return "Published: " + fmt_mm(datetime(*t[:6], tzinfo=timezone.utc) + timedelta(hours=6, minutes=30))

def load_state():
    st = {"links": [], "n": 0, "titles": [], "sent": [], "objs": [], "mint_day": "", "mint_tries": 0, "mint_done": False}
    try:
        data = json.load(open("seen.json"))
        if isinstance(data, dict):
            st.update({k: data[k] for k in st if k in data})
    except Exception:
        pass
    st["links"] = set(st["links"])
    return st

def save_state(st):
    out = dict(st)
    out["v"] = 5
    out["links"] = sorted(st["links"])[-3500:]
    out["titles"] = st["titles"][-300:]
    out["sent"] = st["sent"][-30:]
    out["objs"] = st["objs"][-10:]
    json.dump(out, open("seen.json", "w"))

def age_ok(entry, hours):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return True
    dt = datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt < timedelta(hours=hours)

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

def build_pool(results, seen):
    pool, nft_items = [], []
    for name, ents in results:
        limit = 15 if name.startswith("GN:") else 25
        for e in ents[:limit]:
            link = e.get("link")
            title = clean_html(e.get("title", ""))
            source = name
            if name.startswith("GN:") and " - " in title:
                title, source = title.rsplit(" - ", 1)
            if not link or not title:
                continue
            item = {"source": source, "title": title, "link": link, "summary": clean_html(e.get("summary", "")), "entry": e}
            if name in NFT_FEEDS and age_ok(e, 36):
                nft_items.append(item)
            if link not in seen and age_ok(e, MAX_AGE_HOURS):
                pool.append(item)
    pool.sort(key=lambda c: tuple(c["entry"].get("published_parsed") or c["entry"].get("updated_parsed") or ()), reverse=True)
    return pool, nft_items

def post_one(c_out, c_label, st, stamp_text):
    g = c_out.get("graphic") or {}
    choose_object(g, st["objs"], str(g.get("kicker", "")))
    try:
        png = render(g, variant=st["n"])
        st["n"] += 1
        send_photo(png)
    except Exception as ex:
        errors.append("Graphic error: " + str(ex)[:100])
    st["objs"].append(str(g.get("object", "")).lower())
    post = str(c_out.get("post", "")).rstrip()
    if stamp_text:
        post = post + "\n\n" + stamp_text
    return post, g

def daily_mints(st, nft_items):
    now = mm_now()
    today = now.strftime("%Y-%m-%d")
    if st["mint_day"] != today:
        st["mint_day"], st["mint_tries"], st["mint_done"] = today, 0, False
    due = (now.hour >= 9 and st["mint_tries"] == 0) or (now.hour >= 15 and st["mint_tries"] == 1)
    if st["mint_done"] or not due or not nft_items:
        return 0
    st["mint_tries"] += 1
    seen_t, items = [], []
    for it in nft_items:
        if any(similar(it["title"], t) for t in seen_t):
            continue
        seen_t.append(it["title"])
        items.append(f"{it['title']} | {it['source']} | {it['summary'][:260]}")
    try:
        out = gemini(MINT_PROMPT + "Today is " + str(now.day) + " " + now.strftime("%B %Y") + " (Myanmar time).\n" + "\n".join(items[:30]))
        if not isinstance(out, dict) or out.get("skip"):
            return 0
        post, g = post_one(out, "mints", st, "Compiled: " + fmt_mm(now))
        if send(f"Daily NFT mint list\n\n{post}\n\nVerify: {out.get('verify', '')}"):
            st["mint_done"] = True
            return 1
    except Exception as ex:
        errors.append("Mint list: " + str(ex)[:100])
    return 0

def main():
    if MANUAL:
        send("Bot started. Checking news...")

    st = load_state()
    seen = st["links"]

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_feed, FEEDS))
    broken = [name for name, ents in results if not ents]
    pool, nft_items = build_pool(results, seen)

    # cheap duplicate filter: same story already processed, or covered by another outlet in this batch
    cands, skipped_dups = [], 0
    for c in pool:
        if any(similar(c["title"], t) for t in st["titles"]) or any(similar(c["title"], k["title"]) for k in cands):
            seen.add(c["link"])
            skipped_dups += 1
            continue
        if len(cands) < MAX_CANDIDATES:
            cands.append(c)

    drafts, picked, dups, scores = 0, [], 0, []
    if cands:
        try:
            lines = [f"{i} | {c['source']} | {c['title']} | {c['summary'][:200]}" for i, c in enumerate(cands)]
            recent_txt = "\n".join("- " + t for t in st["sent"][-15:]) or "(none)"
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
                    prompt = WRITE_PROMPT + "RECENTLY USED OBJECTS (avoid repeating these): " + ", ".join(st["objs"][-4:]) + "\n\n"
                    out = gemini(prompt + f"STORY:\nSource: {c['source']}\nTitle: {c['title']}\nSummary: {c['summary'][:2500]}\nLink: {c['link']}")
                    fails = 0
                    post, g = post_one(out, "story", st, mm_time(c["entry"]))
                    if send(f"Score {c['score']}/10\n\n{post}\n\nVerify: {out.get('verify', '')}\n\nSource: {c['link']}"):
                        drafts += 1
                        unsent.discard(c["link"])
                        st["sent"].append(str(g.get("headline") or c["title"]))
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
                    st["titles"].append(c["title"])

    minted = daily_mints(st, nft_items)
    save_state(st)

    if MANUAL:
        send(
            f"Run done. Feeds working: {len(FEEDS) - len(broken)}/{len(FEEDS)}. Not working: {', '.join(broken) if broken else 'none'}. "
            f"New stories: {len(pool)}. Duplicates skipped: {skipped_dups + dups}. Scored: {len(scores)}. "
            f"Scores: {scores}. Sent: {drafts}. Mint list: {minted}. Errors: {errors[:3] if errors else 'none'}"
        )

main()
