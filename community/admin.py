from django.contrib import admin
from .models import Category, Post, Comment

admin.site.register(Category)
admin.site.register(Comment)

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "is_pinned", "is_featured", "created_at")
    list_editable = ("is_pinned", "is_featured")