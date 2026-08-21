from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    current_app,
    send_file
)

from database.db import get_connection
from utils.notifications import add_notification
from datetime import datetime
import math
import csv
from io import StringIO
import os
from werkzeug.utils import secure_filename

from openpyxl import Workbook

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
import io


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = get_connection()
        cursor = connection.cursor()

        sql = """
        SELECT * FROM admin
        WHERE email=%s AND password=%s
        """

        cursor.execute(sql, (email, password))

        admin = cursor.fetchone()

        cursor.close()
        connection.close()

        if admin:

            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["name"]
            session["admin_email"] = admin["email"]

            return redirect(url_for("admin.dashboard"))

        else:

            return render_template(
                "admin/login.html",
                error="Invalid Email or Password"
            )

    return render_template("admin/login.html")


@admin_bp.route("/admin/dashboard")
def dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    connection = get_connection()
    cursor = connection.cursor()

    # Total Customers
    cursor.execute("SELECT COUNT(*) AS total FROM customers")
    total_customers = cursor.fetchone()["total"]

    # Total Packages
    cursor.execute("SELECT COUNT(*) AS total FROM packages")
    total_packages = cursor.fetchone()["total"]

    # Total Bookings
    cursor.execute("SELECT COUNT(*) AS total FROM bookings")
    total_bookings = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS pending FROM bookings WHERE status='Pending'")
    pending_bookings = cursor.fetchone()["pending"]

    cursor.execute("SELECT COUNT(*) AS confirmed FROM bookings WHERE status='Confirmed'")
    confirmed_bookings = cursor.fetchone()["confirmed"]

    cursor.execute("SELECT COUNT(*) AS cancelled FROM bookings WHERE status='Cancelled'")
    cancelled_bookings = cursor.fetchone()["cancelled"]
    # Total Partners
    cursor.execute("SELECT COUNT(*) AS total FROM partners")
    total_partners = cursor.fetchone()["total"]

    # Total Hotels
    cursor.execute("SELECT COUNT(*) AS total FROM hotels")
    total_hotels = cursor.fetchone()["total"]

    # Total Buses
    cursor.execute("SELECT COUNT(*) AS total FROM buses")
    total_buses = cursor.fetchone()["total"]

    # Total Taxis
    cursor.execute("SELECT COUNT(*) AS total FROM taxis")
    total_taxis = cursor.fetchone()["total"]

    # Total Revenue
    cursor.execute("""
        SELECT IFNULL(SUM(amount),0) AS revenue
        FROM payments
    """)
    total_revenue = cursor.fetchone()["revenue"]
    #=============================
# TOTAL UNREAD NOTIFICATIONS
#=============================

    cursor.execute("""

SELECT COUNT(*)

FROM notifications

WHERE status='Unread'

""")

    notification_count=cursor.fetchone()['COUNT(*)']


#=============================
# LATEST NOTIFICATIONS
#=============================

    cursor.execute("""

SELECT *

FROM notifications

ORDER BY id DESC

LIMIT 5

    """)

    latest_notifications=cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin/dashboard.html",
        admin_name=session["admin_name"],
        total_customers=total_customers,
        total_packages=total_packages,
        total_bookings=total_bookings,
        pending_bookings=pending_bookings,
        confirmed_bookings=confirmed_bookings,
        cancelled_bookings=cancelled_bookings,
        total_partners=total_partners,
        total_hotels=total_hotels,
        total_buses=total_buses,
        total_taxis=total_taxis,
        total_revenue=total_revenue,
        notification_count=notification_count,
        latest_notifications=latest_notifications
    )


@admin_bp.route("/admin/logout")
def logout():

    session.clear()

    return redirect(url_for("admin.admin_login"))

@admin_bp.route("/admin/customers")
def customers():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    search = request.args.get("search")

    conn = get_connection()
    cursor = conn.cursor()

    if search:

        sql = """
        SELECT *
        FROM customers
        WHERE name LIKE %s
        OR email LIKE %s
        OR mobile LIKE %s
        ORDER BY id DESC
        """

        value = "%" + search + "%"

        cursor.execute(sql, (value, value, value))

    else:

        cursor.execute("SELECT * FROM customers ORDER BY id DESC")

    customers = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/customers.html",
        customers=customers,
        search=search
    )

@admin_bp.route("/admin/edit_customer/<int:id>", methods=["GET", "POST"])
def edit_customer(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        mobile = request.form["mobile"]
        address = request.form["address"]

        sql = """
        UPDATE customers
        SET
            name=%s,
            email=%s,
            mobile=%s,
            address=%s
        WHERE id=%s
        """

        cursor.execute(sql, (name, email, mobile, address, id))
        conn.commit()

        cursor.close()
        conn.close()

        return redirect(url_for("admin.customers"))

    cursor.execute(
        "SELECT * FROM customers WHERE id=%s",
        (id,)
    )

    customer = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "admin/edit_customer.html",
        customer=customer
    )

@admin_bp.route("/admin/delete_customer/<int:id>")
def delete_customer(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    # Get customer details first
    cursor.execute(
        "SELECT name FROM customers WHERE id=%s",
        (id,)
    )

    customer = cursor.fetchone()

    if customer is None:
        cursor.close()
        conn.close()
        return "Customer not found"

    customer_name = customer["name"]

    # Delete customer
    cursor.execute(
        "DELETE FROM customers WHERE id=%s",
        (id,)
    )

    conn.commit()

    add_notification(
        "Customer Deleted",
        f"Customer '{customer_name}' has been deleted."
    )

    cursor.close()
    conn.close()

    return redirect(url_for("admin.customers"))
@admin_bp.route("/admin/block_customer/<int:id>")
def block_customer(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    # Fetch customer name
    cursor.execute(
        "SELECT name FROM customers WHERE id=%s",
        (id,)
    )

    customer = cursor.fetchone()
    customer_name = customer["name"]

    # Block customer
    cursor.execute(
        "UPDATE customers SET status='Blocked' WHERE id=%s",
        (id,)
    )

    conn.commit()

    add_notification(
        "Customer Blocked",
        f"Customer '{customer_name}' has been blocked."
    )

    cursor.close()
    conn.close()

    return redirect(url_for("admin.customers"))

@admin_bp.route("/admin/unblock_customer/<int:id>")
def unblock_customer(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    # Get customer name first
    cursor.execute(
        "SELECT name FROM customers WHERE id=%s",
        (id,)
    )

    customer = cursor.fetchone()

    if customer is None:
        cursor.close()
        conn.close()
        return "Customer not found"

    customer_name = customer["name"]

    # Update status
    cursor.execute(
        "UPDATE customers SET status='Active' WHERE id=%s",
        (id,)
    )

    conn.commit()

    add_notification(
        "Customer Activated",
        f"Customer '{customer_name}' has been activated."
    )

    cursor.close()
    conn.close()

    return redirect(url_for("admin.customers"))
   
@admin_bp.route("/admin/add_package", methods=["GET", "POST"])
def add_package():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    if request.method == "POST":

        package_name = request.form["package_name"]
        location = request.form["location"]
        duration = request.form["duration"]
        price = request.form["price"]
        description = request.form["description"]
        package_type = request.form["package_type"]

        hotel = request.form["hotel"]

        transport = request.form["transport"]

        meals = request.form["meals"]

        pickup_point = request.form["pickup_point"]

        drop_point = request.form["drop_point"]

        guide = request.form["guide"]

        sightseeing = request.form["sightseeing"]
        image = request.files["image"]
        filename = secure_filename(image.filename)

        image.save(
            os.path.join(
            "static",
            "images",
            filename
        )
    )

        conn = get_connection()
        cursor = conn.cursor()

        sql = """
INSERT INTO packages
(

package_name,

location,

duration,

hotel,

transport,

meals,

pickup_point,

drop_point,

guide,

sightseeing,

package_type,

price,

description,

image,

status

)

VALUES
(

%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s

)
"""

        cursor.execute(sql, (
            package_name,
            location,
            duration,
            hotel,

            transport,

            meals,

            pickup_point,

            drop_point,

            guide,

            sightseeing,

            package_type,
            price,
            description,
            filename,
            "Available"
        ))

        conn.commit()

        add_notification(
            "Package Added",
            f"New package '{package_name}' has been added."
        )

        cursor.close()
        conn.close()

        return redirect(url_for("admin.view_packages"))

    return render_template("admin/add_package.html")


# import math

@admin_bp.route("/admin/packages")
def view_packages():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    # ----------------------------
    # Search Values
    # ----------------------------

    package_name = request.args.get("package_name", "").strip()
    location = request.args.get("location", "").strip()
    duration = request.args.get("duration", "").strip()
    price = request.args.get("price", "").strip()
    status = request.args.get("status", "").strip()

    location_filter = request.args.get("location_filter", "")
    duration_filter = request.args.get("duration_filter", "")
    price_filter = request.args.get("price_filter", "")
    sort_by = request.args.get("sort_by", "")

    page = request.args.get("page", 1, type=int)

    per_page = 10
    offset = (page - 1) * per_page

    conn = get_connection()
    cursor = conn.cursor()

    # ----------------------------------
    # WHERE CLAUSE
    # ----------------------------------

    where = " WHERE 1=1 "

    values = []

    if package_name:
        where += " AND package_name LIKE %s "
        values.append(f"%{package_name}%")

    if location:
        where += " AND location LIKE %s "
        values.append(f"%{location}%")

    if duration:
        where += " AND duration LIKE %s "
        values.append(f"%{duration}%")

    if price:
        where += " AND price=%s "
        values.append(price)

    if status:
        where += " AND status=%s "
        values.append(status)

    if location_filter:
        where += " AND location=%s "
        values.append(location_filter)

    if duration_filter:
        where += " AND duration=%s "
        values.append(duration_filter)

    if price_filter == "0-5000":
        where += " AND price BETWEEN 0 AND 5000 "

    elif price_filter == "5001-10000":
        where += " AND price BETWEEN 5001 AND 10000 "

    elif price_filter == "10001-20000":
        where += " AND price BETWEEN 10001 AND 20000 "

    elif price_filter == "20000+":
        where += " AND price > 20000 "

    # ----------------------------------
    # COUNT QUERY
    # ----------------------------------

    count_sql = """
    SELECT COUNT(*) AS total
    FROM packages
    """ + where

    cursor.execute(count_sql, tuple(values))

    result = cursor.fetchone()

    total_packages = result["total"]

    total_pages = max(1, math.ceil(total_packages / per_page))

    # ----------------------------------
    # MAIN QUERY
    # ----------------------------------

    sql = """
    SELECT
        id,
        package_name,
        location,
        duration,
        price,
        hotel,
        hotel_type,
        transport,
        meals,
        pickup_point,
        drop_point,
        guide,
        sightseeing,
        package_type,
        description,
        image,
        status
    FROM packages
    """

    sql += where

    # ----------------------------------
    # SORTING
    # ----------------------------------

    if sort_by == "newest":

        sql += " ORDER BY id DESC "

    elif sort_by == "oldest":

        sql += " ORDER BY id ASC "

    elif sort_by == "price_low":

        sql += " ORDER BY price ASC "

    elif sort_by == "price_high":

        sql += " ORDER BY price DESC "

    elif sort_by == "name_asc":

        sql += " ORDER BY package_name ASC "

    elif sort_by == "name_desc":

        sql += " ORDER BY package_name DESC "

    else:

        sql += " ORDER BY id DESC "

    sql += " LIMIT %s OFFSET %s "

    main_values = values.copy()

    main_values.append(per_page)
    main_values.append(offset)

    cursor.execute(sql, tuple(main_values))

    packages = cursor.fetchall()

    # ----------------------------------
    # FILTER DROPDOWNS
    # ----------------------------------

    cursor.execute("""
        SELECT DISTINCT location
        FROM packages
        ORDER BY location
    """)

    locations = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT duration
        FROM packages
        ORDER BY duration
    """)

    durations = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin/view_packages.html",

        packages=packages,

        package_name=package_name,
        location=location,
        duration=duration,
        price=price,
        status=status,

        location_filter=location_filter,
        duration_filter=duration_filter,
        price_filter=price_filter,

        locations=locations,
        durations=durations,

        sort_by=sort_by,

        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_packages=total_packages
    )
# from werkzeug.utils import secure_filename
# import os

@admin_bp.route("/admin/edit_package/<int:id>", methods=["GET", "POST"])
def edit_package(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    # Get current package first
    cursor.execute(
        "SELECT * FROM packages WHERE id=%s",
        (id,)
    )

    package = cursor.fetchone()

    if not package:
        flash("Package not found.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("admin.view_packages"))

    if request.method == "POST":

        package_name = request.form["package_name"]
        location = request.form["location"]
        duration = request.form["duration"]
        price = request.form["price"]

        hotel = request.form["hotel"]
        hotel_type = request.form["hotel_type"]

        transport = request.form["transport"]
        meals = request.form["meals"]

        pickup_point = request.form["pickup_point"]
        drop_point = request.form["drop_point"]

        guide = request.form["guide"]
        sightseeing = request.form["sightseeing"]

        package_type = request.form["package_type"]

        description = request.form["description"]

        status = request.form["status"]

        # -------- IMAGE --------
        image_file = request.files.get("image")

        # Keep old image by default
        image = package["image"]

        if image_file and image_file.filename != "":

            image = secure_filename(image_file.filename)

            upload_folder = os.path.join("static", "images")

            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)

            image_file.save(
                os.path.join(upload_folder, image)
            )

        sql = """
        UPDATE packages
        SET
            package_name=%s,
            location=%s,
            duration=%s,
            price=%s,
            hotel=%s,
            hotel_type=%s,
            transport=%s,
            meals=%s,
            pickup_point=%s,
            drop_point=%s,
            guide=%s,
            sightseeing=%s,
            package_type=%s,
            description=%s,
            image=%s,
            status=%s
        WHERE id=%s
        """

        cursor.execute(sql, (

            package_name,
            location,
            duration,
            price,
            hotel,
            hotel_type,
            transport,
            meals,
            pickup_point,
            drop_point,
            guide,
            sightseeing,
            package_type,
            description,
            image,
            status,
            id

        ))

        conn.commit()

        add_notification(
            "Package Updated",
            f"Package '{package_name}' has been updated."
        )

        flash("Package updated successfully.", "success")

        cursor.close()
        conn.close()

        return redirect(url_for("admin.view_packages"))

    cursor.close()
    conn.close()

    return render_template(
        "admin/edit_package.html",
        package=package
    )

@admin_bp.route("/admin/delete_package/<int:id>")
def delete_package(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    # Get package details first
    cursor.execute(
        "SELECT package_name FROM packages WHERE id=%s",
        (id,)
    )

    package = cursor.fetchone()

    if package is None:
        cursor.close()
        conn.close()
        return "Package not found"

    # If using dictionary=True cursor
    package_name = package["package_name"]

    # Delete package
    cursor.execute(
        "DELETE FROM packages WHERE id=%s",
        (id,)
    )

    conn.commit()

    add_notification(
        "Package Deleted",
        f"Package '{package_name}' has been deleted."
    )

    cursor.close()
    conn.close()

    return redirect(url_for("admin.view_packages"))

@admin_bp.route("/admin/disable_package/<int:id>")
def disable_package(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE packages SET status='Unavailable' WHERE id=%s",
        (id,)
    )
    
    conn.commit()
    add_notification(
    "Package Disabled",
    "A tour package has been disabled."
)
    cursor.close()
    conn.close()

    return redirect(url_for("admin.view_packages"))


@admin_bp.route("/admin/enable_package/<int:id>")
def enable_package(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE packages SET status='Available' WHERE id=%s",
        (id,)
    )

    conn.commit()
    add_notification(
    "Package Enabled",
    "A tour package has been enabled."
)
    cursor.close()
    conn.close()

    return redirect(url_for("admin.view_packages"))
@admin_bp.route("/admin/export_packages_excel")
def export_packages_excel():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            package_name,
            location,
            duration,
            hotel,
            hotel_type,
            transport,
            meals,
            pickup_point,
            drop_point,
            guide,
            package_type,
            price,
            status
        FROM packages
        ORDER BY id DESC
    """)

    packages = cursor.fetchall()

    cursor.close()
    conn.close()

    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Packages"

    headers = [
        "Package",
        "Location",
        "Duration",
        "Hotel",
        "Hotel Type",
        "Transport",
        "Meals",
        "Pickup",
        "Drop",
        "Guide",
        "Package Type",
        "Price",
        "Status"
    ]

    sheet.append(headers)

    for p in packages:

        sheet.append([
            p["package_name"],
            p["location"],
            p["duration"],
            p["hotel"],
            p["hotel_type"],
            p["transport"],
            p["meals"],
            p["pickup_point"],
            p["drop_point"],
            p["guide"],
            p["package_type"],
            float(p["price"]),
            p["status"]
        ])

    output = io.BytesIO()

    workbook.save(output)

    output.seek(0)

    return send_file(
        output,
        download_name="Packages_Report.xlsx",
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@admin_bp.route("/admin/export_packages_pdf")
def export_packages_pdf():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            package_name,
            location,
            duration,
            hotel,
            transport,
            meals,
            price,
            status
        FROM packages
        ORDER BY id DESC
    """)

    packages = cursor.fetchall()

    cursor.close()
    conn.close()

    buffer = io.BytesIO()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4)
    )

    data = [[
        "Package",
        "Location",
        "Duration",
        "Hotel",
        "Transport",
        "Meals",
        "Price",
        "Status"
    ]]

    for p in packages:

        data.append([
            p["package_name"],
            p["location"],
            p["duration"],
            p["hotel"],
            p["transport"],
            p["meals"],
            f"₹{p['price']}",
            p["status"]
        ])

    table = Table(data)

    table.setStyle(TableStyle([

        ("BACKGROUND", (0,0), (-1,0), colors.darkblue),

        ("TEXTCOLOR", (0,0), (-1,0), colors.white),

        ("GRID", (0,0), (-1,-1), 1, colors.black),

        ("BACKGROUND", (0,1), (-1,-1), colors.beige),

        ("ALIGN", (0,0), (-1,-1), "CENTER"),

        ("BOTTOMPADDING", (0,0), (-1,0), 10),

        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")

    ]))

    pdf.build([table])

    buffer.seek(0)

    return send_file(
        buffer,
        download_name="Packages_Report.pdf",
        as_attachment=True,
        mimetype="application/pdf"
    )

@admin_bp.route("/admin/package/<int:id>")
def package_details(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM packages
        WHERE id=%s
    """, (id,))

    package = cursor.fetchone()

    cursor.close()
    conn.close()

    if not package:
        flash("Package not found.", "danger")
        return redirect(url_for("admin.view_packages"))

    return render_template(
        "admin/package_details.html",
        package=package
    )

@admin_bp.route("/admin/bookings")
def view_bookings():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    search = request.args.get("search", "")
    status = request.args.get("status", "")

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    SELECT
        b.id,
        c.name,
        c.email,
        c.mobile,
        p.package_name,
        p.location,
        b.travel_date,
        b.travelers,
        b.booking_date,
        b.status
    FROM bookings b
    INNER JOIN customers c
        ON b.customer_id = c.id
    INNER JOIN packages p
        ON b.package_id = p.id
    WHERE 1=1
    """

    values = []

    if search:
        sql += " AND c.name LIKE %s"
        values.append("%" + search + "%")

    if status:
        sql += " AND b.status=%s"
        values.append(status)

    sql += " ORDER BY b.booking_date DESC"

    cursor.execute(sql, tuple(values))
    bookings = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "admin/view_bookings.html",
        bookings=bookings,
        search=search,
        status=status
    )

@admin_bp.route("/admin/booking/<int:id>")
def booking_details(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    sql = """
    SELECT
        b.id,
        c.name,
        c.email,
        c.mobile,
        c.address,
        p.package_name,
        p.location,
        p.duration,
        p.price,
        b.travel_date,
        b.travelers,
        b.booking_date,
        b.status
    FROM bookings b
    INNER JOIN customers c
        ON b.customer_id = c.id
    INNER JOIN packages p
        ON b.package_id = p.id
    WHERE b.id=%s
    """

    cursor.execute(sql, (id,))
    booking = cursor.fetchone()

    cursor.close()
    conn.close()

    if booking is None:
        return "Booking Not Found"

    return render_template(
        "admin/booking_details.html",
        booking=booking
    )

@admin_bp.route("/admin/approve_booking/<int:id>")
def approve_booking(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE bookings
        SET status='Confirmed'
        WHERE id=%s
        """,
        (id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("admin.booking_details", id=id))


@admin_bp.route("/admin/reject_booking/<int:id>")
def reject_booking(id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE bookings
        SET status='Cancelled'
        WHERE id=%s
        """,
        (id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    return redirect(url_for("admin.booking_details", id=id))

@admin_bp.route("/admin/reports")
def reports_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS total FROM customers")
    total_customers = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM packages")
    total_packages = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM bookings")
    total_bookings = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT IFNULL(SUM(p.price * b.travelers),0) AS revenue
        FROM bookings b
        JOIN packages p ON b.package_id = p.id
        WHERE b.status='Confirmed'
    """)
    total_revenue = cursor.fetchone()["revenue"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM bookings
        WHERE DATE(booking_date)=CURDATE()
    """)
    today_bookings = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM bookings WHERE status='Pending'")
    pending = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM bookings WHERE status='Confirmed'")
    confirmed = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM bookings WHERE status='Cancelled'")
    cancelled = cursor.fetchone()["total"]

    # Booking status counts
    cursor.execute("""
    SELECT status, COUNT(*) AS total
    FROM bookings
    GROUP BY status
    """)
    status_data = cursor.fetchall()

    cursor.execute("""
    SELECT
    MONTH(booking_date) AS month_no,
    DATE_FORMAT(MIN(booking_date), '%b') AS month,
    COUNT(*) AS total
    FROM bookings
    GROUP BY MONTH(booking_date)
    ORDER BY month_no
    """)

    monthly_data = cursor.fetchall()
    conn.close()

    return render_template(
        "admin/reports_dashboard.html",
        total_customers=total_customers,
        total_packages=total_packages,
        total_bookings=total_bookings,
        total_revenue=total_revenue,
        today_bookings=today_bookings,
        pending=pending,
        confirmed=confirmed,
        cancelled=cancelled,
        status_data=status_data,
        monthly_data=monthly_data
    )


@admin_bp.route("/admin/booking_reports", methods=["GET", "POST"])
def booking_reports():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    report_type = ""
    report_value = ""
    reports = []

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        report_type = request.form["report_type"]
        report_value = request.form["report_value"]

        sql = """
        SELECT
            b.id,
            c.name,
            p.package_name,
            b.travel_date,
            b.travelers,
            b.booking_date,
            b.status
        FROM bookings b
        JOIN customers c ON b.customer_id=c.id
        JOIN packages p ON b.package_id=p.id
        """

        values = ()

        if report_type == "daily":
            sql += " WHERE DATE(b.booking_date)=%s"
            values = (report_value,)

        elif report_type == "monthly":
            sql += " WHERE DATE_FORMAT(b.booking_date,'%%Y-%%m')=%s"
            values = (report_value,)

        elif report_type == "yearly":
            sql += " WHERE YEAR(b.booking_date)=%s"
            values = (report_value,)

        sql += " ORDER BY b.booking_date DESC"

        cursor.execute(sql, values)
        reports = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/booking_reports.html",
        reports=reports,
        report_type=report_type,
        report_value=report_value
    )

@admin_bp.route("/admin/revenue_reports", methods=["GET", "POST"])
def revenue_reports():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    report_type = ""
    report_value = ""
    reports = []
    total_revenue = 0

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        report_type = request.form["report_type"]
        report_value = request.form["report_value"]

        sql = """
        SELECT
            b.id,
            c.name,
            p.package_name,
            p.price,
            b.travelers,
            (p.price * b.travelers) AS amount,
            b.booking_date
        FROM bookings b
        JOIN customers c ON b.customer_id = c.id
        JOIN packages p ON b.package_id = p.id
        WHERE b.status='Confirmed'
        """

        values = ()

        if report_type == "daily":
            sql += " AND DATE(b.booking_date)=%s"
            values = (report_value,)

        elif report_type == "monthly":
            sql += " AND DATE_FORMAT(b.booking_date,'%%Y-%%m')=%s"
            values = (report_value,)

        elif report_type == "yearly":
            sql += " AND YEAR(b.booking_date)=%s"
            values = (report_value,)

        sql += " ORDER BY b.booking_date DESC"

        cursor.execute(sql, values)
        reports = cursor.fetchall()

        total_revenue = sum(row["amount"] for row in reports)

    cursor.close()
    conn.close()

    return render_template(
        "admin/revenue_reports.html",
        reports=reports,
        total_revenue=total_revenue
    )

@admin_bp.route("/admin/export_bookings_csv")
def export_bookings_csv():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            b.id,
            c.name,
            p.package_name,
            b.travel_date,
            b.travelers,
            b.booking_date,
            b.status
        FROM bookings b
        INNER JOIN customers c
            ON b.customer_id = c.id
        INNER JOIN packages p
            ON b.package_id = p.id
        ORDER BY b.booking_date DESC
    """)

    bookings = cursor.fetchall()

    

    cursor.close()
    conn.close()

    def generate():

        yield "Booking ID,Customer Name,Package,Travel Date,Travelers,Booking Date,Status\n"

        for booking in bookings:

            yield (
                f"{booking['id']},"
                f"{booking['name']},"
                f"{booking['package_name']},"
                f"{booking['travel_date']},"
                f"{booking['travelers']},"
                f"{booking['booking_date']},"
                f"{booking['status']}\n"
            )

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=booking_report.csv"
        }
    )

@admin_bp.route("/reviews")
def reviews():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    search = request.args.get("search", "").strip()
    rating = request.args.get("rating", "").strip()
    status = request.args.get("status", "").strip()
    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            r.id,
            r.customer_name,
            r.rating,
            r.review_status,
            r.admin_reply,
            r.review,
            r.review_date,
            p.package_name
        FROM reviews r
        LEFT JOIN packages p
            ON r.package_id = p.id
        WHERE 1=1
    """

    values = []

    if search:
        query += """
            AND (
                r.customer_name LIKE %s
                OR p.package_name LIKE %s
            )
        """
        values.extend([f"%{search}%", f"%{search}%"])

    if rating:
        query += " AND r.rating=%s "
        values.append(rating)
    if status:
        query += " AND r.review_status=%s "
        values.append(status)
    query += " ORDER BY r.review_date DESC"

    cursor.execute(query, values)

    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/reviews.html",
        reviews=reviews,
        search=search,
        rating=rating,
        status=status
    )

@admin_bp.route("/delete_review/<int:review_id>")
def delete_review(review_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM reviews WHERE id=%s",
        (review_id,)
    )

    review = cursor.fetchone()

    if not review:
        flash("Review not found.", "danger")
        cursor.close()
        conn.close()
        return redirect(url_for("admin.reviews"))

    cursor.execute(
        "DELETE FROM reviews WHERE id=%s",
        (review_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash("Review deleted successfully.", "success")

    return redirect(url_for("admin.reviews"))
@admin_bp.route("/approve_review/<int:review_id>")
def approve_review(review_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE reviews
        SET review_status='Approved'
        WHERE id=%s
    """,(review_id,))

    conn.commit()

    cursor.close()
    conn.close()

    flash("Review approved successfully.","success")

    return redirect(url_for("admin.reviews"))
@admin_bp.route("/reject_review/<int:review_id>")
def reject_review(review_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn=get_connection()
    cursor=conn.cursor()

    cursor.execute("""
        UPDATE reviews
        SET review_status='Rejected'
        WHERE id=%s
    """,(review_id,))

    conn.commit()

    cursor.close()
    conn.close()

    flash("Review rejected successfully.","warning")

    return redirect(url_for("admin.reviews"))
@admin_bp.route("/reply_review/<int:review_id>", methods=["GET", "POST"])
def reply_review(review_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        reply = request.form["reply"]

        cursor.execute("""
            UPDATE reviews
            SET admin_reply=%s
            WHERE id=%s
        """, (reply, review_id))

        conn.commit()

        cursor.close()
        conn.close()

        flash("Reply added successfully.", "success")

        return redirect(url_for("admin.reviews"))

    cursor.execute("""
        SELECT *
        FROM reviews
        WHERE id=%s
    """, (review_id,))

    review = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "admin/reply_review.html",
        review=review
    )

@admin_bp.route("/review_statistics")
def review_statistics():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT
        COUNT(*) AS total_reviews,

        ROUND(AVG(rating),1) AS average_rating,

        SUM(CASE WHEN review_status='Pending' THEN 1 ELSE 0 END) AS pending_reviews,

        SUM(CASE WHEN review_status='Approved' THEN 1 ELSE 0 END) AS approved_reviews,

        SUM(CASE WHEN review_status='Rejected' THEN 1 ELSE 0 END) AS rejected_reviews,

        SUM(CASE WHEN rating=5 THEN 1 ELSE 0 END) AS five_star,

        SUM(CASE WHEN rating=4 THEN 1 ELSE 0 END) AS four_star,

        SUM(CASE WHEN rating=3 THEN 1 ELSE 0 END) AS three_star,

        SUM(CASE WHEN rating=2 THEN 1 ELSE 0 END) AS two_star,

        SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) AS one_star

    FROM reviews
""")

    stats = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "admin/review_statistics.html",
        stats=stats
    )

@admin_bp.route("/top_rated_packages")
def top_rated_packages():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.id,
            p.package_name,
            p.price,
            p.duration,
            ROUND(AVG(r.rating),1) AS average_rating,
            COUNT(r.id) AS total_reviews
        FROM packages p
        LEFT JOIN reviews r
            ON p.id = r.package_id
        GROUP BY
            p.id,
            p.package_name,
            p.price,
            p.duration
        ORDER BY average_rating DESC, total_reviews DESC
    """)

    packages = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/top_rated_packages.html",
        packages=packages
    )
@admin_bp.route("/review_report")
def review_report():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
            SELECT
            r.customer_name,
            p.package_name,
            r.rating,
            r.review_status,
            r.review,
            r.admin_reply,
            r.review_date
            FROM reviews r
            LEFT JOIN packages p
            ON r.package_id = p.id
            ORDER BY r.review_date DESC
    """)

    reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    def generate():

        data = csv.writer(Echo())

        yield data.writerow([
            "Customer Name",
            "Package ID",
            "Rating",
            "Status",
            "Review",
            "Admin Reply",
            "Review Date"
        ])

        for review in reviews:

            yield data.writerow([
                review["customer_name"],
                review["package_name"],
                review["rating"],
                review["review_status"],
                review["review"],
                review["admin_reply"] if review["admin_reply"] else "",
                review["review_date"]
            ])

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=review_report.csv"
        }
    )


class Echo:
    def write(self, value):
        return value

@admin_bp.route("/most_wishlisted_packages")
def most_wishlisted_packages():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.id,
            p.package_name,
            p.price,
            COUNT(w.id) AS wishlist_count
        FROM packages p
        LEFT JOIN wishlist w
            ON p.id = w.package_id
        GROUP BY
            p.id,
            p.package_name,
            p.price
        ORDER BY
            wishlist_count DESC,
            p.package_name ASC
    """)

    packages = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/most_wishlisted_packages.html",
        packages=packages
    )

@admin_bp.route("/wishlist_report")
def wishlist_report():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    search = request.args.get("search", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            w.id,
            c.name AS customer_name,
            p.package_name,
            p.price,
            w.added_date
        FROM wishlist w
        INNER JOIN customers c
            ON w.customer_id = c.id
        INNER JOIN packages p
            ON w.package_id = p.id
        WHERE 1=1
    """

    values = []

    if search:
        query += """
            AND (
                c.name LIKE %s
                OR p.package_name LIKE %s
            )
        """
        values.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY w.added_date DESC"

    cursor.execute(query, values)

    wishlist = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/wishlist_report.html",
        wishlist=wishlist,
        search=search
    )

@admin_bp.route("/wishlist_statistics")
def wishlist_statistics():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) AS total_wishlist,
            COUNT(DISTINCT customer_id) AS total_customers,
            COUNT(DISTINCT package_id) AS total_packages,
            ROUND(
                COUNT(*) / NULLIF(COUNT(DISTINCT customer_id),0),
                2
            ) AS average_per_customer
        FROM wishlist
    """)

    stats = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(
        "admin/wishlist_statistics.html",
        stats=stats
    )

@admin_bp.route("/export_wishlist_csv")
def export_wishlist_csv():

    if "admin_id" not in session:
        return redirect(url_for("admin.login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            w.id,
            c.name AS customer_name,
            p.package_name,
            p.price,
            w.added_date
        FROM wishlist w
        INNER JOIN customers c
            ON w.customer_id = c.id
        INNER JOIN packages p
            ON w.package_id = p.id
        ORDER BY w.added_date DESC
    """)

    records = cursor.fetchall()

    cursor.close()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Wishlist ID",
        "Customer Name",
        "Package Name",
        "Price",
        "Added Date"
    ])

    for row in records:
        writer.writerow([
            row["id"],
            row["customer_name"],
            row["package_name"],
            row["price"],
            row["added_date"]
        ])

    output.seek(0)

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=wishlist_report.csv"
        }
    )

#==================================
# VIEW NOTIFICATIONS
#==================================

@admin_bp.route("/admin/notifications")
def notifications():

    if "admin_id" not in session:

        return redirect(
            url_for(
                "admin.admin_login"
            )
        )


    conn=get_connection()

    cursor=conn.cursor()


    cursor.execute("""

    SELECT *

    FROM notifications

    ORDER BY id DESC

    """)


    notifications=cursor.fetchall()

    cursor.execute("""

    SELECT COUNT(*)

    FROM notifications

    WHERE status='Unread'

    """)

    unread_count=cursor.fetchone()['COUNT(*)']


    cursor.execute("""

    SELECT COUNT(*)

    FROM notifications

    WHERE status='Read'

    """)

    read_count=cursor.fetchone()['COUNT(*)']


    cursor.close()

    conn.close()


    return render_template(

        "admin/notifications.html",

        notifications=notifications,
        unread_count=unread_count,
        read_count=read_count

    )


#==================================
# MARK AS READ
#==================================

@admin_bp.route(
"/admin/read_notification/<int:id>"
)
def read_notification(id):


    conn=get_connection()

    cursor=conn.cursor()


    cursor.execute("""

    UPDATE notifications

    SET status='Read'

    WHERE id=%s

    """,(id,))


    conn.commit()


    cursor.close()

    conn.close()


    return redirect(

    url_for(

    "admin.notifications"

    ))




#==================================
# DELETE NOTIFICATION
#==================================


@admin_bp.route(
"/admin/delete_notification/<int:id>"
)
def delete_notification(id):


    conn=get_connection()

    cursor=conn.cursor()


    cursor.execute("""

    DELETE FROM notifications

    WHERE id=%s

    """,(id,))


    conn.commit()


    cursor.close()

    conn.close()


    return redirect(

    url_for(

    "admin.notifications"

    ))



#==================================
# MARK ALL READ
#==================================


@admin_bp.route(
"/admin/read_all_notifications"
)
def read_all_notifications():

    conn=get_connection()

    cursor=conn.cursor()


    cursor.execute("""

    UPDATE notifications

    SET status='Read'

    """)


    conn.commit()


    cursor.close()

    conn.close()


    return redirect(

    url_for(

    "admin.notifications"

    ))



#==================================
# DELETE ALL
#==================================


@admin_bp.route(
"/admin/delete_all_notifications"
)
def delete_all_notifications():

    conn=get_connection()

    cursor=conn.cursor()


    cursor.execute("""

    DELETE FROM notifications

    """)


    conn.commit()


    cursor.close()

    conn.close()


    return redirect(

    url_for(

    "admin.notifications"

    ))

def add_notification(
    title,
    message,
    notification_type="General",
    user_type="Customer"
):

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO notifications(
            title,
            message,
            notification_type,
            user_type,
            status
        )
        VALUES(%s,%s,%s,%s,%s)
    """, (
        title,
        message,
        notification_type,
        user_type,
        "Unread"
    ))

    connection.commit()

    cursor.close()
    connection.close()

@admin_bp.route("/add_coupon", methods=["GET", "POST"])
def add_coupon():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        coupon_code = request.form["coupon_code"].strip().upper()
        discount_type = request.form["discount_type"]
        discount_value = request.form["discount_value"]
        minimum_amount = request.form["minimum_amount"]
        expiry_date = request.form["expiry_date"]
        usage_limit = request.form["usage_limit"]

        cursor.execute(
            "SELECT id FROM coupons WHERE coupon_code=%s",
            (coupon_code,)
        )

        existing = cursor.fetchone()

        if existing:

            flash("Coupon code already exists.", "warning")

            cursor.close()
            conn.close()

            return redirect(url_for("admin.add_coupon"))

        cursor.execute("""
            INSERT INTO coupons
            (
                coupon_code,
                discount_type,
                discount_value,
                minimum_amount,
                expiry_date,
                usage_limit
            )
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (
            coupon_code,
            discount_type,
            discount_value,
            minimum_amount,
            expiry_date,
            usage_limit
        ))

        conn.commit()

        flash("Coupon created successfully.", "success")

        cursor.close()
        conn.close()

        return redirect(url_for("admin.add_coupon"))

    cursor.close()
    conn.close()

    return render_template("admin/add_coupon.html")

@admin_bp.route("/manage_coupons")
def manage_coupons():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    search = request.args.get("search", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    query = """
        SELECT *
        FROM coupons
        WHERE 1=1
    """

    values = []

    if search:
        query += " AND coupon_code LIKE %s"
        values.append(f"%{search}%")

    query += " ORDER BY created_at DESC"

    cursor.execute(query, values)

    coupons = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/manage_coupons.html",
        coupons=coupons,
        search=search
    )

@admin_bp.route("/edit_coupon/<int:coupon_id>", methods=["GET", "POST"])
def edit_coupon(coupon_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM coupons WHERE id=%s",
        (coupon_id,)
    )

    coupon = cursor.fetchone()

    if not coupon:

        flash("Coupon not found.", "danger")

        cursor.close()
        conn.close()

        return redirect(url_for("admin.manage_coupons"))

    if request.method == "POST":

        coupon_code = request.form["coupon_code"].strip().upper()
        discount_type = request.form["discount_type"]
        discount_value = request.form["discount_value"]
        minimum_amount = request.form["minimum_amount"]
        expiry_date = request.form["expiry_date"]
        usage_limit = request.form["usage_limit"]

        cursor.execute("""
            SELECT id
            FROM coupons
            WHERE coupon_code=%s
            AND id!=%s
        """, (coupon_code, coupon_id))

        existing = cursor.fetchone()

        if existing:

            flash("Coupon code already exists.", "warning")

            cursor.close()
            conn.close()

            return redirect(
                url_for(
                    "admin.edit_coupon",
                    coupon_id=coupon_id
                )
            )

        cursor.execute("""
            UPDATE coupons
            SET
                coupon_code=%s,
                discount_type=%s,
                discount_value=%s,
                minimum_amount=%s,
                expiry_date=%s,
                usage_limit=%s
            WHERE id=%s
        """, (

            coupon_code,
            discount_type,
            discount_value,
            minimum_amount,
            expiry_date,
            usage_limit,
            coupon_id

        ))

        conn.commit()

        flash("Coupon updated successfully.", "success")

        cursor.close()
        conn.close()

        return redirect(url_for("admin.manage_coupons"))

    cursor.close()
    conn.close()

    return render_template(
        "admin/edit_coupon.html",
        coupon=coupon
    )

@admin_bp.route("/toggle_coupon_status/<int:coupon_id>")
def toggle_coupon_status(coupon_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status
        FROM coupons
        WHERE id=%s
    """, (coupon_id,))

    coupon = cursor.fetchone()

    if not coupon:

        flash("Coupon not found.", "danger")

        cursor.close()
        conn.close()

        return redirect(url_for("admin.manage_coupons"))

    if coupon["status"] == "Active":
        new_status = "Inactive"
    else:
        new_status = "Active"

    cursor.execute("""
        UPDATE coupons
        SET status=%s
        WHERE id=%s
    """, (
        new_status,
        coupon_id
    ))

    conn.commit()

    flash(
        f"Coupon {new_status.lower()} successfully.",
        "success"
    )

    cursor.close()
    conn.close()

    return redirect(url_for("admin.manage_coupons"))
@admin_bp.route("/coupon_dashboard")
def coupon_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    # Total Coupons
    cursor.execute("""
        SELECT COUNT(*) AS total_coupons
        FROM coupons
    """)
    total_coupons = cursor.fetchone()["total_coupons"]

    # Active Coupons
    cursor.execute("""
        SELECT COUNT(*) AS active_coupons
        FROM coupons
        WHERE status='Active'
    """)
    active_coupons = cursor.fetchone()["active_coupons"]

    # Inactive Coupons
    cursor.execute("""
        SELECT COUNT(*) AS inactive_coupons
        FROM coupons
        WHERE status='Inactive'
    """)
    inactive_coupons = cursor.fetchone()["inactive_coupons"]

    # Expired Coupons
    cursor.execute("""
        SELECT COUNT(*) AS expired_coupons
        FROM coupons
        WHERE expiry_date < CURDATE()
    """)
    expired_coupons = cursor.fetchone()["expired_coupons"]

    # Coupons Used
    cursor.execute("""
        SELECT IFNULL(SUM(used_count),0) AS total_used
        FROM coupons
    """)
    total_used = cursor.fetchone()["total_used"]

    cursor.close()
    conn.close()

    return render_template(
        "admin/coupon_dashboard.html",
        total_coupons=total_coupons,
        active_coupons=active_coupons,
        inactive_coupons=inactive_coupons,
        expired_coupons=expired_coupons,
        total_used=total_used
    )
@admin_bp.route("/delete_coupon/<int:coupon_id>")
def delete_coupon(coupon_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM coupons WHERE id=%s",
        (coupon_id,)
    )

    coupon = cursor.fetchone()

    if not coupon:

        flash("Coupon not found.", "danger")

        cursor.close()
        conn.close()

        return redirect(url_for("admin.manage_coupons"))

    cursor.execute(
        "DELETE FROM coupons WHERE id=%s",
        (coupon_id,)
    )

    conn.commit()

    flash(
        "Coupon deleted successfully.",
        "success"
    )

    cursor.close()
    conn.close()

    return redirect(url_for("admin.manage_coupons"))
@admin_bp.route("/coupon_report")
def coupon_report():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            coupon_code,
            discount_type,
            discount_value,
            minimum_amount,
            usage_limit,
            used_count,
            expiry_date,
            status

        FROM coupons

        ORDER BY created_at DESC

    """)

    coupons = cursor.fetchall()

    cursor.close()
    conn.close()

    def generate():

        data = csv.writer(Echo())

        yield data.writerow([

            "Coupon Code",
            "Discount Type",
            "Discount Value",
            "Minimum Amount",
            "Usage Limit",
            "Used Count",
            "Expiry Date",
            "Status"

        ])

        for coupon in coupons:

            yield data.writerow([

                coupon["coupon_code"],
                coupon["discount_type"],
                coupon["discount_value"],
                coupon["minimum_amount"],
                coupon["usage_limit"],
                coupon["used_count"],
                coupon["expiry_date"],
                coupon["status"]

            ])

    return Response(

        generate(),

        mimetype="text/csv",

        headers={
            "Content-Disposition":
            "attachment; filename=coupon_report.csv"
        }

    )

@admin_bp.route("/payment_dashboard")
def payment_dashboard():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    # Total Payments
    cursor.execute("""
        SELECT COUNT(*) AS total_payments
        FROM payments
    """)
    total_payments = cursor.fetchone()["total_payments"]

    # Paid Payments
    cursor.execute("""
        SELECT COUNT(*) AS paid_payments
        FROM payments
        WHERE payment_status='Paid'
    """)
    paid_payments = cursor.fetchone()["paid_payments"]

    # Pending Payments
    cursor.execute("""
        SELECT COUNT(*) AS pending_payments
        FROM payments
        WHERE payment_status='Pending'
    """)
    pending_payments = cursor.fetchone()["pending_payments"]

    # Failed Payments
    cursor.execute("""
        SELECT COUNT(*) AS failed_payments
        FROM payments
        WHERE payment_status='Failed'
    """)
    failed_payments = cursor.fetchone()["failed_payments"]

    # Refunded Payments
    cursor.execute("""
        SELECT COUNT(*) AS refunded_payments
        FROM payments
        WHERE refund_status='Refunded'
    """)
    refunded_payments = cursor.fetchone()["refunded_payments"]

    # Pending Refund Requests
    cursor.execute("""
        SELECT COUNT(*) AS pending_refunds
        FROM payments
        WHERE refund_status='Paid'
    """)
    pending_refunds = cursor.fetchone()["pending_refunds"]

    # Coupon Used

    cursor.execute("""
    SELECT COUNT(*) AS coupon_used
    FROM payments
    WHERE coupon_code IS NOT NULL
    AND coupon_code!=''
    """)

    coupon_used = cursor.fetchone()["coupon_used"]

    # Without Coupon

    cursor.execute("""
    SELECT COUNT(*) AS no_coupon
    FROM payments
    WHERE coupon_code IS NULL
    OR coupon_code=''
    """)

    no_coupon = cursor.fetchone()["no_coupon"]

    # Revenue
    cursor.execute("""
        SELECT IFNULL(SUM(final_amount),0) AS revenue
        FROM payments
        WHERE payment_status='Paid'
    """)
    total_revenue = cursor.fetchone()["revenue"]

    cursor.close()
    conn.close()

    return render_template(
        "admin/payment_dashboard.html",
        total_payments=total_payments,
        paid_payments=paid_payments,
        pending_payments=pending_payments,
        failed_payments=failed_payments,
        refunded_payments=refunded_payments,
        pending_refunds=pending_refunds,
        coupon_used=coupon_used,
        no_coupon=no_coupon,
        total_revenue=total_revenue
    )

@admin_bp.route("/manage_payments")
def manage_payments():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    query = """
       SELECT
        p.id,
        p.booking_id,
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
        c.name AS customer_name,

        pk.package_name

        FROM payments p

    JOIN bookings b
        ON p.booking_id=b.id

    JOIN customers c
        ON b.customer_id=c.id

    JOIN packages pk
        ON b.package_id=pk.id

    WHERE 1=1
    """

    values = []

    if search:
        query += """
        AND (
        c.name LIKE %s
        OR pk.package_name LIKE %s
        OR p.payment_method LIKE %s
        OR p.transaction_id LIKE %s
        )
        """

        values.extend([
            f"%{search}%",
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ])

    if status:
        query += " AND p.payment_status=%s "
        values.append(status)

    query += " ORDER BY p.id DESC"

    cursor.execute(query, values)

    payments = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "admin/manage_payments.html",
        payments=payments,
        search=search,
        status=status
    )
@admin_bp.route("/edit_payment/<int:payment_id>", methods=["GET","POST"])
def edit_payment(payment_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT

        id,

        booking_id,

        transaction_id,

        original_amount,

        discount_amount,

        final_amount,

        coupon_code,

        payment_method,

        payment_gateway,

        payment_status,

        refund_status,

        remarks,

        payment_date

    FROM payments

    WHERE id=%s
    """, (payment_id,))
    payment = cursor.fetchone()

    if not payment:
        flash("Payment not found.","danger")
        cursor.close()
        conn.close()
        return redirect(url_for("admin.manage_payments"))

    if request.method=="POST":

        status = request.form["payment_status"]
        gateway = request.form["payment_gateway"]
        refund = request.form["refund_status"]
        remarks = request.form["remarks"]

        cursor.execute("""
        UPDATE payments
        SET
            payment_status=%s,
            payment_gateway=%s,
            refund_status=%s,
            remarks=%s
        WHERE id=%s
        """,(
            status,
            gateway,
            refund,
            remarks,
            payment_id
            ))

        conn.commit()

        cursor.close()
        conn.close()

        flash("Payment updated successfully.","success")

        return redirect(url_for("admin.manage_payments"))

    cursor.close()
    conn.close()

    return render_template(
        "admin/edit_payment.html",
        payment=payment
    )

@admin_bp.route("/delete_payment/<int:payment_id>")
def delete_payment(payment_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM payments WHERE id=%s",
        (payment_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash("Payment deleted successfully.","success")

    return redirect(url_for("admin.manage_payments"))

@admin_bp.route("/payment_report")
def payment_report():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            p.id,
            p.transaction_id,
            c.name,
            pk.package_name,
            p.booking_id,
            p.original_amount,
            p.discount_amount,
            p.final_amount,
            p.coupon_code,
            p.payment_method,
            p.payment_gateway,
            p.payment_status,
            p.payment_date,
            p.refund_status,
            p.remarks
        FROM payments p
        JOIN bookings b
            ON p.booking_id=b.id
        JOIN customers c
            ON b.customer_id=c.id
        JOIN packages pk
            ON b.package_id=pk.id
        ORDER BY p.id DESC
    """)

    payments = cursor.fetchall()

    cursor.close()
    conn.close()

    def generate():

        data = csv.writer(Echo())

        yield data.writerow([
            "Payment ID",
            "Transaction ID",
            "Customer",
            "Package",
            "Booking ID",
            "Original Amount",
            "Discount Amount",
            "Final Amount",
            "Coupon Code",
            "Payment Method",
            "Payment Gateway",
            "Payment Status",
            "Payment Date",
            "Refund Status",
            "Remarks"
        ])

        for payment in payments:

            yield data.writerow([
                payment["id"],
                payment["transaction_id"],
                payment["name"],
                payment["package_name"],
                payment["booking_id"],
                payment["original_amount"],
                payment["discount_amount"],
                payment["final_amount"],
                payment["coupon_code"],
                payment["payment_method"],
                payment["payment_gateway"],
                payment["payment_status"],
                payment["payment_date"],
                payment["refund_status"],
                payment["remarks"]
            ])

    return Response(
        generate(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=payment_report.csv"
        }
    )
# class Echo:
#     def write(self, value):
#         return value
    
@admin_bp.route("/payment_statistics")
def payment_statistics():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""

    SELECT

    COUNT(*) AS total_payments,

    SUM(
    CASE
    WHEN payment_status='Paid'
    THEN 1
    ELSE 0
    END
    ) AS paid_payments,

    SUM(
    CASE
    WHEN payment_status='Pending'
    THEN 1
    ELSE 0
    END
    ) AS pending_payments,

    SUM(
    CASE
    WHEN payment_status='Failed'
    THEN 1
    ELSE 0
    END
    ) AS failed_payments,

    SUM(
    CASE
    WHEN payment_status='Refunded'
    THEN 1
    ELSE 0
    END
    ) AS refunded_payments,

    SUM(
    CASE
    WHEN refund_status='Partial'
    THEN 1
    ELSE 0
    END
    ) AS partial_refunds,

    SUM(
    CASE
    WHEN coupon_code IS NOT NULL
    AND coupon_code!=''
    THEN 1
    ELSE 0
    END
    ) AS coupon_used,

    SUM(
    CASE
    WHEN coupon_code IS NULL
    OR coupon_code=''
    THEN 1
    ELSE 0
    END
    ) AS no_coupon,

    IFNULL(

    SUM(

    CASE

    WHEN payment_status='Paid'

    THEN final_amount

    ELSE 0

    END

    ),0

    ) AS total_revenue

    FROM payments

    """)

    stats = cursor.fetchone()

    total = stats["total_payments"] or 0
    paid = stats["paid_payments"] or 0

    if total > 0:
        payment_rate = round((paid / total) * 100, 1)
    else:
        payment_rate = 0

    cursor.close()
    conn.close()

    return render_template(
        "admin/payment_statistics.html",
        stats=stats,
        payment_rate=payment_rate
    )
@admin_bp.route("/add_gallery", methods=["GET", "POST"])
def add_gallery():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        image = request.files["image"]

        title = request.form["title"]

        category = request.form["category"]

        description = request.form["description"]

        if image.filename == "":

            flash("Please select an image.", "warning")

            cursor.close()
            conn.close()

            return redirect(url_for("admin.add_gallery"))

        filename = secure_filename(image.filename)

        image.save(

            os.path.join(

                current_app.root_path,

                "static",

                "images",

                filename

            )

        )

        cursor.execute("""

            INSERT INTO gallery
            (

                image,

                title,

                category,

                description

            )

            VALUES
            (

                %s,

                %s,

                %s,

                %s

            )

        """, (

            filename,

            title,

            category,

            description

        ))

        conn.commit()

        flash(

            "Gallery image uploaded successfully.",

            "success"

        )

        cursor.close()
        conn.close()

        return redirect(url_for("admin.manage_gallery"))

    cursor.close()
    conn.close()

    return render_template("admin/add_gallery.html")

@admin_bp.route("/manage_gallery")
def manage_gallery():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = get_connection()
    cursor = conn.cursor()

    query = """

        SELECT *

        FROM gallery

        WHERE 1=1

    """

    values = []

    if search:

        query += """

        AND

        (

            title LIKE %s

            OR

            category LIKE %s

        )

        """

        values.extend(

            [

                f"%{search}%",

                f"%{search}%"

            ]

        )

    query += """

    ORDER BY id DESC

    """

    cursor.execute(

        query,

        values

    )

    gallery = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin/manage_gallery.html",

        gallery=gallery,

        search=search

    )
@admin_bp.route(
    "/edit_gallery/<int:gallery_id>",
    methods=["GET","POST"]
)
def edit_gallery(gallery_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM gallery WHERE id=%s",
        (gallery_id,)
    )

    gallery = cursor.fetchone()

    if not gallery:

        flash(
            "Gallery image not found.",
            "danger"
        )

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin.manage_gallery")
        )

    if request.method == "POST":

        title = request.form["title"]

        category = request.form["category"]

        description = request.form["description"]

        filename = gallery["image"]

        image = request.files["image"]

        if image and image.filename != "":

            filename = secure_filename(
                image.filename
            )

            image.save(

                os.path.join(

                    current_app.root_path,

                    "static",

                    "images",

                    filename

                )

            )

        cursor.execute("""

            UPDATE gallery

            SET

                image=%s,

                title=%s,

                category=%s,

                description=%s

            WHERE id=%s

        """,(

            filename,

            title,

            category,

            description,

            gallery_id

        ))

        conn.commit()

        flash(

            "Gallery updated successfully.",

            "success"

        )

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin.manage_gallery")
        )

    cursor.close()
    conn.close()

    return render_template(

        "admin/edit_gallery.html",

        gallery=gallery

    )

@admin_bp.route("/delete_gallery/<int:gallery_id>")
def delete_gallery(gallery_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT image FROM gallery WHERE id=%s",
        (gallery_id,)
    )

    gallery = cursor.fetchone()

    if not gallery:

        flash(
            "Gallery image not found.",
            "danger"
        )

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin.manage_gallery")
        )

    image_path = os.path.join(

        current_app.root_path,

        "static",

        "images",

        gallery["image"]

    )

    if os.path.exists(image_path):

        os.remove(image_path)

    cursor.execute(

        "DELETE FROM gallery WHERE id=%s",

        (gallery_id,)

    )

    conn.commit()

    cursor.close()
    conn.close()

    flash(

        "Gallery image deleted successfully.",

        "success"

    )

    return redirect(
        url_for("admin.manage_gallery")
    )

@admin_bp.route(
    "/add_blog",
    methods=["GET","POST"]
)
def add_blog():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        title = request.form["title"]

        category = request.form["category"]

        short_description = request.form[
            "short_description"
        ]

        content = request.form["content"]

        image = request.files["image"]

        filename = secure_filename(
            image.filename
        )

        image.save(

            os.path.join(

                current_app.root_path,

                "static",

                "images",

                filename

            )

        )

        cursor.execute("""

            INSERT INTO blogs
            (

                title,

                image,

                category,

                short_description,

                content

            )

            VALUES
            (%s,%s,%s,%s,%s)

        """,(

            title,

            filename,

            category,

            short_description,

            content

        ))

        conn.commit()

        flash(

            "Blog published successfully.",

            "success"

        )

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin.manage_blogs")
        )

    cursor.close()
    conn.close()

    return render_template(
        "admin/add_blog.html"
    )

@admin_bp.route("/manage_blogs")
def manage_blogs():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = get_connection()
    cursor = conn.cursor()

    query = """

        SELECT *

        FROM blogs

        WHERE 1=1

    """

    values = []

    if search:

        query += """

            AND title LIKE %s

        """

        values.append(f"%{search}%")

    query += """

        ORDER BY created_at DESC

    """

    cursor.execute(
        query,
        values
    )

    blogs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin/manage_blogs.html",

        blogs=blogs,

        search=search

    )
@admin_bp.route(
    "/edit_blog/<int:blog_id>",
    methods=["GET","POST"]
)
def edit_blog(blog_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM blogs WHERE id=%s",
        (blog_id,)
    )

    blog = cursor.fetchone()

    if not blog:

        flash("Blog not found.","danger")

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin.manage_blogs")
        )

    if request.method=="POST":

        title=request.form["title"]

        category=request.form["category"]

        short_description=request.form[
            "short_description"
        ]

        content=request.form["content"]

        filename=blog["image"]

        image=request.files["image"]

        if image and image.filename!="":

            filename=secure_filename(
                image.filename
            )

            image.save(

                os.path.join(

                    current_app.root_path,

                    "static",

                    "images",

                    filename

                )

            )

        cursor.execute("""

            UPDATE blogs

            SET

                title=%s,

                image=%s,

                category=%s,

                short_description=%s,

                content=%s

            WHERE id=%s

        """,(

            title,

            filename,

            category,

            short_description,

            content,

            blog_id

        ))

        conn.commit()

        flash(
            "Blog updated successfully.",
            "success"
        )

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin.manage_blogs")
        )

    cursor.close()
    conn.close()

    return render_template(

        "admin/edit_blog.html",

        blog=blog

    )
@admin_bp.route("/delete_blog/<int:blog_id>")
def delete_blog(blog_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT image FROM blogs WHERE id=%s",
        (blog_id,)
    )

    blog = cursor.fetchone()

    if not blog:

        flash("Blog not found.", "danger")

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin.manage_blogs")
        )

    image_path = os.path.join(

        current_app.root_path,

        "static",

        "images",

        blog["image"]

    )

    if os.path.exists(image_path):

        os.remove(image_path)

    cursor.execute(
        "DELETE FROM blogs WHERE id=%s",
        (blog_id,)
    )

    conn.commit()

    cursor.close()
    conn.close()

    flash(
        "Blog deleted successfully.",
        "success"
    )

    return redirect(
        url_for("admin.manage_blogs")
    )

@admin_bp.route("/manage_contacts")
def manage_contacts():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    search = request.args.get("search", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    query = """

        SELECT *

        FROM contact_messages

    """

    values = []

    if search:

        query += """

            WHERE

            name LIKE %s

            OR email LIKE %s

            OR subject LIKE %s

        """

        keyword = "%" + search + "%"

        values.extend([keyword, keyword, keyword])

    query += """

        ORDER BY created_at DESC

    """

    cursor.execute(query, values)

    contacts = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin/manage_contacts.html",

        contacts=contacts,

        search=search

    )
@admin_bp.route("/view_contact/<int:contact_id>", methods=["GET", "POST"])
def view_contact(contact_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        status = request.form["status"]

        cursor.execute("""

            UPDATE contact_messages

            SET status=%s

            WHERE id=%s

        """, (

            status,

            contact_id

        ))

        conn.commit()

        flash(

            "Contact status updated successfully.",

            "success"

        )

        cursor.close()
        conn.close()

        return redirect(url_for("admin.manage_contacts"))

    cursor.execute("""

        SELECT *

        FROM contact_messages

        WHERE id=%s

    """, (contact_id,))

    contact = cursor.fetchone()

    cursor.close()
    conn.close()

    if not contact:

        flash(

            "Contact message not found.",

            "danger"

        )

        return redirect(url_for("admin.manage_contacts"))

    return render_template(

        "admin/view_contact.html",

        contact=contact

    )

@admin_bp.route("/delete_contact/<int:contact_id>")
def delete_contact(contact_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""

        DELETE FROM contact_messages

        WHERE id=%s

    """, (contact_id,))

    conn.commit()

    cursor.close()
    conn.close()

    flash(

        "Contact message deleted successfully.",

        "success"

    )

    return redirect(url_for("admin.manage_contacts"))

@admin_bp.route("/add_faq", methods=["GET", "POST"])
def add_faq():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    if request.method == "POST":

        question = request.form["question"].strip()

        answer = request.form["answer"].strip()

        display_order = request.form["display_order"]

        status = request.form["status"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""

            INSERT INTO faq
            (

                question,

                answer,

                display_order,

                status

            )

            VALUES
            (

                %s,

                %s,

                %s,

                %s

            )

        """, (

            question,

            answer,

            display_order,

            status

        ))

        conn.commit()

        cursor.close()
        conn.close()

        flash(
            "FAQ added successfully.",
            "success"
        )

        return redirect(url_for("admin.manage_faq"))

    return render_template(
        "admin/add_faq.html"
    )

@admin_bp.route("/manage_faq")
def manage_faq():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    search = request.args.get("search", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    if search:

        cursor.execute("""

            SELECT *

            FROM faq

            WHERE question LIKE %s

            ORDER BY display_order ASC

        """, ("%" + search + "%",))

    else:

        cursor.execute("""

            SELECT *

            FROM faq

            ORDER BY display_order ASC

        """)

    faqs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(

        "admin/manage_faq.html",

        faqs=faqs,

        search=search

    )

@admin_bp.route("/edit_faq/<int:faq_id>", methods=["GET", "POST"])
def edit_faq(faq_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""

        SELECT *

        FROM faq

        WHERE id=%s

    """, (faq_id,))

    faq = cursor.fetchone()

    if not faq:

        cursor.close()
        conn.close()

        flash("FAQ not found.", "danger")

        return redirect(url_for("admin.manage_faq"))

    if request.method == "POST":

        question = request.form["question"].strip()

        answer = request.form["answer"].strip()

        display_order = request.form["display_order"]

        status = request.form["status"]

        cursor.execute("""

            UPDATE faq

            SET

                question=%s,

                answer=%s,

                display_order=%s,

                status=%s

            WHERE id=%s

        """, (

            question,

            answer,

            display_order,

            status,

            faq_id

        ))

        conn.commit()

        cursor.close()
        conn.close()

        flash("FAQ updated successfully.", "success")

        return redirect(url_for("admin.manage_faq"))

    cursor.close()
    conn.close()

    return render_template(

        "admin/edit_faq.html",

        faq=faq

    )

@admin_bp.route("/delete_faq/<int:faq_id>")
def delete_faq(faq_id):

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""

        DELETE FROM faq

        WHERE id=%s

    """, (faq_id,))

    conn.commit()

    cursor.close()
    conn.close()

    flash(

        "FAQ deleted successfully.",

        "success"

    )

    return redirect(url_for("admin.manage_faq"))

@admin_bp.route("/admin_profile")
def admin_profile():

    if "admin_id" not in session:

        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""

        SELECT

            id,
            name,
            name,
            email

        FROM admin

        WHERE id=%s

    """, (session["admin_id"],))

    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    if not admin:

        flash(
            "Admin not found.",
            "danger"
        )

        return redirect(
            url_for("admin.dashboard")
        )

    return render_template(

        "admin/admin_profile.html",

        admin=admin

    )

@admin_bp.route("/edit_admin_profile", methods=["GET", "POST"])
def edit_admin_profile():

    if "admin_id" not in session:

        return redirect(url_for("admin.admin_login"))

    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]

        cursor.execute("""

            UPDATE admin

            SET

                name=%s,

                email=%s

            WHERE id=%s

        """, (

            name,

            email,

            session["admin_id"]

        ))

        conn.commit()

        session["admin_name"] = name
        session["admin_email"] = email

        flash(

            "Profile updated successfully.",

            "success"

        )

        cursor.close()
        conn.close()

        return redirect(
            url_for("admin.admin_profile")
        )

    cursor.execute("""

        SELECT

            id,

            name,

            email

        FROM admin

        WHERE id=%s

    """, (session["admin_id"],))

    admin = cursor.fetchone()

    cursor.close()
    conn.close()

    return render_template(

        "admin/edit_admin_profile.html",

        admin=admin

    )

@admin_bp.route("/change_admin_password", methods=["GET", "POST"])
def change_admin_password():

    if "admin_id" not in session:
        return redirect(url_for("admin.admin_login"))

    if request.method == "POST":

        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""

            SELECT password

            FROM admin

            WHERE id=%s

        """, (session["admin_id"],))

        admin = cursor.fetchone()

        if admin["password"] != current_password:

            flash(
                "Current password is incorrect.",
                "danger"
            )

            cursor.close()
            conn.close()

            return redirect(
                url_for("admin.change_admin_password")
            )

        if new_password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            cursor.close()
            conn.close()

            return redirect(
                url_for("admin.change_admin_password")
            )

        cursor.execute("""

            UPDATE admin

            SET password=%s

            WHERE id=%s

        """, (

            new_password,

            session["admin_id"]

        ))

        conn.commit()

        cursor.close()
        conn.close()

        flash(
            "Password updated successfully.",
            "success"
        )

        return redirect(
            url_for("admin.admin_profile")
        )

    return render_template(
        "admin/change_admin_password.html"
    )