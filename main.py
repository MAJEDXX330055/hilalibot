import os
import time
import requests
import feedparser
import google.generativeai as genai
from flask import Flask
from threading import Thread

app = Flask(__name__)

# إعداد مفتاح API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# قائمة مصادر الأخبار (RSS Feeds)
RSS_FEEDS = [
    "https://www.alhilal.com/feed",  # استبدل أو أضف روابط RSS المصادر هنا
    "https://www.kooora.com/rss",
]

# مصفوفة لحفظ الأناوين السابقة ومنع التكرار
seen_articles = set()

def fetch_and_publish():
    """دالة جلب الأخبار من كافة المصادر وتلخيصها ونشرها"""
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:  # أخذ أحدث 3 أخبار من كل مصدر
                title = entry.title
                link = entry.link
                
                if link in seen_articles:
                    continue
                
                seen_articles.add(link)
                
                # تلخيص الخبر باستخدام الجيميني
                prompt = f"لخص هذا الخبر الرياضي بشكل جذاب وقصير للتليجرام مع إعادة صياغته:\nالعنوان: {title}"
                response = model.generate_content(prompt)
                summary = response.text if response else title
                
                # إرسال التلخيص لـ Telegram
                bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
                chat_id = os.environ.get("TELEGRAM_CHAT_ID")
                
                if bot_token and chat_id:
                    message = f"<b>{title}</b>\n\n{summary}\n\n🔗 <a href='{link}'>المصدر</a>"
                    requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
                    )
                    print(f"[نجاح] تم إرسال الخبر: {title}")
                    
        except Exception as e:
            print(f"[خطأ في المصدر {feed_url}]: {e}")
            continue

@app.route('/')
def home():
    # يتم تشغيل الفحص عند كل طلب GET يصل من cron-job
    fetch_and_publish()
    return "Bot is active and checked feeds", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # تشغيل السيرفر
    run_flask()
