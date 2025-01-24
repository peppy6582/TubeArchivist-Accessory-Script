#!/usr/bin/env python3

import logging
from pathlib import Path
from typing import Dict, Set, Optional, List, Union
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import requests
import apprise
import yaml
from time import sleep
from collections import defaultdict
import time

# Logging configuration
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
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.processed_files = self._load_processed_files()
        self.apprise_client = self._setup_apprise()
        self.api_quota_remaining = 1000
        self.processed_channels = defaultdict(list)
        self.deleted_files = defaultdict(list)
        self.video_id_map = {}

    def _load_config(self, path: str) -> Dict[str, Optional[str]]:
        """Load configuration from a YAML file."""
        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
            
        if config.get("channel_specific_delete_after", False):
             if "channels" not in config:
                config["channels"] = self._discover_channels(config.get("channels_directory"))
                config["channels"] = {channel: {"delete_after": None} for channel in config["channels"]}
             else:
                 discovered_channels = self._discover_channels(config.get("channels_directory"))
                 existing_channels = config["channels"]

                 if isinstance(existing_channels, list):
                     config["channels"] = {channel: {"delete_after": None} for channel in existing_channels}
                     existing_channels = config["channels"]
                    

                 if isinstance(existing_channels, dict):
                     for channel in discovered_channels:
                         if channel not in existing_channels:
                               existing_channels[channel] = {"delete_after": None}

                         elif isinstance(existing_channels[channel], dict) and "delete_after" not in existing_channels[channel]:
                             existing_channels[channel]["delete_after"] = None
                     
                 config["channels"] = existing_channels
        elif "channels" in config:
            del config["channels"]


        return config

    def _discover_channels(self, channels_dir_path: Optional[str]) -> List[str]:
        """Discover channel directories in the specified directory."""
        if not channels_dir_path:
            return []

        channels_dir = Path(channels_dir_path)
        if not channels_dir.is_dir():
            logger.warning(f"Channels directory does not exist: {channels_dir}")
            return []
        
        return [d.name for d in channels_dir.iterdir() if d.is_dir()]

    def _load_processed_files(self) -> Set[str]:
        tracker_path = Path(self.config["processed_files_tracker"])
        return set(tracker_path.read_text().splitlines()) if tracker_path.exists() else set()

    def _setup_apprise(self) -> Optional[apprise.Apprise]:
        """Set up Apprise for notifications if configured."""
        if url := self.config.get("apprise_url"):
            client = apprise.Apprise()
            client.add(url)
            return client
        return None

    @lru_cache(maxsize=1000)
    def get_video_metadata(self, video_id: str) -> Optional[VideoMetadata]:
        """Fetch video metadata using YouTube API."""
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
                        "key": self.config["youtube_api_key"]
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
        """Get or create the destination directory and file info for a video."""
        if video_id not in self.video_id_map:
            if metadata := self.get_video_metadata(video_id):
                channel_name = self._map_uploader_to_channel(metadata.uploader)
                channel_dir = Path(self.config["channels_directory"]) / channel_name
                channel_dir.mkdir(parents=True, exist_ok=True)
                base_filename = self._sanitize_filename(metadata.title)

                self.video_id_map[video_id] = {
                    "metadata": metadata,
                    "channel_dir": channel_dir,
                    "base_filename": base_filename,
                }
                self.processed_channels[channel_name].append(metadata.title)
            else:
                return None

        return self.video_id_map[video_id]
    
    def _map_uploader_to_channel(self, uploader: str) -> str:
        """Map the uploader name to a configured channel, or default to 'Other'."""
        if "channels" in self.config:
            for channel in self.config["channels"]:
                channel_name = channel if isinstance(channel, str) else channel if isinstance(channel, dict) else list(channel.keys())[0]
                if self._sanitize_filename(uploader) == self._sanitize_filename(channel_name):
                    return channel_name
        return "Other"

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a filename to allow only safe characters."""
        allowed_chars = "-_.()[], '\""
        return "".join(c if c.isalnum() or c in allowed_chars else "_" for c in name)[:255]

    def _process_file(self, file_path: Path) -> bool:
        """Process a single file."""
        try:
            video_id = file_path.stem.split('.')[0]

            if not (dest_info := self._get_destination_info(video_id)):
                return False

            # Determine the new filename
            new_filename = dest_info['base_filename'] + file_path.suffix

            # Rename the file
            file_path.rename(dest_info['channel_dir'] / new_filename)

            # Handle .nfo generation for video and JSON files
            if file_path.suffix in self.FILE_TYPES['video']:
                # For video files, generate .nfo based on the video metadata
                nfo_path = dest_info['channel_dir'] / f"{dest_info['base_filename']}.nfo"
                self._generate_nfo(dest_info['metadata'], nfo_path)

            elif file_path.suffix == '.json':
                # For JSON files, convert to .nfo with the same base filename
                nfo_path = dest_info['channel_dir'] / f"{dest_info['base_filename']}.nfo"
                self._convert_json_to_nfo(file_path, nfo_path)

            return True
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            return False

    def _generate_nfo(self, metadata: VideoMetadata, path: Path) -> None:
        """Generate an .nfo file for a video."""
        content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<movie>
    <title>{metadata.title}</title>
    <plot>{metadata.description}</plot>
    <studio>{metadata.uploader}</studio>
    <premiered>{metadata.upload_date}</premiered>
</movie>"""
        path.write_text(content, encoding="utf-8")

    def _convert_json_to_nfo(self, json_path: Path, nfo_path: Path) -> None:
        """Convert a JSON file to an NFO file."""
        try:
            data = json_path.read_text(encoding="utf-8")
            nfo_content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<nfo>
    <content>{data}</content>
</nfo>"""
            nfo_path.write_text(nfo_content, encoding="utf-8")
            logger.info(f"Converted {json_path} to {nfo_path}")
        except Exception as e:
            logger.error(f"Failed to convert {json_path} to NFO: {e}")
    
    def _get_channel_delete_after(self, channel_name: str) -> Optional[int]:
        """Get the delete_after value for a channel, or the global value if none is set."""
        if self.config.get("channel_specific_delete_after", False):
            if "channels" in self.config:
                for channel, config_values in self.config["channels"].items():
                     if self._sanitize_filename(channel) == self._sanitize_filename(channel_name):
                           if isinstance(config_values, dict) and "delete_after" in config_values:
                                if config_values["delete_after"] is not None:
                                    return int(config_values["delete_after"])
                                else:
                                    return None
        if "delete_after" in self.config:
            if self.config["delete_after"] is not None:
                return int(self.config["delete_after"])
        return None

    def cleanup_old_files(self) -> None:
        """Delete files older than DELETE_AFTER days if configured."""
        channels_dir = Path(self.config["channels_directory"])
        if not channels_dir.exists():
            return

        for channel in channels_dir.iterdir():
            if channel.is_dir():
                delete_after = self._get_channel_delete_after(channel.name)

                if not delete_after:
                    logger.info(f"No DELETE_AFTER set for {channel.name}, not deleting files.")
                    continue
                
                cutoff_time = time.time() - (delete_after * 86400)
                deleted_count = 0
                deleted_files_list = []
                
                for file_path in channel.rglob("*"):
                    try:
                        if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                            file_name = file_path.name
                            file_path.unlink()
                            deleted_files_list.append(file_name)
                            deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path}: {e}")
                if deleted_count > 0:
                    self.deleted_files[channel.name] = deleted_files_list
                    self.deleted_files[channel.name].append(f"Total files deleted: {deleted_count}")

    def _send_notification(self) -> None:
        """Send notifications for processed and deleted files using Apprise."""
        if not self.apprise_client:
            return

        try:
            message_parts = []
            
            if self.processed_channels:
                message_parts.append("Processed Files:")
                summary = [f"{channel}: {len(videos)} videos" for channel, videos in self.processed_channels.items()]
                details = [f"  - {title}" for videos in self.processed_channels.values() for title in videos]
                message_parts.extend(summary + details)
                message_parts.append(f"Total videos processed: {sum(len(v) for v in self.processed_channels.values())}")
            
            if self.deleted_files:
               if any(len(v) > 0 for v in self.deleted_files.values()):
                    if message_parts:  # Add blank line if processed files exist
                        message_parts.append("")
                    message_parts.append("Deleted Files:")
                    summary = [f"{channel}: {len(files)} files" for channel, files in self.deleted_files.items()]
                    details = [f"  - {file}" for files in self.deleted_files.values() for file in files]
                    message_parts.extend(summary + details)
                    message_parts.append(f"Total files deleted: {sum(len(v) for v in self.deleted_files.values()) - sum(1 for v in self.deleted_files.values() if isinstance(v[-1], str) and 'Total files deleted:' in v[-1])}")

            if message_parts:
                self.apprise_client.notify(
                    title="YouTube Video Processing Report",
                    body="\n".join(message_parts)
                )
        except Exception as e:
            logger.error(f"Notification failed: {e}")

    def _refresh_channels_dvr(self) -> None:
        """Trigger Channels DVR to refresh its library."""
        if url := self.config.get("channels_dvr_api_refresh_url"):
            try:
                requests.put(url, timeout=10).raise_for_status()
                logger.info("Channels DVR metadata refresh completed.")
            except Exception as e:
                logger.error(f"Channels DVR refresh failed: {e}")

    def process_videos(self) -> None:
        """Process all videos in the directory."""
        try:
            video_dir = Path(self.config["video_directory"])
            files = [f for f in video_dir.rglob("*")
                     if f.suffix.lower() in (self.FILE_TYPES['video'] | self.FILE_TYPES['auxiliary'])
                     and f.name not in self.processed_files]

            with ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(self._process_file, files))
            
            # Persist the changes to the config if needed
            with open(self.config_path, "w") as f:
                yaml.dump(self.config, f)

            self.cleanup_old_files()

            if self.apprise_client:
                self._send_notification()

            self._refresh_channels_dvr()

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise

if __name__ == "__main__":
    processor = VideoProcessor("config.yaml")
    processor.process_videos()
