"""Al-Hilal News Bot - Full Stable & Smart Image Version

Required Environment Variables on Render:
- GEMINI_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import time
import urllib.parse
import threading
from datetime import datetime, timezone, timedelta
import requests
from flask import Flask
import feedparser
from google import genai

app = Flask(__name__)

@app.route('/')
def home():
    return "Hilal News Bot is Active!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


NEWS_FEEDS = {
    "أخبار الهلال": "https://news.google.com/rss/search?q=%D9%86%D8%A7%D8%AF%D9%8A+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "صفقات الهلال والميركاتو": "https://news.google.com/rss/search?q=%D8%B5%D9%81%D9%82%D8%A7%D8%AA+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "تصريحات أكشن مع وليد": "https://news.google.com/rss/search?q=%D8%A3%D9%83%D8%B4%D9%86+%D9%85%D8%B9+%D9%88%D9%84%D9%8A%D8%AF&hl=ar&gl=SA&ceid=SA:ar",
    "دوري روشن السعودي": "https://news.google.com/rss/search?q=%D8%AF%D9%88%D8%B1%D9%8A+%D8%B1%D9%88%D8%B4%D9%86+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A&hl=ar&gl=SA&ceid=SA:ar"
}

DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?q=80&w=1080",
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1080",
    "https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1080"
]

MATCH_IMAGES = {
    "الأهلي": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?q=80&w=1080",
    "النصر": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1080",
    "الاتحاد": "https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1080",
    "كلاسيكو": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1080",
    "ديربي": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?q=80&w=1080"
}

seen_titles = set()
FEMALE_KEYWORDS = ["سيدات", "النساء", "للنساء", "فريق السيدات", "دوري السيدات", "نسائي"]


def is_female_news(text: str) -> bool:
    return any(keyword in text for keyword in FEMALE_KEYWORDS)


def is_recent_news(published_parsed) -> bool:
    if not published_parsed:
        return True
    published_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
    now_dt = datetime.now(timezone.utc)
    return (now_dt - published_dt) < timedelta(hours=3)


def fetch_image_from_entry(entry) -> str:
    """استخراج رابط الصورة المرفقة بملف الخبر الأصلي إن وجدت"""
    try:
        if "media_content" in entry and len(entry.media_content) > 0:
            return entry.media_content[0].get("url")
        if "media_thumbnail" in entry and len(entry.media_thumbnail) > 0:
            return entry.media_thumbnail[0].get("url")
        if "links" in entry:
            for link in entry.links:
                if link.get("type", "").startswith("image/"):
                    return link.get("href")
    except Exception:
        pass
    return None


def fetch_smart_image(text_context: str, entry_image: str = None) -> str:
    """اختيار صورة مطابقة لمضمون الخبر بدقة"""
    if entry_image:
        return entry_image

    for keyword, img_url in MATCH_IMAGES.items():
        if keyword in text_context:
            return img_url

    try:
        clean_query = urllib.parse.quote(f"Al Hilal FC {text_context[:20]}")
        wiki_url = f"https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsearch={clean_query}&prop=pageimages&pithumbsize=1000&format=json"
        res = requests.get(wiki_url, timeout=4).json()
        pages = res.get("query", {}).get("pages", {})
        for _, val in pages.items():
            if "thumbnail" in val:
                return val["thumbnail"]["source"]
    except Exception:
        pass

    import random
    return random.choice(DEFAULT_IMAGES)


def setup_gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("مفتاح GEMINI_API_KEY غير موجود.")
    return genai.Client(api_key=api_key)


def process_with_gemini(client, source_name: str, title: str, summary: str):
    prompt = f"""المصدر: {source_name}
العنوان: {title}
التفاصيل: {summary}

المطلوب إخراج النتيجة بتنسيق محدد يفصل بين اسم الشخصية الرياضية ونص المنشور باستخدام الكلمة المفتاحية "---SPLIT---":

السطر الأول: اسم اللاعب أو الشخصية الرياضية المعنية فقط (مثل: مالكوم أو وليد الفراج أو الهلال).
---SPLIT---
المنشور:
صغ المحتوى كـ خبر عاجل أو تصريح حُصري حماسي لمتابعي الكرة السعودية وجماهير الهلال. ابدأ بـ 🚨🚨🚨 | **عاجل:** أو 🎙️ | **تصريح:**
"""
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        text = response.text
        if "---SPLIT---" in text:
            parts = text.split("---SPLIT---")
            return parts[0].strip(), parts[1].strip()
        else:
            return "الهلال", text.strip()

    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "Quota" in err_msg:
            print("[الكوتا ممتلئة] تخطي مؤقت لحين تجدد الكوتا...", flush=True)
            return None, None
        print(f"[خطأ Gemini] {e}", flush=True)
        return None, None


def send_telegram_photo_post(caption_text: str, photo_url: str) -> bool:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption_text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=15)
        res_data = response.json()
        if res_data.get("ok"):
            print("[نجاح] تم إرسال الخبر إلى تلجرام بنجاح!", flush=True)
            return True
        else:
            import random
            payload["photo"] = random.choice(DEFAULT_IMAGES)
            requests.post(url, json=payload, timeout=10)
            return True
    except Exception as e:
        print(f"[خطأ اتصال] {e}", flush=True)
        return False


def process_single_source(source_key: str, feed_url: str, client) -> bool:
    try:
        parsed_feed = feedparser.parse(feed_url)
    except Exception:
        return False
    
    if not parsed_feed.entries:
        return False

    for entry in parsed_feed.entries[:2]:
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()
        published_parsed = entry.get("published_parsed")

        if not title or title in seen_titles:
            continue

        if is_female_news(title) or is_female_news(summary):
            seen_titles.add(title)
            continue

        if not is_recent_news(published_parsed):
            seen_titles.add(title)
            continue

        print(f"[خبر جديد] جاري التلخيص: {title[:35]}...", flush=True)

        person_name, post_text = process_with_gemini(client, source_key, title, summary)
        
        if not post_text:
            continue

        entry_img = fetch_image_from_entry(entry)
        full_text = f"{title} {summary} {person_name}"
        photo_url = fetch_smart_image(full_text, entry_img)

        if send_telegram_photo_post(post_text, photo_url):
            seen_titles.add(title)
            time.sleep(10)
            return True

    return False


def bot_loop() -> None:
    try:
        client = setup_gemini_client()
        print("[جاهز] تم الاتصال بالـ SDK.", flush=True)
    except Exception as e:
        print(f"[خطأ] {e}", flush=True)
        return

    print("[تشغيل متوازن] البوت يفحص كل 5 دقائق لمنع نفاد الكوتا...", flush=True)

    while True:
        try:
            for source_key, url in NEWS_FEEDS.items():
                process_single_source(source_key, url, client)
                time.sleep(5)
        except Exception as e:
            print(f"[خطأ الدورة] {e}", flush=True)

        time.sleep(300)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    bot_loop()
