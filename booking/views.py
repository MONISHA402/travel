from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from booking.models import Destination, Package, Booking, Offer, Payment
from .forms import CustomSignupForm
from django.core.mail import EmailMessage
from django.db.models import Q
import razorpay
import qrcode
from io import BytesIO
from xhtml2pdf import pisa
import os

import hmac
import hashlib
# ----------------------------
# PUBLIC VIEWS
# ----------------------------
def home(request):
    top_destinations = Destination.objects.all()[:3]
    top_packages = Package.objects.all()[:3]
    offers = Offer.objects.filter(active=True)
    return render(request, "booking/home.html", {
        "top_destinations": top_destinations,
        "top_packages": top_packages,
        "offers": offers,
    })

def destination_list(request):
    destinations = Destination.objects.all()
    return render(request, "booking/destination_list.html", {"destinations": destinations})

def destination_detail(request, slug):
    dest = get_object_or_404(Destination, slug=slug)
    packages = dest.packages.all()
    return render(request, "booking/destination_detail.html", {"destination": dest, "packages": packages})

def package_detail(request, slug):
    package = get_object_or_404(Package, slug=slug)
    return render(request, "booking/package_detail.html", {"package": package})

def holiday_packages(request):
    packages = Package.objects.all()
    return render(request, "booking/holiday_packages.html", {"packages": packages})

def hotels(request):
    return render(request, "booking/hotels.html")

def flights(request):
    return render(request, "booking/flights.html")

def offers(request):
    offers = Offer.objects.filter(active=True)
    return render(request, "booking/offers.html", {"offers": offers})

def contact_view(request):
    return render(request, "booking/contact.html")

def search(request):
    query = request.GET.get("q", "")
    destinations = Destination.objects.filter(
        Q(name__icontains=query) | Q(country__icontains=query)
    )
    packages = Package.objects.filter(
        Q(title__icontains=query) | Q(description__icontains=query)
    )
    return render(request, "booking/search_results.html", {
        "query": query,
        "destinations": destinations,
        "packages": packages,
    })

# ----------------------------
# AUTH
# ----------------------------
def signup_view(request):
    if request.method == "POST":
        form = CustomSignupForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()
            login(request, user)
            return redirect("home")
    else:
        form = CustomSignupForm()
    return render(request, "booking/signup.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("home")
    else:
        form = AuthenticationForm()
    return render(request, "booking/login.html", {"form": form})

def logout_view(request):
    logout(request)
    return redirect("home")

@login_required
def profile_view(request):
    return render(request, "booking/profile.html")

@login_required
def booking_list(request):
    bookings = Booking.objects.filter(user=request.user).order_by("-booking_time")
    return render(request, "booking/booking_list.html", {"bookings": bookings})

# ----------------------------
# BOOKING
# ----------------------------
@login_required
def book_package(request, package_id):
    package = get_object_or_404(Package, id=package_id)
    if request.method == "POST":
        travelers = int(request.POST.get("travelers", 1))
        offer_code = request.POST.get("offer_code", "").strip()

        total_amount = package.price * travelers
        if offer_code.lower() == "save10":
            total_amount *= 0.9

        booking = Booking.objects.create(
            user=request.user,
            package=package,
            total_amount=total_amount,
            travelers=travelers,
            status="PENDING"
        )
        return redirect("make_payment", booking_id=booking.id)

    return render(request, "booking/book_package.html", {"package": package})

# ----------------------------
# PAYMENT
# ----------------------------
@login_required
def make_payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    if hasattr(booking, "payment") and booking.payment.paid:
        return redirect("booking_list")

    amount_paise = int(booking.total_amount * 100)
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    razorpay_order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"booking_{booking.id}",
        "payment_capture": 1,
    })

    payment_obj, _ = Payment.objects.get_or_create(
        booking=booking,
        defaults={
            "amount": booking.total_amount,
            "razorpay_order_id": razorpay_order["id"],
            "paid": False,
        },
    )
    if payment_obj.razorpay_order_id != razorpay_order["id"]:
        payment_obj.razorpay_order_id = razorpay_order["id"]
        payment_obj.paid = False
        payment_obj.save()

    return render(request, "booking/payment.html", {
        "booking": booking,
        "payment": payment_obj,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "razorpay_order_id": razorpay_order["id"],
        "amount_paise": amount_paise,
        "currency": "INR",
    })

@login_required
def verify_payment(request):
    if request.method == "POST":
        import json
        data = json.loads(request.body)
        booking_id = data.get("booking_id")
        razorpay_payment_id = data.get("razorpay_payment_id")
        razorpay_order_id = data.get("razorpay_order_id")
        razorpay_signature = data.get("razorpay_signature")

        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        payment = booking.payment

        generated_signature = hmac.new(
            bytes(settings.RAZORPAY_KEY_SECRET, "utf-8"),
            msg=bytes(razorpay_order_id + "|" + razorpay_payment_id, "utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()

        if generated_signature == razorpay_signature:
            payment.razorpay_payment_id = razorpay_payment_id
            payment.paid = True
            payment.save()
            booking.status = "CONFIRMED"
            booking.save()
            generate_ticket(booking)
            send_ticket_email(booking)
            return JsonResponse({"status": "success"})
        else:
            return JsonResponse({"status": "failure"}, status=400)

# ----------------------------
# TICKET & PDF
# ----------------------------
def generate_ticket(booking):
    qr_dir = os.path.join(settings.MEDIA_ROOT, "qr")
    os.makedirs(qr_dir, exist_ok=True)
    qr_data = f"TripTrek | Booking:{booking.id} | User:{booking.user.username} | Package:{booking.package.title}"
    qr = qrcode.make(qr_data)
    qr_path = os.path.join(qr_dir, f"qr_{booking.id}.png")
    qr.save(qr_path)
    booking.qr_code = f"qr/qr_{booking.id}.png"
    booking.save()

def render_to_pdf(template_src, context_dict):
    html = render_to_string(template_src, context_dict)
    result = BytesIO()
    pdf = pisa.CreatePDF(html, dest=result)
    if pdf.err:
        return None
    result.seek(0)
    return result

def send_ticket_email(booking):
    context = {
        "booking": booking,
        "user": booking.user,
        "package": booking.package,
        "qr_uri": settings.MEDIA_URL + booking.qr_code,
        "generated_at": timezone.now(),
    }
    pdf = render_to_pdf("booking/booking_ticket.html", context)
    subject = f"TripTrek Ticket Confirmation - Booking #{booking.id}"
    body = f"Hello {booking.user.get_full_name() or booking.user.username},\n\nYour booking is CONFIRMED ✅\n\nPackage: {booking.package.title}\nTravelers: {booking.travelers}\nBooking ID: {booking.id}\nAmount Paid: ₹{booking.total_amount}\n\nYour ticket is attached in PDF format.\nThank you for choosing TripTrek!"
    email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [booking.user.email])
    email.attach(f"ticket_{booking.id}.pdf", pdf.getvalue(), "application/pdf")
    email.send(fail_silently=False)

@login_required
def download_ticket(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    if not booking.payment.paid or booking.status != "CONFIRMED":
        return HttpResponse("Ticket not available. Payment incomplete.", status=403)
    tickets_dir = os.path.join(settings.MEDIA_ROOT, "tickets")
    os.makedirs(tickets_dir, exist_ok=True)
    pdf_filename = f"ticket_{booking.id}.pdf"
    pdf_filepath = os.path.join(tickets_dir, pdf_filename)
    if not os.path.exists(pdf_filepath):
        if not booking.qr_code:
            generate_ticket(booking)
        context = {
            "booking": booking,
            "user": booking.user,
            "package": booking.package,
            "qr_uri": settings.MEDIA_URL + booking.qr_code,
            "generated_at": timezone.now(),
        }
        pdf = render_to_pdf("booking/booking_ticket.html", context)
        with open(pdf_filepath, "wb") as f:
            f.write(pdf.getvalue())
    return FileResponse(open(pdf_filepath, "rb"), as_attachment=True, filename=pdf_filename)

@login_required
def booking_ticket(request):
    bookings = Booking.objects.filter(user=request.user)
    return render(request, "booking/booking_ticket.html", {"bookings": bookings})
