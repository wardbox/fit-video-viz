from stravalib import Client
import os
import glob
from pytz import timezone
import fitdecode
import datetime
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageSequenceClip, VideoFileClip, concatenate_videoclips
import math
import gc
import argparse
from tqdm import tqdm


with open("tokens.txt", "r") as f:
    access_token, refresh_token = f.read().strip().split("\n")

client = Client(access_token=access_token)


def get_activities(access_token, limit=10):
    client = Client(access_token=access_token)
    activities = client.get_activities(limit=limit)
    return activities


def get_activity_and_streams(access_token, id):
    client = Client(access_token=access_token)
    activity = client.get_activity(id)
    streams = client.get_activity_streams(
        id,
        types=["latlng", "time", "altitude", "heartrate", "temp", "moving"],
        series_type="time",
        resolution="high",
    )
    return activity, streams


def create_overlay_images(fields, font, fps, output_folder):
    width = 500
    height = 120

    field_coordinates = (20, 20)

    raw_frames = []
    filled_frames = []

    with fitdecode.FitReader("test.fit") as fit:
        for frame in fit:
            if isinstance(frame, fitdecode.FitDataMessage) and frame.name == "record":
                data = {}
                for field in frame.fields:
                    data[field.name] = field.value

                raw_frames.append(data)

    for idx in range(len(raw_frames)):
        if idx == 0:
            filled_frames.append(raw_frames[idx])
            continue

        prev_frame = raw_frames[idx - 1]
        curr_frame = raw_frames[idx]

        time_diff = curr_frame["timestamp"] - prev_frame["timestamp"]
        gap_seconds = int(time_diff.total_seconds())

        if gap_seconds > 1:
            start_rate = prev_frame["heart_rate"]
            end_rate = curr_frame["heart_rate"]
            rate_diff = end_rate - start_rate

            # Calculate gradient
            gradient = rate_diff / gap_seconds

            fill_time = prev_frame["timestamp"]
            last_rate = start_rate
            for _ in range(gap_seconds - 1):
                fill_time += datetime.timedelta(seconds=1)
                last_rate += gradient
                filled_frame = {"timestamp": fill_time, "heart_rate": last_rate}
                filled_frames.append(filled_frame)

        filled_frames.append(curr_frame)

    total_seconds = len(filled_frames)
    total_frames = round(total_seconds * fps)
    batch_size = 1440
    num_batches = math.ceil(total_frames / batch_size)

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for field in ["heartrate", "time"]:
        for batch_num in tqdm(
            range(num_batches), desc=f"Processing {field}", colour="green"
        ):
            overlay_batch = []
            start_frame = batch_num * batch_size
            end_frame = min((batch_num + 1) * batch_size, total_frames)

            for frame_num in tqdm(
                range(start_frame, end_frame),
                desc=f"Batch {batch_num}",
                colour="blue",
                leave=False,
            ):
                img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)

                # Find corresponding index in the 'filled_frames' list
                index = int(frame_num // fps)

                if index < len(filled_frames):
                    if field == "heartrate":
                        # heartrate might not be there
                        if "heart_rate" in filled_frames[index]:
                            value = str(round(filled_frames[index]["heart_rate"]))
                        else:
                            value = "0"
                    elif field == "time":
                        dt_value = filled_frames[index]["timestamp"]
                        # Convert to local time
                        dt_value = dt_value.astimezone(timezone("US/Pacific"))
                        value = dt_value.strftime("%H:%M:%S")

                    # do temp later

                    x, y = field_coordinates
                    draw.text((x, y), value, fill=(250, 225, 2), font=font)

                overlay_batch.append(np.array(img.convert("RGBA")))

            overlay_clip = ImageSequenceClip(overlay_batch, fps=fps)
            overlay_clip.write_videofile(
                os.path.join(
                    output_folder, f"{field}_batch_{str(batch_num).zfill(4)}.mov"
                ),
                codec="png",
                logger=None,
                audio=False,
                preset="ultrafast",
            )
            del overlay_batch
            if overlay_clip is not None:
                del overlay_clip
            gc.collect()

        # Reading saved overlay images into a list
        video_files = sorted(glob.glob(f"{output_folder}/{field}_*.mov"))
        video_file_clips = []
        for video in video_files:
            video_file_clips.append(VideoFileClip(video))

        final_clip = concatenate_videoclips(video_file_clips)
        final_clip.write_videofile(f"{output_folder}/{field}.mov", codec="png")

        # Delete the overlay images
        for video in video_files:
            os.remove(video)

        if final_clip is not None:
            del final_clip
        gc.collect()

    return "Done"


def main(activity_id, access_token, fps=24, fields="heartrate,time,temp"):
    activity, streams = get_activity_and_streams(access_token, activity_id)

    font_path = r"C:\Windows\Fonts\BebasNeue-Bold.otf"
    font = ImageFont.truetype(font_path, size=100)
    output_folder = f"./output_folder/{activity.id}/"

    create_overlay_images(
        fields.split(","),
        font,
        fps,
        output_folder,
    )


if __name__ == "__main__":
    with open("tokens.txt", "r") as f:
        access_token, refresh_token = f.read().strip().split("\n")
    parser = argparse.ArgumentParser(
        description="Generate overlay videos for activity fields."
    )
    parser.add_argument(
        "--activity_id", required=True, help="The ID of the activity to process."
    )
    parser.add_argument("--fps", type=int, default=23.796, help="Frames per second.")
    parser.add_argument(
        "--fields", default="heartrate,time,temp,distance", help="Fields to process."
    )

    args = parser.parse_args()
    main(args.activity_id, access_token, args.fps, args.fields)
