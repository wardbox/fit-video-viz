#!flask/bin/python
import os
from datetime import timedelta
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import math
from dotenv import load_dotenv
from flask import Flask, render_template, request, url_for
from stravalib import Client
from moviepy.editor import ImageSequenceClip

load_dotenv()

app = Flask(__name__)
app.config["STRAVA_CLIENT_ID"] = os.getenv("CLIENT_ID")
app.config["STRAVA_CLIENT_SECRET"] = os.getenv("CLIENT_SECRET")


@app.route("/")
def login():
    c = Client()
    url = c.authorization_url(
        client_id=app.config["STRAVA_CLIENT_ID"],
        redirect_uri=url_for(".logged_in", _external=True),
        approval_prompt="auto",
    )
    return render_template("login.html", authorize_url=url)


@app.route("/strava-oauth")
def logged_in():
    """
    Method called by Strava (redirect) that includes parameters.
    - state
    - code
    - error
    """
    error = request.args.get("error")
    state = request.args.get("state")
    if error:
        return render_template("login_error.html", error=error)
    else:
        code = request.args.get("code")
        client = Client()
        access_token = client.exchange_code_for_token(
            client_id=app.config["STRAVA_CLIENT_ID"],
            client_secret=app.config["STRAVA_CLIENT_SECRET"],
            code=code,
        )
        # Probably here you'd want to store this somewhere -- e.g. in a database.
        # write access, refresh to local file
        with open("tokens.txt", "w") as f:
            f.write(access_token["access_token"])
            f.write("\n")
            f.write(access_token["refresh_token"])

        strava_athlete = client.get_athlete()

        # store athlete in json file
        with open("athlete.json", "w") as outfile:
            # convert athlete object to json
            athlete_json = strava_athlete.json()
            # write to file
            outfile.write(athlete_json)

        return render_template(
            "login_results.html",
            athlete=strava_athlete,
            access_token=access_token,
        )


# list all activities
@app.route("/activities")
def activities():
    # read access token from file
    with open("tokens.txt", "r") as f:
        access_token = f.readline().strip()
        refresh_token = f.readline().strip()

    client = Client(access_token=access_token)
    activities = client.get_activities()

    # display activities on page
    return render_template("activities.html", activities=activities)


# individual activity based on id
@app.route("/activity_detail/<id>")
def create_video(id):
    # read access token from file
    with open("tokens.txt", "r") as f:
        access_token = f.readline().strip()
        refresh_token = f.readline().strip()

    client = Client(access_token=access_token)
    activity = client.get_activity(id)

    types = ["time", "latlng", "altitude", "heartrate", "temp"]

    streams = client.get_activity_streams(id, types=types, resolution="high")

    temp_values = streams["temp"].data
    # Create a list of heartrate values
    heartrate_values = streams["heartrate"].data
    time_values = streams["time"].data  # Assume these are the timestamps

    # Get a subset of the heartrate and time values
    start_index = 1000
    end_index = 1100
    subset_heartrate_values = heartrate_values[start_index:end_index]
    subset_time_values = time_values[start_index:end_index]
    subset_temp_values = temp_values[start_index:end_index]

    font_path = r"C:\Windows\Fonts\BebasNeue-Bold.otf"
    font = ImageFont.truetype(font_path, size=100)

    overlay_images = []
    width = 1920
    height = 1080
    x = width - 400
    y = height - 200

    total_samples = len(heartrate_values)
    total_time = streams["time"].data[-1] - streams["time"].data[0]
    sampling_rate = total_samples / total_time  # samples per second

    samples_per_frame = math.ceil(sampling_rate / 24)
    averaged_heartrate_values = average_samples(
        subset_heartrate_values, samples_per_frame
    )
    averaged_time_values = average_samples(subset_time_values, samples_per_frame)
    averaged_temp_values = average_samples(subset_temp_values, samples_per_frame)

    frames_per_sample = 25  # Adjust as needed
    # Stretch the new data

    stretched_heartrate_values = []
    for hr in averaged_heartrate_values:
        stretched_heartrate_values.extend([hr] * frames_per_sample)

    stretched_time_values = []
    for timestamp in averaged_time_values:
        stretched_time_values.extend([timestamp] * frames_per_sample)

    stretched_temp_values = []
    for temp in averaged_temp_values:
        stretched_temp_values.extend([temp] * frames_per_sample)

    overlay_images = []
    for heart_rate, timestamp, temp in zip(
        stretched_heartrate_values,
        stretched_time_values,
        stretched_temp_values,
    ):
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Displaying Heart Rate, and Temp
        draw.text((x, y), f"{int(heart_rate)} BPM", fill=(250, 225, 2), font=font)
        draw.text(
            (x, y + 100),
            f"{timedelta(seconds=int(timestamp))}",
            fill=(250, 225, 2),
            font=font,
        )
        temp_fahrenheit = (temp * 9 / 5) + 32
        draw.text(
            (width - 400, height - 800),
            f"{round(temp_fahrenheit)} °F",
            fill=(250, 225, 2),
            font=font,
        )

        overlay_images.append(np.array(img.convert("RGBA")))

    overlay_clip = ImageSequenceClip(overlay_images, fps=24)
    overlay_clip.write_videofile(f"{id}.mov", codec="png")

    return render_template("activity.html", activity=activity)


def average_samples(data, samples_per_frame):
    averaged_data = []
    for i in range(0, len(data), samples_per_frame):
        avg_value = np.mean(data[i : i + samples_per_frame])
        averaged_data.append(avg_value)
    return averaged_data


if __name__ == "__main__":
    app.run(debug=True)
