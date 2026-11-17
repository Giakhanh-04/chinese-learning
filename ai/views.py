import time
import re
from datetime import timedelta
import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from google.genai import types

from .gemini_client import get_gemini_client
import markdown
from django.shortcuts import render, redirect
from django.utils import timezone

from .gemini_client import ask_gemini
from .models import AILearningPlan, AIChatHistory
from premium.utils import is_premium_user


def ai_chat(request):
    answer = None

    # ==================================================
    # KIỂM TRA ĐĂNG NHẬP
    # ==================================================

    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    # ==================================================
    # KIỂM TRA PREMIUM
    # ==================================================

    if not is_premium_user(user_id):

        answer = """
        <div class="premium-required">
            <h3>⭐ Tính năng Premium</h3>

            <p>
                <strong>AI Trợ lý tiếng Trung</strong>
                là tính năng dành cho tài khoản Premium.
            </p>

            <p>
                Với Premium, bạn có thể:
            </p>

            <ul>
                <li>🤖 Hỏi AI về tiếng Trung</li>
                <li>📚 Tạo lộ trình học cá nhân hóa</li>
                <li>📝 Hỏi về từ vựng và ngữ pháp</li>
                <li>🌏 Hỗ trợ dịch câu</li>
                <li>🎯 Hỗ trợ mục tiêu HSK</li>
            </ul>

            <p>
                Hãy nâng cấp Premium để sử dụng
                đầy đủ các tính năng AI.
            </p>

            <a href="/premium/" class="btn">
                ⭐ Nâng cấp Premium
            </a>
        </div>
        """

        return render(
            request,
            "ai/ai_chat.html",
            {
                "answer": answer
            }
        )

    # ==================================================
    # XỬ LÝ CÂU HỎI
    # ==================================================

    if request.method == "POST":

        question = request.POST.get(
            "question",
            ""
        ).strip()

        if question:

            # ==================================================
            # KIỂM TRA YÊU CẦU TẠO LỘ TRÌNH
            # ==================================================

            plan_keywords = [
                "lộ trình",
                "kế hoạch học",
                "kế hoạch học tập",
                "lịch học",
                "học từ hsk",
                "lên hsk",
                "đạt hsk",
            ]

            is_plan_request = any(
                keyword in question.lower()
                for keyword in plan_keywords
            )

            # ==================================================
            # TẠO LỘ TRÌNH HỌC
            # ==================================================

            if is_plan_request:

                # ==============================
                # Tìm HSK hiện tại
                # ==============================

                current_hsk_match = re.search(
                    r"(?:đang|hiện tại|hiện nay).*?hsk\s*([1-6])",
                    question.lower()
                )

                current_hsk = (
                    int(current_hsk_match.group(1))
                    if current_hsk_match
                    else 1
                )

                # ==============================
                # Tìm HSK mục tiêu
                # ==============================

                target_hsk_match = re.search(
                    r"(?:lên|đạt|tới|đến).*?hsk\s*([1-6])",
                    question.lower()
                )

                if target_hsk_match:

                    target_hsk = int(
                        target_hsk_match.group(1)
                    )

                else:

                    target_hsk = min(
                        current_hsk + 1,
                        6
                    )

                # ==============================
                # Tìm thời gian học mỗi ngày
                # ==============================

                minutes_match = re.search(
                    r"(\d+)\s*(?:phút|p)\s*"
                    r"(?:mỗi ngày|/ngày|một ngày)",
                    question.lower()
                )

                daily_minutes = (
                    int(minutes_match.group(1))
                    if minutes_match
                    else 30
                )

                # ==============================
                # Tìm thời gian của lộ trình
                # ==============================

                duration_match = re.search(
                    r"(\d+)\s*(ngày|tuần|tháng)",
                    question.lower()
                )

                if duration_match:

                    duration_value = int(
                        duration_match.group(1)
                    )

                    duration_unit = (
                        duration_match.group(2)
                    )

                    if duration_unit == "ngày":

                        duration_days = duration_value

                    elif duration_unit == "tuần":

                        duration_days = (
                            duration_value * 7
                        )

                    else:

                        duration_days = (
                            duration_value * 30
                        )

                else:

                    duration_days = 30

                # ==============================
                # Prompt tạo lộ trình
                # ==============================

                prompt = f"""
Bạn là chuyên gia xây dựng lộ trình học tiếng Trung.

Hãy tạo một lộ trình học cá nhân hóa cho người học.

Thông tin:
- HSK hiện tại: HSK {current_hsk}
- HSK mục tiêu: HSK {target_hsk}
- Thời gian lộ trình: {duration_days} ngày
- Thời gian học mỗi ngày: {daily_minutes} phút
- Yêu cầu của người học: {question}

Yêu cầu:
1. Chia lộ trình thành từng tuần.
2. Nêu mục tiêu cụ thể của từng tuần.
3. Đề xuất từ vựng cần học.
4. Đề xuất ngữ pháp cần học.
5. Có luyện nghe, đọc và dịch.
6. Có bài tập hoặc hoạt động luyện tập.
7. Phân bổ thời gian học mỗi ngày phù hợp với {daily_minutes} phút.
8. Cuối lộ trình đưa ra cách tự đánh giá kết quả.
9. Trình bày rõ ràng, dễ đọc bằng tiếng Việt.
10. Không cần nói rằng bạn là AI.
"""

                # ==================================================
                # GỌI GEMINI
                # ==================================================

                print(
                    "\n===== AI DEBUG: BAT DAU GOI GEMINI ====="
                )

                ai_start = time.time()

                plan_content = ask_gemini(prompt)

                ai_time = time.time() - ai_start

                print(
                    "===== AI DEBUG: GEMINI MAT",
                    round(ai_time, 2),
                    "GIAY ====="
                )

                # ==================================================
                # LƯU LỘ TRÌNH
                # ==================================================

                if (
                    plan_content
                    and not plan_content.startswith("⚠️")
                ):

                    start_date = timezone.localdate()

                    end_date = (
                        start_date
                        + timedelta(
                            days=duration_days
                        )
                    )

                    AILearningPlan.objects.create(
                        user_id=user_id,
                        current_hsk=current_hsk,
                        target_hsk=target_hsk,
                        learning_goal=question,
                        daily_minutes=daily_minutes,
                        plan_content=plan_content,
                        start_date=start_date,
                        end_date=end_date,
                        status="active"
                    )

                    answer = plan_content

                else:

                    answer = plan_content

            # ==================================================
            # CÂU HỎI AI THÔNG THƯỜNG
            # ==================================================

            else:

                prompt = f"""
Bạn là AI trợ lý học tiếng Trung trên một website học tiếng Trung.

Hãy trả lời câu hỏi của người học bằng tiếng Việt,
rõ ràng, dễ hiểu và chính xác.

Người dùng hỏi:
{question}

Có thể hỗ trợ:
- Từ vựng
- Ngữ pháp
- Dịch câu
- Phát âm
- Bài tập
- HSK
- Cách học tiếng Trung
- Giải thích các vấn đề liên quan đến tiếng Trung

Nếu phù hợp, hãy đưa ví dụ tiếng Trung kèm giải thích tiếng Việt.

Không cần nói rằng bạn là AI.
"""

                # ==================================================
                # GỌI GEMINI
                # ==================================================

                print(
                    "\n===== AI DEBUG: BAT DAU GOI GEMINI ====="
                )

                ai_start = time.time()

                answer = ask_gemini(prompt)

                ai_time = time.time() - ai_start

                print(
                    "===== AI DEBUG: GEMINI MAT",
                    round(ai_time, 2),
                    "GIAY ====="
                )

            # ==================================================
            # CHUYỂN MARKDOWN THÀNH HTML
            # ==================================================

            if answer and not answer.startswith("⚠️"):

                answer = markdown.markdown(
                    answer,
                    extensions=[
                        "extra",
                        "nl2br"
                    ]
                )

                # ==================================================
                # LƯU LỊCH SỬ AI
                # ==================================================

                AIChatHistory.objects.create(
                    user_id=user_id,
                    question=question,
                    answer=answer
                )

    # ==================================================
    # HIỂN THỊ TRANG
    # ==================================================

    return render(
        request,
        "ai/ai_chat.html",
        {
            "answer": answer
        }
    )

def ai_learning_plans(request):
    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    plans = AILearningPlan.objects.filter(
        user_id=user_id
    ).order_by("-created_at", "-id")

    for plan in plans:
        plan.plan_content_html = markdown.markdown(
            plan.plan_content,
            extensions=[
                "extra",
                "nl2br"
            ]
        )

    return render(
        request,
        "ai/ai_learning_plans.html",
        {
            "plans": plans
        }
    )
CHAT_SYSTEM_PROMPT = """Bạn là gia sư tiếng Trung thân thiện trên website học tiếng Trung Hanzii.

Quy tắc:
- Trả lời bằng tiếng Việt, ngắn gọn, dễ hiểu, đúng trọng tâm.
- Khi nhắc đến chữ Hán, luôn kèm pinyin và nghĩa tiếng Việt.
- Khi giải thích từ vựng hoặc ngữ pháp, cho 1-2 câu ví dụ tiếng Trung kèm pinyin và bản dịch.
- Nếu người học viết câu tiếng Trung sai, hãy sửa lại và giải thích lỗi.
- Nếu câu hỏi không liên quan đến việc học tiếng Trung, hãy nhẹ nhàng đưa cuộc trò chuyện về chủ đề học tập.
- Định dạng bằng Markdown đơn giản: in đậm, danh sách gạch đầu dòng. Không dùng bảng.
- Không cần nói rằng bạn là AI."""


@require_POST
def ai_chat_stream(request):

    user_id = request.session.get("user_id")

    if not user_id:
        return JsonResponse({"error": "login_required"}, status=401)

    if not is_premium_user(user_id):
        return JsonResponse({"error": "premium_required"}, status=403)

    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({"error": "bad_request"}, status=400)

    message = str(data.get("message", "")).strip()[:1000]

    if not message:
        return JsonResponse({"error": "empty"}, status=400)

    # Lịch sử hội thoại do trình duyệt gửi lên, chỉ giữ 8 tin gần nhất
    contents = []
    history = data.get("history", [])

    if isinstance(history, list):
        for item in history[-8:]:
            if not isinstance(item, dict):
                continue

            role = "user" if item.get("role") == "user" else "model"
            text = str(item.get("text", "")).strip()[:2000]

            if text:
                contents.append({"role": role, "parts": [{"text": text}]})

    # Gemini yêu cầu lượt đầu phải là của người dùng
    while contents and contents[0]["role"] == "model":
        contents.pop(0)

    contents.append({"role": "user", "parts": [{"text": message}]})

    def generate():

        parts = []

        try:
            client = get_gemini_client()

            stream = client.models.generate_content_stream(
                model="gemini-3.5-flash-lite",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=CHAT_SYSTEM_PROMPT
                ),
            )

            for chunk in stream:
                if chunk.text:
                    parts.append(chunk.text)
                    yield chunk.text

        except Exception as e:
            print("========== AI CHAT ERROR ==========")
            print(type(e).__name__)
            print(str(e))
            print("===================================")

            yield "⚠️ Không thể kết nối với AI. Vui lòng thử lại sau."
            return
        yield "\x03"
        answer = "".join(parts).strip()

        if answer:
            try:
                AIChatHistory.objects.create(
                    user_id=user_id,
                    question=message,
                    answer=markdown.markdown(
                        answer,
                        extensions=["extra", "nl2br"]
                    )
                )
            except Exception as e:
                print("AI CHAT: không lưu được lịch sử:", e)

    response = StreamingHttpResponse(
        generate(),
        content_type="text/plain; charset=utf-8"
    )

    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"

    return response