import io

from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from courses.models import (
    Course, Exercise, ExerciseQuestion, Lesson, LessonVocabulary,
)
from vocabulary.models import Vocabulary, VocabularyCategories

from .decorators import admin_required
from .views_courses import HSK_LEVELS, LESSON_STATUSES
from .views_vocab import CATEGORY_NULLABLE

MAX_FILE_MB = 5
MAX_ERRORS_SHOWN = 40
DEFAULT_CATEGORY_NAME = "Chưa phân loại"

# Tên sheet và số cột của từng sheet (đọc theo vị trí cột, không đọc theo tên cột)
SHEET_LESSONS = ("BaiHoc", 4)
SHEET_VOCAB = ("TuVung", 9)
SHEET_QUIZ = ("CauHoi", 9)


# =========================================================
# ĐỌC EXCEL
# =========================================================

def _cell(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _to_int(text):
    text = str(text).strip()
    return int(text) if text.isdigit() else None


def _sheet_rows(wb, spec):
    """Trả về [(số dòng, [các ô]), ...] hoặc [] nếu không có sheet."""
    name, ncols = spec

    ws = None
    for sheet_name in wb.sheetnames:
        if sheet_name.strip().lower() == name.lower():
            ws = wb[sheet_name]
            break

    if ws is None:
        return []

    rows = []

    for index, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        cells = [_cell(c) for c in (list(row) + [None] * ncols)[:ncols]]

        if any(cells):
            rows.append((index, cells))

    return rows


# =========================================================
# KIỂM TRA DỮ LIỆU (chưa ghi gì vào database)
# =========================================================

def _parse(wb, course):

    errors = []

    existing = {}
    for lesson in Lesson.objects.filter(course_id=course.id).order_by("id"):
        existing.setdefault(lesson.lesson_order, lesson)

    # ---------- BaiHoc ----------
    lessons = []
    seen = set()

    for row, c in _sheet_rows(wb, SHEET_LESSONS):

        order = _to_int(c[0])
        title = c[1]
        description = c[2]
        status = (c[3] or LESSON_STATUSES[0]).lower()

        if order is None:
            errors.append(f"BaiHoc, dòng {row}: cột 'thu_tu' phải là số nguyên.")
        elif not title:
            errors.append(f"BaiHoc, dòng {row}: thiếu 'tieu_de'.")
        elif status not in LESSON_STATUSES:
            errors.append(
                f"BaiHoc, dòng {row}: trạng thái '{c[3]}' không hợp lệ "
                f"(chỉ nhận: {', '.join(LESSON_STATUSES)})."
            )
        elif order in seen:
            errors.append(f"BaiHoc, dòng {row}: thứ tự bài {order} bị trùng trong file.")
        else:
            seen.add(order)
            lessons.append({
                "order": order,
                "title": title,
                "description": description,
                "status": status,
            })

    valid_orders = seen | set(existing)

    def lesson_problem(order):
        if order is None:
            return "cột 'bai' phải là số thứ tự bài học."
        if order not in valid_orders:
            return f"bài số {order} chưa có trong sheet BaiHoc và chưa có trong khóa học."
        return None

    # ---------- TuVung ----------
    vocab = []

    for row, c in _sheet_rows(wb, SHEET_VOCAB):

        order = _to_int(c[0])
        word, pinyin, meaning = c[1], c[2], c[3]
        hsk = _to_int(c[4]) if c[4] else course.hsk_level

        problem = lesson_problem(order)

        if problem:
            errors.append(f"TuVung, dòng {row}: {problem}")
        elif not word or not meaning:
            errors.append(f"TuVung, dòng {row}: thiếu chữ Hán hoặc nghĩa.")
        elif hsk not in HSK_LEVELS:
            errors.append(f"TuVung, dòng {row}: cấp HSK phải từ 1 đến 6.")
        else:
            vocab.append({
                "order": order,
                "word": word,
                "pinyin": pinyin,
                "meaning": meaning,
                "hsk": hsk,
                "category": c[5],
                "example": c[6],
                "example_pinyin": c[7],
                "example_meaning": c[8],
            })

    # ---------- CauHoi ----------
    quiz = []

    for row, c in _sheet_rows(wb, SHEET_QUIZ):

        order = _to_int(c[0])
        exercise_title = c[1] or "Bài tập"
        question = c[2]
        options = {"A": c[3], "B": c[4], "C": c[5], "D": c[6]}
        answer = c[7].upper()

        problem = lesson_problem(order)

        if problem:
            errors.append(f"CauHoi, dòng {row}: {problem}")
        elif not question:
            errors.append(f"CauHoi, dòng {row}: thiếu nội dung câu hỏi.")
        elif not options["A"] or not options["B"]:
            errors.append(f"CauHoi, dòng {row}: cần ít nhất đáp án A và B.")
        elif answer not in options or not options[answer]:
            errors.append(
                f"CauHoi, dòng {row}: 'dap_an' phải là A, B, C hoặc D "
                "và đáp án đó phải có nội dung."
            )
        else:
            quiz.append({
                "order": order,
                "exercise": exercise_title,
                "question": question,
                "options": options,
                "answer": answer,
                "explanation": c[8],
            })

    if not lessons and not vocab and not quiz and not errors:
        errors.append("File không có dữ liệu nào. Hãy điền vào các sheet BaiHoc, TuVung, CauHoi.")

    return {"lessons": lessons, "vocab": vocab, "quiz": quiz}, errors


# =========================================================
# GHI VÀO DATABASE (một giao dịch: lỗi thì không lưu gì cả)
# =========================================================

@transaction.atomic
def _apply(course, plan):

    now = timezone.now()

    summary = {
        "lessons_new": 0,
        "lessons_kept": 0,
        "vocab_new": 0,
        "vocab_linked": 0,
        "exercises_new": 0,
        "exercises_skipped": 0,
        "questions_new": 0,
    }

    # ---------- Bài học ----------
    by_order = {}
    for lesson in Lesson.objects.filter(course_id=course.id).order_by("id"):
        by_order.setdefault(lesson.lesson_order, lesson)

    for item in plan["lessons"]:

        if item["order"] in by_order:
            summary["lessons_kept"] += 1
            continue

        by_order[item["order"]] = Lesson.objects.create(
            course=course,
            title=item["title"],
            description=item["description"],
            lesson_order=item["order"],
            status=item["status"],
            created_at=now,
            updated_at=now,
        )

        summary["lessons_new"] += 1

    # ---------- Từ vựng ----------
    categories = {}

    def get_category(name):

        if not name:
            if CATEGORY_NULLABLE:
                return None
            name = DEFAULT_CATEGORY_NAME

        key = name.lower()

        if key not in categories:
            category = VocabularyCategories.objects.filter(name__iexact=name).first()

            if category is None:
                category = VocabularyCategories.objects.create(
                    name=name,
                    description="",
                    created_at=now,
                )

            categories[key] = category

        return categories[key]

    link_state = {}

    def state_for(lesson):

        if lesson.id not in link_state:
            link_state[lesson.id] = [
                set(
                    LessonVocabulary.objects
                    .filter(lesson_id=lesson.id)
                    .values_list("vocabulary_id", flat=True)
                ),
                LessonVocabulary.objects
                .filter(lesson_id=lesson.id)
                .aggregate(m=Max("word_order"))["m"] or 0,
            ]

        return link_state[lesson.id]

    for item in plan["vocab"]:

        lesson = by_order[item["order"]]

        vocabulary = Vocabulary.objects.filter(
            word=item["word"],
            pinyin=item["pinyin"],
        ).first()

        if vocabulary is None:
            vocabulary = Vocabulary.objects.create(
                word=item["word"],
                pinyin=item["pinyin"],
                meaning=item["meaning"],
                example_sentence=item["example"],
                example_pinyin=item["example_pinyin"],
                example_meaning=item["example_meaning"],
                audio="",
                hsk_level=item["hsk"],
                category=get_category(item["category"]),
                created_at=now,
            )
            summary["vocab_new"] += 1

        ids, _last = state_for(lesson)

        if vocabulary.id in ids:
            continue

        state = link_state[lesson.id]
        state[1] += 1
        ids.add(vocabulary.id)

        LessonVocabulary.objects.create(
            lesson=lesson,
            vocabulary=vocabulary,
            word_order=state[1],
        )

        summary["vocab_linked"] += 1

    # ---------- Bài tập và câu hỏi ----------
    groups = {}

    for item in plan["quiz"]:
        groups.setdefault((item["order"], item["exercise"]), []).append(item)

    for (order, title), questions in groups.items():

        lesson = by_order[order]

        if Exercise.objects.filter(lesson_id=lesson.id, title=title).exists():
            summary["exercises_skipped"] += 1
            continue

        exercise = Exercise.objects.create(
            lesson=lesson,
            title=title,
            description="",
            created_at=now,
            updated_at=now,
        )

        summary["exercises_new"] += 1

        for number, q in enumerate(questions, start=1):

            ExerciseQuestion.objects.create(
                exercise=exercise,
                question=q["question"],
                option_a=q["options"]["A"],
                option_b=q["options"]["B"],
                option_c=q["options"]["C"],
                option_d=q["options"]["D"],
                correct_answer=q["answer"],
                explanation=q["explanation"],
                question_order=number,
                created_at=now,
            )

            summary["questions_new"] += 1

    return summary


# =========================================================
# TRANG NHẬP EXCEL
# =========================================================

@admin_required
def lesson_import(request, course_id):

    course = get_object_or_404(Course, id=course_id)

    context = {"course": course, "errors": [], "more_errors": 0}

    if request.method != "POST":
        return render(request, "admin_panel/lesson_import.html", context)

    upload = request.FILES.get("file")

    def fail(message):
        context["errors"] = [message]
        return render(request, "admin_panel/lesson_import.html", context)

    if upload is None:
        return fail("Bạn chưa chọn file.")

    if not upload.name.lower().endswith(".xlsx"):
        return fail("Chỉ nhận file Excel định dạng .xlsx.")

    if upload.size > MAX_FILE_MB * 1024 * 1024:
        return fail(f"File quá lớn (tối đa {MAX_FILE_MB} MB).")

    try:
        wb = load_workbook(upload, read_only=True, data_only=True)
    except Exception:
        return fail("Không đọc được file. Hãy dùng đúng file mẫu và lưu ở định dạng .xlsx.")

    try:
        plan, errors = _parse(wb, course)
    finally:
        wb.close()

    if errors:
        context["errors"] = errors[:MAX_ERRORS_SHOWN]
        context["more_errors"] = max(0, len(errors) - MAX_ERRORS_SHOWN)
        messages.error(request, "File có lỗi nên chưa nhập gì cả. Hãy sửa rồi tải lại.")
        return render(request, "admin_panel/lesson_import.html", context)

    try:
        summary = _apply(course, plan)
    except Exception as e:
        print("IMPORT ERROR:", type(e).__name__, e)
        return fail(f"Lỗi khi lưu vào database ({type(e).__name__}). Chưa có gì được lưu.")

    messages.success(
        request,
        "Đã nhập xong: "
        f"{summary['lessons_new']} bài học mới "
        f"({summary['lessons_kept']} bài đã có được giữ nguyên), "
        f"{summary['vocab_new']} từ vựng mới, "
        f"{summary['vocab_linked']} từ được gắn vào bài, "
        f"{summary['exercises_new']} bài tập ({summary['questions_new']} câu hỏi)"
        + (
            f", bỏ qua {summary['exercises_skipped']} bài tập đã có."
            if summary["exercises_skipped"] else "."
        )
    )

    return redirect("admin_lessons", course_id=course.id)


# =========================================================
# FILE EXCEL MẪU
# =========================================================

@admin_required
def lesson_import_template(request):

    wb = Workbook()

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="354A7D")

    def make_sheet(ws, headers, rows, widths):
        ws.append(headers)

        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(vertical="center")

        for row in rows:
            ws.append(row)

        for index, width in enumerate(widths, start=1):
            ws.column_dimensions[ws.cell(row=1, column=index).column_letter].width = width

        ws.freeze_panes = "A2"

    # ---------- Hướng dẫn ----------
    guide = wb.active
    guide.title = "HuongDan"

    lines = [
        "HƯỚNG DẪN NHẬP BÀI HỌC TỪ EXCEL",
        "",
        "1. Điền dữ liệu vào các sheet BaiHoc, TuVung, CauHoi (không đổi tên sheet, không đổi thứ tự cột, không xóa dòng tiêu đề).",
        "2. Cột 'bai' ở sheet TuVung và CauHoi là SỐ THỨ TỰ của bài học, trùng với cột 'thu_tu' ở sheet BaiHoc.",
        "3. Có thể bỏ trống sheet nào không dùng. Ví dụ chỉ muốn thêm từ vựng cho bài đã có thì chỉ điền sheet TuVung.",
        "4. Bài học đã có cùng thứ tự trong khóa sẽ được giữ nguyên, chỉ bổ sung từ vựng và bài tập mới.",
        "5. Từ vựng đã có trong hệ thống (cùng chữ Hán và pinyin) được dùng lại, không tạo trùng.",
        "6. Bài tập đã có cùng tên trong bài sẽ bị bỏ qua. Mỗi nhóm câu hỏi cùng 'ten_bai_tap' là một bài tập.",
        "7. Cột dap_an chỉ nhận A, B, C hoặc D. Cần ít nhất đáp án A và B.",
        f"8. Cột trang_thai nhận: {', '.join(LESSON_STATUSES)}. Để trống thì lấy '{LESSON_STATUSES[0]}'.",
        "9. Nếu có dòng sai, hệ thống báo rõ dòng nào và không nhập gì cả. Sửa xong tải lại là được.",
        "10. Xóa các dòng ví dụ trước khi nhập dữ liệu thật.",
    ]

    for line in lines:
        guide.append([line])

    guide["A1"].font = Font(bold=True, size=14)
    guide.column_dimensions["A"].width = 130

    # ---------- BaiHoc ----------
    make_sheet(
        wb.create_sheet("BaiHoc"),
        ["thu_tu", "tieu_de", "mo_ta", "trang_thai"],
        [[1, "Chào hỏi", "Học cách chào hỏi cơ bản", LESSON_STATUSES[0]]],
        [10, 36, 50, 14],
    )

    # ---------- TuVung ----------
    make_sheet(
        wb.create_sheet("TuVung"),
        ["bai", "tu", "pinyin", "nghia", "hsk", "danh_muc",
         "cau_vi_du", "pinyin_vi_du", "nghia_vi_du"],
        [[1, "你好", "nǐ hǎo", "xin chào", 1, "Chào hỏi",
          "你好，我叫王明。", "Nǐ hǎo, wǒ jiào Wáng Míng.", "Xin chào, tôi tên là Vương Minh."]],
        [8, 14, 18, 24, 8, 18, 28, 36, 36],
    )

    # ---------- CauHoi ----------
    make_sheet(
        wb.create_sheet("CauHoi"),
        ["bai", "ten_bai_tap", "cau_hoi", "A", "B", "C", "D", "dap_an", "giai_thich"],
        [[1, "Bài tập 1", "你好 nghĩa là gì?", "Xin chào", "Cảm ơn",
          "Tạm biệt", "Xin lỗi", "A", "你好 là lời chào thông dụng."]],
        [8, 22, 40, 20, 20, 20, 20, 10, 40],
    )

    buffer = io.BytesIO()
    wb.save(buffer)

    response = HttpResponse(
        buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )

    response["Content-Disposition"] = 'attachment; filename="mau_nhap_bai_hoc.xlsx"'

    return response