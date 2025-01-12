
# TubeArchivist Accessory Script: YouTube Video Processor

A Python script designed to enhance your **TubeArchivist** setup by:
- Fetching video metadata from YouTube via the YouTube Data API.
- Generating `.nfo` files for future integration with **Channels DVR** or other media systems [Should already work with Jellyfin|Emby|KODI].
- Renaming video files and `.nfo` files based on their titles.
- Organizing video files into directories based on their uploaders.
- Sending notifications using **Apprise** with support for multiple services.
- Optionally triggering a Channels DVR metadata refresh after processing.

This script works alongside **TubeArchivist**, providing enhanced file organization and compatibility for additional media workflows.

---

## Features

- **Metadata Retrieval**: Fetches YouTube video metadata (title, description, uploader, upload date) for each processed video.
- **Generate `.nfo` Files**: Creates `.nfo` files with the metadata for use in **Channels DVR** or other media library systems.
- **File Renaming**: Renames video files and associated `.nfo` files to match the video's title.
- **Directory Organization**: Moves processed files into directories named after their uploaders.
- **Notifications with Apprise**: Sends detailed summaries of processed videos through services like Pushover, Discord, Slack, etc.
- **Channels DVR Metadata Refresh**: Optionally triggers a Channels DVR library refresh after processing.
- **DELETE_AFTER**: Optionally removes video files older than x days
---

## Requirements

### Software
- Python 3.6 or later.
- A working **TubeArchivist** instance.

### Python Libraries
Install required libraries with:
```bash
pip install -r requirements.txt
```

### APIs and Keys
- A valid YouTube Data API key.
- Apprise-compatible notification service URLs (optional).

---

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/peppy6582/TubeArchivist-Accessory-Script.git
   cd TubeArchivist-Accessory-Script
   ```

2. Make the script executable:
   ```bash
   chmod +x youtube-process.py
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the script by creating a `config.txt` file:
   ```txt
   VIDEO_DIRECTORY=/path/to/TubeArchivist/YouTube/
   CHANNELS_DIRECTORY=/path/to/TubeArchivist/YouTube Channels/
   PROCESSED_FILES_TRACKER=processed_files.txt
   YOUTUBE_API_KEY=your-youtube-api-key
   APPRISE_URL=pover://your_user_key@your_api_token
   CHANNELS_DVR_API_REFRESH_URL=http://YOUR_IP_ADDRESS:8089/dvr/scanner/scan
   DELETE_AFTER=30 (Remove files older than x days)
   ```

   - **Required**:
     - `VIDEO_DIRECTORY`: Directory where TubeArchivist stores downloaded videos.
     - `CHANNELS_DIRECTORY`: Directory to organize videos by uploader.
     - `YOUTUBE_API_KEY`: YouTube Data API key.
     - `PROCESSED_FILES_TRACKER`: Keeps a record of processed files so api hits are not duplicated.
   - **Optional**:
     - `APPRISE_URL`: URL for sending notifications via Apprise-supported services.
     - `CHANNELS_DVR_API_REFRESH_URL`: URL for Channels DVR metadata refresh.
     - `DELETE_AFTER`: Remove files older than x days

---

## Apprise Notifications

The script supports **Apprise** for notifications. Apprise allows you to send notifications to various services like Pushover, Discord, Slack, Email, and more.

### Example `APPRISE_URL` Values
Here are some examples of how to configure the `APPRISE_URL` in your `config.txt` file:

1. **Pushover**:
   ```txt
   APPRISE_URL=pover://your_user_key@your_api_token
   ```

2. **Discord**:
   ```txt
   APPRISE_URL=discord://webhook_id/webhook_token
   ```

3. **Slack**:
   ```txt
   APPRISE_URL=slack://workspace_token@channel_id
   ```

4. **Email (SMTP)**:
   ```txt
   APPRISE_URL=mailto://username:password@mailserver.example.com:587/?to=recipient@example.com
   ```

### Test Notifications
You can test your notification setup using the Apprise CLI:
```bash
apprise -vv -t "Test Notification" -b "This is a test message" "pover://your_user_key@your_api_token"
```

Replace the URL with the `APPRISE_URL` from your `config.txt`.

---

## Usage

### Manual Execution
Run the script manually:
```bash
cd /path/to/TubeArchivist-Accessory-Script
./youtube-process.py
```

### Scheduled Execution
To process videos twice a day (at 8:00 AM and 8:00 PM), add this line to your crontab:
```bash
0 8,20 * * * cd /path/to/TubeArchivist/YouTube && ./youtube-process.py >> /path/to/TubeArchivist/YouTube/youtube-process.log 2>&1
```

---

## Integration with TubeArchivist and Channels DVR

1. **TubeArchivist**:
   - This script works alongside TubeArchivist to organize downloaded YouTube videos by uploader and enhance metadata compatibility.

2. **Channels DVR**:
   - Generated `.nfo` files are compatible with future integration into Channels DVR.
   - After processing, the script can optionally trigger a Channels DVR library refresh using the `CHANNELS_DVR_API_REFRESH_URL`.

---

## Example Workflow

1. TubeArchivist downloads videos into the `VIDEO_DIRECTORY`.
2. This script processes the videos:
   - Retrieves metadata from YouTube.
   - Generates `.nfo` files for future use in Channels DVR or other systems.
   - Renames files to match video titles.
   - Organizes files by uploader in the `CHANNELS_DIRECTORY`.
3. (Optional) Deletes files older than x days.
4. (Optional) Sends a notification summarizing the processed videos using Apprise.
5. (Optional) Triggers a Channels DVR library refresh.

---

## Troubleshooting

### Common Issues
- **Missing API Key**: Ensure `YOUTUBE_API_KEY` is correctly set in `config.txt`.
- **Invalid Notification URL**: Verify your `APPRISE_URL` with the Apprise CLI to ensure it is correct.
- **File Permissions**: Check read/write permissions for the specified directories.

### Debugging
Check the log file for errors (only works if you set your cron job to output to this file as above):
```bash
cat /path/to/TubeArchivist/YouTube/youtube-process.log
```

---

## Contributing

1. Fork this repository.
2. Create a new branch:
   ```bash
   git checkout -b feature-name
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add feature name"
   ```
4. Push the branch:
   ```bash
   git push origin feature-name
   ```
5. Submit a pull request.

---

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/peppy6582/TubeArchivist-Accessory-Script/blob/main/LICENSE) file for details.

---

## Acknowledgments

- [TubeArchivist](https://www.tubearchivist.com/)
- [YouTube Data API](https://developers.google.com/youtube/v3)
- [Apprise](https://github.com/caronc/apprise)
- [Channels DVR](https://getchannels.com/dvr/)

---
