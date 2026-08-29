"""Multi-source Al-Hilal Telegram Bot with Media & Auto-Banter Generator.

Monitored Accounts:
- @Alhilal_FC (Official match events, goals, substitutions)
- @RotanaSport (Media statements & shows)
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

app = Flask(__name__)

@app.route('/')
def home():
    return "Hilal Multi-Source & Banter Bot is running live 24/7!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# حسابات المراقبة عبر RSS
ACCOUNTS = {
    "official": "https://nitter.poast.org/Alhilal_FC/rss",
    "rotana": "https://nitter.poast.org/RotanaSport/rss",
    "thmanyah": "https://nitter.poast.org/thmanyahsports/rss",
    "mnbr": "https://nitter.poast.org/MnbrAlhilal/rss",
    "bayt": "https://nitter.poast.org/baytAlhilal/rss",
    "radar": "https://nitter.poast.org/Radar_alhilal1/rss",
    "fabrizio": "https://nitter.poast.org/FabrizioRomano/rss"
}

seen_posts = set()
no_news_counter = 0  # عداد لمراقبة فترات خلو الأخبار


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
    """Prompt for media quotes and statements."""
    return f"""المصدر: {source_name}
التغريدة الأصلية:
{tweet_text}

المطلوب:
1. صغ المنشور كـ "تصريح إعلامي".
2. ابدأ المنشور بالسطر التالي تماماً وبشكل بارز:
🚨🚨🚨 | **تصريح:**
3. استخرج واذكر اسم الإعلامي أو الضيف المذكور (مثل: عبد الله فلاته، وليد الفراج...) متبوعاً بنص التصريح بوضوح.
4. لا تضف أي شرح أو مقدمة إضافية.
"""


def format_official_prompt(tweet_text: str) -> str:
    """Prompt for official Al-Hilal match updates."""
    return f"""التغريدة من حساب نادي الهلال الرسمي:
{tweet_text}

المطلوب:
1. صغ المنشور كـ تغطية مباشرة لمباراة أو خبر رسمي.
2. استخدم الإيموجيات المناسبة للحدث (⚽️ للأهداف، ⏱️ للتوقيت والدقيقة، 🔄 للتبديلات).
3. اكتب التوقيت أو الدقيقة في بداية النص بشكل واضح مع صياغة جذابة ومباشرة.
4. اقتصر فقط على نص التغطية بدون أي مقدمات.
"""


def format_fabrizio_prompt(tweet_text: str) -> str:
    """Prompt for Fabrizio Romano tweets."""
    return f"""التغريدة من فابريزيو رومانو:
{tweet_text}

المطلوب:
1. ابدأ المنشور بـ: 🚨⚡️ **فابريزيو رومانو:**
2. ترجم الخبر إلى العربية بدقة مع تفصيل النقاط المهمة.
3. بدون أي مقدمات إضافية.
"""


def format_interactive_banter_prompt() -> str:
    """Prompt to generate viral banter/history tweets when no news is available."""
    return """أنت مدير حساب تويتر مشهور ومعروف بتغريداته التفاعلية والمستفزة لجماهير الأندية المنافسة لدعم نادي الهلال السعودي.

المطلوب:
اكتب تغريدة واحدة قصيرة وجذابة جداً للتفاعل (Banter / الطقطقة الرياضية الذكية):
- قد تكون عن تاريخ الهلال وبطولاته والسيطرة على الألقاب، مقارنة بعقدة الأندية الأخرى.
- أو طقطقة رياضية طريفة ومستفزة لمنافسي الهلال (النصر، الاتحاد...) بأسلوب مدرسي ذكي وبدون إساءة غير أخلاقية.
- استخدم إيموجيات حماسية (🔥، 💙، 🏆، 👀، 🤐).
- لا تضف أي مقدمات أو شرح، اعطني نص التغريدة فوراً ليكون جاهزاً للنسخ والأنستغرام/تويتر.
"""


def extract_media_url(entry) -> str:
    """Extract attached image from RSS entry."""
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
    for entry in parsed_feed.entries[:3]:
        link = entry.get("link", "")
        if link in seen_posts:
            continue

        title = entry.get("title", "")
        summary = entry.get("summary", "")
        full_text = f"{title}\n{summary}"
        image_url = extract_media_url(entry)

        # تصفية الأخبار غير المتعلقة بالهلال من الحسابات العامة
        if source_key in ["rotana", "thmanyah", "fabrizio"]:
            if not any(k in full_text for k in ["الهلال", "Hilal", "فلاته", "الفراج"]):
                continue

        if source_key == "official":
            prompt = format_official_prompt(full_text)
        elif source_key == "fabrizio":
            prompt = format_fabrizio_prompt(full_text)
        else:
            prompt = format_statement_prompt(source_key, full_text)

        post_text = generate_text(gemini_client, prompt)

        if send_telegram_post(post_text, image_url):
            seen_posts.add(link)
            sent_count += 1

    return sent_count


def bot_loop() -> None:
    global no_news_counter
    gemini_client = create_gemini_client()
    print("البوت يعمل الآن ومزود بمولد التغريدات التفاعلية...")

    while True:
        total_new_posts = 0
        try:
            for source_key, url in ACCOUNTS.items():
                total_new_posts += process_feed(source_key, url, gemini_client)

            # إذا لم تظهر أي أخبار جديدة
            if total_new_posts == 0:
                no_news_counter += 1
                print(f"لا توجد أخبار جديدة (العداد: {no_news_counter})")

                # عند وصول العداد إلى 3 دورات بدون أخبار (كل 6 دقائق تقريباً)
                if no_news_counter >= 3:
                    print("توليد تغريدة تفاعلية/طقطقة...")
                    banter_prompt = format_interactive_banter_prompt()
                    banter_text = generate_text(gemini_client, banter_prompt)
                    
                    # إرسال التغريدة التفاعلية
                    formatted_banter = f"💬 **تغريدة تفاعلية / طقطقة:**\n\n{banter_text}"
                    send_telegram_post(formatted_banter)
                    
                    # إعادة ضبط العداد
                    no_news_counter = 0
            else:
                # تصفير العداد فور نزول خبر جديد
                no_news_counter = 0

        except Exception as e:
            print(f"حدث خطأ في الدورة: {e}")

        time.sleep(120)


if __name__ == "__main__":
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    bot_loop()
