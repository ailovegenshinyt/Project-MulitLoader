import os, time, shutil, threading, uuid, re, json, traceback
import subprocess, random, requests
import yt_dlp
from flask import Flask, request, jsonify, send_file, Response

# Load .env for local dev
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Configuration ──────────────────────────────────────────────────────────
app = Flask(__name__, static_folder='.', static_url_path='')
DOWNLOAD_FOLDER = 'downloads'

# --- ล้างโฟลเดอร์ downloads ทุกครั้งที่เริ่มแอป ---
if os.path.exists(DOWNLOAD_FOLDER):
    try:
        shutil.rmtree(DOWNLOAD_FOLDER)
        print("🧹 Startup Cleanup: Old downloads cleared.")
    except Exception as e:
        print(f"⚠️ Startup Cleanup failed: {e}")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

tasks = {}

# ── Background cleanup (ทุกๆ 5 นาที) ──────────────────────────────────────────
def background_cleanup():
    while True:
        time.sleep(300) # 5 นาที
        t = time.time()
        for root, dirs, files in os.walk(DOWNLOAD_FOLDER, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    # ลบไฟล์ที่เก่ากว่า 5 นาที
                    if os.path.getmtime(fp) < t - 300: os.unlink(fp)
                except: pass
            for d in dirs:
                dp = os.path.join(root, d)
                try:
                    if not os.listdir(dp): os.rmdir(dp)
                except: pass
threading.Thread(target=background_cleanup, daemon=True).start()

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route('/')
def index(): return send_file('index.html')

@app.route('/download', methods=['POST'])
def start_download():
    data = request.json
    url, fmt, quality = data.get('url'), data.get('format'), data.get('quality')
    if not url: return jsonify({'error': 'URL required'}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {'status': 'processing', 'logs': [], 'download_url': None, 'filename': None}

    def run(task_id, url, fmt, quality):
        task = tasks[task_id]
        
        try:
            task['logs'].append("Connecting to MultiLoader Engine....... Done")
            task['logs'].append("🌐 [Direct Mode] Active.")
            
            # แสดงผลใน Console ของเพื่อนด้วย
            print(f"--- Task {task_id} Started ---")

            # ── Cross-Platform Metadata Resolution ───────────────────────────────────
            if 'spotify.com' in url:
                task['logs'].append("Analysis Link....... Spotify (Bypass Mode)")
                task['logs'].append("Fetching track identity from Spotify Global...")
                
                search_query = url
                try:
                    # ดึงชื่อเพลงจากระบบแชร์ของ Spotify (ไม่ต้องใช้ API Key)
                    oembed_url = f"https://open.spotify.com/oembed?url={url}"
                    res = requests.get(oembed_url, timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        song_title = data.get('title', 'Unknown')
                        search_query = song_title
                        task['logs'].append(f"Identified Track: {search_query}")
                    else:
                        task['logs'].append("⚠️ Identity fetch failed, using raw URL.")
                except Exception as e:
                    task['logs'].append(f"⚠️ Metadata error: {e}")
                
                # หัวใจสำคัญ: แปลงร่างลิงก์ Spotify เป็นการค้นหาใน YouTube Music
                url = f"ytsearch1:{search_query} audio"
                task['logs'].append("Redirecting to YouTube Music equivalent...")

            # ── Core Download Engine (yt-dlp) ────────────────────────────────────────
            task['logs'].append("Warming up Core Engine...")

            def pp_hook(d):
                if d['status'] == 'started':
                    task['logs'].append(f"Stage: {d['postprocessor']} started...")
                elif d['status'] == 'finished':
                    task['logs'].append(f"Stage: {d['postprocessor']} completed.")

            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                'quiet': True, 'no_warnings': True,
                'user_agent': random.choice([
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
                ]),
                'progress_hooks': [lambda d: None],
                'postprocessor_hooks': [pp_hook],
                'overwrites': True, 'nooverwrites': False,
                'nocheckcertificate': True, 
                'cache_dir': False,
                'legacy_server_connect': True, 
                'retries': 5,                  # ลดจำนวน Retry ให้รู้ผลไวขึ้น
                'fragment_retries': 5,
                'socket_timeout': 15,          # ลด Timeout ลงหน่อย
                'http_client': 'urllib',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['ios', 'android', 'web'], # เพิ่ม web เข้าไป
                    }
                },
                'youtube_include_dash_manifest': False,
            }
                
            task['logs'].append("🌐 [Direct Mode] Active.")

            if fmt == 'video':
                res = {'4k':'2160','1080p':'1080','720p':'720','480p':'480'}.get(quality, '1080')
                ydl_opts['format'] = f'bestvideo[height<={res}]+bestaudio/best'
                ydl_opts['postprocessors'] = [{'key':'FFmpegMetadata'},{'key':'EmbedThumbnail'}]
            else:
                br = {'4k':'320','1080p':'256','720p':'192','480p':'128'}.get(quality, '320')
                ext = 'mp3' if fmt == 'audio' else 'wav'
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key':'FFmpegExtractAudio','preferredcodec':ext,'preferredquality':br},
                    {'key':'FFmpegMetadata'}, {'key':'EmbedThumbnail'},
                ]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                task['logs'].append("Checking server cache and clearing old artifacts...")
                info_pre = ydl.extract_info(url, download=False)
                title_s = info_pre.get('title', 'Unknown')
                
                # Safe clear
                for fn in os.listdir(DOWNLOAD_FOLDER):
                    if title_s and title_s[:20] in fn:
                        try: os.unlink(os.path.join(DOWNLOAD_FOLDER, fn))
                        except: pass

                info = ydl.extract_info(url, download=True)
                if 'entries' in info:
                    title = info.get('title', 'Playlist')
                    task['logs'].append(f"Downloading Playlist: [{title}].......")
                    temp_dir = f"{DOWNLOAD_FOLDER}/yt_{int(time.time())}"
                    os.makedirs(temp_dir, exist_ok=True)
                    for e in info['entries']:
                        if e:
                            f = ydl.prepare_filename(e)
                            if fmt != 'video':
                                f = os.path.splitext(f)[0] + ('.mp3' if fmt == 'audio' else '.wav')
                            if os.path.exists(f):
                                shutil.move(f, os.path.join(temp_dir, os.path.basename(f)))
                    zip_name = f"{title}_{int(time.time())}"
                    shutil.make_archive(f"{DOWNLOAD_FOLDER}/{zip_name}", 'zip', temp_dir)
                    task['filename'] = f"{zip_name}.zip"
                    task['download_url'] = f"/files/{zip_name}.zip"
                else:
                    title = info.get('title', 'Media')
                    task['logs'].append(f"Downloading [{title}].......")
                    f = ydl.prepare_filename(info)
                    if fmt != 'video':
                        f = os.path.splitext(f)[0] + ('.mp3' if fmt == 'audio' else '.wav')
                    if os.path.exists(f):
                        task['filename'] = os.path.basename(f)
                        task['download_url'] = f"/files/{os.path.basename(f)}"
                    else:
                        raise Exception("Download completed but file not found on server.")

            task['logs'].append("Editing Media Tags...... Done")
            task['logs'].append("Sending File to User.....")
            task['status'] = 'completed'

        except Exception as e:
            traceback.print_exc()
            task['status'] = 'error'
            task['error'] = str(e)
            task['logs'].append(f"ERROR: {e}")

    threading.Thread(target=run, args=(task_id, url, fmt, quality), daemon=True).start()
    return jsonify({'task_id': task_id})

@app.route('/progress/<task_id>')
def progress(task_id):
    def generate():
        idx = 0
        while True:
            task = tasks.get(task_id)
            if not task: break
            while idx < len(task['logs']):
                yield f"event: log\ndata: {task['logs'][idx]}\n\n"
                idx += 1
            if task['status'] == 'completed':
                yield f"event: completed\ndata: {json.dumps({'download_url':task['download_url'],'filename':task['filename']})}\n\n"
                break
            if task['status'] == 'error':
                yield f"event: error\ndata: {task['error']}\n\n"
                break
            time.sleep(0.5)
    return Response(generate(), mimetype='text/event-stream')

@app.route('/files/<path:filename>')
def serve_file(filename):
    fp = os.path.join(DOWNLOAD_FOLDER, filename)
    if not os.path.exists(fp):
        for root, _, files in os.walk(DOWNLOAD_FOLDER):
            if filename in files: fp = os.path.join(root, filename); break
    return send_file(fp, as_attachment=True, download_name=filename) if os.path.exists(fp) else ("File not found", 404)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, debug=True)
