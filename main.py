import os
import time
import threading
import requests
import feedparser
import google.generativeai as genai
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Hilal News Bot is Active!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# إعدادات مصادر الأخبار الخاصة بك
NEWS_FEEDS = {
    "أخبار الهلال": "https://news.google.com/rss/search?q=%D9%86%D8%A7%D8%AF%D9%8A%20%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "صفقات الهلال والميركاتو": "https://news.google.com/rss/search?q=%D8%B5%D9%81%D9%82%D8%A7%D8%AA%20%D8%A7%D9%84%D9%87%D9%84%D8%A7%D9%84&hl=ar&gl=SA&ceid=SA:ar",
    "تصريحات أشن مع وليد": "https://news.google.com/rss/search?q=%D8%A3%D9%83%D8%B4%D9%86%20%D9%85%D8%B9%20%D9%88%D9%84%D9%8A%D8%AF&hl=ar&gl=SA&ceid=SA:ar",
    "دوري روشن السعودي": "https://news.google.com/rss/search?q=%D8%AF%D9%88%D8%B1%D9%8A%20%D8%B1%D9%88%D8%B4%D9%86&hl=ar&gl=SA&ceid=SA:ar"
}

DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?q=80&w=1080",
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1080",
    "https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1080"
]

MATCH_IMAGES = {
    "الأهلي": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?q=80&w=1080",
    "النصر": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1080",
    "الاتحاد": "https://images.unsplash.com/photo-1518091043644-c1d4457512c6?q=80&w=1080",
    "كلاسيكو": "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?q=80&w=1080",
    "ديربي": "https://images.unsplash.com/photo-1574629810360-7efbbe195018?q=80&w=1080"
}

seen_titles = set()
FEMALE_KEYWORDS = ["النساء", "للنساء", "فريق السيدات", "دوري السيدات", "نسائي"]

# إعداد مفتاح API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

def fetch_and_publish():
    """دالة الفحص باستخدام مصادر وقواميس كودك الأصلي"""
    print("=== [بدء عملية فحص المصادر] ===")
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        print(f"[خطأ في إعداد نموذج Gemini]: {e}")
        return

    for category, feed_url in NEWS_FEEDS.items():
        try:
            print(f"جاري فحص تصنيف ({category}): {feed_url}")
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                print(f"لا توجد أخبار جديدة في ({category})")
                continue
                
            for entry in feed.entries[:3]:
                title = entry.title
                link = entry.link
                
                # استبعاد أية أخبار تحتوي على الكلمات النسائية
                if any(keyword in title for keyword in FEMALE_KEYWORDS):
                    print(f"تم استبعاد خبر نسائي: {title}")
                    continue

                if title in seen_titles:
                    print(f"خبر مكرر: {title}")
                    continue
                
                seen_titles.add(title)
                print(f"خبر جديد! جاري التلخيص: {title}")
                
                # تلخيص الخبر
                prompt = f"لخص هذا الخبر الرياضي بشكل جذاب وقصير للتليجرام:\nالعنوان: {title}"
                response = model.generate_content(prompt)
                summary = response.text if response else title
                
                # الإرسال للتليجرام
                bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
                chat_id = os.environ.get("TELEGRAM_CHAT_ID")
                
                if bot_token and chat_id:
                    message = f"<b>[{category}] {title}</b>\n\n{summary}\n\n🔗 <a href='{link}'>المصدر</a>"
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
                    )
                    print(f"[نجاح] تم إرسال الخبر: {title}")
                    
        except Exception as e:
            print(f"[خطأ في التصنيف {category}]: {e}")
            continue
    print("=== [انتهى الفحص] ===")

def start_loop():
    """تفعيل الفحص المستمر كل 10 دقائق في الخلفية"""
    while True:
        fetch_and_publish()
        time.sleep(600)

if __name__ == "__main__":
    # تشغيل حلقة الفحص في الخلفية
    bot_thread = threading.Thread(target=start_loop, daemon=True)
    bot_thread.start()
    
    # تشغيل السيرفر
    run_web_server()
