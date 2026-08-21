from flask import Flask ,session
from routes.user import user_bp
from flask_mail import Mail
from database.db import get_connection
app = Flask(__name__)

app.secret_key = "swastik_secret_key"

app.register_blueprint(user_bp)

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "swastiholidays0919@gmail.com"
app.config["MAIL_PASSWORD"] = "dwsd kloj bisx sqvv"
app.config["MAIL_DEFAULT_SENDER"] = "swastiholidays0919@gmail.com"

mail = Mail(app)

@app.context_processor
def wishlist_count():

    count = 0

    if "customer_id" in session:

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM wishlist
            WHERE customer_id=%s
        """, (session["customer_id"],))

        count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

    return dict(wishlist_count=count)

if __name__ == "__main__":
    app.run(debug=True)