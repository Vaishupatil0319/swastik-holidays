from flask import Flask
from routes.admin import admin_bp

app = Flask(__name__)

app.secret_key = "swastik_secret_key"

app.register_blueprint(admin_bp)

@app.route("/")
def home():
    return "<h2>Welcome to Swastik Holidays</h2>"

if __name__ == "__main__":
    app.run(debug=True)