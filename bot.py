import os, json, time, requests, feedparser
from datetime import datetime, timezone, timedelta

FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://www.theblock.co/rss.xml",
]
MODEL = "gemini-2.5-flash"
MIN_SCORE = 7
MAX_SCORED = 10
MAX_DRAFTS = 5
MAX_AGE_HOURS = 12

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
TG_TOKEN = os.environ["TELEGRAM_TOKEN"]
TG_CHAT = os.environ["TELEGRAM_CHAT_ID"]

PROMPT = """You are the editor of @YoXo_Station, a Web3 news account on X.
Given a news story, do two things.

1) Score 1-10 how likely people are to actually read and share it
(big numbers, big names, hacks, major launches, regulation, surprising facts score high;
routine price commentary, sponsored content, and opinion pieces score low).

2) Write two versions of an X post.
FORMAT:
Line 1 (hook): "JUST IN:" or "BREAKING:" + the single most surprising fact, with a number if one exists. ALL CAPS, max 20 words.
Line 2-3 (details): 1-2 short lines with key numbers, names, or a direct quote from the source.
Line 4 (optional): one line on why it matters.
Use $CASHTAGS for tokens. No hashtags, no emojis.
RULES: Use ONLY facts in the source. Never invent numbers, quotes or names.
Keep words like "reportedly" or "alleged". No price predictions or financial advice.
Under 280 characters each.

Also give a one-line "verify" note: what the editor should double-check before posting.

Return ONLY JSON: {"score": int, "post_a": str, "post_b": str, "verify": str}

STORY:
"""

def load_seen():
    try:
        return set(json.load(open("seen.json")))
    except Exception:
        return set()

def recent(entry):
    t = entry.get("published_parsed")
    if not t:
        return True
    dt = datetime(*t[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - dt < timedelta(hours=MAX_AGE_HOURS)

def ask_gemini(title, summary, link):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_KEY}"
    story = f"Title: {title}\nSummary: {summary[:1500]}\nLink: {link}"
    body = {
        "contents": [{"parts": [{"text": PROMPT + story}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    r = requests.post(url, json=body, timeout=60)
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)

def send(text):
    requests.post(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        json={"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )

def main():
    seen = load_seen()
    new = []
    for feed in FEEDS:
        for e in feedparser.parse(feed).entries:
            link = e.get("link")
            if link and link not in seen and recent(e):
                new.append(e)

    drafts = 0
    for e in new[:MAX_SCORED]:
        link = e.link
        try:
            res = ask_gemini(e.get("title", ""), e.get("summary", ""), link)
            if res["score"] >= MIN_SCORE and drafts < MAX_DRAFTS:
                send(
                    f"Score {res['score']}/10\n\nA:\n{res['post_a']}\n\n"
                    f"B:\n{res['post_b']}\n\nVerify: {res['verify']}\n\nSource: {link}"
                )
                drafts += 1
        except Exception as ex:
            print("error:", ex)
        seen.add(link)
        time.sleep(5)

    json.dump(sorted(seen)[-2000:], open("seen.json", "w"))

main()
