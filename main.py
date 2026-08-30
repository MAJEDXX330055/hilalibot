"""Al-Hilal News Telegram Bot for Replit.

Fetches sports news, formats it via Gemini, and publishes directly to Telegram.

Set the following Secrets in Replit (Tools -> Secrets):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    GEMINI_API_KEY

Optional Secrets:
    GEMINI_MODEL (defaults to gemini-2.5-flash)
    NEWS_FEED_URL
"""

import os
import time
import threading
import requests
from flask import Flask
import feedparser
from google import genai

# إعداد خادم Flask لإبقاء السكريبت يعمل 24/7 على Replit
app = Flask(__name__)

@app.route('/')
def home():
    return "Al-Hilal Telegram News Bot is Active on Replit!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# رابط تغذية أخبار نادي الهلال الافتراضي من Google News
DEFAULT_NEWS_FEED_URL = (
    "https://news.google.com/rss/search?q=%D9%86%D8%A7%D8%AF%D9%8A+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar"
)

seen_posts = set()


def send_telegram_post(text: str) -> bool:
    """إرسال الخبر المنسق مباشرة إلى قناة/مجموعة التلجرام."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[خطأ] يرجى إضافة TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID في Secrets")
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
            print("تم نشر الخبر بنجاح على التلجرام!")
            return True
        else:
            print(f"فشل الإرسال: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"حدث خطأ أثناء الاتصال بتلجرام: {e}")
        return False


def create_gemini_client() -> genai.Client:
    """إنشاء عميل Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("مفتاح GEMINI_API_KEY غير موجود في Secrets.")
    return genai.Client(api_key=api_key)


def generate_text(client: genai.Client, prompt: str) -> str:
    """توليد النص باستخدام Gemini."""
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text


def read_rss_feed(feed_url: str, limit: int = 5) -> list[dict[str, str]]:
    """قراءة موجز RSS وإعادة قائمة المنشورات."""
    parsed_feed = feedparser.parse(feed_url)
    if not parsed_feed.entries:
        return []

    return [
        {
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
        }
        for entry in parsed_feed.entries[:limit]
    ]


def build_telegram_prompt(news_item: dict[str, str]) -> str:
    """بناء التعليمات لـ Gemini لصياغة منشور تلجرام إخباري."""
    return f"""العنوان: {news_item['title']}
التفاصيل: {news_item['summary']}

المطلوب:
1. صغ منشوراً إخبارياً عاجلاً يخص نادي الهلال باللغة العربية.
2. ابدأ المنشور بـ 🚨🚨🚨 | **عاجل:** أو **خبر هلالي:**
3. حافظ على الدقة وجميع الأسماء المذكورة بدون اختصار مخل.
4. استخدم التنسيق المباشر والرموز التعبيرية المناسبة بدون أي مقدمات أو شرح إضافي.
"""


def process_and_publish(gemini_client: genai.Client, feed_url: str) -> None:
    """فحص الأخبار الجديدة وصياغتها ونشرها."""
    news_items = read_rss_feed(feed_url)

    for item in news_items:
        link = item["link"]
        if link in seen_posts:
            continue

        prompt = build_telegram_prompt(item)
        post_text = generate_text(gemini_client, prompt)

        if send_telegram_post(post_text):
            seen_posts.add(link)


def bot_loop() -> None:
    """الحلقة التكرارية للفحص الدوري المستمر."""
    gemini_client = create_gemini_client()
    feed_url = os.getenv("NEWS_FEED_URL", DEFAULT_NEWS_FEED_URL)
    print("البوت يعمل الآن على Replit وجاهز لنشر أخبار الهلال على التلجرام...")

    while True:
        try:
            process_and_publish(gemini_client, feed_url)
        except Exception as e:
            print(f"حدث خطأ أثناء فحص الأخبار: {e}")

        # فحص الأخبار كل 60 ثانية
        time.sleep(60)


if __name__ == "__main__":
    # تشغيل خادم الويب في مسار خلفي (Thread) لإبقاء Replit نشطاً
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    # تشغيل حلقة البوت الرئيسية
    bot_loop()
