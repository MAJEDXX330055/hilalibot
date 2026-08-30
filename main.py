import os
import time
import threading
import requests
import feedparser
import google.generativeai as genai
from flask import Flask

app = Flask(__name__)

# إعداد مفتاح API
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# قائمة مصادر الأخبار
RSS_FEEDS = [
    "https://www.alhilal.com/feed",
    "https://www.kooora.com/rss",
]

seen_articles = set()

def fetch_and_publish():
    """دالة فحص المصادر وتلخيصها"""
    print("=== [بدء عملية فحص المصادر] ===")
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception as e:
        print(f"[خطأ في إعداد نموذج Gemini]: {e}")
        return

    for feed_url in RSS_FEEDS:
        try:
            print(f"جاري فحص المصدر: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            if not feed.entries:
                print(f"لا توجد أخبار في: {feed_url}")
                continue
                
            for entry in feed.entries[:3]:
                title = entry.title
                link = entry.link
                
                if link in seen_articles:
                    print(f"خبر مكرر: {title}")
                    continue
                
                seen_articles.add(link)
                print(f"خبر جديد! جاري التلخيص: {title}")
                
                # تلخيص الخبر
                prompt = f"لخص هذا الخبر الرياضي بشكل جذاب وقصير للتليجرام:\nالعنوان: {title}"
                response = model.generate_content(prompt)
                summary = response.text if response else title
                
                # الإرسال للتليجرام
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
    print("=== [انتهى الفحص] ===")

def start_loop():
    """حلقة تكرارية تعمل بالخلفية بشكل مستمر"""
    while True:
        fetch_and_publish()
        # الانتظار 10 دقائق (600 ثانية) بين كل فحص
        time.sleep(600)

@app.route('/')
def home():
    return "Bot is alive and running", 200

if __name__ == "__main__":
    # تشغيل حلقة الفحص في الخلفية عند بدء التطبيق
    bot_thread = threading.Thread(target=start_loop, daemon=True)
    bot_thread.start()
    
    # تشغيل سيرفر Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
