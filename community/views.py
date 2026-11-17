from collections import defaultdict
from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string

from accounts.models import User

from .models import Category, Comment, Post, PostLike

PERIOD_DAYS = {"week": 7, "month": 30, "year": 365}


def current_user(request):
    uid = request.session.get("user_id")
    return User.objects.filter(id=uid).first() if uid else None


def login_needed(request):
    messages.error(request, "Vui lòng đăng nhập để tiếp tục.")
    return redirect("login")


def leaderboard(period):
    """Điểm = 10 / bài đăng + 2 / bình luận trong khoảng thời gian."""
    since = timezone.now() - timedelta(days=PERIOD_DAYS[period])
    scores = defaultdict(int)

    for row in (Post.objects.filter(created_at__gte=since)
                .values("author_id").annotate(c=Count("id"))):
        scores[row["author_id"]] += row["c"] * 10

    for row in (Comment.objects.filter(created_at__gte=since)
                .values("author_id").annotate(c=Count("id"))):
        scores[row["author_id"]] += row["c"] * 2

    top = sorted(scores.items(), key=lambda x: -x[1])[:10]
    users = User.objects.in_bulk([uid for uid, _ in top])

    return [
        {"rank": i + 1, "user": users[uid], "score": score}
        for i, (uid, score) in enumerate(top) if uid in users
    ]


def community_home(request):
    user = current_user(request)

    tab = request.GET.get("tab", "all")
    cat_slug = request.GET.get("cat", "")
    q = request.GET.get("q", "").strip()
    period = request.GET.get("period", "week")
    if period not in PERIOD_DAYS:
        period = "week"

    posts = (Post.objects.select_related("author", "category")
             .annotate(like_count=Count("likes", distinct=True),
                       comment_count=Count("comments", distinct=True)))

    if tab == "liked" and user:
        posts = posts.filter(likes__user=user)
    elif tab == "mine" and user:
        posts = posts.filter(author=user)
    elif tab == "featured":
        posts = posts.filter(is_featured=True)

    if cat_slug:
        posts = posts.filter(category__slug=cat_slug)
    if q:
        posts = posts.filter(title__icontains=q) | posts.filter(content__icontains=q)

    posts = posts.order_by("-is_pinned", "-created_at")

    page_obj = Paginator(posts, 10).get_page(request.GET.get("page"))

    liked_ids = set()
    if user:
        page_post_ids = [p.id for p in page_obj.object_list]
        liked_ids = set(PostLike.objects.filter(
            user=user, post_id__in=page_post_ids).values_list("post_id", flat=True))
    # giữ nguyên bộ lọc khi chuyển trang
    params = request.GET.copy()
    params.pop("page", None)

    top_questions = (Post.objects.annotate(cc=Count("comments"))
                     .order_by("-cc", "-created_at")[:6])

    ranking = leaderboard(period)

    context = {
        "me": user,
        "page_obj": page_obj,
        "liked_ids": liked_ids,
        "tab": tab,
        "cat_slug": cat_slug,
        "q": q,
        "period": period,
        "categories": Category.objects.all(),
        "top_questions": top_questions,
        "podium": ranking[:3],
        "ranking_rest": ranking[3:],
        "qs": params.urlencode(),
    }
    return render(request, "community/home.html", context)


def post_detail(request, post_id):
    user = current_user(request)
    post = get_object_or_404(Post.objects.select_related("author", "category"), id=post_id)

    Post.objects.filter(id=post.id).update(views=F("views") + 1)
    post.views += 1

    if request.method == "POST":
        if not user:
            return login_needed(request)
        content = request.POST.get("content", "").strip()
        if content:
            Comment.objects.create(post=post, author=user, content=content[:1000])
        return redirect("community_post", post_id=post.id)

    context = {
        "me": user,
        "post": post,
        "comments": post.comments.select_related("author"),
        "like_count": post.likes.count(),
        "liked": bool(user and post.likes.filter(user=user).exists()),
        "can_delete": bool(user and (user.id == post.author_id or user.role == "admin")),
    }
    return render(request, "community/detail.html", context)


@require_POST
def post_create(request):
    user = current_user(request)
    if not user:
        return login_needed(request)

    title = request.POST.get("title", "").strip()
    content = request.POST.get("content", "").strip()
    category = Category.objects.filter(id=request.POST.get("category") or None).first()

    if not title or not content:
        messages.error(request, "Vui lòng nhập tiêu đề và nội dung.")
        return redirect("community_home")

    Post.objects.create(author=user, title=title[:200],
                        content=content[:3000], category=category)
    messages.success(request, "Đã đăng bài.")
    return redirect("community_home")


@require_POST
def post_like(request, post_id):
    user = current_user(request)
    if not user:
        return JsonResponse({"error": "login"}, status=401)

    post = get_object_or_404(Post, id=post_id)
    like, created = PostLike.objects.get_or_create(post=post, user=user)
    if not created:
        like.delete()

    return JsonResponse({"liked": created, "count": post.likes.count()})


@require_POST
def post_delete(request, post_id):
    user = current_user(request)
    if not user:
        return login_needed(request)

    post = get_object_or_404(Post, id=post_id)
    if user.id != post.author_id and user.role != "admin":
        messages.error(request, "Bạn không có quyền xóa bài này.")
        return redirect("community_post", post_id=post.id)

    post.delete()
    messages.success(request, "Đã xóa bài viết.")
    return redirect("community_home")


@require_POST
def comment_delete(request, comment_id):
    user = current_user(request)
    if not user:
        return login_needed(request)

    comment = get_object_or_404(Comment, id=comment_id)
    if user.id != comment.author_id and user.role != "admin":
        messages.error(request, "Bạn không có quyền xóa bình luận này.")
    else:
        comment.delete()
    return redirect("community_post", post_id=comment.post_id)

def post_modal(request, post_id):
    """Trả về HTML nội dung popup."""
    post = get_object_or_404(Post.objects.select_related("author", "category"), id=post_id)

    Post.objects.filter(id=post.id).update(views=F("views") + 1)
    post.views += 1

    return render(request, "community/_modal_post.html", {
        "post": post,
        "comments": post.comments.select_related("author"),
    })


@require_POST
def comment_add(request, post_id):
    user = current_user(request)
    if not user:
        return JsonResponse({"error": "login"}, status=401)

    post = get_object_or_404(Post, id=post_id)
    content = request.POST.get("content", "").strip()[:1000]
    if not content:
        return JsonResponse({"error": "empty"}, status=400)

    c = Comment.objects.create(post=post, author=user, content=content)
    html = render_to_string("community/_comment.html", {"c": c}, request=request)

    return JsonResponse({"html": html, "count": post.comments.count()})