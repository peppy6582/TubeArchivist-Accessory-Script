
# TubeArchivist Accessory Script: YouTube Video Processor

A Python script designed to enhance your **TubeArchivist** setup by:
- Fetching video metadata from YouTube via the YouTube Data API.
- Generating `.nfo` files for future integration with **Channels DVR** or other media systems.
- Renaming video files and `.nfo` files based on their titles.
- Organizing video files into directories based on their uploaders.
- Sending optional Pushover notifications summarizing the processed videos.

This script works alongside **TubeArchivist**, providing enhanced file organization and compatibility for additional media workflows.

---

## Features

- **Metadata Retrieval**: Fetches YouTube video metadata (title, description, uploader, upload date) for each processed video.
- **Generate `.nfo` Files**: Creates `.nfo` files with the metadata for use in **Channels DVR** or other media library systems[Jellyfin/EMBY/KODI].
- **File Renaming**: Renames video files and associated `.nfo` files to match the video's title.
- **Directory Organization**: Moves processed files into directories named after their uploaders.
- **Optional Pushover Notifications**: Sends a detailed summary of processed videos grouped by channel.
- **Channels DVR Metadata Refresh**: Optionally triggers a Channels DVR library refresh after processing.

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

### API Keys
- A valid YouTube Data API key.
- Pushover credentials (optional) for notifications.

---

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/YouTube-Processor.git
   cd YouTube-Processor
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
   VIDEO_DIRECTORY=/TubeArchivist/YouTube/
   CHANNELS_DIRECTORY=/TubeArchivist/YouTube Channels/
   PROCESSED_FILES_TRACKER=processed_files.txt
   YOUTUBE_API_KEY=your-youtube-api-key
   PUSHOVER_USER_KEY=your-pushover-user-key
   PUSHOVER_API_TOKEN=your-pushover-api-token
   CHANNELS_DVR_API_REFRESH_URL=http://[YOUR CHANNELS DVR IP HERE]/dvr/scanner/scan
   ```

   - **Required**:
     - `VIDEO_DIRECTORY`: Directory where TubeArchivist stores downloaded videos.
     - `CHANNELS_DIRECTORY`: Directory to organize videos by uploader.
     - `YOUTUBE_API_KEY`: YouTube Data API key.
   - **Optional**:
     - `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN`: Required for Pushover notifications.
     - `CHANNELS_DVR_API_REFRESH_URL`: URL for Channels DVR metadata refresh.

---

## Usage

### Manual Execution
Run the script manually:
```bash
cd /path/to/YouTube-Processor
./youtube-process.py
```

### Scheduled Execution
To process videos twice a day (at 8:00 AM and 8:00 PM), add this line to your crontab:
```bash
0 8,20 * * * cd /TubeArchivist/YouTube && ./youtube-process.py >> /TubeArchivist/YouTube/youtube-process.log 2>&1
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
3. (Optional) Sends a Pushover notification summarizing the processed videos.
4. (Optional) Triggers a Channels DVR library refresh.

---

## Pushover Notifications

### How it Works:
- **Enabled**: Notifications are sent if `PUSHOVER_USER_KEY` and `PUSHOVER_API_TOKEN` are present in the `config.txt`.
- **Disabled**: If these values are missing, the notification section is skipped.

### Example Notification
```
Channel A: 3 videos
  - Video Title 1
  - Video Title 2
  - Video Title 3
Channel B: 2 videos
  - Video Title 4
  - Video Title 5
Total videos processed: 5
```

---

## Troubleshooting

### Common Issues
- **Missing API Key**: Ensure `YOUTUBE_API_KEY` is correctly set in `config.txt`.
- **File Permissions**: Check read/write permissions for the specified directories.
- **TubeArchivist Configuration**: Ensure TubeArchivist is configured to download videos to the specified `VIDEO_DIRECTORY`.

### Debugging
Check the log file for errors:
```bash
cat /TubeArchivist/YouTube/youtube-process.log
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

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [TubeArchivist](https://www.tubearchivist.com/)
- [YouTube Data API](https://developers.google.com/youtube/v3)
- [Pushover](https://pushover.net/)
- [Channels DVR](https://getchannels.com/dvr/)

