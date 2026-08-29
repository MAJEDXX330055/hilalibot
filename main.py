"""Multi-source Al-Hilal Telegram Bot with Media & Custom Formatting.

Monitored Accounts:
- @Alhilal_FC (Official match events, goals, substitutions)
- @RotanaSport (Media statements & shows - Rotana Sport with Waleed)
- @thmanyahsports (Media statements)
- @MnbrAlhilal (Fan news & updates)
- @baytAlhilal (Fan news & updates)
- @Radar_alhilal1 (News & media clips)
- @FabrizioRomano (Transfers news)

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

# سيرفر خفيف لإبقاء الخدمة Live واستقبال طلبات الـ Ping من موقع cron-job
app = Flask(__name__)

@app.route('/')
def home():
    return "Hilal Multi-Source Telegram Bot is running live 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# الحسابات المستهدفة عبر RSS (Nitter)
ACCOUNTS = {
    "official": "https://nitter.net/Alhilal_FC/rss",
    "rotana": "https://nitter.net/RotanaSport/rss",
    "thmanyah": "https://nitter.net/thmanyahsports/rss",
    "mnbr": "https://nitter.net/MnbrAlhilal/rss",
    "bayt": "https://nitter.net/baytAlhilal/rss",
    "radar": "https://nitter.net/Radar_alhilal1/rss",
    "fabrizio": "https://nitter.net/FabrizioRomano/rss"
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


def format_statement_prompt(source_name: str, tweet_text: str) -> str:
    """Prompt for media quotes and statements (Rotana, Thmanyah, etc.)."""
    return f"""المصدر: {source_name}
التغريدة الأصلية:
{tweet_text}

المطلوب:
1. صغ المنشور كـ "تصريح إعلامي".
2. ابدأ المنشور بالسطر التالي تماماً وبشكل بارز:
🚨🚨🚨 | **تصريح:**
3. استخرج واذكر اسم الإعلامي أو الضيف المذكور (مثل: عبد الله فلاته، وليد الفراج...) متبوعاً بالنص الدقيق لتصريحه.
4. لا تضف أي مقدمات أو خاتمة.
"""


def format_official_prompt(tweet_text: str) -> str:
    """Prompt for official Al-Hilal match updates."""
    return f"""التغريدة من حساب نادي الهلال الرسمي:
{tweet_text}

المطلوب:
1. صغ المنشور كـ تغطية مباشرة لمباراة أو خبر رسمي.
2. استخدم الإيموجيات المناسبة للحدث (⚽️ للأهداف، ⏱️ للتوقيت والدقيقة، 🔄 للتبديلات).
3. اكتب التوقيت أو الدقيقة في بداية النص بشكل واضح مع صياغة جذابة ومباشرة.
4. لا تضف أي مقدمات إضافية.
"""


def format_fabrizio_prompt(tweet_text: str) -> str:
    """Prompt for Fabrizio Romano tweets."""
    return f"""التغريدة من فابريزيو رومانو:
{tweet_text}

المطلوب:
1. ابدأ المنشور بـ: 🚨⚡️ **فابريزيو رومانو:**
2. ترجم الخبر إلى العربية بدقة مع تفصيل نقاط الاتفاق، بنود العقد، والمبالغ المالية إن وجدت في أسطر مستقلة.
3. بدون أي مقدمات إضافية.
"""


def extract_media_url(entry) -> str:
    """Extract attached image from RSS entry."""
    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0].get('url')
    if hasattr(entry, 'enclosures') and entry.enclosures:
        return entry.enclosures[0].get('href')
    return None


def process_feed(source_key: str, feed_url: str, gemini_client: genai.Client):
    parsed_feed = feedparser.parse(feed_url)
    if not parsed_feed.entries:
        return

    for entry in parsed_feed.entries[:3]:
        link = entry.get("link", "")
        if link in seen_posts:
            continue

        title = entry.get("title", "")
        summary = entry.get("summary", "")
        full_text = f"{title}\n{summary}"
        image_url = extract_media_url(entry)

        # فلترة التغريدات غير المتعلقة بالهلال من الحسابات العامة
        if source_key in ["rotana", "thmanyah", "fabrizio"]:
            if not any(k in full_text for k in ["الهلال", "Hilal", "فلاته", "الفراج"]):
                continue

        # تحديد التنسيق المناسب حسب المصدر
        if source_key == "official":
            prompt = format_official_prompt(full_text)
        elif source_key == "fabrizio":
            prompt = format_fabrizio_prompt(full_text)
        else:
            prompt = format_statement_prompt(source_key, full_text)

        post_text = generate_text(gemini_client, prompt)

        if send_telegram_post(post_text, image_url):
            seen_posts.add(link)


def bot_loop() -> None:
    gemini_client = create_gemini_client()
    print("البوت يعمل الآن ويراقب الحسابات الـ 7 المحددة...")

    while True:
        try:
            for source_key, url in ACCOUNTS.items():
                process_feed(source_key, url, gemini_client)
        except Exception as e:
            print(f"حدث خطأ في الدورة: {e}")

        time.sleep(180)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    bot_loop()
