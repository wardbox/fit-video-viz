from stravalib import Client
import os
import glob
import numpy as np
from scipy.interpolate import interp1d
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageSequenceClip, VideoFileClip, concatenate_videoclips
import math
import gc
from datetime import timedelta
import argparse
from tqdm import tqdm

# Read tokens from a file or receive them from your Flask app
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


def create_overlay_images(streams, fields, font, fps, total_seconds, output_folder):
    width = 500
    height = 120

    field_coordinates = {
        "heartrate": (20, 20),
        "time": (20, 20),
        "temp": (20, 20),
    }

    total_frames = round(total_seconds * fps)
    batch_size = 1440
    num_batches = math.ceil(total_frames / batch_size)

    total_samples = len(streams["time"].data)
    sampling_rate = total_samples / total_seconds
    frames_per_sample = round(fps / sampling_rate)

    stretched_heartrate_values = []
    for hr in streams["heartrate"].data:
        stretched_heartrate_values.extend([hr] * frames_per_sample)

    stretched_time_values = []
    for timestamp in streams["time"].data:
        stretched_time_values.extend([timestamp] * frames_per_sample)

    stretched_temp_values = []
    for temp in streams["temp"].data:
        stretched_temp_values.extend([temp] * frames_per_sample)

    # Create output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for field in fields:
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

                if field in streams:
                    if field == "heartrate":
                        if frame_num < len(stretched_heartrate_values):
                            value = str(int(stretched_heartrate_values[frame_num]))
                        else:
                            value = "N/A"
                    elif field == "time":
                        if frame_num < len(stretched_time_values):
                            value = str(stretched_time_values[frame_num])
                        else:
                            value = "N/A"
                    elif field == "temp":
                        value = (
                            str(int(stretched_temp_values[frame_num]))
                            if stretched_temp_values[frame_num] != "N/A"
                            else "N/A"
                        )

                    x, y = field_coordinates[field]
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
        streams,
        fields.split(","),
        font,
        fps,
        activity.elapsed_time.total_seconds(),
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
    parser.add_argument("--fps", type=int, default=24, help="Frames per second.")
    parser.add_argument(
        "--fields", default="heartrate,time,temp,distance", help="Fields to process."
    )

    args = parser.parse_args()
    main(args.activity_id, access_token, args.fps, args.fields)
