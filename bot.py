import os, json, time, requests, feedparser
from datetime import datetime, timezone, timedelta

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
Given a news story, do two things.

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

Also give a one-line "verify" note: what the editor should double-check before posting.

Return ONLY JSON: {"score": int, "post": str, "verify": str}

STORY:
"""

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
            f"Models: {MODELS}. Errors: {errors[:3] if errors else 'none'}"
        )

main()
