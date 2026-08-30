"""Saudi Football News Telegram Bot for Replit.

Fetches general Saudi football & Saudi Pro League news,
formats it via Gemini, and publishes directly to Telegram every 10 seconds.

Set the following Secrets in Replit (Tools -> Secrets):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    GEMINI_API_KEY

Optional Secrets:
    GEMINI_MODEL (defaults to gemini-2.5-flash)
"""

import os
import time
import threading
import requests
from flask import Flask
import feedparser
from google import genai

# إعداد خادم Flask لإبقاء البوت متصلاً 24/7 على Replit
app = Flask(__name__)

@app.route('/')
def home():
    return "Saudi Football News Bot is Live & Active 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# توسيع نطاق المصادر لتغطية كافة أخبار الكرة السعودية
NEWS_FEEDS = {
    "أخبار الكرة السعودية": "https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%83%D8%B1%D8%A9+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A%D8%A9&hl=ar&gl=SA&ceid=SA:ar",
    "دوري روشن للمحترفين": "https://news.google.com/rss/search?q=%D8%AF%D9%88%D8%B1%D9%8A+%D8%B1%D9%88%D8%B4%D9%86&hl=ar&gl=SA&ceid=SA:ar",
    "صفقات وميركاتو السعودية": "https://news.google.com/rss/search?q=%D8%B5%D9%81%D9%82%D8%A7%D8%AA+%D8%A7%D9%84%D8%AF%D9%88%D8%B1%D9%8A+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A&hl=ar&gl=SA&ceid=SA:ar",
    "المنتخب السعودي": "https://news.google.com/rss/search?q=%D8%A7%D9%84%D9%85%D9%86%D8%AA%D8%AE%D8%A9+%D8%A7%D9%84%D8%B3%D8%B9%D9%88%D8%AF%D9%8A&hl=ar&gl=SA&ceid=SA:ar"
}

seen_posts = set()


def send_telegram_post(text: str) -> bool:
    """إرسال الخبر المنسق مباشرة إلى التلجرام."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[خطأ] يرجى التأكد من إضافة TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID في Secrets")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=8)
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
    """إنشاء عميل Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("مفتاح GEMINI_API_KEY غير موجود في Secrets.")
    return genai.Client(api_key=api_key)


def generate_text(client: genai.Client, prompt: str) -> str:
    """توليد النص المنسق باستخدام Gemini."""
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text


def build_news_prompt(source_name: str, title: str, summary: str) -> str:
    """بناء التوجيه لصياغة خبر رياضي سعودي عاجل."""
    return f"""التصنيف: {source_name}
عنوان الخبر: {title}
التفاصيل: {summary}

المطلوب:
1. صغ المنشور بأسلوب صحفي عاجل ومحترف مخصص للكرة السعودية.
2. ابدأ المنشور بـ 🚨🚨🚨 | **عاجل:** أو **خبر رياضي:**
3. اذكر كافة الأسماء والتفاصيل الواردة بدقة بدون اختصار مخل.
4. اخرج النص المنسق النهائي فقط بدون أي مقدمات أو شرح.
"""


def process_feed(source_key: str, feed_url: str, gemini_client: genai.Client) -> int:
    """فحص الخادم وقراءة الأخبار الجديدة ونشرها."""
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

        prompt = build_news_prompt(source_key, title, summary)
        post_text = generate_text(gemini_client, prompt)

        if send_telegram_post(post_text):
            seen_posts.add(link)
            sent_count += 1

    return sent_count


def bot_loop() -> None:
    """الحلقة التكرارية السريعة للفحص كل 10 ثوانٍ."""
    gemini_client = create_gemini_client()
    print("البوت يعمل الآن ويراقب أخبار الكرة السعودية بفحص سريع كل 10 ثوانٍ...")

    while True:
        try:
            for source_key, url in NEWS_FEEDS.items():
                process_feed(source_key, url, gemini_client)
        except Exception as e:
            print(f"حدث خطأ أثناء فحص الأخبار: {e}")

        # زمن الفحص والتكرار: كل 10 ثوانٍ
        time.sleep(10)


if __name__ == "__main__":
    # تشغيل خادم الويب في خلفية التطبيق
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    # تشغيل حلقة البوت
    bot_loop()
