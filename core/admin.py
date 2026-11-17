from django.contrib import admin

from .models import HSKTest, HSKQuestion


class HSKQuestionInline(admin.TabularInline):
    model = HSKQuestion
    extra = 1


@admin.register(HSKTest)
class HSKTestAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "hsk_level",
        "duration",
        "created_at",
    )

    list_filter = (
        "hsk_level",
    )

    search_fields = (
        "title",
    )

    inlines = [
        HSKQuestionInline
    ]


@admin.register(HSKQuestion)
class HSKQuestionAdmin(admin.ModelAdmin):

    list_display = (
        "test",
        "question_order",
        "correct_answer",
    )

    list_filter = (
        "test",
    )

    search_fields = (
        "question",
    )