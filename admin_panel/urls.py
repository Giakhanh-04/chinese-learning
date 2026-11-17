from django.urls import path

from . import views, views_courses, views_grammar, views_import, views_premium, views_vocab, views_exam, views_report

urlpatterns = [
    path("", views.dashboard, name="admin_dashboard"),

    # Người dùng
    path("nguoi-dung/", views.user_list, name="admin_users"),
    path("nguoi-dung/<int:user_id>/sua/", views.user_edit, name="admin_user_edit"),
    path("nguoi-dung/<int:user_id>/xoa/", views.user_delete, name="admin_user_delete"),

    # Doanh thu & giao dịch
    path("giao-dich/", views_premium.payment_list, name="admin_payments"),
    path("giao-dich/bao-cao/", views_report.payment_report, name="admin_payment_report"),
    # Gói Premium
    path("goi-premium/", views_premium.package_list, name="admin_packages"),
    path("goi-premium/them/", views_premium.package_form, name="admin_package_create"),
    path("goi-premium/<int:package_id>/sua/", views_premium.package_form, name="admin_package_edit"),
    path("goi-premium/<int:package_id>/an-hien/", views_premium.package_toggle, name="admin_package_toggle"),

    # Người dùng Premium
    path("nguoi-dung-premium/", views_premium.premium_user_list, name="admin_premium_users"),
    path("nguoi-dung-premium/tang/", views_premium.premium_grant, name="admin_premium_grant"),
    path("nguoi-dung-premium/<int:premium_id>/ket-thuc/", views_premium.premium_end, name="admin_premium_end"),

    # Từ vựng
    path("tu-vung/", views_vocab.vocab_list, name="admin_vocab"),
    path("tu-vung/them/", views_vocab.vocab_form, name="admin_vocab_create"),
    path("tu-vung/<int:vocab_id>/sua/", views_vocab.vocab_form, name="admin_vocab_edit"),
    path("tu-vung/<int:vocab_id>/xoa/", views_vocab.vocab_delete, name="admin_vocab_delete"),

    # Danh mục từ vựng
    path("danh-muc/", views_vocab.category_list, name="admin_categories"),
    path("danh-muc/them/", views_vocab.category_save, name="admin_category_create"),
    path("danh-muc/<int:category_id>/luu/", views_vocab.category_save, name="admin_category_save"),
    path("danh-muc/<int:category_id>/xoa/", views_vocab.category_delete, name="admin_category_delete"),

    # Khóa học
    path("khoa-hoc/", views_courses.course_list, name="admin_courses"),
    path("khoa-hoc/them/", views_courses.course_form, name="admin_course_create"),
    path("khoa-hoc/<int:course_id>/sua/", views_courses.course_form, name="admin_course_edit"),
    path("khoa-hoc/<int:course_id>/xoa/", views_courses.course_delete, name="admin_course_delete"),

    # Ngữ pháp
    path("ngu-phap/", views_grammar.grammar_list, name="admin_grammar"),
    path("ngu-phap/them/", views_grammar.grammar_form, name="admin_grammar_create"),
    path("ngu-phap/<int:grammar_id>/sua/", views_grammar.grammar_form, name="admin_grammar_edit"),
    path("ngu-phap/<int:grammar_id>/xoa/", views_grammar.grammar_delete, name="admin_grammar_delete"),

    # Bài học
    path("khoa-hoc/<int:course_id>/bai-hoc/", views_courses.lesson_list, name="admin_lessons"),
    path("khoa-hoc/<int:course_id>/bai-hoc/them/", views_courses.lesson_form, name="admin_lesson_create"),
    path("bai-hoc/<int:lesson_id>/sua/", views_courses.lesson_form, name="admin_lesson_edit"),
    path("bai-hoc/<int:lesson_id>/xoa/", views_courses.lesson_delete, name="admin_lesson_delete"),
    path("khoa-hoc/<int:course_id>/bai-hoc/nhap-excel/", views_import.lesson_import, name="admin_lesson_import"),
    path("bai-hoc/mau-excel/", views_import.lesson_import_template, name="admin_lesson_import_template"),

    # Từ vựng của bài học
    path("bai-hoc/<int:lesson_id>/tu-vung/", views_courses.lesson_vocab, name="admin_lesson_vocab"),
    path("bai-hoc/<int:lesson_id>/tu-vung/them/", views_courses.lesson_vocab_add, name="admin_lesson_vocab_add"),
    path("bai-hoc/<int:lesson_id>/tu-vung/thu-tu/", views_courses.lesson_vocab_order, name="admin_lesson_vocab_order"),
    path("bai-hoc-tu-vung/<int:link_id>/xoa/", views_courses.lesson_vocab_remove, name="admin_lesson_vocab_remove"),
    path("bai-hoc/<int:lesson_id>/gan/<str:kind>/", views_courses.lesson_attach, name="admin_lesson_attach"),
    path("bai-hoc/<str:kind>/<int:item_id>/go/", views_courses.lesson_detach, name="admin_lesson_detach"),

    path("bai-tap/", views_exam.exercise_list, name="admin_exercises"),
    path("bai-tap/them/", views_exam.exercise_form, name="admin_exercise_create"),
    path("bai-tap/<int:exercise_id>/sua/", views_exam.exercise_form, name="admin_exercise_edit"),
    path("bai-tap/<int:parent_id>/xoa/", views_exam.parent_delete, {"kind": "bai-tap"}, name="admin_exercise_delete"),

    # Bài kiểm tra
    path("kiem-tra/", views_exam.test_list, name="admin_tests"),
    path("kiem-tra/them/", views_exam.test_form, name="admin_test_create"),
    path("kiem-tra/<int:test_id>/sua/", views_exam.test_form, name="admin_test_edit"),
    path("kiem-tra/<int:parent_id>/xoa/", views_exam.parent_delete, {"kind": "kiem-tra"}, name="admin_test_delete"),

    # Câu hỏi (dùng chung cho bài tập và bài kiểm tra)
    path("cau-hoi/<str:kind>/<int:parent_id>/", views_exam.question_list, name="admin_questions"),
    path("cau-hoi/<str:kind>/<int:parent_id>/them/", views_exam.question_form, name="admin_question_create"),
    path("cau-hoi/<str:kind>/sua/<int:question_id>/", views_exam.question_form, name="admin_question_edit"),
    path("cau-hoi/<str:kind>/xoa/<int:question_id>/", views_exam.question_delete, name="admin_question_delete"),

]
