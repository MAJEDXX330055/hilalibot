def process_with_gemini(client, source_name: str, title: str, summary: str):
    prompt = f"""المصدر: {source_name}
العنوان: {title}
التفاصيل: {summary}

المطلوب إخراج النتيجة بتنسيق محدد يفصل بين اسم الشخصية الرياضية ونص المنشور باستخدام الكلمة المفتاحية "---SPLIT---":

السطر الأول: اسم اللاعب أو الشخصية الرياضية المعنية فقط (مثل: مالكوم أو وليد الفراج أو الهلال).
---SPLIT---
المنشور:
صغ المحتوى كـ خبر عاجل أو تصريح حُصري حماسي لمتابعي الكرة السعودية وجماهير الهلال. ابدأ بـ 🚨🚨🚨 | **عاجل:** أو 🎙️ | **تصريح:**
"""
    try:
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=prompt,
        )
        text = response.text
        if "---SPLIT---" in text:
            parts = text.split("---SPLIT---")
            person_name = parts[0].strip()
            post_text = parts[1].strip()
            return person_name, post_text
        else:
            return "Al Hilal FC", text.strip()

    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            print("[تجاوز الكوتا] تم تخطي هذا الخبر لمنع توقف البوت والالتفاف للمصدر التالي.", flush=True)
            return None, None
        print(f"[خطأ Gemini] {e}", flush=True)
        return None, None
