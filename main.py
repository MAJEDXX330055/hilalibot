"""Al-Hilal Live News Bot (Render & Telegram)
Fetches official and verified football news about Al-Hilal via Google News RSS.

Required Environment Variables on Render:
- GEMINI_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
"""

import os
import time
import threading
import requests
from flask import Flask
import feedparser
from google import genai

app = Flask(__name__)

@app.route('/')
def home():
    return "Hilal Live News Bot is Active & Running 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# مصادر أخبار مباشرة ومستقرة تغطي كافة أخبار نادي الهلال والصفقات لحظة بلحظة
NEWS_FEEDS = {
    "أخبار الهلال العاجلة": "https://news.google.com/rss/search?q=%D9%86%D8%A7%D8%AF%D9%8A+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "صفقات الهلال": "https://news.google.com/rss/search?q=%D8%B5%D9%81%D9%82%D8%A7%D8%AA+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "ميركاتو نادي الهلال": "https://news.google.com/rss/search?q=%D9%85%D9%8A%D8%B1%D9%83%D8%A7%D8%AA%D9%88+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar"
}

seen_posts = set()

def send_telegram_post(text: str) -> bool:
    """Send generated news text directly to Telegram."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[خطأ] معلومات التلجرام غير متوفرة في البيئة.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=12)
        res_data = response.json()
        if res_data.get("ok"):
            print("تم إرسال الخبر إلى تلجرام بنجاح!")
            return True
        else:
            print(f"فشل الإرسال: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"حدث خطأ أثناء الاتصال بتلجرام: {e}")
        return False

def create_gemini_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("مفتاح GEMINI_API_KEY غير موجود في متغيرات البيئة.")
    return genai.Client(api_key=api_key)

def generate_text(client: genai.Client, prompt: str) -> str:
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text

def format_news_prompt(source_name: str, news_title: str, news_summary: str) -> str:
    return f"""المصدر: {source_name}
عنوان الخبر: {news_title}
تفاصيل الخبر: {news_summary}

المطلوب:
1. صغ الخبر بأسلوب إخباري عاجل وجذاب لمتابعي نادي الهلال.
2. ابدأ المنشور بـ 🚨🚨🚨 | **عاجل:** أو **خبر هلالي:**
3. اذكر التفاصيل والأسماء المذكورة بوضوح بدون اختصار مخل.
4. استخدم الإيموجيات المناسبة واقتصر على نص التغطية فقط دون مقدمات.
"""

def process_feed(source_key: str, feed_url: str, gemini_client: genai.Client) -> int:
    parsed_feed = feedparser.parse(feed_url)
    if not parsed_feed.entries:
        return 0

    sent_count = 0
    for entry in parsed_feed.entries[:5]:
        link = entry.get("link", "")
        if link in seen_posts:
            continue

        title = entry.get("title", "")
        summary = entry.get("summary", "")

        prompt = format_news_prompt(source_key, title, summary)
        post_text = generate_text(gemini_client, prompt)

        if send_telegram_post(post_text):
            seen_posts.add(link)
            sent_count += 1

    return sent_count

def bot_loop() -> None:
    gemini_client = create_gemini_client()
    print("البوت يعمل الآن بنظام جلب الأخبار المباشر والمضمون...")

    while True:
        try:
            for source_key, url in NEWS_FEEDS.items():
                process_feed(source_key, url, gemini_client)
        except Exception as e:
            print(f"حدث خطأ أثناء فحص الأخبار: {e}")

        # التكرار كل 30 ثانية لتحديث سريع ومضمون
        time.sleep(30)

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    bot_loop()
