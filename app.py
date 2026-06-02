import os
import re
import uuid
import json
import urllib.request
import urllib.parse
from functools import wraps
from datetime import datetime

import cloudinary
import cloudinary.uploader
import cloudinary.utils

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from models import db, Car, Photo

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production-please")

# Fix Railway's postgres:// → postgresql:// for SQLAlchemy
database_url = os.environ.get("DATABASE_URL", "sqlite:///cars.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB
app.config["PREFERRED_URL_SCHEME"] = "https"

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEO_EXT = {"mp4", "mov", "webm"}
ALLOWED_EXT = ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT
CARS_PER_PAGE = 12

WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "966500000000")

# Cloudinary config (reads CLOUDINARY_URL env var automatically)
cloudinary.config(
    cloudinary_url=os.environ.get("CLOUDINARY_URL", "")
)
USE_CLOUDINARY = bool(os.environ.get("CLOUDINARY_URL", ""))

db.init_app(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ---------------------------------------------------------------------------
# HTTPS redirect
# ---------------------------------------------------------------------------

@app.before_request
def force_https():
    # On Railway, X-Forwarded-Proto is set by the load balancer
    if request.headers.get("X-Forwarded-Proto", "https") == "http":
        return redirect(request.url.replace("http://", "https://", 1), code=301)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def allowed_file(filename, allowed=None):
    if allowed is None:
        allowed = ALLOWED_EXT
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed


def save_file(file_obj):
    """Upload to Cloudinary if configured, otherwise save locally."""
    if USE_CLOUDINARY:
        result = cloudinary.uploader.upload(
            file_obj,
            folder="elite-motors",
            resource_type="image"
        )
        return result["secure_url"]
    else:
        ext = file_obj.filename.rsplit(".", 1)[1].lower()
        fname = f"{uuid.uuid4().hex}.{ext}"
        file_obj.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
        return fname


def delete_file(filename):
    """Delete from Cloudinary or local storage."""
    if USE_CLOUDINARY and filename.startswith("http"):
        # Extract public_id from Cloudinary URL
        try:
            # URL format: https://res.cloudinary.com/<cloud>/image/upload/v123/elite-motors/filename
            parts = filename.split("/upload/")
            if len(parts) == 2:
                public_id = parts[1].split("/", 1)[-1]  # remove version
                public_id = public_id.rsplit(".", 1)[0]  # remove extension
                cloudinary.uploader.destroy(f"elite-motors/{public_id.split('/')[-1]}")
        except Exception:
            pass
    else:
        fpath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(fpath):
            os.remove(fpath)


def photo_url(filename):
    """Return the correct URL for a photo filename (Cloudinary URL or static)."""
    if not filename:
        return ""
    if filename.startswith("http"):
        return filename
    return url_for("static", filename=f"uploads/{filename}")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# Cache the password hash in memory (no file needed)
_admin_hash_cache = None

def get_admin_password_hash():
    global _admin_hash_cache
    raw = os.environ.get("ADMIN_PASSWORD", "admin1234")
    if _admin_hash_cache is None:
        _admin_hash_cache = generate_password_hash(raw)
    return _admin_hash_cache


# ---------------------------------------------------------------------------
# Context processors
# ---------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    lang = session.get("lang", "en")
    return dict(lang=lang, whatsapp_number=WHATSAPP_NUMBER, photo_url=photo_url)


# ---------------------------------------------------------------------------
# Language toggle
# ---------------------------------------------------------------------------

@app.route("/set-lang/<lang>")
def set_lang(lang):
    if lang in ("en", "ar"):
        session["lang"] = lang
    return redirect(request.referrer or url_for("index"))


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    lang = session.get("lang", "en")
    page = request.args.get("page", 1, type=int)

    query = Car.query

    # Filters
    search = request.args.get("search", "").strip()
    brand = request.args.get("brand", "").strip()
    color = request.args.get("color", "").strip()
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    min_year = request.args.get("min_year", type=int)
    max_year = request.args.get("max_year", type=int)

    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(
                Car.make.ilike(like),
                Car.model.ilike(like),
                Car.description_en.ilike(like),
                Car.description_ar.ilike(like),
            )
        )
    if brand:
        query = query.filter(Car.make.ilike(f"%{brand}%"))
    if color:
        query = query.filter(Car.color.ilike(f"%{color}%"))
    if min_price is not None:
        query = query.filter(Car.price >= min_price)
    if max_price is not None:
        query = query.filter(Car.price <= max_price)
    if min_year is not None:
        query = query.filter(Car.year >= min_year)
    if max_year is not None:
        query = query.filter(Car.year <= max_year)

    pagination = query.order_by(Car.created_at.desc()).paginate(page=page, per_page=CARS_PER_PAGE, error_out=False)
    cars = pagination.items

    brands = [r[0] for r in db.session.query(Car.make).distinct().order_by(Car.make).all()]
    colors = [r[0] for r in db.session.query(Car.color).distinct().order_by(Car.color).all()]

    return render_template(
        "index.html",
        cars=cars,
        pagination=pagination,
        brands=brands,
        colors=colors,
        lang=lang,
        args=request.args,
    )


@app.route("/car/<int:car_id>")
def car_detail(car_id):
    car = Car.query.get_or_404(car_id)
    lang = session.get("lang", "en")
    wa_msg = f"Hi, I'm interested in the {car.display_name}"
    if lang == "ar":
        wa_msg = f"مرحبا، أنا مهتم بـ {car.display_name}"
    return render_template("car.html", car=car, lang=lang, wa_msg=wa_msg)


@app.route("/test-drive", methods=["POST"])
@limiter.limit("5 per minute")
def test_drive():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    car_id = request.form.get("car_id", "").strip()

    if not name or not phone:
        flash("Please fill all fields." if session.get("lang") != "ar" else "يرجى ملء جميع الحقول.", "error")
        return redirect(request.referrer or url_for("index"))

    phone = re.sub(r"[^\d+\-\s]", "", phone)
    car = Car.query.get(car_id)

    flash(
        "Request received! We'll contact you shortly."
        if session.get("lang") != "ar"
        else "تم استلام طلبك! سنتواصل معك قريبًا.",
        "success",
    )
    return redirect(url_for("car_detail", car_id=car_id) if car_id else url_for("index"))


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password_hash(get_admin_password_hash(), password):
            session["admin_logged_in"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Invalid password.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    cars = Car.query.order_by(Car.created_at.desc()).all()
    return render_template("admin/dashboard.html", cars=cars)


@app.route("/admin/car/new", methods=["GET", "POST"])
@login_required
def admin_car_new():
    if request.method == "POST":
        car = Car(
            make=request.form["make"].strip(),
            model=request.form["model"].strip(),
            year=int(request.form["year"]),
            price=float(request.form["price"]),
            mileage=int(request.form["mileage"]),
            color=request.form["color"].strip(),
            description_en=request.form.get("description_en", "").strip(),
            description_ar=request.form.get("description_ar", "").strip(),
            video_url=request.form.get("video_url", "").strip(),
        )
        db.session.add(car)
        db.session.flush()

        photos = request.files.getlist("photos")
        for i, f in enumerate(photos):
            if f and f.filename and allowed_file(f.filename, ALLOWED_IMAGE_EXT):
                fname = save_file(f)
                db.session.add(Photo(car_id=car.id, filename=fname, order=i))

        db.session.commit()
        flash("Car added successfully!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/edit.html", car=None)


@app.route("/admin/car/<int:car_id>/edit", methods=["GET", "POST"])
@login_required
def admin_car_edit(car_id):
    car = Car.query.get_or_404(car_id)

    if request.method == "POST":
        car.make = request.form["make"].strip()
        car.model = request.form["model"].strip()
        car.year = int(request.form["year"])
        car.price = float(request.form["price"])
        car.mileage = int(request.form["mileage"])
        car.color = request.form["color"].strip()
        car.description_en = request.form.get("description_en", "").strip()
        car.description_ar = request.form.get("description_ar", "").strip()
        car.video_url = request.form.get("video_url", "").strip()

        photos = request.files.getlist("photos")
        current_max_order = max((p.order for p in car.photos), default=-1)
        for i, f in enumerate(photos):
            if f and f.filename and allowed_file(f.filename, ALLOWED_IMAGE_EXT):
                fname = save_file(f)
                db.session.add(Photo(car_id=car.id, filename=fname, order=current_max_order + i + 1))

        db.session.commit()
        flash("Car updated!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/edit.html", car=car)


@app.route("/admin/car/<int:car_id>/delete", methods=["POST"])
@login_required
def admin_car_delete(car_id):
    car = Car.query.get_or_404(car_id)
    for photo in car.photos:
        delete_file(photo.filename)
    db.session.delete(car)
    db.session.commit()
    flash("Car deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/car/<int:car_id>/toggle-sold", methods=["POST"])
@login_required
def admin_toggle_sold(car_id):
    car = Car.query.get_or_404(car_id)
    car.is_sold = not car.is_sold
    db.session.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/photo/<int:photo_id>/delete", methods=["POST"])
@login_required
def admin_photo_delete(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    car_id = photo.car_id
    delete_file(photo.filename)
    db.session.delete(photo)
    db.session.commit()
    flash("Photo deleted.", "success")
    return redirect(url_for("admin_car_edit", car_id=car_id))


# ---------------------------------------------------------------------------
# Chat & Inventory API
# ---------------------------------------------------------------------------

@app.route("/api/inventory")
def api_inventory():
    cars = Car.query.filter_by(is_sold=False).order_by(Car.created_at.desc()).all()
    result = []
    for c in cars:
        result.append({
            "id": c.id,
            "make": c.make,
            "model": c.model,
            "year": c.year,
            "price": c.price,
            "mileage": c.mileage,
            "color": c.color,
            "description_en": c.description_en,
            "description_ar": c.description_ar,
        })
    return jsonify(result)


@app.route("/api/chat", methods=["POST"])
@limiter.limit("30 per minute")
def api_chat():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    lang = data.get("lang", "en")
    inventory = data.get("inventory", [])

    if not message:
        return jsonify({"error": "empty message"}), 400

    # Build bilingual system prompt with live inventory
    if inventory:
        inv_text = "\n".join(
            f"- {c.get('year')} {c.get('make')} {c.get('model')}, {c.get('color')}, "
            f"{int(c.get('mileage',0)):,} miles, ${int(c.get('price',0)):,}"
            for c in inventory
        )
    else:
        inv_text = "No cars currently available" if lang == "en" else "لا توجد سيارات متاحة حالياً"

    if lang == "ar":
        system_prompt = (
            "أنت مساعد 371cars. نحن وسيط نربط المشترين بوكلاء السيارات في أمريكا فقط."
            " لا نقدم فحوصات ولا تمويل ولا شحن - فقط نساعد في إيجاد السيارة المناسبة من الوكلاء."
            " موقعنا أورلاندو فلوريدا ونعمل مع وكلاء في جميع أنحاء أمريكا."
            " رد باللغة العربية، جملتان أو ثلاث كحد أقصى، لا تستخدم نقاط."
            " واتساب: 3863012863، ساعات العمل: 9 ص - 5 م."
            f" السيارات المتاحة: {inv_text}"
        )
    else:
        system_prompt = (
            "You are a sales assistant for 371cars, based in Orlando Florida USA."
            " 371cars is a middleman — we simply connect buyers with car dealerships across the US."
            " We do NOT offer inspections, financing, shipping, or paperwork. We just help find the right car."
            " Keep replies under 3 sentences. No bullet points. Be friendly and direct."
            " Contact: WhatsApp (386)301-2863, hours 9AM-5PM, @371cars on TikTok/Instagram/Facebook."
            f" Available cars: {inv_text}"
        )

    try:
        encoded_msg = urllib.parse.quote(message, safe='')
        encoded_sys = urllib.parse.quote(system_prompt, safe='')
        url = f"https://text.pollinations.ai/{encoded_msg}?model=openai&seed=42&system={encoded_sys}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            reply = resp.read().decode("utf-8").strip()
        # Strip any Pollinations ad footer
        for marker in ["---", "🌸", "Support Pollinations", "Powered by Pollinations"]:
            if marker in reply:
                reply = reply[:reply.index(marker)].strip()
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"reply": "Sorry, I'm having trouble connecting right now. Please try again shortly."}), 200


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

def seed_data():
    if Car.query.count() > 0:
        return

    cars_data = [
        dict(
            make="Mercedes-Benz", model="S-Class", year=2023,
            price=450000, mileage=15000, color="Obsidian Black",
            description_en="Luxury flagship sedan with AMG package. Full options, panoramic roof, massage seats, night vision.",
            description_ar="سيارة مرسيدس بنز S-Class الفاخرة مع باقة AMG.",
            video_url="", is_sold=False,
        ),
        dict(
            make="BMW", model="X7", year=2022,
            price=320000, mileage=28000, color="Alpine White",
            description_en="Full-size luxury SUV. M Sport package, 7 seats, head-up display, laser headlights.",
            description_ar="سيارة دفع رباعي فاخرة. باقة M Sport، 7 مقاعد.",
            video_url="", is_sold=False,
        ),
    ]

    for data in cars_data:
        db.session.add(Car(**data))
    db.session.commit()


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()
    seed_data()


if __name__ == "__main__":
    app.run(debug=False)
