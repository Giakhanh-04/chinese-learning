import json

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from ai.gemini_client import get_gemini_client

# Giữ đúng tên model bạn đang dùng. Nếu lỗi 404 / model not found thì đổi tại đây.
MODEL_NAME = "gemini-3.5-flash-lite"

MAX_CHARS = 800

LANGUAGE_NAMES = {
    "zh": "tiếng Trung giản thể",
    "zh-TW": "tiếng Trung phồn thể",
    "vi": "tiếng Việt",
    "en": "tiếng Anh",
}


@require_http_methods(["GET", "POST"])
def translation_page(request):

    if request.method == "GET":
        return render(request, "translation/translation.html")

    # ---------- đọc dữ liệu ----------
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Dữ liệu gửi lên không hợp lệ."},
            status=400
        )

    text = (data.get("text") or "").strip()
    source = data.get("source", "")
    target = data.get("target", "")

    if not text:
        return JsonResponse(
            {"error": "Vui lòng nhập nội dung cần dịch."},
            status=400
        )

    if len(text) > MAX_CHARS:
        return JsonResponse(
            {"error": f"Nội dung tối đa {MAX_CHARS} ký tự."},
            status=400
        )

    if source == target:
        return JsonResponse(
            {"error": "Ngôn ngữ nguồn và đích đang giống nhau."},
            status=400
        )

    source_name = LANGUAGE_NAMES.get(source, source)
    target_name = LANGUAGE_NAMES.get(target, target)

    prompt = f"""Bạn là công cụ dịch thuật.
Dịch chính xác nội dung dưới đây từ {source_name} sang {target_name}.
Giữ nguyên ý nghĩa, không thêm hoặc bớt nội dung.
Chỉ trả về bản dịch, không giải thích.

{text}"""

    # ---------- gọi Gemini (một lần, không stream) ----------
    try:
        client = get_gemini_client()

        result = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        translated = (result.text or "").strip()

        if not translated:
            return JsonResponse(
                {"error": "AI không trả về bản dịch. Vui lòng thử lại."},
                status=502
            )

        return HttpResponse(
            translated,
            content_type="text/plain; charset=utf-8"
        )

    except Exception as e:
        print("========== TRANSLATION ERROR ==========")
        print(type(e).__name__)
        print(str(e))
        print("========================================")

        return JsonResponse(
            {"error": "Không thể kết nối với AI. Vui lòng thử lại."},
            status=502
        )