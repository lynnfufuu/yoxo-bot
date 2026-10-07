import os, json, time, re, html, calendar, requests, feedparser
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from graphic import render

def gn(q, days=2):
    return "https://news.google.com/rss/search?q=" + quote(q + " when:" + str(days) + "d") + "&hl=en-US&gl=US&ceid=US:en"

# (name, url, fallback site if the feed is blocked)
FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", ""),
    ("Cointelegraph", "https://cointelegraph.com/rss", ""),
    ("Decrypt", "https://decrypt.co/feed", ""),
    ("The Block", "https://www.theblock.co/rss.xml", ""),
    ("Bitcoin Magazine", "https://bitcoinmagazine.com/feed", ""),
    ("CryptoSlate", "https://cryptoslate.com/feed/", ""),
    ("U.Today", "https://u.today/rss", ""),
    ("BeInCrypto", "https://beincrypto.com/feed/", ""),
    ("CryptoPotato", "https://cryptopotato.com/feed/", ""),
    ("NewsBTC", "https://www.newsbtc.com/feed/", ""),
    ("Bitcoinist", "https://bitcoinist.com/feed/", ""),
    ("AMBCrypto", "https://ambcrypto.com/feed/", ""),
    ("Blockworks", "https://blockworks.co/feed", ""),
    ("Crypto Briefing", "https://cryptobriefing.com/feed/", ""),
    ("CoinGape", "https://coingape.com/feed/", "coingape.com"),
    ("Cryptonews", "https://cryptonews.com/news/feed/", ""),
    ("Cryptopolitan", "https://www.cryptopolitan.com/feed/", ""),
    ("Protos", "https://protos.com/feed/", ""),
    ("Unchained", "https://unchainedcrypto.com/feed/", ""),
    ("crypto.news", "https://crypto.news/feed/", ""),
    ("DL News", "https://www.dlnews.com/arc/outboundfeeds/rss/", "dlnews.com"),
    ("Ethereum Foundation", "https://blog.ethereum.org/feed.xml", ""),
    ("Kraken Blog", "https://blog.kraken.com/feed", ""),
    ("CoinGecko Blog", "https://blog.coingecko.com/rss/", ""),
    ("NFT Evening", "https://nftevening.com/feed/", "nftevening.com"),
    ("NFT Now", "https://nftnow.com/feed/", "nftnow.com"),
    ("NFT Plazas", "https://nftplazas.com/feed/", "nftplazas.com"),
    ("NFTgators", "https://nftgators.com/feed/", "nftgators.com"),
    ("DappRadar", "https://dappradar.com/blog/feed", "dappradar.com"),
    ("Meme Insider", "https://memeinsider.com/feed", "memeinsider.com"),
    ("Rekt News", "https://rekt.news/rss.xml", "rekt.news"),
    ("Web3 Is Going Great", "https://www.web3isgoinggreat.com/feed", "web3isgoinggreat.com"),
    ("SlowMist", "https://slowmist.medium.com/feed", ""),
    ("GN:listing1", gn('"will list" OR "lists" OR "to list" Binance OR Coinbase OR Upbit OR Bithumb OR Bybit OR OKX token'), ""),
    ("GN:listing2", gn("new token listing spot trading"), ""),
    ("GN:listing3", gn("Coinbase OR Robinhood OR Kraken lists token"), ""),
    ("GN:launch1", gn("launchpad OR launchpool OR IDO crypto"), ""),
    ("GN:launch2", gn("token generation event TGE airdrop"), ""),
    ("GN:perp1", gn('"perp DEX"'), ""),
    ("GN:perp2", gn("perpetual futures DEX launch"), ""),
    ("GN:chain1", gn("testnet launch blockchain"), ""),
    ("GN:chain2", gn("mainnet launch blockchain"), ""),
    ("GN:nft1", gn("upcoming NFT mint"), ""),
    ("GN:nft2", gn("NFT collection floor price"), ""),
    ("GN:nft3", gn('NFT sales OpenSea OR "Magic Eden"'), ""),
    ("GN:meme1", gn("memecoin"), ""),
    ("GN:meme2", gn("memecoin rally OR pump OR crash"), ""),
    ("GN:meme3", gn("pump.fun OR Bonk OR Dogecoin OR Pepe OR Shiba Inu"), ""),
    ("GN:trader1", gn("crypto whale transfers OR accumulation"), ""),
    ("GN:trader2", gn("crypto trader liquidation OR profit OR loss"), ""),
    ("GN:token1", gn("token unlock OR vesting crypto"), ""),
    ("GN:scam1", gn('crypto rug pull OR "exit scam" OR phishing OR drainer'), ""),
    ("GN:scam2", gn("DeFi exploit OR hack drained million"), ""),
]
NICHE = {"NFT Evening", "NFT Now", "NFT Plazas", "NFTgators", "DappRadar", "Meme Insider", "Rekt News",
         "Web3 Is Going Great", "SlowMist", "Protos", "Kraken Blog", "CoinGecko Blog"}
MODEL = "gemini-3.8-flash"
MIN_SCORE = 5
MAX_CANDIDATES = 60
MAX_DRAFTS = 6
GENERAL_MAX = 2
PRIORITY = ["nft", "meme", "listing", "launch", "token", "trader", "scam"]
CG_KEY = os.environ.get("COINGECKO_KEY", "").strip()
MAX_AGE_HOURS = 24
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]
MANUAL = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
errors = []

SCORE_PROMPT = """You are the news editor of @YoXo_Station, an X account about Web3: crypto, blockchain, NFTs, DeFi, stablecoins, exchanges, tokenization, memecoins, traders and whales, Web3 gaming, AI x crypto, and regulation that affects them.
You get NEW STORIES (id | source | title | snippet) and RECENT POSTS that were already sent.

For EVERY story return:
- "score" 1-10 = how likely people are to read and share it as a Web3 post.
  8-10: hacks, exploits, rug pulls or scams with big numbers; major exchange listings (Binance, Coinbase, Upbit, Bybit, OKX, Bithumb, Robinhood); big launches (launchpads, perp DEXs, testnet or mainnet going live, airdrops); hyped NFT collections or mints; trending memecoins; big whale or trader moves; big institutions moving in or out; regulation decisions; record numbers; big names.
  6-7: genuine news in the niche categories (listing, launch, nft, meme, trader, token, scam) even if smaller. Give these at least 6 unless sponsored or purely promotional.
  4-5: solid but low-impact general news.
  1-3: price predictions and technical-analysis articles, sponsored or promoted content, opinion pieces, how-to guides, listicles, or anything NOT related to Web3.
  DATA ALERTS (items whose source is CoinGecko or DexScreener: price moves, NFT floor moves, trending or new tokens) are real news. Score them by size and substance: NFT floor move of 30% or more = 7; memecoin or small token move of 100% or more with real liquidity = 7; new token with real liquidity = 6; top-100 coin move of 10% or more = 6; tiny moves or illiquid tokens = 4.
- "cat" = one of: listing, launch, nft, meme, scam, trader, token, regulation, market, other.
- "dup" = true if the story reports the same news event as any RECENT POST, or as another story earlier in the list. If several stories cover one event, keep dup=false only on the best one. Different tokens or projects are different events, even if the headline wording is similar.

Return ONLY JSON: [{"id": int, "score": int, "cat": str, "dup": bool}, ...] with one item per story.

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
Given a news story, do two things.

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
No guessing about what it could mean for price, adoption or market perception unless the source quotes someone saying it.
If the snippet is only a headline, write a shorter post (hook plus 2 lines) from the facts in it.
If the story is a data alert (price move, NFT floor move, trending or new token), write it from the numbers only: hook with the move and the number, then lines with the price, 24h and 1h change, volume, liquidity or floor price, whichever are given. For small DEX tokens add one line saying it is high-risk when liquidity is under $250K. No predictions, no advice to buy or sell.

2) """ + GRAPHIC_SPEC + """

Return ONLY JSON:
{"post": str, """ + GRAPHIC_JSON + """}

"""

MINT_PROMPT = """You are the editor of @YoXo_Station, a Web3 news account on X.
Below are NFT news items from the last 36 hours (title | source | snippet). Build today's NFT MINT LIST post using ONLY mints, drops or collections mentioned in these items: the name, the chain, and the mint date, time or price ONLY if the items state them.

FORMAT: line 1: "TODAY'S NFT MINT LIST:" plus a short teaser (ALL CAPS, max 14 words). Blank line. Then 4-6 lines, one per collection: "- Name (Chain): date or time, price" (leave out anything the items do not say). Last line: one short note on the hottest drop, using only facts from the items. Under 700 characters. No hashtags, no emojis.
If fewer than 3 real upcoming or live mints are mentioned, return {"skip": true}.

Also fill in the graphic. """ + GRAPHIC_SPEC + """ For this post the objects must be from: calendar (text = today's day number), ticket or nft.

Return ONLY JSON: {"skip": false, "post": str, """ + GRAPHIC_JSON + """} or {"skip": true}

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

GENERIC_CAPS = {"sec", "etf", "us", "ai", "nft", "dex", "defi", "usd", "uk", "eu", "ceo", "cto", "api"}

def hard(s):
    out = set()
    for w in re.findall(r"[A-Za-z0-9$%.\-]+", s):
        lw = w.lower().strip(".-")
        if not lw:
            continue
        if (w.isupper() and 2 <= len(w) <= 6 and lw not in GENERIC_CAPS) or any(ch.isdigit() for ch in w) or "$" in w:
            out.add(lw)
    return out

def similar(a, b):
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return False
    ha, hb = hard(a), hard(b)
    if ha and hb and not (ha & hb):
        return False
    inter = ta & tb
    if ta == tb:
        return True
    return len(inter) >= 4 and len(inter) / len(ta | tb) >= 0.75

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
    st = {"links": [], "n": 0, "titles": [], "sent": [], "objs": [], "mint_day": "", "mint_tries": 0, "mint_done": False, "queue": [], "rr": 0}
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
    out["v"] = 6
    out["links"] = sorted(st["links"])[-4000:]
    out["titles"] = st["titles"][-400:]
    out["sent"] = st["sent"][-30:]
    out["objs"] = st["objs"][-10:]
    out["queue"] = st["queue"][:60]
    json.dump(out, open("seen.json", "w"))

def age_ok(entry, hours):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return True
    dt = datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt < timedelta(hours=hours)

def get_entries(url):
    try:
        r = requests.get(url, headers=UA, timeout=15)
        if r.ok:
            return "ok", feedparser.parse(r.content).entries
        return "fail", []
    except Exception:
        return "fail", []

def fetch_feed(item):
    name, url, site = item
    status, ents = get_entries(url)
    via_gn = name.startswith("GN:")
    if not ents and site:
        status2, ents = get_entries(gn("site:" + site))
        if ents:
            return name, ents, True, "ok"
    return name, ents, via_gn, status if ents else ("empty" if status == "ok" else "fail")

def is_niche(name):
    return name.startswith("GN:") or name in NICHE

def send(text, link=""):
    try:
        body = {"chat_id": TG_CHAT, "text": text[:4000], "disable_web_page_preview": True}
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", json=body, timeout=30)
        if not r.ok:
            errors.append(f"Telegram {r.status_code}: {r.text[:150]}")
            return False
        return True
    except Exception as ex:
        errors.append(f"Telegram error: {str(ex)[:100]}")
        return False

def send_photo(png, caption, link="", label="Source"):
    try:
        data = {"chat_id": TG_CHAT, "caption": caption[:1024]}
        if link:
            data["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": label, "url": link}]]})
        r = requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto", data=data,
                          files={"photo": ("graphic.png", png, "image/png")}, timeout=60)
        if not r.ok:
            errors.append(f"Photo {r.status_code}: {r.text[:100]}")
        return r.ok
    except Exception as ex:
        errors.append(f"Photo error: {str(ex)[:100]}")
        return False

def fit_caption(post, stamp, limit=1000):
    tail = ("\n\n" + stamp) if stamp else ""
    parts = post.split("\n\n")
    while len("\n\n".join(parts)) + len(tail) > limit and len(parts) > 2:
        parts.pop()
    text = "\n\n".join(parts)
    if len(text) + len(tail) > limit:
        text = text[: limit - len(tail) - 1].rstrip() + "..."
    return text + tail

def build_post(out, st):
    g = out.get("graphic") or {}
    choose_object(g, st["objs"], str(g.get("kicker", "")))
    png = None
    try:
        png = render(g, variant=st["n"])
        st["n"] += 1
    except Exception as ex:
        errors.append("Graphic error: " + str(ex)[:100])
    st["objs"].append(str(g.get("object", "")).lower())
    return str(out.get("post", "")).rstrip(), g, png

def deliver(post, stamp, png, link="", label="Source"):
    caption = fit_caption(post, stamp)
    if png and send_photo(png, caption, link, label):
        return True
    return send(caption + (("\n\nSource: " + link) if link else ""))

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

def parse_json(text):
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    for cand in (t, re.sub(r",\s*([}\]])", r"\1", t)):
        try:
            return json.loads(cand)
        except Exception:
            pass
    t2 = re.sub(r",\s*([}\]])", r"\1", t)
    m = re.search(r"(\{.*\}|\[.*\])", t2, re.S)
    if m:
        return json.loads(m.group(1))
    raise ValueError("no valid JSON")

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
                    return parse_json(data["candidates"][0]["content"]["parts"][0]["text"])
                except Exception as ex:
                    last = f"{model} bad output: {str(ex)[:80]}"
                    break
            last = f"{model} {r.status_code}"
            if r.status_code in (429, 500, 503):
                time.sleep(4)
                continue
            break
    raise Exception(last)

def build_pool(results, seen):
    pool, nft_items = [], []
    for name, ents, via_gn, status in results:
        limit = 15 if name.startswith("GN:") else 25
        for e in ents[:limit]:
            link = e.get("link")
            title = clean_html(e.get("title", ""))
            source = name
            if via_gn and " - " in title:
                title, source = title.rsplit(" - ", 1)
            elif name.startswith("GN:"):
                source = "Google News"
            if not link or not title:
                continue
            item = {"feed": name, "source": source, "title": title, "link": link,
                    "summary": clean_html(e.get("summary", "")), "entry": e}
            if ("nft" in name.lower() or name in ("NFT Evening", "NFT Now", "NFT Plazas", "NFTgators", "DappRadar")) and age_ok(e, 36):
                nft_items.append(item)
            if link not in seen and age_ok(e, MAX_AGE_HOURS):
                pool.append(item)
    pool.sort(key=lambda c: tuple(c["entry"].get("published_parsed") or c["entry"].get("updated_parsed") or ()), reverse=True)
    return pool, nft_items

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
        post, g, png = build_post(out, st)
        if deliver(post, "Compiled: " + fmt_mm(now), png):
            st["mint_done"] = True
            return 1
    except Exception as ex:
        errors.append("Mint list: " + str(ex)[:100])
    return 0

def money(v):
    try:
        v = float(v)
    except Exception:
        return str(v)
    if v >= 1000:
        return f"${v:,.0f}"
    if v >= 1:
        return f"${v:,.2f}"
    if v >= 0.01:
        return f"${v:.4f}"
    return "$" + f"{v:.8f}".rstrip("0")

def big(v):
    try:
        v = float(v)
    except Exception:
        return "n/a"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(v) >= div:
            return f"${v / div:.1f}{unit}"
    return f"${v:.0f}"

def mk(feed, source, title, summary, link):
    return {"feed": feed, "source": source, "title": title, "link": link, "summary": summary,
            "entry": {"published_parsed": time.gmtime()}}

def cg_get(path):
    headers = {"accept": "application/json", "User-Agent": UA["User-Agent"]}
    if CG_KEY:
        headers["x-cg-demo-api-key"] = CG_KEY
    return requests.get("https://api.coingecko.com/api/v3" + path, headers=headers, timeout=20)

def data_items():
    """Real price, NFT floor and new-token data, turned into news items."""
    items, status = [], {}
    day = mm_now().strftime("%Y%m%d")
    try:
        r = cg_get("/search/trending")
        status["cg-trending"] = "ok" if r.ok else "http " + str(r.status_code)
        j = r.json() if r.ok else {}
        n_nft = 0
        for n in (j.get("nfts") or [])[:7]:
            try:
                pct = float(n.get("floor_price_24h_percentage_change"))
            except Exception:
                continue
            if abs(pct) < 8 or n_nft >= 5:
                continue
            n_nft += 1
            d = n.get("data") or {}
            sym = n.get("native_currency_symbol", "ETH")
            floor = n.get("floor_price_in_native_currency")
            way = "up" if pct > 0 else "down"
            title = f"{n.get('name', 'NFT collection')} NFT floor {way} {abs(pct):.0f}% in 24h" + (f" to {round(float(floor), 3)} {sym}" if floor is not None else "")
            summary = (f"CoinGecko trending NFT collection. Floor price {floor} {sym}. 24h floor change {pct:+.1f}%. "
                       f"24h volume {d.get('h24_volume', 'n/a')}. Average sale price {d.get('h24_average_sale_price', 'n/a')}.")
            items.append(mk("DATA:nft", "CoinGecko", title, summary,
                            f"https://www.coingecko.com/en/nft/{n.get('id', '')}#{day}-{way}-{int(abs(pct) // 25)}"))
        n_coin = 0
        for c in (j.get("coins") or [])[:15]:
            it = c.get("item") or {}
            d = it.get("data") or {}
            pc = d.get("price_change_percentage_24h")
            try:
                pct = float(pc.get("usd") if isinstance(pc, dict) else pc)
            except Exception:
                continue
            if abs(pct) < 8 or n_coin >= 5:
                continue
            n_coin += 1
            way = "up" if pct > 0 else "down"
            title = f"{it.get('name', 'Token')} (${str(it.get('symbol', '')).upper()}) trending, {way} {abs(pct):.0f}% in 24h"
            summary = (f"CoinGecko trending token, market cap rank {it.get('market_cap_rank', 'n/a')}. Price {money(d.get('price'))}. "
                       f"24h change {pct:+.1f}%. Market cap {d.get('market_cap', 'n/a')}. 24h volume {d.get('total_volume', 'n/a')}.")
            items.append(mk("DATA:token", "CoinGecko", title, summary,
                            f"https://www.coingecko.com/en/coins/{it.get('id', '')}#{day}-{way}-{int(abs(pct) // 15)}"))
    except Exception as ex:
        status["cg-trending"] = "error " + str(ex)[:40]
    try:
        r = cg_get("/coins/markets?vs_currency=usd&order=volume_desc&per_page=100&page=1&price_change_percentage=1h,24h")
        status["cg-markets"] = "ok" if r.ok else "http " + str(r.status_code)
        movers = []
        for c in (r.json() if r.ok else []):
            try:
                pct = float(c.get("price_change_percentage_24h"))
            except Exception:
                continue
            if abs(pct) >= 12 and (c.get("market_cap_rank") or 9999) <= 400:
                movers.append((abs(pct), c, pct))
        movers.sort(key=lambda x: -x[0])
        for _, c, pct in movers[:5]:
            way = "up" if pct > 0 else "down"
            h1 = c.get("price_change_percentage_1h_in_currency")
            title = f"{c.get('name')} (${str(c.get('symbol', '')).upper()}) {'jumps' if pct > 0 else 'drops'} {abs(pct):.0f}% in 24h to {money(c.get('current_price'))}"
            summary = (f"CoinGecko market data. Price {money(c.get('current_price'))}. 24h change {pct:+.1f}%"
                       + (f", 1h change {float(h1):+.1f}%" if h1 is not None else "")
                       + f". 24h volume {big(c.get('total_volume'))}. Market cap {big(c.get('market_cap'))}, rank {c.get('market_cap_rank')}.")
            items.append(mk("DATA:token", "CoinGecko", title, summary,
                            f"https://www.coingecko.com/en/coins/{c.get('id', '')}#{day}-{way}-{int(abs(pct) // 12)}"))
    except Exception as ex:
        status["cg-markets"] = "error " + str(ex)[:40]
    try:
        addrs = {}
        ok_any = False
        for path in ("/token-boosts/top/v1", "/token-boosts/latest/v1", "/token-profiles/latest/v1"):
            r = requests.get("https://api.dexscreener.com" + path, headers=UA, timeout=20)
            if not r.ok:
                continue
            ok_any = True
            for t in (r.json() or [])[:40]:
                ch, ad = t.get("chainId"), t.get("tokenAddress")
                if ch and ad and ad not in addrs.setdefault(ch, []):
                    addrs[ch].append(ad)
        status["dexscreener"] = "ok" if ok_any else "no data"
        n_dex = 0
        for ch, lst in list(addrs.items())[:5]:
            r = requests.get(f"https://api.dexscreener.com/tokens/v1/{ch}/{','.join(lst[:30])}", headers=UA, timeout=20)
            if not r.ok:
                continue
            best = {}
            for p in r.json() or []:
                key = (p.get("baseToken") or {}).get("address")
                liq = (p.get("liquidity") or {}).get("usd") or 0
                if key and liq >= (best.get(key, {}).get("liquidity") or {}).get("usd", 0):
                    best[key] = p
            for p in best.values():
                liq = (p.get("liquidity") or {}).get("usd") or 0
                vol = (p.get("volume") or {}).get("h24") or 0
                pc = p.get("priceChange") or {}
                h24, h1 = float(pc.get("h24") or 0), float(pc.get("h1") or 0)
                created = p.get("pairCreatedAt")
                age_h = (time.time() * 1000 - created) / 3.6e6 if created else None
                new_token = age_h is not None and age_h < 24
                if liq < 40000 or vol < 100000 or not (abs(h24) >= 40 or h1 >= 20 or new_token) or n_dex >= 10:
                    continue
                n_dex += 1
                bt = p.get("baseToken") or {}
                name, sym = bt.get("name", "Token"), str(bt.get("symbol", "")).upper()
                way = "up" if h24 >= 0 else "down"
                if new_token and abs(h24) < 40:
                    title = f"New token {name} (${sym}) launches on {ch} with {big(liq)} liquidity"
                else:
                    title = f"{name} (${sym}) {'surges' if h24 >= 0 else 'plunges'} {abs(h24):.0f}% in 24h on {ch}"
                summary = (f"DexScreener trending DEX token on {ch}. Price {money(p.get('priceUsd'))}. 24h change {h24:+.0f}%, 1h change {h1:+.0f}%. "
                           f"24h volume {big(vol)}. Liquidity {big(liq)}. Market cap {big(p.get('marketCap') or p.get('fdv'))}. "
                           + (f"Pair is {age_h:.0f} hours old. " if age_h is not None else "") + "High-risk small-cap DEX token.")
                items.append(mk("DATA:meme", "DexScreener", title, summary,
                                (p.get("url") or "https://dexscreener.com") + f"#{day}-{way}-{int(abs(h24) // 50)}"))
    except Exception as ex:
        status["dexscreener"] = "error " + str(ex)[:40]
    return items, status

def entry_ts(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    return calendar.timegm(t) if t else time.time()

def to_queue(c):
    return {"feed": c["feed"], "source": c["source"], "title": c["title"], "link": c["link"], "summary": c["summary"][:500],
            "cat": c.get("cat", "other"), "score": c.get("score", 0), "ts": entry_ts(c["entry"])}

def from_queue(q):
    cutoff = time.time() - 16 * 3600
    out = []
    for d in q:
        try:
            if d["ts"] >= cutoff:
                out.append({"feed": d["feed"], "source": d["source"], "title": d["title"], "link": d["link"], "summary": d["summary"],
                            "entry": {"published_parsed": time.gmtime(d["ts"])}, "score": d["score"], "cat": d["cat"], "dup": False})
        except Exception:
            continue
    return out

def select(items, rr):
    """Fair pick: one story from each priority category in rotation, then the best general news, then the best of the rest."""
    items = sorted(items, key=lambda c: (-c["score"], -entry_ts(c["entry"])))
    buckets = {}
    for c in items:
        buckets.setdefault(c["cat"] if c["cat"] in PRIORITY else "general", []).append(c)
    k = rr % len(PRIORITY)
    order = PRIORITY[k:] + PRIORITY[:k]
    chosen, per = [], {}
    def take(c):
        chosen.append(c)
        key = c["cat"] if c["cat"] in PRIORITY else "general"
        per[key] = per.get(key, 0) + 1
        buckets[key].remove(c)
    for cat in order:
        if buckets.get(cat) and len(chosen) < MAX_DRAFTS:
            take(buckets[cat][0])
    for c in list(buckets.get("general", []))[:GENERAL_MAX]:
        if len(chosen) < MAX_DRAFTS:
            take(c)
    rest = [c for c in items if c not in chosen]
    for c in rest:
        key = c["cat"] if c["cat"] in PRIORITY else "general"
        if len(chosen) >= MAX_DRAFTS:
            break
        if per.get(key, 0) < (2 if key != "general" else GENERAL_MAX):
            take(c)
    return chosen

def write_one(args):
    c, recent_objs = args
    try:
        prompt = WRITE_PROMPT + "RECENTLY USED OBJECTS (avoid repeating these): " + ", ".join(recent_objs[-4:]) + "\n\n"
        return c, gemini(prompt + f"STORY:\nSource: {c['source']}\nTitle: {c['title']}\nSummary: {c['summary'][:2500]}\nLink: {c['link']}"), None
    except Exception as ex:
        return c, None, ex

def main():
    if MANUAL:
        send("Bot started. Checking news...")

    st = load_state()
    seen = st["links"]
    queued = from_queue(st["queue"])
    queued_links = set(c["link"] for c in queued)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(fetch_feed, FEEDS))
    failed = [r[0] for r in results if r[3] == "fail"]
    empty = [r[0] for r in results if r[3] == "empty"]
    pool, nft_items = build_pool(results, seen)
    try:
        dpool, dstatus = data_items()
    except Exception as ex:
        dpool, dstatus = [], {"data": "error " + str(ex)[:40]}
    pool = pool + [d for d in dpool if d["link"] not in seen]

    # balanced candidates: niche and data sources first, then general sources
    cands, skipped_dups, per = [], 0, {}
    for phase in (1, 2):
        for c in pool:
            if len(cands) >= MAX_CANDIDATES:
                break
            niche = is_niche(c["feed"]) or c["feed"].startswith("DATA:")
            if (phase == 1) != niche or c["link"] in seen or c["link"] in queued_links or any(k is c for k in cands):
                continue
            cap = 4 if c["feed"].startswith("DATA:") else (2 if niche else 3)
            if per.get(c["feed"], 0) >= cap:
                continue
            if any(similar(c["title"], t) for t in st["titles"]) or any(similar(c["title"], k["title"]) for k in cands):
                seen.add(c["link"])
                skipped_dups += 1
                continue
            per[c["feed"]] = per.get(c["feed"], 0) + 1
            cands.append(c)

    drafts, scores, dups = 0, [], 0
    qualifying, scored_ok = [], True
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
            by_id, scored_ok = None, False
        if by_id is not None:
            for i, c in enumerate(cands):
                r = by_id.get(i, {})
                c["score"] = int(r.get("score", 0) or 0)
                c["dup"] = bool(r.get("dup", False))
                c["cat"] = str(r.get("cat", "other")).lower()
                scores.append(c["score"])
                dups += 1 if c["dup"] else 0
                seen.add(c["link"])
                st["titles"].append(c["title"])
                if c["score"] >= MIN_SCORE and not c["dup"]:
                    qualifying.append(c)

    # new qualifying stories join the queue of stories that did not fit in earlier runs
    pool_all = queued + qualifying
    picked = select(pool_all, st["rr"]) if scored_ok else []
    st["rr"] += 1
    cats = {}
    for c in picked:
        cats[c["cat"]] = cats.get(c["cat"], 0) + 1

    left = {c["link"]: c for c in pool_all}
    if picked:
        with ThreadPoolExecutor(max_workers=3) as ex:
            written = list(ex.map(write_one, [(c, list(st["objs"])) for c in picked]))
        for c, out, err in written:
            if err is not None or not out:
                errors.append(str(err)[:120])
                continue
            post, g, png = build_post(out, st)
            if deliver(post, mm_time(c["entry"]), png, c["link"], f"Source ({c['score']}/10)"):
                drafts += 1
                left.pop(c["link"], None)
                st["sent"].append(str(g.get("headline") or c["title"]))
            time.sleep(1)
    st["queue"] = [to_queue(c) for c in sorted(left.values(), key=lambda c: -c["score"])[:60]]

    minted = daily_mints(st, nft_items)
    save_state(st)

    if MANUAL:
        send(
            f"Run done. Feeds failed: {', '.join(failed) if failed else 'none'}. Empty: {', '.join(empty) if empty else 'none'}. "
            f"Data: {dstatus}, {len(dpool)} items. New stories: {len(pool)}. Scored: {len(scores)}. Duplicates skipped: {skipped_dups + dups}. "
            f"Sent: {drafts} {cats}. Waiting in queue: {len(st['queue'])}. Mint list: {minted}. Errors: {errors[:3] if errors else 'none'}"
        )

main()
