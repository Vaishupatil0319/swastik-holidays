from flask import Blueprint, render_template, request, session, redirect, url_for, flash, current_app, jsonify
from database.db import get_connection
from flask import send_file
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import io
from flask_mail import Message
from datetime import datetime
import random
import string
from datetime import date
from decimal import Decimal
# from pymysql.cursors import DictCursor

user_bp = Blueprint("user", __name__)

@user_bp.route("/")
def home():
    return render_template("user/index.html")

@user_bp.route("/about")
def about():
    return render_template("user/about.html")

@user_bp.route("/packages")
def packages():

    search = request.args.get(
        "search",
        ""
    ).strip()

    location_filter = request.args.get(
                    "location_filter",
                    ""
                    )


    duration_filter = request.args.get(
                    "duration_filter",
                    ""
                    )


    price_filter = request.args.get(
                    "price_filter",
                    ""
                    )
    
    sort_by=request.args.get(
                    "sort_by",
                    ""
                    )


    conn = get_connection()

    cursor = conn.cursor(dictionary=True)


    sql = """

    SELECT *
    FROM packages
    WHERE status='Available'

    """


    values=[]


    if search:

        sql += """

        AND(

        package_name LIKE %s

        OR

        location LIKE %s

        OR

        duration LIKE %s

        )

        """


        values.append(
            "%" + search + "%"
        )

        values.append(
            "%" + search + "%"
        )

        values.append(
            "%" + search + "%"
        )
    if location_filter:

        sql += """

        AND location=%s

        """

        values.append(
            location_filter
        )

    
    if duration_filter:

        sql += """

        AND duration=%s

        """

        values.append(
            duration_filter
        )

    if price_filter=="0-5000":

        sql += """

        AND price BETWEEN
        0 AND 5000

        """


    elif price_filter=="5001-10000":

        sql += """

        AND price BETWEEN
        5001 AND 10000

        """


    elif price_filter=="10001-20000":

        sql += """

        AND price BETWEEN
        10001 AND 20000

        """


    elif price_filter=="20000+":

        sql += """

        AND price >20000

        """
   

    # Default Sorting

    order_by="""

    ORDER BY id DESC

    """


# Newest Packages

    if sort_by=="newest":

        order_by="""

        ORDER BY id DESC

        """


# Oldest Packages

    elif sort_by=="oldest":

        order_by="""

        ORDER BY id ASC

        """


# Price Low to High

    elif sort_by=="price_low":

        order_by="""

        ORDER BY price ASC

        """


# Price High to Low

    elif sort_by=="price_high":

        order_by="""

        ORDER BY price DESC

        """


# Package Name A-Z

    elif sort_by=="name_asc":

        order_by="""

        ORDER BY package_name ASC

        """


# Package Name Z-A

    elif sort_by=="name_desc":

        order_by="""

        ORDER BY package_name DESC

        """


# Final Sorting Query

    sql += order_by


    cursor.execute(
        sql,
        tuple(values)
    )


    packages=cursor.fetchall()


    

    # Fetch All Locations

    cursor.execute("""

    SELECT DISTINCT location
    FROM packages
    WHERE status='Available'
    ORDER BY location ASC

    """)

    locations = cursor.fetchall()


# Fetch All Durations

    cursor.execute("""

    SELECT DISTINCT duration
    FROM packages
    WHERE status='Available'
    ORDER BY duration ASC

    """)

    durations = cursor.fetchall()
    cursor.close()

    conn.close()



    return render_template(

        "user/packages.html",

        packages=packages,

        search=search,

        location_filter=
        location_filter,

        duration_filter=
        duration_filter,

        price_filter=
        price_filter,

        sort_by=sort_by,

        locations=locations,

        durations=durations

    


    )

@user_bp.route("/package/<int:id>")
def package_details(id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get package details
    cursor.execute("""
        SELECT *
        FROM packages
        WHERE id=%s
    """, (id,))

    package = cursor.fetchone()

    if package is None:
        cursor.close()
        conn.close()
        return "Package Not Found"

    # Get reviews for this package
    cursor.execute("""
        SELECT
            customer_name,
            rating,
            review,
            review_date
        FROM reviews
        WHERE package_id=%s
        ORDER BY review_date DESC
    """, (id,))

    reviews = cursor.fetchall()

    # Get average rating and total reviews
    cursor.execute("""
        SELECT
            ROUND(AVG(rating), 1) AS average_rating,
            COUNT(*) AS total_reviews
        FROM reviews
        WHERE package_id=%s
    """, (id,))

    rating_data = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "user/package_details.html",
        package=package,
        reviews=reviews,
        rating_data=rating_data
    )


@user_bp.route("/book/<int:id>", methods=["GET", "POST"])
def book_package(id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM packages WHERE id=%s",
        (id,)
    )

    package = cursor.fetchone()
    

    if package is None:
        cursor.close()
        conn.close()
        return "Package Not Found"

    if request.method == "POST":

        travel_date = request.form["travel_date"]
        travelers = int(request.form["travelers"])
        booking_date = datetime.now()

        sql = """
        INSERT INTO bookings
        (customer_id, package_id, booking_date, travel_date, travelers, status)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        

        cursor.execute(sql, (
            session["customer_id"],
            id,
            booking_date,
            travel_date,
            travelers,
            "Pending"
        ))
        booking_id = cursor.lastrowid

        cursor.execute("""
        DELETE FROM wishlist
        WHERE customer_id=%s
        AND package_id=%s
        """, (
            session["customer_id"],
            id
        ))

    

        conn.commit()

        
        cursor.close()
        conn.close()

        return redirect(url_for("user.payment", booking_id=booking_id))

    cursor.close()
    conn.close()

    return render_template(
        "user/book_package.html",
        package=package
    )

@user_bp.route("/payment/<int:booking_id>")
def payment(booking_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            b.id,
            b.travel_date,
            b.travelers,
            p.package_name,
            p.price,
            (p.price * b.travelers) AS total_amount
        FROM bookings b
        JOIN packages p
            ON b.package_id = p.id
        WHERE b.id=%s
        AND b.customer_id=%s
    """, (
        booking_id,
        session["customer_id"]
    ))

    booking = cursor.fetchone()

    cursor.close()
    conn.close()

    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("user.my_bookings"))

    return render_template(
        "user/payment.html",
        booking=booking,
        discount=0,
        final_amount=booking["total_amount"]
    )

@user_bp.route("/apply_coupon", methods=["POST"])
def apply_coupon():

    if "customer_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login first."
        })

    coupon_code = request.form["coupon_code"].strip().upper()

    booking_id = request.form["booking_id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get booking amount
    cursor.execute("""
        SELECT
            p.price,
            b.travelers
        FROM bookings b
        JOIN packages p
            ON b.package_id=p.id
        WHERE b.id=%s
    """, (booking_id,))

    booking = cursor.fetchone()

    if not booking:

        cursor.close()
        conn.close()

        return jsonify({
            "success": False,
            "message": "Booking not found."
        })

    total_amount = booking["price"] * booking["travelers"]

    # Find coupon
    cursor.execute("""
        SELECT *
        FROM coupons
        WHERE coupon_code=%s
    """, (coupon_code,))

    coupon = cursor.fetchone()
    if not coupon:

        cursor.close()
        conn.close()

        return jsonify({

            "success": False,

            "message": "Invalid coupon code."

        })
    if coupon["status"] != "Active":

        cursor.close()
        conn.close()

        return jsonify({

            "success": False,

            "message": "Coupon is inactive."

        })
    if coupon["expiry_date"] < date.today():

        cursor.close()
        conn.close()

        return jsonify({

            "success": False,

            "message": "Coupon has expired."

        })
    if coupon["usage_limit"] > 0 and \
    coupon["used_count"] >= coupon["usage_limit"]:

        cursor.close()
        conn.close()

        return jsonify({

            "success": False,

            "message": "Coupon usage limit reached."

        })
    if total_amount < coupon["minimum_amount"]:

        cursor.close()
        conn.close()

        return jsonify({

            "success": False,

            "message":
            f"Minimum booking amount is ₹{coupon['minimum_amount']}."

        })
    if coupon["discount_type"] == "Percentage":

        discount = (
            total_amount *
            coupon["discount_value"]
        ) / 100

    else:

        discount = coupon["discount_value"]

    if discount > total_amount:

        discount = total_amount

    final_amount = total_amount - discount

    cursor.close()
    conn.close()

    return jsonify({

        "success": True,

        "message": "Coupon applied successfully.",

        "discount": float(discount),

        "final_amount": float(final_amount),

        "coupon_code": coupon["coupon_code"]

    })

@user_bp.route("/make_payment", methods=["POST"])
def make_payment():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    booking_id = request.form["booking_id"]
    payment_method = request.form["payment_method"]

    discount_amount = Decimal(
        request.form.get("discount", "0")
    )

    final_amount = Decimal(
        request.form.get("final_amount", "0")
    )

    coupon_code = request.form.get(
        "coupon_code",
        ""
    ).strip().upper()

    coupon_id = None

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # -----------------------------
    # Verify Booking
    # -----------------------------
    cursor.execute("""
        SELECT
            b.id,
            b.customer_id,
            p.price,
            b.travelers
        FROM bookings b
        JOIN packages p
            ON b.package_id = p.id
        WHERE b.id=%s
        AND b.customer_id=%s
    """, (
        booking_id,
        session["customer_id"]
    ))

    booking = cursor.fetchone()

    if not booking:

        cursor.close()
        conn.close()

        flash("Invalid Booking.", "danger")
        return redirect(url_for("user.my_bookings"))

    # -----------------------------
    # Calculate Amount
    # -----------------------------
    original_amount = (
        booking["price"] *
        booking["travelers"]
    )

    if final_amount <= 0:
        final_amount = original_amount

    discount_amount = (
        original_amount -
        final_amount
    )

    transaction_id = "TXN" + ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=10
        )
    )

    # -----------------------------
    # Check Coupon (Only if applied)
    # -----------------------------
    if coupon_code:

        cursor.execute("""
            SELECT id
            FROM coupons
            WHERE coupon_code=%s
        """, (coupon_code,))

        coupon = cursor.fetchone()

        if coupon:
            coupon_id = coupon["id"]

    # -----------------------------
    # Insert Payment (Always)
    # -----------------------------
    cursor.execute("""
        INSERT INTO payments
        (
            booking_id,
            transaction_id,
            original_amount,
            discount_amount,
            final_amount,
            coupon_id,
            coupon_code,
            amount,
            payment_method,
            payment_gateway,
            payment_status
        )
        VALUES
        (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
    """, (

        booking_id,
        transaction_id,
        original_amount,
        discount_amount,
        final_amount,
        coupon_id,
        coupon_code,
        final_amount,
        payment_method,
        "Manual",
        "Paid"

    ))

    # -----------------------------
    # Confirm Booking
    # -----------------------------
    cursor.execute("""
        UPDATE bookings
        SET status='Confirmed'
        WHERE id=%s
    """, (booking_id,))

    # -----------------------------
    # Update Coupon Usage
    # -----------------------------
    if coupon_code:

        cursor.execute("""
            UPDATE coupons
            SET used_count = used_count + 1
            WHERE coupon_code=%s
        """, (coupon_code,))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(
        url_for(
            "user.payment_success",
            booking_id=booking_id
        )
    )

@user_bp.route("/payment_success/<int:booking_id>")
def payment_success(booking_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            b.id,
            b.travel_date,
            b.travelers,
            b.status,
            c.name,
            c.email,
            p.package_name,
            p.price,
            pay.id AS payment_id,
            pay.transaction_id,
            pay.payment_method,
            pay.payment_status,
            pay.payment_date
        FROM bookings b

        JOIN customers c
            ON b.customer_id=c.id

        JOIN packages p
            ON b.package_id=p.id

        JOIN payments pay
            ON b.id=pay.booking_id

        WHERE b.id=%s
        AND b.customer_id=%s

        ORDER BY pay.id DESC
        LIMIT 1
    """, (
        booking_id,
        session["customer_id"]
    ))

    booking = cursor.fetchone()

    if not booking:

        cursor.close()
        conn.close()

        flash("Payment not found.", "danger")

        return redirect(url_for("user.my_bookings"))

    total_amount = booking["price"] * booking["travelers"]
    msg = Message(
        subject="Swastik Holidays - Payment Successful",
        recipients=[booking["email"]]
    )

    msg.body = f"""
    Dear {booking['name']},

Greetings from Swastik Holidays!

We are delighted to inform you that your payment has been received successfully and your tour booking has been confirmed.

--------------------------------------------------

BOOKING CONFIRMATION

Booking ID       : {booking['id']}

Package Name     : {booking['package_name']}

Travel Date      : {booking['travel_date']}

Number of Travelers : {booking['travelers']}

--------------------------------------------------

PAYMENT DETAILS

Transaction ID   : {booking['transaction_id']}

Payment Method   : {booking['payment_method']}

Amount Paid      : ₹{total_amount}

Payment Status   : {booking['payment_status']}

Payment Date     : {booking['payment_date']}

--------------------------------------------------

Your booking has been successfully reserved in our system.

If you need any assistance before your journey, our team is always happy to help.

Thank you for choosing Swastik Holidays.

We wish you a safe, memorable, and wonderful journey.

Warm Regards,

Swastik Holidays
Email: swastiholidays0919@gmail.com
"""

    current_app.extensions["mail"].send(msg)

    

    cursor.close()
    conn.close()
    

    return render_template(
        "user/payment_success.html",
        booking=booking,
        total_amount=total_amount
    )

    

@user_bp.route("/booking_success")
def booking_success():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    return render_template("user/booking_success.html")

@user_bp.route("/my_bookings")
def my_bookings():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        b.id,
        p.package_name,
        p.location,
        p.duration,
        p.price,
        b.travel_date,
        b.travelers,
        b.booking_date,
        b.status
    FROM bookings b
    INNER JOIN packages p
        ON b.package_id = p.id
    WHERE b.customer_id = %s
    ORDER BY b.booking_date DESC
    """

    cursor.execute(sql, (session["customer_id"],))
    bookings = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "user/my_bookings.html",
        bookings=bookings
    )

@user_bp.route("/booking_details/<int:id>")
def booking_details(id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    sql = """
    SELECT
        b.id,
        b.travel_date,
        b.travelers,
        b.booking_date,
        b.status,
        p.package_name,
        p.location,
        p.duration,
        p.price,
        p.description,
        p.image
    FROM bookings b
    INNER JOIN packages p
        ON b.package_id = p.id
    WHERE b.id=%s
    AND b.customer_id=%s
    """

    cursor.execute(sql, (id, session["customer_id"]))

    booking = cursor.fetchone()

    cursor.close()
    conn.close()

    if booking is None:
        return "Booking not found."

    return render_template(
        "user/booking_details.html",
        booking=booking
    )


@user_bp.route("/profile", methods=["GET", "POST"])
def profile():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        mobile = request.form["mobile"]
        address = request.form["address"]

        cursor.execute("""
            UPDATE customers
            SET
                name=%s,
                email=%s,
                mobile=%s,
                address=%s
            WHERE id=%s
        """, (
            name,
            email,
            mobile,
            address,
            session["customer_id"]
        ))

        conn.commit()

    cursor.execute(
        "SELECT * FROM customers WHERE id=%s",
        (session["customer_id"],)
    )

    customer = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "user/profile.html",
        customer=customer
    )

@user_bp.route("/change_password", methods=["GET", "POST"])
def change_password():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT password FROM customers WHERE id=%s",
            (session["customer_id"],)
        )

        customer = cursor.fetchone()

        if customer["password"] != current_password:
            cursor.close()
            conn.close()
            return "Current password is incorrect."

        if new_password != confirm_password:
            cursor.close()
            conn.close()
            return "New passwords do not match."

        cursor.execute(
            """
            UPDATE customers
            SET password=%s
            WHERE id=%s
            """,
            (new_password, session["customer_id"])
        )

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("user.profile"))

    return render_template("user/change_password.html")

@user_bp.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        name = request.form["name"].strip()

        email = request.form["email"].strip()

        subject = request.form["subject"].strip()

        message = request.form["message"].strip()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""

            INSERT INTO contact_messages
            (

                name,

                email,

                subject,

                message

            )

            VALUES
            (

                %s,

                %s,

                %s,

                %s

            )

        """, (

            name,

            email,

            subject,

            message

        ))

        conn.commit()

        cursor.close()
        conn.close()

        flash(

            "Your message has been sent successfully. We will contact you soon.",

            "success"

        )

        return redirect(url_for("user.contact"))

    return render_template("user/index.html")

@user_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM customers WHERE email=%s AND password=%s",
            (email, password)
        )

        customer = cursor.fetchone()

        cursor.close()
        conn.close()

        if customer:

            session["customer_id"] = customer["id"]
            session["customer_name"] = customer["name"]

            return redirect(url_for("user.dashboard"))

        return "Invalid Email or Password"

    return render_template("user/login.html")

@user_bp.route("/dashboard")
def dashboard():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))
    
# ============================
# UNREAD NOTIFICATIONS COUNT
# ============================

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) AS unread_count
        FROM notifications
        WHERE user_type='Customer'
        AND status='Unread'
    """)

    result = cursor.fetchone()
    unread_count = result[0]

    # ================================
# Latest Notifications
# ================================

    cursor.execute("""
    SELECT *
    FROM notifications
    WHERE user_type='Customer'
    ORDER BY created_at DESC
    LIMIT 5
    """)

    latest_notifications = cursor.fetchall()

    cursor.close()
    conn.close()

    

    return render_template(
        "user/dashboard.html",
        unread_count=unread_count,
        customer_name=session["customer_name"],
        latest_notifications=latest_notifications

    )

@user_bp.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("user.login"))

@user_bp.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        try:
            full_name = request.form["full_name"]
            email = request.form["email"]
            mobile = request.form["mobile"]
            address = request.form["address"]
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]

            # Check password match
            if password != confirm_password:
                return "Passwords do not match"

            conn = get_connection()
            cursor = conn.cursor()

            # Check duplicate email
            cursor.execute(
                "SELECT * FROM customers WHERE email=%s",
                (email,)
            )

            user = cursor.fetchone()

            if user:
                cursor.close()
                conn.close()
                return "Email already registered."

            # Insert new customer
            sql = """
            INSERT INTO customers
            (name, email, mobile, address, password)
            VALUES (%s, %s, %s, %s, %s)
            """

            values = (
                full_name,
                email,
                mobile,
                address,
                password
            )

            cursor.execute(sql, values)
            conn.commit()

            cursor.close()
            conn.close()

            return render_template("user/registration_success.html")

        except Exception as e:
            return f"Database Error : {e}"

    return render_template("user/register.html")

@user_bp.route("/cancel_booking/<int:booking_id>")
def cancel_booking(booking_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Verify the booking belongs to the logged-in customer
    cursor.execute("""
        SELECT id, status
        FROM bookings
        WHERE id=%s AND customer_id=%s
    """, (booking_id, session["customer_id"]))

    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        conn.close()
        flash("Booking not found.", "error")
        return redirect(url_for("user.my_bookings"))

    if booking["status"] == "Pending":
        cursor.execute("""
            UPDATE bookings
            SET status='Cancelled'
            WHERE id=%s
        """, (booking_id,))
        conn.commit()
        flash("Booking cancelled successfully.", "success")
    else:
        flash("Only pending bookings can be cancelled.", "warning")

    cursor.close()
    conn.close()

    return redirect(url_for("user.my_bookings"))

@user_bp.route("/download_receipt/<int:booking_id>")
def download_receipt(booking_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            b.id,
            b.travel_date,
            b.travelers,
            b.booking_date,
            b.status,
            c.name,
            p.package_name,
            p.price
        FROM bookings b
        JOIN customers c
            ON b.customer_id = c.id
        JOIN packages p
            ON b.package_id = p.id
        WHERE b.id=%s
        AND b.customer_id=%s
    """, (booking_id, session["customer_id"]))

    booking = cursor.fetchone()

    cursor.close()
    conn.close()

    if not booking:
        return "Booking not found."

    total_amount = booking["price"] * booking["travelers"]

    buffer = io.BytesIO()

    pdf = canvas.Canvas(buffer)

    pdf.setTitle("Booking Receipt")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(180, 800, "SWASTIK HOLIDAYS")

    pdf.setFont("Helvetica", 12)

    y = 760

    details = [
        f"Booking ID : {booking['id']}",
        f"Customer : {booking['name']}",
        f"Package : {booking['package_name']}",
        f"Travel Date : {booking['travel_date']}",
        f"Travelers : {booking['travelers']}",
        f"Price : Rs. {booking['price']}",
        f"Total Amount : Rs. {total_amount}",
        f"Booking Date : {booking['booking_date']}",
        f"Status : {booking['status']}"
    ]

    for item in details:
        pdf.drawString(80, y, item)
        y -= 30

    pdf.drawString(80, y - 30, "Thank you for choosing Swastik Holidays!")

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Booking_{booking_id}.pdf",
        mimetype="application/pdf"
    )

@user_bp.route("/add_review/<int:booking_id>", methods=["GET", "POST"])
def add_review(booking_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Get booking details
    cursor.execute("""
        SELECT
            b.id,
            b.package_id,
            p.package_name
        FROM bookings b
        JOIN packages p
            ON b.package_id = p.id
        WHERE b.id=%s
        AND b.customer_id=%s
    """, (booking_id, session["customer_id"]))

    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        conn.close()
        flash("Booking not found.", "danger")
        return redirect(url_for("user.my_bookings"))

    # Check if review already exists
    cursor.execute("""
        SELECT id
        FROM reviews
        WHERE booking_id=%s
    """, (booking_id,))

    existing_review = cursor.fetchone()

    if existing_review:
        cursor.close()
        conn.close()
        flash("You have already submitted a review for this booking.", "warning")
        return redirect(url_for("user.booking_details", id=booking_id))

    if request.method == "POST":

        rating = request.form["rating"]
        review = request.form["review"]

        # Get customer name
        cursor.execute("""
            SELECT name
            FROM customers
            WHERE id=%s
        """, (session["customer_id"],))

        customer = cursor.fetchone()

        # Insert review
        cursor.execute("""
            INSERT INTO reviews
            (
                customer_name,
                customer_id,
                package_id,
                booking_id,
                rating,
                review,
                review_status
            )
            VALUES
            (%s,%s,%s,%s,%s,%s,'Pending')
        """, (
            customer["name"],
            session["customer_id"],
            booking["package_id"],
            booking_id,
            rating,
            review
        ))

        conn.commit()

        cursor.close()
        conn.close()

        flash("Thank you! Your review has been submitted successfully.", "success")

        return redirect(url_for("user.booking_details", id=booking_id))

    cursor.close()
    conn.close()

    return render_template(
        "user/add_review.html",
        booking=booking
    )

@user_bp.route("/my_reviews")
def my_reviews():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    search = request.args.get("search", "").strip()
    rating = request.args.get("rating", "").strip()
    status = request.args.get("status", "").strip()

    query = """
    SELECT
        r.id,
        r.rating,
        r.review,
        r.review_date,
        r.review_status,
        r.admin_reply,
        p.package_name
    FROM reviews r
    JOIN packages p
    ON r.package_id = p.id
    WHERE r.customer_id=%s
    """

    values = [session["customer_id"]]

    if search:

        query += " AND p.package_name LIKE %s"

        values.append(f"%{search}%")

    if rating:

        query += " AND r.rating=%s"

        values.append(rating)

    if status:

        query += " AND r.review_status=%s"

        values.append(status)

    query += " ORDER BY r.review_date DESC"

    cursor.execute(query, values)

    reviews = cursor.fetchall()

    cursor.execute("""
    SELECT

        COUNT(*) AS total_reviews,

        ROUND(AVG(rating),1) AS average_rating,

        SUM(CASE
            WHEN review_status='Approved'
            THEN 1 ELSE 0 END) AS approved_reviews,

        SUM(CASE
            WHEN review_status='Pending'
            THEN 1 ELSE 0 END) AS pending_reviews

    FROM reviews

    WHERE customer_id=%s
    """, (session["customer_id"],))

    stats = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "user/my_reviews.html",
        reviews=reviews,
        stats=stats,search=search,
        rating=rating,
        status=status
    )

@user_bp.route("/edit_review/<int:review_id>", methods=["GET", "POST"])
def edit_review(review_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT *
        FROM reviews
        WHERE id=%s AND customer_id=%s
    """, (review_id, session["customer_id"]))

    review = cursor.fetchone()

    if not review:
        flash("Review not found.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("user.my_reviews"))

    if request.method == "POST":

        rating = request.form["rating"]
        review_text = request.form["review"]

        cursor.execute("""
            UPDATE reviews
            SET
                rating=%s,
                review=%s,
                review_status='Pending',
                admin_reply=NULL
            WHERE id=%s
        """, (rating, review_text, review_id))

        conn.commit()

        cursor.close()
        conn.close()

        flash(
            "Review updated successfully. Your review is pending admin approval.",
            "success"
        )
        return redirect(url_for("user.my_reviews"))

    cursor.close()
    conn.close()

    return render_template(
        "user/edit_review.html",
        review=review
    )

@user_bp.route("/delete_review/<int:review_id>")
def delete_review(review_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM reviews
        WHERE id=%s
        AND customer_id=%s
    """, (review_id, session["customer_id"]))

    conn.commit()

    cursor.close()
    conn.close()

    flash("Review deleted successfully.", "success")

    return redirect(url_for("user.my_reviews"))

@user_bp.route("/add_to_wishlist/<int:package_id>")
def add_to_wishlist(package_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    customer_id = session["customer_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM wishlist
        WHERE customer_id=%s
        AND package_id=%s
    """, (customer_id, package_id))

    exists = cursor.fetchone()

    if exists:
        flash("Package is already in your wishlist.", "warning")
    else:
        cursor.execute("""
            INSERT INTO wishlist(customer_id, package_id)
            VALUES(%s,%s)
        """, (customer_id, package_id))

        conn.commit()
        flash("Package added to wishlist successfully.", "success")

    cursor.close()
    conn.close()

    return redirect(url_for("user.package_details", id=package_id))

@user_bp.route("/wishlist")
def wishlist():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    customer_id = session["customer_id"]

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            w.id AS wishlist_id,
            p.id AS package_id,
            p.package_name,
            p.price,
            p.duration,
            p.description,
            w.added_date
        FROM wishlist w
        INNER JOIN packages p
            ON w.package_id = p.id
        WHERE w.customer_id = %s
        ORDER BY w.added_date DESC
    """, (customer_id,))

    wishlist = cursor.fetchall()
    print(wishlist)

    cursor.close()
    conn.close()

    return render_template(
        "user/wishlist.html",
        wishlist=wishlist
    )

@user_bp.route("/remove_from_wishlist/<int:wishlist_id>")
def remove_from_wishlist(wishlist_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    customer_id = session["customer_id"]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM wishlist
        WHERE id=%s
        AND customer_id=%s
    """, (wishlist_id, customer_id))

    item = cursor.fetchone()

    if item:

        cursor.execute("""
            DELETE FROM wishlist
            WHERE id=%s
        """, (wishlist_id,))

        conn.commit()

        flash("Package removed from wishlist successfully.", "success")

    else:

        flash("Wishlist item not found.", "warning")

    cursor.close()
    conn.close()

    return redirect(url_for("user.wishlist"))

@user_bp.route("/notifications")
def notifications():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM notifications
        WHERE user_type='Customer'
        ORDER BY created_at DESC
    """)

    notifications = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*) AS unread
        FROM notifications
        WHERE user_type='Customer'
        AND status='Unread'
    """)

    result = cursor.fetchone()
    unread = result[0]

    cursor.close()
    conn.close()

    return render_template(
        "user/notifications.html",
        notifications=notifications,
        unread=unread
    )

@user_bp.route("/notification/read/<int:id>")
def read_notification(id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE notifications
        SET status='Read'
        WHERE id=%s
        AND user_type='Customer'
    """, (id,))

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("user.notifications"))

@user_bp.route("/notification/delete/<int:id>")
def delete_notification(id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM notifications
        WHERE id=%s
        AND user_type='Customer'
    """, (id,))

    conn.commit()

    cursor.close()
    conn.close()

    flash("Notification deleted successfully.", "success")

    return redirect(url_for("user.notifications"))

@user_bp.route("/notifications/read_all")
def read_all_notifications():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE notifications
        SET status='Read'
        WHERE user_type='Customer'
        AND status='Unread'
    """)

    conn.commit()

    cursor.close()
    conn.close()

    flash("All notifications marked as read.", "success")

    return redirect(url_for("user.notifications"))

@user_bp.route("/notifications/delete_all")
def delete_all_notifications():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM notifications
        WHERE user_type='Customer'
    """)

    conn.commit()

    cursor.close()
    conn.close()

    flash("All notifications deleted successfully.", "success")

    return redirect(url_for("user.notifications"))

@user_bp.route("/notification/<int:id>")
def notification_details(id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM notifications
        WHERE id=%s
        AND user_type='Customer'
    """, (id,))

    notification = cursor.fetchone()

    if notification:

        cursor.execute("""
            UPDATE notifications
            SET status='Read'
            WHERE id=%s
        """, (id,))

        conn.commit()

    cursor.close()
    conn.close()

    if notification is None:
        return "Notification Not Found"

    return render_template(
        "user/notification_details.html",
        notification=notification
    )

@user_bp.route("/my_payments")
def my_payments():

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT

            p.id,

            p.transaction_id,

            p.original_amount,

            p.discount_amount,

            p.final_amount,

            p.coupon_code,

            p.payment_method,

            p.payment_gateway,

            p.payment_status,

            p.payment_date,

            b.travel_date,

            b.travelers,

            pk.package_name

        FROM payments p

        INNER JOIN bookings b
            ON p.booking_id=b.id

        INNER JOIN packages pk
            ON b.package_id=pk.id

        WHERE b.customer_id=%s

        ORDER BY p.payment_date DESC

    """,(session["customer_id"],))

    payments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "user/my_payments.html",
        payments=payments
    )

@user_bp.route("/payment_details/<int:payment_id>")
def payment_details(payment_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""

        SELECT

        p.id,
        p.transaction_id,

        p.original_amount,
        p.discount_amount,
        p.final_amount,

        p.coupon_code,

        p.payment_method,
        p.payment_gateway,
        p.payment_status,
        p.payment_date,

        p.refund_status,
        p.remarks,

        b.id AS booking_id,
        b.booking_date,
        b.travel_date,
        b.travelers,

        pk.package_name,
        pk.price

            FROM payments p

        INNER JOIN bookings b
            ON p.booking_id=b.id

        INNER JOIN packages pk
            ON b.package_id=pk.id

        WHERE

            p.id=%s

            AND

            b.customer_id=%s

    """,(payment_id,session["customer_id"]))

    payment = cursor.fetchone()
    print(payment)

    cursor.close()
    conn.close()

    if not payment:

        flash("Payment not found.","danger")

        return redirect(url_for("user.my_payments"))

    return render_template(

        "user/payment_details.html",

        payment=payment

    )

@user_bp.route("/download_payment_receipt/<int:payment_id>")
def download_payment_receipt(payment_id):

    if "customer_id" not in session:
        return redirect(url_for("user.login"))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT

            p.id,
            p.transaction_id,
            p.original_amount,
            p.discount_amount,
            p.final_amount,
            p.coupon_code,
            p.payment_method,
            p.payment_gateway,
            p.payment_status,
            p.payment_date,

            b.id AS booking_id,
            b.travel_date,
            b.travelers,

            c.name,

            pk.package_name

        FROM payments p

        INNER JOIN bookings b
            ON p.booking_id=b.id

        INNER JOIN customers c
            ON b.customer_id=c.id

        INNER JOIN packages pk
            ON b.package_id=pk.id

        WHERE
            p.id=%s
            AND b.customer_id=%s
    """, (
        payment_id,
        session["customer_id"]
    ))

    payment = cursor.fetchone()

    cursor.close()
    conn.close()

    if not payment:

        flash("Receipt not found.", "danger")

        return redirect(url_for("user.my_payments"))
    buffer = io.BytesIO()

    pdf = canvas.Canvas(buffer)

    pdf.setTitle("Payment Receipt")

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(170, 810, "SWASTIK HOLIDAYS")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(190, 785, "PAYMENT RECEIPT")

    pdf.setFont("Helvetica", 11)

    y = 745

    details = [

        f"Receipt No : PAY-{payment['id']}",

        f"Transaction ID : {payment['transaction_id']}",

        f"Booking ID : {payment['booking_id']}",

        f"Customer Name : {payment['name']}",

        f"Package : {payment['package_name']}",

        f"Travel Date : {payment['travel_date']}",

        f"Travelers : {payment['travelers']}",

        f"Original Amount : ₹{payment['original_amount']}",

        f"Discount Amount : ₹{payment['discount_amount']}",

        f"Coupon Code : {payment['coupon_code'] or 'Not Applied'}",

        f"Final Amount Paid : ₹{payment['final_amount']}",

        f"Payment Method : {payment['payment_method']}",

        f"Payment Gateway : {payment['payment_gateway']}",

        f"Payment Status : {payment['payment_status']}",

        f"Payment Date : {payment['payment_date']}"
    ]

    for item in details:

        pdf.drawString(60, y, item)

        y -= 28

    pdf.line(50, y, 550, y)

    y -= 35

    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawString(
        60,
        y,
        "Thank you for choosing Swastik Holidays."
    )

    y -= 20

    pdf.setFont("Helvetica", 11)

    pdf.drawString(
        60,
        y,
        "We wish you a safe and happy journey!"
    )

    pdf.save()

    buffer.seek(0)

    return send_file(

        buffer,

        as_attachment=True,

        download_name=f"Payment_Receipt_{payment['id']}.pdf",

        mimetype="application/pdf"

    )

@user_bp.route("/gallery")
def gallery():

    conn = get_connection()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""

        SELECT

            *

        FROM gallery

        ORDER BY id DESC

    """)

    gallery = cursor.fetchall()

    cursor.close()

    conn.close()

    return render_template(

        "user/gallery.html",

        gallery=gallery

    )

@user_bp.route("/travel_blogs")
def travel_blogs():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""

        SELECT *

        FROM blogs

        ORDER BY created_at DESC

    """)

    blogs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "user/travel_blogs.html",

        blogs=blogs

    )

@user_bp.route("/blog_details/<int:blog_id>")
def blog_details(blog_id):

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""

        SELECT *

        FROM blogs

        WHERE id=%s

    """,(blog_id,))

    blog = cursor.fetchone()

    cursor.close()
    conn.close()

    if not blog:

        flash(
            "Blog not found.",
            "danger"
        )

        return redirect(
            url_for("user.travel_blogs")
        )

    return render_template(

        "user/blog_details.html",

        blog=blog

    )

@user_bp.route("/faq")
def faq():

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""

        SELECT *

        FROM faq

        WHERE status='Active'

        ORDER BY display_order ASC

    """)

    faqs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "user/faq.html",

        faqs=faqs

    )

@user_bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"].strip()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""

            SELECT *

            FROM customers

            WHERE email=%s

        """, (email,))

        customer = cursor.fetchone()

        cursor.close()
        conn.close()

        if not customer:

            flash(
                "Email is not registered.",
                "danger"
            )

            return redirect(
                url_for("user.forgot_password")
            )

        otp = str(random.randint(100000, 999999))

        session["reset_email"] = email

        session["reset_otp"] = otp

        try:

            msg = Message(

                subject="Swastik Holidays - Password Reset OTP",

                recipients=[email]

            )

            msg.body = f"""
        Hello,

        Your OTP for resetting your Swastik Holidays account password is:

        {otp}

        This OTP is valid only for your current password reset request.

        If you did not request a password reset, please ignore this email.

        Thank you,
        Swastik Holidays
        """

            current_app.extensions["mail"].send(msg)

            flash(

                "OTP has been sent to your registered email.",

                "success"

            )

            return redirect(
                url_for("user.verify_otp")
            )

        except Exception as e:

            print(e)

            flash(

                "Unable to send OTP email. Please try again.",

                "danger"

            )

            return redirect(
                url_for("user.forgot_password")
            )

    return render_template(
        "user/forgot_password.html"
    )

@user_bp.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():

    if "reset_otp" not in session:

        flash("OTP session expired. Please try again.", "danger")

        return redirect(url_for("user.forgot_password"))

    if request.method == "POST":

        entered_otp = request.form["otp"].strip()

        if entered_otp == session["reset_otp"]:

            flash("OTP verified successfully.", "success")

            return redirect(url_for("user.reset_password"))

        else:

            flash("Invalid OTP.", "danger")

    return render_template("user/verify_otp.html")

@user_bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():

    if "reset_email" not in session:

        flash(
            "Password reset session expired.",
            "danger"
        )

        return redirect(
            url_for("user.forgot_password")
        )

    if request.method == "POST":

        new_password = request.form["new_password"]

        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("user.reset_password")
            )

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""

            UPDATE customers

            SET password=%s

            WHERE email=%s

        """, (

            new_password,

            session["reset_email"]

        ))

        conn.commit()

        cursor.close()
        conn.close()

        session.pop("reset_email", None)
        session.pop("reset_otp", None)

        flash(

            "Password changed successfully. Please login.",

            "success"

        )

        return redirect(
            url_for("user.login")
        )

    return render_template(
        "user/reset_password.html"
    )