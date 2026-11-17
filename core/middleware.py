from django.contrib import messages
from django.shortcuts import redirect

# Các trang cần đăng nhập, tính theo tên đường dẫn (name=... trong urls.py)
LOGIN_REQUIRED_URL_NAMES = {
    # Học tập
    "TÊN_MENU_HỌC_TẬP",     # <- thay bằng tên bạn tìm ở bước 1
    "course_list",
    "course_detail",
    "lesson_detail",
    "exercise_list",
    "exercise_detail",
    "progress",

    # Thi thử
    "TÊN_MENU_THI_THỬ",     # <- thay bằng tên bạn tìm ở bước 1
    "test_list",
    "test_detail",

    # Muốn chặn thêm thì bỏ dấu # ở 2 dòng dưới:
    # "vocabulary_list",
    # "grammar_list",
}


class LoginRequiredMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):

        match = request.resolver_match
        name = match.url_name if match else None

        if name in LOGIN_REQUIRED_URL_NAMES and not request.session.get("user_id"):

            # nhớ trang vừa bấm để đăng nhập xong quay lại đúng chỗ
            if request.method == "GET":
                request.session["next_url"] = request.get_full_path()

            messages.info(request, "Vui lòng đăng nhập để sử dụng tính năng này.")

            return redirect("login")

        return None