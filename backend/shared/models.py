from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    products = db.relationship("Product", back_populates="category")


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)  # intentionally nullable — causes NoneType bug
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=100)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.relationship("Category", back_populates="products")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "stock": self.stock,
            "image_url": self.image_url,
            "category_id": self.category_id,
        }

    def to_dict_with_category(self):
        # BUG: this triggers a lazy load — used in N+1 context
        return {
            **self.to_dict(),
            "category": self.category.name if self.category else "Uncategorized",
            # BUG: description.upper() will throw AttributeError if description is None
            "description_preview": self.description.upper()[:80],
        }


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    orders = db.relationship("Order", back_populates="user")

    def to_dict(self):
        return {"id": self.id, "email": self.email, "name": self.name}


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    total = db.Column(db.Float)
    status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "total": self.total,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "items": [i.to_dict() for i in self.items],
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product")

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_name": self.product.name if self.product else "Unknown",
            "quantity": self.quantity,
            "price": self.price,
        }
