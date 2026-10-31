from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from accounts.forms import EmailAuthenticationForm
from accounts import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("staff/", views.StaffListView.as_view(), name="staff-list"),
    path("staff/new/", views.StaffCreateView.as_view(), name="staff-create"),
    path(
        "password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url=reverse_lazy("accounts:password-change-done"),
        ),
        name="password-change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),
        name="password-change-done",
    ),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            success_url=reverse_lazy("accounts:password-reset-done"),
        ),
        name="password-reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password-reset-done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password-reset-complete"),
        ),
        name="password-reset-confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password-reset-complete",
    ),
    path("login/", auth_views.LoginView.as_view(form_class=EmailAuthenticationForm), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
