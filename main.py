"""Al-Hilal News Telegram Bot (With Images & Fresh News Filter)

- Filters news to only publish articles from the last 3 hours.
- Attaches high-quality images to every Telegram post.
- Excludes women's sports news automatically.
- Uses gemini-3.6-flash.

Required Environment Variables on Render:
- GEMINI_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import time
import threading
from datetime import datetime, timezone, timedelta
import requests
from flask import Flask
import feedparser
from google import genai

app = Flask(__name__)

@app.route('/')
def home():
    return "Hilal News Bot is Active on Render!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


NEWS_FEEDS = {
    "أخبار الهلال": "https://news.google.com/rss/search?q=%D9%86%D8%A7%D8%AF%D9%8A+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "صفقات الهلال": "https://news.google.com/rss/search?q=%D8%B5%D9%81%D9%82%D8%A7%D8%AA+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "دوري روشن": "https://news.google.com/rss/search?q=%D8%AF%D9%88%D8%B1%D9%8A+%D8%B1%D9%88%D8%B4%D9%86&hl=ar&gl=SA&ceid=SA:ar"
}

# مكتبة صور هلالية ورياضية عالية الجودة بديلة لإرفاقها مع الأخبار
DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1080",
    "https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1080",
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?q=80&w=1080",
    "https://images.unsplash.com/photo-1522778119026-d647f0596c20?q=80&w=1080"
]

seen_titles = set()
FEMALE_KEYWORDS = ["سيدات", "النساء", "للنساء", "فريق السيدات", "دوري السيدات", "نسائي"]


def is_female_news(text: str) -> bool:
    for keyword in FEMALE_KEYWORDS:
        if keyword in text:
            return True
    return False


def is_recent_news(published_parsed) -> bool:
    """التحقق مما إذا كان عمر الخبر أقل من 3 ساعات."""
    if not published_parsed:
        return True # في حال عدم توفر التاريخ، نمرره احترازيًا
    
    published_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
    now_dt = datetime.now(timezone.utc)
    
    # حساب الفرق بالساعات
    time_diff = now_dt - published_dt
    return time_diff < timedelta(hours=3)


def send_telegram_photo_post(caption_text: str) -> bool:
    """إرسال الخبر كـ صورة عالية الجودة مع نص تشويقي."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[خطأ] TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID مفقود!", flush=True)
        return False

    # اختيار صورة عشوائية عالية الجودة من القائمة
    import random
    photo_url = random.choice(DEFAULT_IMAGES)

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
            print("[نجاح] تم إرسال الخبر بالصورة إلى تلجرام بنجاح!", flush=True)
            return True
        else:
            print(f"[خطأ تلجرام] فشل الإرسال: {res_data.get('description')}", flush=True)
            return False
    except Exception as e:
        print(f"[خطأ اتصال] تعذر الاتصال بتلجرام: {e}", flush=True)
        return False


def create_gemini_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("مفتاح GEMINI_API_KEY غير موجود في متغيرات البيئة.")
    return genai.Client(api_key=api_key)


def generate_text(client: genai.Client, prompt: str) -> str:
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text


def build_news_prompt(source_name: str, title: str, summary: str) -> str:
    return f"""المصدر: {source_name}
عنوان الخبر: {title}
تفاصيل الخبر: {summary}

المطلوب:
1. صغ المنشور كـ خبر عاجل مخصص لمتابعي نادي الهلال والكرة السعودية للرجال.
2. ابدأ المنشور بـ 🚨🚨🚨 | **عاجل:** أو **خبر هلالي:**
3. اكتب التفاصيل والأسماء المذكورة بوضوح ودون اختصار.
4. اجعل النص مناسبًا كشرح لصورة (Caption).
5. اخرج النص النهائي المنسق فقط بدون أي مقدمات أو كلام إضافي.
"""


def process_feed(source_key: str, feed_url: str, gemini_client: genai.Client) -> int:
    print(f"[فحص] جاري قراءة مصدر: {source_key}", flush=True)
    parsed_feed = feedparser.parse(feed_url)
    
    if not parsed_feed.entries:
        print(f"[تنبيه] لم يتم العثور على عناوين في: {source_key}", flush=True)
        return 0

    sent_count = 0
    for entry in parsed_feed.entries[:5]:
        title = entry.get("title", "").strip()
        summary = entry.get("summary", "").strip()
        published_parsed = entry.get("published_parsed")

        if not title or title in seen_titles:
            continue

        # 1. استبعاد الأخبار النسائية
        if is_female_news(title) or is_female_news(summary):
            print(f"[تجاهل] تم استبعاد خبر نسائي: {title[:40]}...", flush=True)
            seen_titles.add(title)
            continue

        # 2. استبعاد الأخبار القديمة (أكثر من 3 ساعات)
        if not is_recent_news(published_parsed):
            print(f"[تجاهل] خبر قديم (تجاوز 3 ساعات): {title[:40]}...", flush=True)
            seen_titles.add(title)
            continue

        print(f"[جاري العمل] خبر جديد وعاجل مقبول: {title[:50]}...", flush=True)

        prompt = build_news_prompt(source_key, title, summary)
        
        try:
            post_text = generate_text(gemini_client, prompt)
            if send_telegram_photo_post(post_text):
                seen_titles.add(title)
                sent_count += 1
        except Exception as e:
            print(f"[خطأ Gemini] تعذر معالجة الخبر: {e}", flush=True)

    return sent_count


def bot_loop() -> None:
    try:
        gemini_client = create_gemini_client()
        print("[جاهز] تم الاتصال بـ Gemini API بنجاح.", flush=True)
    except Exception as e:
        print(f"[خطأ قاتل] فشل تهيئة Gemini Client: {e}", flush=True)
        return

    print("[بدء التشغيل] البوت يراقب الأخبار الحديثة المصورة الآن على Render...", flush=True)

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
