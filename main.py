from flask import Flask, redirect, request, session, url_for
from stravalib import Client
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = "some_secret_key"


@app.route("/")
def index():
    client = Client()
    url = client.authorization_url(
        client_id=os.getenv("CLIENT_ID"),
        redirect_uri=url_for("logged_in", _external=True),
        approval_prompt="auto",
    )
    return redirect(url)


@app.route("/logged_in")
def logged_in():
    code = request.args.get("code")
    client = Client()
    tokens = client.exchange_code_for_token(
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
        code=code,
    )
    session["access_token"] = tokens["access_token"]
    session["refresh_token"] = tokens["refresh_token"]

    with open("tokens.txt", "w") as f:
        f.write(f"{tokens['access_token']}\n{tokens['refresh_token']}")

    return "Logged in and tokens saved"


if __name__ == "__main__":
    app.run(debug=True)
