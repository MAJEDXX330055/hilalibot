"""Fetch Hilal news, generate a post with Gemini, and send it directly to Telegram.

Set the following environment variables in Render:
    GEMINI_API_KEY
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID

Optional:
    GEMINI_MODEL (defaults to gemini-3.6-flash)
    NEWS_FEED_URL (defaults to Google News Hilal search RSS)
"""

import os
import time
import threading
import requests
from flask import Flask
import feedparser
from google import genai

# سيرفر خفيف لإبقاء الخدمة Live على Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Hilal Telegram Bot is running live!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# رابط RSS مخصص لأخبار نادي الهلال السعودي
DEFAULT_NEWS_FEED_URL = (
    "https://news.google.com/rss/search?q=%D9%86%D8%A7%D8%AF%D9%8A+%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar"
)

seen_articles = set()


def send_telegram_message(text: str) -> bool:
    """Send generated news post to Telegram channel or chat."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[Warning] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in environment variables.")
        print(f"[Log Output]:\n{text}")
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
            print("تم إرسال الخبر إلى تلجرام بنجاح!")
            return True
        else:
            print(f"فشل إرسال التلجرام: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"خطأ أثناء الإرسال لتلجرام: {e}")
        return False


def create_gemini_client() -> genai.Client:
    """Create an authenticated Gemini API client."""
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Missing required environment variable: GEMINI_API_KEY")

    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate_text(client: genai.Client, prompt: str) -> str:
    """Generate text with Gemini."""
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text


def read_rss_feed(feed_url: str, limit: int = 5) -> list[dict[str, str]]:
    """Read a feed and return a small, normalized list of entries."""
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


def build_news_prompt(news_items: list[dict[str, str]]) -> str:
    """Build a prompt for generating Telegram news posts."""
    formatted_items = "\n\n".join(
        f"العنوان: {item['title']}\nالتفاصيل: {item['summary']}"
        for item in news_items
    )
    return f"""صغ منشوراً إخبارياً مشوقاً وقصيراً عن نادي الهلال بناءً على التفاصيل التالية:

الشروط:
- الصياغة باللغة العربية بأسلوب إخباري مميز ورياضي.
- استخدام إيموجيات مناسبة وهاشتاجات مثل #الهلال.
- لا تضف أي مقدمات أو شرح، اكتب نص المنشور فقط.

الأخبار:
{formatted_items}
"""


def bot_loop() -> None:
    """Fetch Hilal news continuously and send to Telegram without duplicates."""
    gemini_client = create_gemini_client()
    feed_url = os.getenv("NEWS_FEED_URL", DEFAULT_NEWS_FEED_URL)

    print("البوت يعمل الآن ويراقب أخبار الهلال...")

    while True:
        try:
            news_items = read_rss_feed(feed_url)
            new_stories = [item for item in news_items if item["link"] not in seen_articles]

            if new_stories:
                print(f"تم العثور على {len(new_stories)} خبر جديد. جاري المعالجة...")
                post_text = generate_text(gemini_client, build_news_prompt(new_stories))
                
                # إرسال الخبر إلى تلجرام
                if send_telegram_message(post_text):
                    for item in new_stories:
                        seen_articles.add(item["link"])
            else:
                print("لا توجد أخبار جديدة لنادي الهلال حالياً.")

        except Exception as e:
            print(f"حدث خطأ أثناء التشغيل: {e}")

        # التحقق كل 10 دقائق
        time.sleep(600)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    bot_loop()
