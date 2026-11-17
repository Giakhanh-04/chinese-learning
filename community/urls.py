from django.urls import path
from . import views

urlpatterns = [
    path("", views.community_home, name="community_home"),
    path("new/", views.post_create, name="community_new"),
    path("post/<int:post_id>/", views.post_detail, name="community_post"),
    path("post/<int:post_id>/like/", views.post_like, name="community_like"),
    path("post/<int:post_id>/delete/", views.post_delete, name="community_delete"),
    path("comment/<int:comment_id>/delete/", views.comment_delete, name="community_comment_delete"),
    path("post/<int:post_id>/modal/", views.post_modal, name="community_modal"),
    path("post/<int:post_id>/comment/", views.comment_add, name="community_comment_add"),
]