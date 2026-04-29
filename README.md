---
title: MultiLoader
emoji: 🎵
colorFrom: purple
colorTo: blue
sdk: docker
pinned: false
license: mit
---

# MultiLoader 🚀
**Premium Multi-Source Downloader with Liquid Glass UI**

MultiLoader is a high-performance video and music downloader that supports YouTube (Videos & Playlists) and Spotify (Tracks & Albums). It features a stunning "Liquid Glass" design and automatic metadata embedding.

## Features
- 🎬 YouTube Videos & Playlists (up to 4K)
- 🎵 Spotify Tracks, Albums & Playlists
- 🔍 Spotify Search by song/artist name
- 📱 iOS/iPadOS native download support
- 🏷️ Auto metadata & thumbnail embedding
- 🧹 Auto cache cleanup every 5 minutes

## Supported Formats
- Video: MP4 (4K, 1080p, 720p, 480p)
- Audio: MP3 (320, 256, 192, 128 kbps)
- Audio: WAV (Lossless)

## Setup (Self-Hosting)

### Requirements
```bash
pip install -r requirements.txt
```

### Environment Variables
Copy `.env.example` to `.env` and fill in your Spotify API credentials:
```
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
```

Get credentials at: https://developer.spotify.com/dashboard

### Run
```bash
python app.py
```

Access at: `http://localhost:7860`

## HuggingFace Spaces
Set these as **Secrets** in your Space settings:
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`

## Tech Stack
- **Backend**: Python, Flask, yt-dlp, spotdl, spotipy
- **Frontend**: Vanilla HTML/CSS/JS (Glassmorphism UI)
- **Media Processing**: FFmpeg

## Created by
**CoR3 Coding-R** — [GitHub](https://github.com/ailovegenshinyt)

© 2026 MultiLoader Project — Open Source & Community Driven
