
# TubeArchivist Accessory Script: YouTube Video Processor

A Python script designed to enhance your **TubeArchivist** setup by:
- Fetching video metadata from YouTube via the YouTube Data API.
- Generating `.nfo` files for integration with **Channels DVR**, **Jellyfin**, **Emby**, or **Kodi**.
- Renaming video files and `.nfo` files based on their titles.
- Organizing video files into directories based on their uploaders.
- Sending notifications using **Apprise** with support for multiple services.
- Optionally triggering a Channels DVR metadata refresh after processing.
- Optionally removing older files with the `delete_after` feature.

This script works alongside **TubeArchivist**, providing enhanced file organization and compatibility for additional media workflows.

---

## Features

- **Metadata Retrieval**: Fetches YouTube video metadata (title, description, uploader, upload date) for each processed video.
- **Generate `.nfo` Files**: Creates `.nfo` files with the metadata for use in **Channels DVR** or other media library systems.
- **File Renaming**: Renames video files and associated `.nfo` files to match the video's title.
- **Directory Organization**: Moves processed files into directories named after their uploaders.
- **Notifications with Apprise**: Sends detailed summaries of processed videos through services like Pushover, Discord, Slack, etc.
- **Channels DVR Metadata Refresh**: Optionally triggers a Channels DVR library refresh after processing.
- **File Cleanup with `delete_after`**: Automatically removes files older than a specified number of days.

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

4. Configure the script by creating a `config.yaml` file:
   ```yaml
   video_directory: "/path/to/TubeArchivist/YouTube/"
   channels_directory: "/path/to/TubeArchivist/YouTube Channels/"
   processed_files_tracker: "processed_files.txt"
   youtube_api_key: "your-youtube-api-key"
   apprise_url: "pover://your_user_key@your_api_token"
   channels_dvr_api_refresh_url: "http://YOUR_IP_ADDRESS:8089/dvr/scanner/scan"
   delete_after: 30  # Remove files older than 30 days
   ```

   - **Required**:
     - `video_directory`: Directory where TubeArchivist stores downloaded videos.
     - `channels_directory`: Directory to organize videos by uploader.
     - `youtube_api_key`: YouTube Data API key.
     - `processed_files_tracker`: Keeps a record of processed files so API hits are not duplicated.
   - **Optional**:
     - `apprise_url`: URL for sending notifications via Apprise-supported services.
     - `channels_dvr_api_refresh_url`: URL for Channels DVR metadata refresh.
     - `delete_after`: Remove files older than the specified number of days.

---

## Apprise Notifications

The script supports **Apprise** for notifications. Apprise allows you to send notifications to various services like Pushover, Discord, Slack, Email, and more.

### Example `apprise_url` Values
Here are some examples of how to configure the `apprise_url` in your `config.yaml` file:

1. **Pushover**:
   ```yaml
   apprise_url: "pover://your_user_key@your_api_token"
   ```

2. **Discord**:
   ```yaml
   apprise_url: "discord://webhook_id/webhook_token"
   ```

3. **Slack**:
   ```yaml
   apprise_url: "slack://workspace_token@channel_id"
   ```

4. **Email (SMTP)**:
   ```yaml
   apprise_url: "mailto://username:password@mailserver.example.com:587/?to=recipient@example.com"
   ```

### Test Notifications
You can test your notification setup using the Apprise CLI:
```bash
apprise -vv -t "Test Notification" -b "This is a test message" "pover://your_user_key@your_api_token"
```

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
   - Generated `.nfo` files are compatible with Channels DVR.
   - After processing, the script can optionally trigger a Channels DVR library refresh using the `channels_dvr_api_refresh_url`.

---

## File Cleanup with `delete_after`

The `delete_after` feature allows you to specify a number of days after which files will be automatically removed. This can help manage disk space and keep your library clean.

- To enable this feature, set `delete_after` in `config.yaml` to the desired number of days.
- Example:
  ```yaml
  delete_after: 30  # Removes files older than 30 days
  ```

If `delete_after` is not set or is `null`, the script will skip file deletion.

---

## Troubleshooting

### Common Issues
- **Missing API Key**: Ensure `youtube_api_key` is correctly set in `config.yaml`.
- **Invalid Notification URL**: Verify your `apprise_url` with the Apprise CLI to ensure it is correct.
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

