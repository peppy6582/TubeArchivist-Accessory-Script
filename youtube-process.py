#!/usr/bin/env python3

import logging
from pathlib import Path
from typing import Dict, Set, Optional, Tuple, List, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import requests
import apprise
from time import sleep
from collections import defaultdict
import time
import json
import sqlite3
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class VideoMetadata:
    title: str
    description: str
    uploader: str
    upload_date: str

class VideoProcessor:
    # Class-level constants
    FILE_TYPES = {
        'video': {'.mp4', '.mkv', '.webm', '.avi', '.mov'},
        'auxiliary': {'.json', '.vtt'}
    }
    BATCH_SIZE = 50
    API_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
    DEFAULT_CACHE_DURATION = 30  # days

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.cache_db = self._setup_cache()
        self.cache_duration = timedelta(days=int(self.config.get("CACHE_DURATION_DAYS", 
                                                               str(self.DEFAULT_CACHE_DURATION))))
        self.processed_files = self._load_processed_files()
        self.apprise_client = self._setup_apprise()
        self.api_quota_remaining = 1000
        self.processed_channels = defaultdict(list)
        self.deleted_files = defaultdict(list)
        self.metadata_cache = {}
        self.video_id_map = {}

    def _load_config(self, path: str) -> Dict[str, str]:
        """Load configuration from file with error handling"""
        try:
            with open(path, "r") as f:
                return dict(line.strip().split("=", 1) for line in f 
                          if line.strip() and not line.startswith("#"))
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {path}")
        except Exception as e:
            raise RuntimeError(f"Error loading configuration: {e}")

    def _setup_cache(self) -> sqlite3.Connection:
        """Initialize SQLite cache database"""
        db_path = self.config.get("CACHE_DB", "youtube_cache.db")
        db = sqlite3.connect(db_path)
        db.execute("""
            CREATE TABLE IF NOT EXISTS api_cache (
                video_id TEXT PRIMARY KEY,
                response_data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                api_quota_cost INTEGER DEFAULT 1
            )
        """)
        db.commit()
        return db

    def _load_processed_files(self) -> Set[str]:
        """Load previously processed files"""
        tracker_path = Path(self.config["PROCESSED_FILES_TRACKER"])
        return set(tracker_path.read_text().splitlines()) if tracker_path.exists() else set()

    def _setup_apprise(self) -> Optional[apprise.Apprise]:
        """Initialize notification client"""
        if url := self.config.get("APPRISE_URL"):
            client = apprise.Apprise()
            client.add(url)
            return client
        return None

    def _get_cached_response(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached API response"""
        cursor = self.cache_db.cursor()
        cursor.execute("""
            SELECT response_data, timestamp
            FROM api_cache
            WHERE video_id = ?
        """, (video_id,))
        
        if result := cursor.fetchone():
            response_data, timestamp = result
            cache_time = datetime.fromisoformat(timestamp)
            
            if datetime.now() - cache_time <= self.cache_duration:
                return json.loads(response_data)
        
        return None

    def _cache_response(self, video_id: str, response_data: Dict[str, Any]) -> None:
        """Store API response in cache"""
        cursor = self.cache_db.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO api_cache (video_id, response_data)
            VALUES (?, ?)
        """, (video_id, json.dumps(response_data)))
        self.cache_db.commit()

    def _process_batch(self, video_ids: List[str]) -> Dict[str, VideoMetadata]:
        """Process a batch of video IDs in a single API call"""
        if not video_ids:
            return {}

        batch_size = len(video_ids)
        quota_saved = batch_size - 1
        logger.info(f"Processing batch of {batch_size} videos (saving {quota_saved} quota units)")

        try:
            response = requests.get(
                self.API_ENDPOINT,
                params={
                    "part": "snippet",
                    "id": ",".join(video_ids),
                    "key": self.config["YOUTUBE_API_KEY"]
                },
                timeout=10
            ).json()

            self.api_quota_remaining -= 1
            results = {}

            if "items" in response:
                for item in response["items"]:
                    video_id = item["id"]
                    snippet = item["snippet"]
                    metadata = VideoMetadata(
                        title=snippet.get("title", "Unknown Title"),
                        description=snippet.get("description", "No Description"),
                        uploader=snippet.get("channelTitle", "Unknown Uploader"),
                        upload_date=snippet.get("publishedAt", "Unknown Date")
                    )
                    results[video_id] = metadata
                    self._cache_response(video_id, {"items": [item]})

            if missed := set(video_ids) - set(results.keys()):
                logger.warning(f"Videos not found in batch: {missed}")

            return results

        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return {}

    @staticmethod
    def _format_channel_name(name: str) -> str:
        """Preserve formatting for channel names"""
        allowed_chars = ".-_', ()[]"
        return "".join(c if c.isalnum() or c in allowed_chars else "_" for c in name)

    @staticmethod
    def _format_title(name: str) -> str:
        """Format title preserving special characters and patterns"""
        parts = name.split('_')
        
        if len(parts) >= 3:
            title = parts[0]
            channel = parts[1].replace('*', "'")
            episode = parts[2].replace('*', '')
            
            if episode.startswith('S'):
                episode = f"({episode})"
            
            name = f"{title} - {channel} {episode}"
        
        allowed_chars = ".-_', ()[]"
        return "".join(c if c.isalnum() or c in allowed_chars else "_" for c in name)[:255]

    def _get_destination_info(self, video_id: str) -> Optional[Dict]:
        """Get or create destination information for a video"""
        if video_id not in self.video_id_map:
            if metadata := self.metadata_cache.get(video_id):
                channel_dir = Path(self.config["CHANNELS_DIRECTORY"]) / self._format_channel_name(metadata.uploader)
                channel_dir.mkdir(parents=True, exist_ok=True)
                
                self.video_id_map[video_id] = {
                    'metadata': metadata,
                    'channel_dir': channel_dir,
                    'base_filename': self._format_title(metadata.title)
                }
                
                self.processed_channels[metadata.uploader].append(metadata.title)
                
        return self.video_id_map.get(video_id)

    def _process_file(self, file_path: Path) -> bool:
        """Process a single file"""
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
        """Generate NFO file for video"""
        content = f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<movie>
    <title>{metadata.title}</title>
    <plot>{metadata.description}</plot>
    <studio>{metadata.uploader}</studio>
    <premiered>{metadata.upload_date}</premiered>
</movie>"""
        path.write_text(content, encoding="utf-8")

    def cleanup_old_files(self) -> None:
        """Delete files older than DELETE_AFTER days"""
        delete_after = self.config.get("DELETE_AFTER")
        if delete_after is None:
            logger.debug("DELETE_AFTER not configured, skipping cleanup")
            return

        try:
            days = int(delete_after)
            channels_dir = Path(self.config["CHANNELS_DIRECTORY"])
            if not channels_dir.exists():
                return

            cutoff_time = time.time() - (days * 86400)
            deleted_count = 0
            deleted_size = 0
            
            logger.info(f"Starting cleanup of files older than {days} days")
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

            size_str = (f"{deleted_size / 1073741824:.2f} GB" 
                       if deleted_size > 1073741824 
                       else f"{deleted_size / 1048576:.2f} MB")
            
            logger.info(f"Cleanup completed: Deleted {deleted_count} files ({size_str})")

            # Remove empty directories
            for dir_path in sorted(channels_dir.rglob("*"), reverse=True):
                if dir_path.is_dir():
                    try:
                        dir_path.rmdir()
                    except OSError:
                        pass  # Directory not empty

        except ValueError:
            logger.error(f"Invalid DELETE_AFTER value: {delete_after}")

    def process_videos(self) -> None:
        """Main processing function"""
        try:
            video_dir = Path(self.config["VIDEO_DIRECTORY"])
            
            # Separate video and auxiliary files
            video_files = [f for f in video_dir.rglob("*") 
                         if f.suffix.lower() in self.FILE_TYPES['video']
                         and f.name not in self.processed_files]
                         
            auxiliary_files = [f for f in video_dir.rglob("*") 
                            if f.suffix.lower() in self.FILE_TYPES['auxiliary']
                            and f.name not in self.processed_files]

            if not video_files and not auxiliary_files:
                logger.info("No new files to process")
                return

            # Get unique video IDs from primary video files
            video_ids = list(set(f.stem.split('.')[0] for f in video_files))
            
            # Add IDs from auxiliary files without deduplication
            auxiliary_ids = [f.stem.split('.')[0] for f in auxiliary_files]
            all_ids = video_ids + [aid for aid in auxiliary_ids if aid not in video_ids]
            
            logger.info(f"Found {len(video_files)} video files and {len(auxiliary_files)} auxiliary files")

            # Process in batches
            for i in range(0, len(all_ids), self.BATCH_SIZE):
                batch = all_ids[i:i + self.BATCH_SIZE]
                batch_results = self._process_batch(batch)
                self.metadata_cache.update(batch_results)

            # Process all files using cached metadata
            all_files = video_files + auxiliary_files
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(self._process_file, all_files))

            # Update processed files tracker
            with open(self.config["PROCESSED_FILES_TRACKER"], "a") as f:
                f.writelines(f"{file.name}\n" for file, success 
                           in zip(all_files, results) if success)

            # Run cleanup and send notifications
            self.cleanup_old_files()
            
            if self.apprise_client and (self.processed_channels or self.deleted_files):
                self._send_notification()

            self._refresh_channels_dvr()

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise

    def _send_notification(self) -> None:
        """Send notification about processed and deleted files"""
        if not self.apprise_client:
            return

        try:
            message_parts = []
            
            if self.processed_channels:
                message_parts.append("Processed Files:")
                summary = [f"{channel}: {len(videos)} videos" 
                          for channel, videos in self.processed_channels.items()]
                details = [f"  - {title}" 
                          for videos in self.processed_channels.values() 
                          for title in videos]
                message_parts.extend(summary + details)
                message_parts.append(f"Total videos processed: {sum(len(v) for v in self.processed_channels.values())}")
            
            if self.deleted_files:
                if message_parts:
                    message_parts.append("")
                message_parts.append("Deleted Files:")
                del_summary = [f"{channel}: {len(files)} files" 
                             for channel, files in self.deleted_files.items()]
                del_details = [f"  - {title}" 
                             for files in self.deleted_files.values() 
                             for title in files]
                message_parts.extend(del_summary + del_details)
                message_parts.append(f"Total files deleted: {sum(len(v) for v in self.deleted_files.values())}")
            
            if message_parts:
                self.apprise_client.notify(
                    title="YouTube Video Processing Report",
                    body="\n".join(message_parts)
                )
        except Exception as e:
            logger.error(f"Notification failed: {e}")

    def _refresh_channels_dvr(self) -> None:
        """Refresh Channels DVR if configured"""
        if url := self.config.get("CHANNELS_DVR_API_REFRESH_URL"):
            try:
                requests.put(url, timeout=10).raise_for_status()
                logger.info("Channels DVR metadata refresh completed")
            except Exception as e:
                logger.error(f"Channels DVR refresh failed: {e}")

if __name__ == "__main__":
    processor = VideoProcessor("config.txt")
    processor.process_videos()
