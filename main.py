"""Al-Hilal Pure News Telegram Bot for Replit.

Fetches real sports news, formats it via Gemini, and publishes directly to Telegram.
No automated banter or random tweets — Pure News Only.

Set the following Secrets in Replit (Tools -> Secrets):
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
    GEMINI_API_KEY
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
    return "Hilal Pure News Bot is Active 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# مصادر الأخبار المباشرة والمضمونة لنادي الهلال والكرة السعودية
NEWS_FEEDS = {
    "أخبار نادي الهلال": "https://news.google.com/rss/search?q=%D9%86%D8%A7%D8%AF%D9%8A+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "صفقات وميركاتو الهلال": "https://news.google.com/rss/search?q=%D8%B5%D9%81%D9%82%D8%A7%D8%AA+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "دوري روشن": "https://news.google.com/rss/search?q=%D8%AF%D9%88%D8%B1%D9%8A+%D8%B1%D9%88%D8%B4%D9%86&hl=ar&gl=SA&ceid=SA:ar"
}

seen_posts = set()


def send_telegram_post(text: str) -> bool:
    """إرسال النص إلى تلجرام."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[خطأ] يرجى تأكيد وجود TELEGRAM_BOT_TOKEN و TELEGRAM_CHAT_ID في Secrets")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if res_data.get("ok"):
            print("تم إرسال الخبر الحقيقي إلى تلجرام بنجاح!")
            return True
        else:
            print(f"فشل الإرسال: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"خطأ اتصال بتلجرام: {e}")
        return False


def create_gemini_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("يرجى إضافة مفتاح GEMINI_API_KEY في Secrets.")
    return genai.Client(api_key=api_key)


def generate_text(client: genai.Client, prompt: str) -> str:
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text


def build_news_prompt(source_name: str, title: str, summary: str) -> str:
    return f"""المصدر: {source_name}
عنوان الخبر: {title}
تفاصيل الخبر: {summary}

المطلوب:
1. صغ المنشور كـ خبر عاجل أو تغطية شمولية تخص نادي الهلال والكرة السعودية.
2. ابدأ المنشور بـ 🚨🚨🚨 | **عاجل:** أو **خبر هلالي:**
3. حافظ على كل التفاصيل والأسماء الواردة بوضوح.
4. اخرج النص النهائي فقط بدون أي مقدمات أو شرح أو طقطقة.
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

        prompt = build_news_prompt(source_key, title, summary)
        post_text = generate_text(gemini_client, prompt)

        if send_telegram_post(post_text):
            seen_posts.add(link)
            sent_count += 1

    return sent_count


def bot_loop() -> None:
    gemini_client = create_gemini_client()
    print("البوت يعمل الآن ومخصص ونقّاد للأخبار الحقيقية فقط بدون أي طقطقة عشوائية...")

    while True:
        try:
            for source_key, url in NEWS_FEEDS.items():
                process_feed(source_key, url, gemini_client)
        except Exception as e:
            print(f"حدث خطأ أثناء فحص الأخبار: {e}")

        # فحص كافي كل 30 ثانية
        time.sleep(30)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    bot_loop()
