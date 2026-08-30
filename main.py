"""Al-Hilal & Saudi Football Smart News Bot

Features:
- Smart Entity Recognition: Extracts player/coach names from news using Gemini.
- Dynamic Fresh Image Fetching: Searches for fresh, high-quality images of the specific person/player without copyrights.
- Comprehensive Saudi Football Feeds: Expanded RSS sources covering all major Saudi football updates.
- Time Filter: Excludes articles older than 4 hours.
- Gender Filter: Automatically filters out women's sports news.

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
    return "Hilal Smart Entity & Multi-Source Bot is Active!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# 1. توسيع مصادر الأخبار لتشمل كافة تحركات الشارع الرياضي السعودي
NEWS_FEEDS = {
    "أخبار الهلال": "https://news.google.com/rss/search?q=%D9%86%D8%A7%D8%AF%D9%8A+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "صفقات الهلال والميركاتو": "https://news.google.com/rss/search?q=%D8%B5%D9%81%D9%82%D8%A7%D8%AA+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "دوري روشن السعودي": "https://news.google.com/rss/search?q=%D8%AF%D9%88%D8%B1%D9%8A+%D8%B1%D9%88%D8%B4%D9%86+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A&hl=ar&gl=SA&ceid=SA:ar",
    "تصريحات أكشن مع وليد": "https://news.google.com/rss/search?q=%D8%A3%D9%83%D8%B4%D9%86+%D9%85%D8%B9+%D9%88%D9%84%D9%8A%D8%AF&hl=ar&gl=SA&ceid=SA:ar",
    "البرامج الرياضية السعودية": "https://news.google.com/rss/search?q=%D8%AA%D8%B5%D8%B1%D9%8A%D8%AD%D8%A7%D8%AA+%D8%A7%D9%84%D9%81%D8%B1%D8%A7%D8%AC+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "أخبار كورة سعودية شاملة": "https://news.google.com/rss/search?q=%D9%83%D8%B1%D8%A9+%D8%A7%D9%84%D9%82%D8%AF%D9%85+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9&hl=ar&gl=SA&ceid=SA:ar",
    "المنتخب السعودي": "https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%85%D9%86%D8%AA%D8%AE%D8%A8+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A&hl=ar&gl=SA&ceid=SA:ar"
}

DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1080",
    "https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1080",
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?q=80&w=1080"
]

seen_titles = set()
FEMALE_KEYWORDS = ["سيدات", "النساء", "للنساء", "فريق السيدات", "دوري السيدات", "نسائي"]


def extract_person_name(client: genai.Client, text: str) -> str:
    """استخراج اسم اللاعب أو الشخصية الرياضية الرئيسية من الخبر لطلب صورته."""
    prompt = f"""من الخبر التالي، استخرج فقط اسم شخصية رياضية رئيسية واحدة (لاعب، مدرب، أو مسؤول) يخصه الخبر بشكل أساسي.
إذا لم يوجد اسم شخص محدد، اخرج كلمة "الهلال" أو "دوري روشن".
لا تكتب أي مقدمات أو شرح، اكتب الاسم فقط.

الخبر:
{text}"""
    try:
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        res = client.models.generate_content(model=model_name, contents=prompt)
        person_name = res.text.strip().replace("\n", "")
        return person_name
    except Exception:
        return "Al Hilal FC"


def fetch_smart_image(search_query: str) -> str:
    """البحث المباشر عن صورة حديثة عالية الجودة بدلالة اسم اللاعب عبر الإنترنت."""
    try:
        # البحث في Unsplash API كمصدر مجاني مفتوح الحقوق
        query = urllib.parse.quote(f"{search_query} football soccer player")
        url = f"https://source.unsplash.com/1600x900/?{query}"
        res = requests.head(url, timeout=5, allow_redirects=True)
        if res.status_code == 200 and res.url:
            return res.url
    except Exception as e:
        print(f"[تنبيه البحث عن الصور] تعذر جلب صورة مخصصة: {e}", flush=True)

    import random
    return random.choice(DEFAULT_IMAGES)


def is_female_news(text: str) -> bool:
    for keyword in FEMALE_KEYWORDS:
        if keyword in text:
            return True
    return False


def is_recent_news(published_parsed) -> bool:
    if not published_parsed:
        return True
    published_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
    now_dt = datetime.now(timezone.utc)
    return (now_dt - published_dt) < timedelta(hours=4)


def send_telegram_photo_post(caption_text: str, photo_url: str) -> bool:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[خطأ] مفاتيح تلجرام مفقودة!", flush=True)
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
            print("[نجاح] تم إرسال الخبر مع صورة الشخصية المعنية بنجاح!", flush=True)
            return True
        else:
            # صورة احتياطية في حال تعثر رابط الصورة الأولى
            import random
            payload["photo"] = random.choice(DEFAULT_IMAGES)
            requests.post(url, json=payload, timeout=10)
            return True
    except Exception as e:
        print(f"[خطأ اتصال] تعذر الاتصال بتلجرام: {e}", flush=True)
        return False


def create_gemini_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("مفتاح GEMINI_API_KEY غير موجود.")
    return genai.Client(api_key=api_key)


def generate_text(client: genai.Client, prompt: str) -> str:
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text


def build_news_prompt(source_name: str, title: str, summary: str) -> str:
    return f"""المصدر: {source_name}
عنوان الخبر أو التصريح: {title}
تفاصيل الخبر: {summary}

المطلوب:
1. صغ المحتوى كـ خبر عاجل أو تصريح حُصري موجه لمتابعي الكرة السعودية وجماهير الهلال.
2. ابدأ المنشور بـ 🚨🚨🚨 | **عاجل:** أو 🎙️ | **تصريح قاطِع:** أو **خبر هلالي:**
3. اذكر اسم الشخصية الرياضية صراحة وبوضوح داخل النص المنسق.
4. حافظ على الحماس وتجنب الكلام الإضافي أو المقدمات المكررة.
"""


def process_feed(source_key: str, feed_url: str, gemini_client: genai.Client) -> int:
    print(f"[فحص] جاري قراءة مصدر: {source_key}", flush=True)
    parsed_feed = feedparser.parse(feed_url)
    
    if not parsed_feed.entries:
        return 0

    sent_count = 0
    for entry in parsed_feed.entries[:5]:
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

        print(f"[جاري العمل] خبر مقبول: {title[:50]}...", flush=True)

        # 1. تحليل نص الخبر هرمياً لمعرفة اسم الشخصية الرياضية المعنية بالخبر
        person_name = extract_person_name(gemini_client, f"{title} {summary}")
        print(f"[ذكاء اصطناعي] تم التعرف على الشخصية: {person_name}", flush=True)

        # 2. البحث عن صورة خاصة ومحدثة للشخصية
        photo_url = fetch_smart_image(person_name)

        # 3. صياغة المنشور
        prompt = build_news_prompt(source_key, title, summary)
        
        try:
            post_text = generate_text(gemini_client, prompt)
            if send_telegram_photo_post(post_text, photo_url):
                seen_titles.add(title)
                sent_count += 1
                time.sleep(5)  # فاصل زمني لتجنب إغراق القناة
        except Exception as e:
            print(f"[خطأ معالجة] {e}", flush=True)

    return sent_count


def bot_loop() -> None:
    try:
        gemini_client = create_gemini_client()
        print("[جاهز] تم الاتصال بـ Gemini API بنجاح.", flush=True)
    except Exception as e:
        print(f"[خطأ قاتل] فشل تهيئة Gemini Client: {e}", flush=True)
        return

    print("[بدء التشغيل] البوت الذكي يراقب الشارع الرياضي السعودي كاملاً الآن...", flush=True)

    while True:
        try:
            for source_key, url in NEWS_FEEDS.items():
                process_feed(source_key, url, gemini_client)
        except Exception as e:
            print(f"[خطأ في الدورة] {e}", flush=True)

        time.sleep(30)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    bot_loop()
