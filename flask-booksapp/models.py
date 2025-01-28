from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import func
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(150), nullable=False)
    books = db.relationship("Book", backref="owner", lazy=True)
    borrowed_books = db.relationship("BookLoan", backref="borrower", lazy=True)
    book_requests = db.relationship("BookRequest", backref="requester", lazy=True)
    account_created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now()
    )

    def __init__(self, username):
        self.username = username

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    author = db.Column(db.String(150), nullable=False)
    isbn = db.Column(db.String(13))  # Added ISBN field
    description = db.Column(db.Text)  # Added description field
    condition = db.Column(db.String(50))  # Added condition field
    status = db.Column(
        db.String(50), default="available"
    )  # available, borrowed, reserved
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    added_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    loans = db.relationship("BookLoan", backref="book", lazy=True)
    requests = db.relationship("BookRequest", backref="book", lazy=True)

    def __repr__(self):
        return f"<Book {self.title}>"

    def is_available(self):
        return self.status == "available"


class BookRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(50), default="pending")  # pending, approved, rejected
    requested_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    response_at = db.Column(db.DateTime(timezone=True))
    response_message = db.Column(db.Text)

    def __repr__(self):
        return f"<Request for Book #{self.book_id} from User #{self.requester_id}>"

    def approve(self):
        self.status = "approved"
        self.response_at = datetime.utcnow()
        return BookLoan(book_id=self.book_id, borrower_id=self.requester_id)

    def reject(self, message=None):
        self.status = "rejected"
        self.response_at = datetime.utcnow()
        self.response_message = message


class BookLoan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    borrowed_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    returned_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(50), default="active")  # active, returned, overdue
    condition_on_return = db.Column(db.String(50))
    notes = db.Column(db.Text)

    def __repr__(self):
        return f"<Loan of Book #{self.book_id} to User #{self.borrower_id}>"

    def return_book(self, condition, notes=None):
        self.returned_at = datetime.utcnow()
        self.status = "returned"
        self.condition_on_return = condition
        self.notes = notes
        book = Book.query.get(self.book_id)
        book.status = "available"
