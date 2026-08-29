"""Multi-source Al-Hilal Telegram Bot - Pure Instant News Fetcher.

Monitored Accounts:
- @Alhilal_FC
- @hilalstuff
- @RotanaSport
- @thmanyahsports
- @MnbrAlhilal
- @baytAlhilal
- @Radar_alhilal1
- @FabrizioRomano

Set environment variables in Render:
    GEMINI_API_KEY
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID
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
    return "Hilal Pure News Bot is running live 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# استخدام خوادم متوزعة ومستقرة لضمان التقاط الأخبار فور نزولها
ACCOUNTS = {
    "official": "https://nitter.poast.org/Alhilal_FC/rss",
    "hilalstuff": "https://nitter.poast.org/hilalstuff/rss",
    "rotana": "https://nitter.poast.org/RotanaSport/rss",
    "thmanyah": "https://nitter.poast.org/thmanyahsports/rss",
    "mnbr": "https://nitter.poast.org/MnbrAlhilal/rss",
    "bayt": "https://nitter.poast.org/baytAlhilal/rss",
    "radar": "https://nitter.poast.org/Radar_alhilal1/rss",
    "fabrizio": "https://nitter.poast.org/FabrizioRomano/rss"
}

seen_posts = set()


def send_telegram_post(text: str, image_url: str = None) -> bool:
    """Send text and optional photo directly to Telegram."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[Warning] Missing Telegram Credentials.")
        print(f"[Log]: {text}")
        return False

    try:
        if image_url:
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            payload = {
                "chat_id": chat_id,
                "photo": image_url,
                "caption": text,
                "parse_mode": "Markdown"
            }
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }

        response = requests.post(url, json=payload, timeout=12)
        res_data = response.json()
        if res_data.get("ok"):
            print("تم الإرسال إلى تلجرام بنجاح!")
            return True
        else:
            print(f"فشل الإرسال: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"خطأ أثناء التواصل مع تلجرام: {e}")
        return False


def create_gemini_client() -> genai.Client:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Missing required environment variable: GEMINI_API_KEY")
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def generate_text(client: genai.Client, prompt: str) -> str:
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(model=model_name, contents=prompt)
    return response.text


def format_news_prompt(source_name: str, tweet_text: str) -> str:
    return f"""المصدر: {source_name}
التغريدة الأصلية:
{tweet_text}

المطلوب:
1. صغ المنشور كـ خبر كروي عاجل أو تغطية شمولية.
2. ابدأ المنشور بـ 🚨🚨🚨 | **خبر:** أو **عاجل:** حسب السياق.
3. اختصر النص مع الحفاظ على كل أسماء اللاعبين وتفاصيل الصفقات أو القائمة المذكورة بالكامل.
4. اترك الصياغة مباشرة وجذابة للنشر بدون مقدمات إضافية.
"""


def extract_media_url(entry) -> str:
    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0].get('url')
    if hasattr(entry, 'enclosures') and entry.enclosures:
        return entry.enclosures[0].get('href')
    return None


def process_feed(source_key: str, feed_url: str, gemini_client: genai.Client) -> int:
    parsed_feed = feedparser.parse(feed_url)
    if not parsed_feed.entries:
        return 0

    sent_count = 0
    for entry in parsed_feed.entries[:10]:
        link = entry.get("link", "")
        if link in seen_posts:
            continue

        title = entry.get("title", "")
        summary = entry.get("summary", "")
        full_text = f"{title}\n{summary}"
        image_url = extract_media_url(entry)

        prompt = format_news_prompt(source_key, full_text)
        post_text = generate_text(gemini_client, prompt)

        if send_telegram_post(post_text, image_url):
            seen_posts.add(link)
            sent_count += 1

    return sent_count


def bot_loop() -> None:
    gemini_client = create_gemini_client()
    print("البوت يعمل الآن مخصصاً للأخبار الحقيقية فقط بدون إرسال أي طقطقة عشوائية...")

    while True:
        try:
            for source_key, url in ACCOUNTS.items():
                process_feed(source_key, url, gemini_client)
        except Exception as e:
            print(f"حدث خطأ في الدورة: {e}")

        # فحص كافي ومتوازن كل 20 ثانية
        time.sleep(20)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    bot_loop()
