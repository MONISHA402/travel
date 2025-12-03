from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("destinations/", views.destination_list, name="destination_list"),
    path("destination/<slug:slug>/", views.destination_detail, name="destination_detail"),
    path("package/<slug:slug>/", views.package_detail, name="package_detail"),

    # Auth
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Booking
    path("book/<int:package_id>/", views.book_package, name="book_package"),
    path("bookings/", views.booking_list, name="booking_list"),
    path("profile/", views.profile_view, name="profile"),

    # Payment
    path("payment/<int:booking_id>/", views.make_payment, name="make_payment"),
    path("payment/verify/", views.verify_payment, name="verify_payment"),

    # Ticket
    path("booking/<int:booking_id>/ticket/", views.download_ticket, name="download_ticket"),

    # Contact
    path("contact/", views.contact_view, name="contact"),

    path("holidays/", views.holiday_packages, name="holiday_packages"),
    path("hotels/", views.hotels, name="hotels"),
    path("flights/", views.flights, name="flights"),
    path("offers/", views.offers, name="offers"),
   
    path("package/<slug:slug>/", views.package_details, name="package_details"),
    path('ticket/<int:booking_id>/', views.booking_ticket, name='booking_ticket'),
]
