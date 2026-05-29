from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Car(db.Model):
    __tablename__ = "cars"

    id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    mileage = db.Column(db.Integer, nullable=False)
    color = db.Column(db.String(50), nullable=False)
    description_en = db.Column(db.Text, default="")
    description_ar = db.Column(db.Text, default="")
    video_url = db.Column(db.String(500), default="")
    is_sold = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    photos = db.relationship("Photo", backref="car", lazy=True, cascade="all, delete-orphan", order_by="Photo.order")

    @property
    def primary_photo(self):
        if self.photos:
            return self.photos[0].filename
        return None

    @property
    def display_name(self):
        return f"{self.year} {self.make} {self.model}"

    def to_dict(self):
        return {
            "id": self.id,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "price": self.price,
            "mileage": self.mileage,
            "color": self.color,
            "description_en": self.description_en,
            "description_ar": self.description_ar,
            "video_url": self.video_url,
            "is_sold": self.is_sold,
            "photos": [p.filename for p in self.photos],
        }


class Photo(db.Model):
    __tablename__ = "photos"

    id = db.Column(db.Integer, primary_key=True)
    car_id = db.Column(db.Integer, db.ForeignKey("cars.id"), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
