#!/usr/bin/env python3

import os
import re
import json
import requests
from pathlib import Path
import apprise  # Apprise library for notifications


def load_config(config_file):
    """Load configuration variables from a text file."""
    config = {}
    with open(config_file, "r") as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith("#"):  # Ignore empty lines and comments
                key, value = line.split("=", 1)
                config[key.strip()] = value.strip()
    return config


# Load configuration
CONFIG_FILE = "config.txt"  # Path to the configuration file
CONFIG = load_config(CONFIG_FILE)

# Configuration variables
VIDEO_DIRECTORY = CONFIG["VIDEO_DIRECTORY"]
CHANNELS_DIRECTORY = CONFIG["CHANNELS_DIRECTORY"]
PROCESSED_FILES_TRACKER = CONFIG["PROCESSED_FILES_TRACKER"]
YOUTUBE_API_KEY = CONFIG["YOUTUBE_API_KEY"]
APPRISE_URL = CONFIG.get("APPRISE_URL")  # Apprise URL for notifications
CHANNELS_DVR_API_REFRESH_URL = CONFIG.get("CHANNELS_DVR_API_REFRESH_URL")  # Optional
VIDEO_EXTENSIONS = (".mp4", ".mkv", ".webm", ".avi", ".mov")


def log(message):
    print(message)


def load_processed_files():
    return set(open(PROCESSED_FILES_TRACKER).read().splitlines()) if os.path.exists(PROCESSED_FILES_TRACKER) else set()


def save_processed_file(file_name):
    with open(PROCESSED_FILES_TRACKER, "a") as file:
        file.write(f"{file_name}\n")


def get_video_metadata(video_id):
    try:
        params = {"part": "snippet", "id": video_id, "key": YOUTUBE_API_KEY}
        response = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params)
        response.raise_for_status()
        data = response.json()
        if data.get("items"):
            snippet = data["items"][0]["snippet"]
            return {
                "title": snippet.get("title", "Unknown Title"),
                "description": snippet.get("description", "No Description"),
                "uploader": snippet.get("channelTitle", "Unknown Uploader"),
                "upload_date": snippet.get("publishedAt", "Unknown Date"),
            }
    except Exception as e:
        log(f"Failed to fetch metadata for video ID {video_id}: {e}")
    return None


def generate_nfo(metadata, nfo_path):
    """Generate the NFO content and save it to a file."""
    content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<movie>
  <title>{metadata.get('title', 'Unknown Title')}</title>
  <plot>{metadata.get('description', 'No description available')}</plot>
  <studio>{metadata.get('uploader', 'Unknown uploader')}</studio>
  <premiered>{metadata.get('upload_date', 'Unknown date')}</premiered>
</movie>
"""
    with open(nfo_path, "w", encoding="utf-8") as file:
        file.write(content)
    log(f"Generated NFO: {nfo_path}")


def sanitize_title(title):
    """Sanitize the title for valid filenames."""
    return re.sub(r'[<>:"/\\|?*]', "_", title)[:255]


def rename_file(file_path, new_title):
    """Rename the file and return the new path."""
    new_path = os.path.join(os.path.dirname(file_path), sanitize_title(new_title) + os.path.splitext(file_path)[1])
    os.rename(file_path, new_path)
    log(f"Renamed file: {file_path} -> {new_path}")
    return new_path


def move_file(file_path, uploader):
    """Move the file to the uploader's directory."""
    channel_dir = os.path.join(CHANNELS_DIRECTORY, uploader)
    os.makedirs(channel_dir, exist_ok=True)
    new_path = os.path.join(channel_dir, os.path.basename(file_path))
    os.rename(file_path, new_path)
    log(f"Moved file: {file_path} -> {new_path}")
    return new_path


def send_notification(processed_channels):
    """Send a notification using Apprise with the processed titles."""
    if not APPRISE_URL:
        log("Notification skipped: Missing APPRISE_URL in config.")
        return

    apprise_client = apprise.Apprise()
    apprise_client.add(APPRISE_URL)

    # Build the summary message
    message_lines = []
    total_videos = 0

    for channel, videos in processed_channels.items():
        message_lines.append(f"{channel}: {len(videos)} videos")
        for title in videos:
            message_lines.append(f"  - {title}")
        total_videos += len(videos)

    message_lines.append(f"Total videos processed: {total_videos}")
    message = "\n".join(message_lines)

    # Send the notification
    try:
        apprise_client.notify(
            title="YouTube Video Processing Completed",
            body=message,
        )
        log("Notification sent via Apprise.")
    except Exception as e:
        log(f"Failed to send notification: {e}")


def refresh_channels_dvr():
    """Trigger a Channels DVR metadata refresh if the URL is configured."""
    if not CHANNELS_DVR_API_REFRESH_URL:
        log("Channels DVR metadata refresh skipped: Missing URL in config.")
        return

    try:
        response = requests.put(CHANNELS_DVR_API_REFRESH_URL)
        response.raise_for_status()
        log("Channels DVR metadata refresh triggered.")
    except requests.RequestException as e:
        log(f"Failed to refresh Channels DVR: {e}")


def process_videos():
    """Process video files: generate NFO, rename files, and move them."""
    processed_files = load_processed_files()
    processed_channels = {}  # Dictionary to track processed videos by channel

    for root, _, files in os.walk(VIDEO_DIRECTORY):
        for file in files:
            if file in processed_files or not file.endswith(VIDEO_EXTENSIONS):
                continue

            file_path = os.path.join(root, file)
            video_id = os.path.splitext(file)[0]
            metadata = get_video_metadata(video_id)

            if metadata:
                uploader = metadata["uploader"]
                title = metadata["title"]

                # Generate NFO before renaming
                nfo_path = os.path.join(root, f"{video_id}.nfo")
                generate_nfo(metadata, nfo_path)

                # Rename the video file
                renamed_path = rename_file(file_path, title)

                # Rename the NFO file to match the renamed video file
                new_nfo_path = renamed_path.replace(os.path.splitext(renamed_path)[1], ".nfo")
                os.rename(nfo_path, new_nfo_path)
                log(f"Renamed NFO file: {nfo_path} -> {new_nfo_path}")

                # Move the video file and its NFO to the uploader's directory
                move_file(renamed_path, uploader)
                move_file(new_nfo_path, uploader)

                # Mark the video file as processed
                save_processed_file(file)

                # Add the video title to the uploader's list in the dictionary
                if uploader not in processed_channels:
                    processed_channels[uploader] = []
                processed_channels[uploader].append(title)

    # Send notification with detailed channel info
    send_notification(processed_channels)

    # Trigger Channels DVR metadata refresh
    refresh_channels_dvr()


if __name__ == "__main__":
    process_videos()
