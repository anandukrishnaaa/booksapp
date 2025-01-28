from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    session,
    flash,
    request,
    jsonify,
)

from models import db, User, Book, BookLoan, BookRequest
from forms import BookForm, RegistrationForm, LoginForm
import os
from dotenv import load_dotenv
from functools import wraps


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            # Store the next page to redirect back to it after login
            session["next"] = request.url
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE")


db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()  # This creates all tables defined in your models


@app.route("/books/add", methods=["GET", "POST"])
@login_required
def add_book():
    form = BookForm()
    if form.validate_on_submit():
        book = Book(
            title=form.title.data,
            author=form.author.data,
            isbn=form.isbn.data,
            description=form.description.data,
            condition=form.condition.data,
            user_id=session["user_id"],
        )
        db.session.add(book)
        db.session.commit()
        flash("Book added successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template("book_form.html", form=form, title="Add Book")


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
def edit_book(book_id):
    book = Book.query.get_or_404(book_id)
    if book.user_id != session["user_id"]:
        flash("You can only edit your own books.", "error")
        return redirect(url_for("dashboard"))

    form = BookForm(obj=book)
    if form.validate_on_submit():
        form.populate_obj(book)
        db.session.commit()
        flash("Book updated successfully!", "success")
        return redirect(url_for("dashboard"))
    return render_template("book_form.html", form=form, title="Edit Book")


@app.route("/books/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id):
    book = Book.query.get_or_404(book_id)
    if book.user_id != session["user_id"]:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    db.session.delete(book)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/books/<int:book_id>/request", methods=["POST"])
@login_required
def request_book(book_id):
    book = Book.query.get_or_404(book_id)
    if book.user_id == session["user_id"]:
        flash("You can't request your own book!", "error")
        return redirect(url_for("dashboard"))

    if book.status != "available":
        flash("This book is not available for borrowing.", "error")
        return redirect(url_for("dashboard"))

    request = BookRequest(book_id=book_id, requester_id=session["user_id"])
    db.session.add(request)
    db.session.commit()
    flash("Book requested successfully!", "success")
    return redirect(url_for("dashboard"))


@app.route("/requests/<int:request_id>/<action>", methods=["POST"])
@login_required
def handle_request(request_id, action):
    request = BookRequest.query.get_or_404(request_id)
    book = request.book

    if book.user_id != session["user_id"]:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    if action == "approve":
        loan = request.approve()
        book.status = "borrowed"
        db.session.add(loan)
    elif action == "reject":
        request.reject(request.form.get("message"))

    db.session.commit()
    return jsonify({"success": True})


@app.route("/loans/<int:loan_id>/return", methods=["POST"])
@login_required
def return_book(loan_id):
    loan = BookLoan.query.get_or_404(loan_id)
    if loan.borrower_id != session["user_id"]:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    condition = request.form.get("condition")
    notes = request.form.get("notes")
    loan.return_book(condition, notes)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Logged in successfully!", "success")

            # Redirect to the original page or dashboard
            next_page = session.get("next", url_for("dashboard"))
            session.pop("next", None)  # Remove 'next' from session after use
            return redirect(next_page)
        else:
            flash("Invalid username or password.", "error")
            return redirect(url_for("login"))

    return render_template("login.html", form=form)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        # Check if the username already exists in the database
        existing_user = User.query.filter_by(username=form.username.data).first()

        if existing_user:
            flash("Username already taken. Please choose a different one.", "error")
            return redirect(url_for("register"))

        # If username is available, create the new user
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash("Account created! Login with username and password.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form=form)


@app.route("/dashboard")
@login_required
def dashboard():
    user = db.session.get(User, session["user_id"])

    # Get user's books
    owned_books = Book.query.filter_by(user_id=user.id).all()

    # Get books borrowed by user
    borrowed_books = (
        BookLoan.query.filter_by(borrower_id=user.id, status="active").join(Book).all()
    )

    # Get pending requests for user's books
    pending_requests = (
        BookRequest.query.join(Book)
        .filter(Book.user_id == user.id, BookRequest.status == "pending")
        .all()
    )

    # Get user's pending requests
    my_requests = BookRequest.query.filter_by(
        requester_id=user.id, status="pending"
    ).all()

    return render_template(
        "dashboard.html",
        user=user,
        owned_books=owned_books,
        borrowed_books=borrowed_books,
        pending_requests=pending_requests,
        my_requests=my_requests,
    )


@app.route("/browse", methods=["GET"])
@login_required
def browse_books():
    user = db.session.get(User, session["user_id"])  # Fetch the logged-in user
    search = request.args.get("search", "").strip()  # Get the search term

    # Query only books that are available and not owned by the user
    query = Book.query.filter(
        Book.user_id != user.id,  # Exclude user's own books
        Book.status == "available",  # Only show available books
    )

    # Apply search filter if provided
    if search:
        query = query.filter(
            db.or_(Book.title.ilike(f"%{search}%"), Book.author.ilike(f"%{search}%"))
        )

    # Fetch all books based on the query
    books = query.order_by(Book.added_at.desc()).all()

    return render_template("browse_books.html", books=books, search=search)


@app.route("/books/<int:book_id>")
@login_required
def view_book(book_id):
    book = Book.query.get_or_404(book_id)
    is_owner = book.user_id == session["user_id"]

    # Check if user has already requested this book
    existing_request = BookRequest.query.filter_by(
        book_id=book_id, requester_id=session["user_id"], status="pending"
    ).first()

    return render_template(
        "view_book.html",
        book=book,
        is_owner=is_owner,
        existing_request=existing_request,
    )


if __name__ == "__main__":
    app.run(debug=True)
