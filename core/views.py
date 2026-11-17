
from django.shortcuts import render
from django.http import HttpResponseForbidden

def csrf_failure(request, reason=""):
    html = f"""
    <div style="font-family:sans-serif;max-width:640px;margin:60px auto;padding:20px">
      <h2>Lỗi 403</h2>
      <p>Lý do: {reason}</p>
      <p>Host: {request.get_host()}<br>
      Origin: {request.META.get('HTTP_ORIGIN', '(không có)')}<br>
      Cookie CSRF: {'có' if 'csrftoken' in request.COOKIES else 'KHÔNG CÓ'}<br>
      Secure: {request.is_secure()}</p>
    </div>
    """
    return HttpResponseForbidden(html)

def home(request):
    return render(request, "core/home.html")


def learning_page(request):
    return render(request, "core/learning.html")
