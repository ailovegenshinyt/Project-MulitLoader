# MultiLoader 🚀
**Premium Multi-Source Downloader with Liquid Glass UI**

MultiLoader is a high-performance video and music downloader that supports YouTube (Videos & Playlists) and Spotify (Tracks & Albums). It features a stunning "Liquid Glass" design and automatic metadata embedding.

## ✨ Features
- **YouTube Support:** Download videos up to 4K resolution.
- **Playlist Support:** Automatically ZIPs entire YouTube or Spotify playlists for one-click downloading.
- **Spotify Music:** Downloads tracks and albums with full metadata and high-quality audio (320kbps).
- **Auto-Tagging:** Automatically embeds thumbnails, titles, and artists into your files.
- **Liquid Glass UI:** Modern, responsive, and animated glassmorphism design.
- **Open Source:** Free to use and community-driven.

## 🛠 Tech Stack
- **Frontend:** HTML5, Vanilla CSS (Glassmorphism), Vanilla JavaScript.
- **Backend:** Python (Flask), yt-dlp, spotdl.
- **Processing:** FFmpeg for merging and metadata embedding.

## 🚀 Installation & Local Run
1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/MultiLoader.git
   cd MultiLoader
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the application:**
   ```bash
   python app.py
   ```
4. **Access the UI:** Open `http://localhost:7860` in your browser.

## ☁️ Hugging Face Deployment
This project is designed to run seamlessly on Hugging Face Spaces.
1. Create a new Space on Hugging Face.
2. Select **Docker** or **Python** as the SDK.
3. Upload all files.
4. Set the port to `7860` in `app.py`.

## 📄 License
This project is licensed under the MIT License.

## 👤 Creator
Created with ❤️ by **[Your Name/Team]**
