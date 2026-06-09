# Downloader Universel

## Description
A comprehensive media downloader supporting YouTube, TikTok, Instagram, and more. It utilizes `yt-dlp` for fetching media and `ffmpeg` for post-processing (extraction, trimming, merging).

## Key Features
- **Format Selection**: MP3, WAV, FLAC, MP4, MKV, etc.
- **Trimming**: Users can select specific start and end times using sliders or text input.
- **Batch & Playlists**: Supports downloading entire playlists or batch processing via `.txt` files.
- **Deezer Integration**: Can automatically upload downloaded `.mp3` files to a Deezer Premium account's "My MP3s" section. This works via a semi-automatic workflow: upon completion, it opens the local folder and the Deezer web page for drag-and-drop.
