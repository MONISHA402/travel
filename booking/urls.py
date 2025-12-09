from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [

    # ===========================
    # HOME & MAIN PAGES
    # ===========================
    path("", views.home, name="home"),
    path("destinations/", views.destination_list, name="destination_list"),
    path("destination/<slug:slug>/", views.destination_detail, name="destination_detail"),
    path("package/<slug:slug>/", views.package_detail, name="package_detail"),
    path("holidays/", views.holiday_packages, name="holiday_packages"),
    path("hotels/", views.hotels, name="hotels"),
    path("flights/", views.flights, name="flights"),
    path("offers/", views.offers, name="offers"),
    path("search/", views.search, name="search"),

    # ===========================
    # AUTH (CUSTOM)
    # ===========================
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # ===========================
    # PASSWORD RESET
    # ===========================
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="booking/password_reset.html"
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="booking/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="booking/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="booking/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # ===========================
    # USER PROFILE & BOOKINGS
    # ===========================
    path("profile/", views.profile_view, name="profile"),
    path("bookings/", views.booking_list, name="booking_list"),
    path("book/<int:package_id>/", views.book_package, name="book_package"),

    # ===========================
    # PAYMENT
    # ===========================
    path("make-payment/<int:booking_id>/", views.make_payment, name="make_payment"),
    path("payment/verify/", views.verify_payment, name="verify_payment"),

    # ===========================
    # TICKET
    # ===========================
    path("booking/<int:booking_id>/ticket/", views.download_ticket, name="download_ticket"),
    path("tickets/", views.booking_ticket, name="booking_ticket"),

    # ===========================
    # CONTACT
    # ===========================
    path("contact/", views.contact_view, name="contact"),
]
