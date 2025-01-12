#!/usr/bin/env python3

import logging
from pathlib import Path
from typing import Dict, Set, Optional, Tuple, List
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import requests
import apprise
from time import sleep
from collections import defaultdict
import time
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class VideoMetadata:
    title: str
    description: str
    uploader: str
    upload_date: str

class VideoProcessor:
    FILE_TYPES = {
        'video': {'.mp4', '.mkv', '.webm', '.avi', '.mov'},
        'auxiliary': {'.json', '.vtt'}
    }

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.processed_files = self._load_processed_files()
        self.apprise_client = self._setup_apprise()
        self.api_quota_remaining = 1000
        self.processed_channels = defaultdict(list)
        self.deleted_files = defaultdict(list)
        self.video_id_map = {}

    def _load_config(self, path: str) -> Dict[str, str]:
        with open(path, "r") as f:
            return dict(line.strip().split("=", 1) for line in f 
                       if line.strip() and not line.startswith("#"))

    def _load_processed_files(self) -> Set[str]:
        tracker_path = Path(self.config["PROCESSED_FILES_TRACKER"])
        return set(tracker_path.read_text().splitlines()) if tracker_path.exists() else set()

    def _setup_apprise(self) -> Optional[apprise.Apprise]:
        if url := self.config.get("APPRISE_URL"):
            client = apprise.Apprise()
            client.add(url)
            return client
        return None

    @lru_cache(maxsize=1000)
    def get_video_metadata(self, video_id: str) -> Optional[VideoMetadata]:
        if self.api_quota_remaining <= 0:
            logger.warning("API quota exceeded")
            return None

        for attempt in range(3):
            try:
                response = requests.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "snippet",
                        "id": video_id,
                        "key": self.config["YOUTUBE_API_KEY"]
                    },
                    timeout=10
                ).json()

                self.api_quota_remaining -= 1

                if items := response.get("items"):
                    snippet = items[0]["snippet"]
                    return VideoMetadata(
                        title=snippet.get("title", "Unknown Title"),
                        description=snippet.get("description", "No Description"),
                        uploader=snippet.get("channelTitle", "Unknown Uploader"),
                        upload_date=snippet.get("publishedAt", "Unknown Date")
                    )
                return None

            except Exception as e:
                logger.error(f"Metadata fetch attempt {attempt + 1}/3 failed: {e}")
                if attempt < 2:
                    sleep(2 ** attempt)

        return None

    def _get_destination_info(self, video_id: str) -> Optional[Dict]:
        if video_id not in self.video_id_map:
            if metadata := self.get_video_metadata(video_id):
                channel_dir = Path(self.config["CHANNELS_DIRECTORY"]) / self._format_channel_name(metadata.uploader)
                channel_dir.mkdir(parents=True, exist_ok=True)
                
                self.video_id_map[video_id] = {
                    'metadata': metadata,
                    'channel_dir': channel_dir,
                    'base_filename': self._format_title(metadata.title)
                }
                
                self.processed_channels[metadata.uploader].append(metadata.title)
            else:
                return None
                
        return self.video_id_map[video_id]

    @staticmethod
    def _format_channel_name(name: str) -> str:
        """Preserve formatting for channel names."""
        allowed_chars = ".-_', ()[]"
        return "".join(c if c.isalnum() or c in allowed_chars else "_" for c in name)

    @staticmethod
    def _format_title(name: str) -> str:
        """
        Format title with proper patterns:
        - Preserves spaces around hyphens
        - Preserves parentheses formatting
        - Preserves apostrophes
        - Allows hyphens in the title structure
        Example: "Title - Channel Name (Season 1)" structure
        """
        # Split the name into parts using hyphen (`-`) as a separator
        parts = name.split('-')

        # Ensure at least a title and a channel part are present
        if len(parts) >= 2:
            title = parts[0].strip()
            channel = parts[1].strip()

            # Check if there's a third part (like an episode or season)
            if len(parts) >= 3:
                episode = parts[2].strip()

                # Format episode if it starts with 'S' (e.g., S1, S2)
                if episode.startswith('S'):
                    episode = f"({episode})"
                name = f"{title} - {channel} {episode}"
            else:
                name = f"{title} - {channel}"

        # Define allowed characters for the title
        allowed_chars = ".-_', ()[]"

        # Filter out unwanted characters and limit length to 255 characters
        return "".join(c if c.isalnum() or c in allowed_chars else "_" for c in name)[:255]

    def _process_file(self, file_path: Path) -> bool:
        try:
            video_id = file_path.stem.split('.')[0]
            
            if not (dest_info := self._get_destination_info(video_id)):
                return False

            new_filename = dest_info['base_filename']
            if '.lang.' in file_path.name:
                new_filename = f"{new_filename}.{file_path.stem.split('.')[-1]}"
            new_filename = f"{new_filename}{file_path.suffix}"
            
            if file_path.suffix in self.FILE_TYPES['video']:
                nfo_path = dest_info['channel_dir'] / f"{new_filename}.nfo"
                self._generate_nfo(dest_info['metadata'], nfo_path)

            file_path.rename(dest_info['channel_dir'] / new_filename)
            return True

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            return False

    def _generate_nfo(self, metadata: VideoMetadata, path: Path) -> None:
        content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<movie>
    <title>{metadata.title}</title>
    <plot>{metadata.description}</plot>
    <studio>{metadata.uploader}</studio>
    <premiered>{metadata.upload_date}</premiered>
</movie>"""
        path.write_text(content, encoding="utf-8")

    def cleanup_old_files(self) -> None:
        """Delete files older than DELETE_AFTER days if configured."""
        delete_after = self.config.get("DELETE_AFTER")

        if not delete_after:  # Check if DELETE_AFTER is None or an empty string
            logger.info("No DELETE_AFTER set, not deleting files.")
            return

        try:
            days = int(delete_after)
        except ValueError:
            logger.error(f"Invalid DELETE_AFTER value: {delete_after}")
            return

        channels_dir = Path(self.config["CHANNELS_DIRECTORY"])
        if not channels_dir.exists():
            return

        cutoff_time = time.time() - (days * 86400)
        deleted_count = 0
        deleted_size = 0

        logger.info(f"Starting cleanup of files older than {days} days")

        # Clear previous deletion records
        self.deleted_files.clear()

        for file_path in channels_dir.rglob("*"):
            if not file_path.is_file():
                continue

            try:
                if file_path.stat().st_mtime < cutoff_time:
                    size = file_path.stat().st_size
                    channel_name = file_path.parent.name
                    base_name = file_path.stem
                    self.deleted_files[channel_name].append(base_name)

                    file_path.unlink()
                    deleted_count += 1
                    deleted_size += size
                    logger.debug(f"Deleted: {file_path}")
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")

        if deleted_size > 1073741824:
            size_str = f"{deleted_size / 1073741824:.2f} GB"
        else:
            size_str = f"{deleted_size / 1048576:.2f} MB"

        logger.info(f"Cleanup completed: Deleted {deleted_count} files ({size_str})")

        for dir_path in sorted(channels_dir.rglob("*"), reverse=True):
            if dir_path.is_dir():
                try:
                    dir_path.rmdir()
                except OSError:
                    pass

    def process_videos(self) -> None:
        try:
            video_dir = Path(self.config["VIDEO_DIRECTORY"])
            files = [f for f in video_dir.rglob("*") 
                    if f.suffix.lower() in (self.FILE_TYPES['video'] | self.FILE_TYPES['auxiliary'])
                    and f.name not in self.processed_files]

            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(self._process_file, files))

            with open(self.config["PROCESSED_FILES_TRACKER"], "a") as f:
                f.writelines(f"{file.name}\n" for file, success 
                           in zip(files, results) if success)

            # Run cleanup before notification
            self.cleanup_old_files()
            
            # Send notification if there are any processed OR deleted files
            if self.apprise_client and (self.processed_channels or self.deleted_files):
                self._send_notification()

            self._refresh_channels_dvr()

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise

    def _send_notification(self) -> None:
        if not self.apprise_client:
            return

        try:
            message_parts = []
            
            # Processed files section
            if self.processed_channels:
                message_parts.append("Processed Files:")
                summary = [f"{channel}: {len(videos)} videos" for channel, videos in self.processed_channels.items()]
                details = [f"  - {title}" for videos in self.processed_channels.values() for title in videos]
                message_parts.extend(summary + details)
                message_parts.append(f"Total videos processed: {sum(len(v) for v in self.processed_channels.values())}")
            
            # Deleted files section
            if self.deleted_files:
                if message_parts:  # Add blank line if there were processed files
                    message_parts.append("")
                message_parts.append("Deleted Files:")
                del_summary = [f"{channel}: {len(files)} files" for channel, files in self.deleted_files.items()]
                del_details = [f"  - {title}" for files in self.deleted_files.values() for title in files]
                message_parts.extend(del_summary + del_details)
                message_parts.append(f"Total files deleted: {sum(len(v) for v in self.deleted_files.values())}")
            
            if message_parts:  # Only send if there's something to report
                self.apprise_client.notify(
                    title="YouTube Video Processing Report",
                    body="\n".join(message_parts)
                )
        except Exception as e:
            logger.error(f"Notification failed: {e}")

    def _refresh_channels_dvr(self) -> None:
        if url := self.config.get("CHANNELS_DVR_API_REFRESH_URL"):
            try:
                requests.put(url, timeout=10).raise_for_status()
                logger.info("Channels DVR metadata refresh completed")
            except Exception as e:
                logger.error(f"Channels DVR refresh failed: {e}")

if __name__ == "__main__":
    processor = VideoProcessor("config.txt")
    processor.process_videos()
