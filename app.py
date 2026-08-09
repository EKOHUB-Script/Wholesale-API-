from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "EKOHUB API is running!"

@app.route("/status")
def status():
    return {
        "status": "online",
        "service": "EKOHUB API"
    }
