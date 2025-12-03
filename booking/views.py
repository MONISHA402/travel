from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, FileResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from booking.models import Package,Offer,Booking
from django.contrib.auth.decorators import login_required


from decimal import Decimal
import razorpay
import hmac, hashlib
import os
import qrcode
from io import BytesIO
from xhtml2pdf import pisa


from .models import Destination, Package, Booking, Offer, Payment

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


# ----------------------------
# AUTH
# ----------------------------

def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = UserCreationForm()
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
    bookings = request.user.bookings.all().order_by("-booking_time")
    return render(request, "booking/booking_list.html", {"bookings": bookings})


def contact_view(request):
    return render(request, "booking/contact.html")


# ----------------------------
# BOOKING
# ----------------------------

@login_required
def book_package(request, package_id):
    package = get_object_or_404(Package, id=package_id)

    if request.method == "POST":
        travelers = int(request.POST.get("travelers", 1))
        offer_code = request.POST.get("offer_code", "").strip()

        offer = None
        discount = Decimal(0)

        if offer_code:
            try:
                offer = Offer.objects.get(code__iexact=offer_code, active=True)
                discount = (package.price * Decimal(offer.discount_percent)) / 100
            except Offer.DoesNotExist:
                pass

        total = (package.price - discount) * travelers

        booking = Booking.objects.create(
            user=request.user,
            package=package,
            travelers=travelers,
            total_amount=total,
            offer=offer,
            status="PENDING",
        )

        package.available_slots = max(0, package.available_slots - travelers)
        package.save()

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


# ----------------------------
# TICKET GENERATION HELPER
# ----------------------------

def generate_ticket(booking):
    """
    Creates only QR and stores path to booking.qr_code.
    PDF is created in download_ticket().
    """
    qr_dir = os.path.join(settings.MEDIA_ROOT, "qr")
    os.makedirs(qr_dir, exist_ok=True)

    qr_data = f"TripTrek | Booking:{booking.id} | User:{booking.user.username} | Package:{booking.package.title}"
    qr = qrcode.make(qr_data)

    qr_path = os.path.join(qr_dir, f"qr_{booking.id}.png")
    qr.save(qr_path)

    booking.qr_code = f"qr/qr_{booking.id}.png"
    booking.save()

    return True


# ----------------------------
# PAYMENT VERIFICATION
# ----------------------------

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def verify_payment(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Only POST allowed"}, status=405)

    data = request.POST
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_signature = data.get("razorpay_signature")

    try:
        payment_obj = Payment.objects.get(razorpay_order_id=razorpay_order_id)
    except Payment.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Payment not found"}, status=400)

    generated_signature = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode(),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()

    if generated_signature != razorpay_signature:
        return JsonResponse({"status": "error", "message": "Invalid signature"}, status=400)

    payment_obj.razorpay_payment_id = razorpay_payment_id
    payment_obj.razorpay_signature = razorpay_signature
    payment_obj.paid = True
    payment_obj.paid_at = timezone.now()
    payment_obj.save()

    booking = payment_obj.booking
    booking.status = "CONFIRMED"
    booking.save()

    generate_ticket(booking)

    return JsonResponse({"status": "success", "booking_id": booking.id})


# ----------------------------
# PDF & TICKET DOWNLOAD
# ----------------------------

def render_to_pdf(template_src, context_dict):
    html = render_to_string(template_src, context_dict)
    result = BytesIO()
    pdf = pisa.CreatePDF(html, dest=result, link_callback=link_callback)
    if pdf.err:
        return None
    result.seek(0)
    return result


def link_callback(uri, rel):
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATICFILES_DIRS[0], uri.replace(settings.STATIC_URL, ""))
    else:
        return uri

    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    return path


@login_required
def download_ticket(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    payment_obj = getattr(booking, "payment", None)

    if not payment_obj or not payment_obj.paid or booking.status != "CONFIRMED":
        return HttpResponse("Ticket not available. Payment incomplete.", status=403)

    tickets_dir = os.path.join(settings.MEDIA_ROOT, "tickets")
    os.makedirs(tickets_dir, exist_ok=True)

    pdf_filename = f"ticket_{booking.id}.pdf"
    pdf_filepath = os.path.join(tickets_dir, pdf_filename)

    # If already generated, serve it
    if os.path.exists(pdf_filepath):
        return FileResponse(open(pdf_filepath, "rb"), as_attachment=True, filename=pdf_filename)

    # Create fresh QR if needed
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
    if pdf is None:
        return HttpResponse("PDF generation failed", status=500)

    with open(pdf_filepath, "wb") as f:
        f.write(pdf.getvalue())

    return FileResponse(open(pdf_filepath, "rb"), as_attachment=True, filename=pdf_filename)

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

def contact(request):
    return render(request, "booking/contact.html")

def package_details(request, slug):
    package = get_object_or_404(Package, slug=slug)
    return render(request, "booking/package_detail.html", {"package": package})

@login_required
def booking_list(request):
    bookings = Booking.objects.filter(user=request.user)
    return render(request, 'booking/booking_list.html', {'bookings': bookings})

@login_required
def booking_ticket(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # If you have QR code generation, include it here
    qr_uri = None  # placeholder
    
    return render(request, 'booking/booking_ticket.html', {'booking': booking, 'qr_uri': qr_uri})

@login_required
def booking_package(request, package_id):
    package = get_object_or_404(Package, id=package_id)

    if request.method == 'POST':
        travelers = int(request.POST.get('travelers', 1))
        offer_code = request.POST.get('offer_code', '')

        # Create booking logic here (simplified)
        booking = Booking.objects.create(
            user=request.user,
            package=package,
            travelers=travelers,
            total_amount=package.price * travelers,
            status='Booked'
        )
        return redirect('booking_ticket', booking_id=booking.id)

    return render(request, 'booking/booking_package.html', {'package': package})
