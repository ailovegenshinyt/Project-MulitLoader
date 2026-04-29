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

            # ── Spotify Identity Resolver (Direct Metadata API) ──────────────────────
            if 'spotify.com' in url:
                task['logs'].append("Analysis Link....... Spotify (API Identity Mode)")
                task['logs'].append("Resolving track identity via Global Metadata API...")
                
                search_query = ""
                try:
                    # ดึง ID จากลิงก์
                    track_id = url.split('track/')[1].split('?')[0]
                    # ใช้ API ของ SpotifyDown (ตัวแม่นที่สุด)
                    api_url = f"https://api.spotifydown.com/metadata/track/{track_id}"
                    
                    res = requests.get(api_url, timeout=15)
                    if res.status_code == 200:
                        data = res.json()
                        if data.get('success'):
                            title = data.get('title', 'Unknown')
                            artist = data.get('artists', 'Unknown')
                            search_query = f"{title} {artist}".strip()
                            task['logs'].append(f"Identified: {search_query}")
                        else:
                            raise Exception("Metadata API returned no success.")
                    else:
                        raise Exception(f"Metadata API Status {res.status_code}")

                except Exception as e:
                    task['logs'].append(f"⚠️ Metadata Failure: {e}")
                    # ถ้าดึงชื่อไม่ได้จริงๆ ลองใช้ oEmbed เป็นทางเลือกสุดท้าย
                    try:
                        o_res = requests.get(f"https://open.spotify.com/oembed?url={url}", timeout=10)
                        if o_res.status_code == 200:
                            search_query = o_res.json().get('title', '')
                    except: pass
                
                if not search_query:
                    raise Exception("Could not identify Spotify track. Please check the link or try a YouTube link.")

                # แปลงร่างเป็นคำค้นหา YouTube (ห้ามส่งลิงก์ Spotify ให้ yt-dlp เด็ดขาด!)
                url = f"ytsearch1:{search_query}"
                task['logs'].append(f"Redirecting to YouTube Engine: {search_query}")

            # ── Core Download Engine (yt-dlp) ────────────────────────────────────────
            task['logs'].append("Warming up Core Engine...")

            def pp_hook(d):
                if d['status'] == 'started':
                    task['logs'].append(f"Stage: {d['postprocessor']} started...")
                elif d['status'] == 'finished':
                    task['logs'].append(f"Stage: {d['postprocessor']} completed.")

            # --- ระบบดาวน์โหลด (Hugging Face / SSL Bypass Mode) ---
            abs_download_path = os.path.abspath(DOWNLOAD_FOLDER)
            temp_dir_name = f"yt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            temp_dir = os.path.join(abs_download_path, temp_dir_name)
            os.makedirs(temp_dir, exist_ok=True)
            
            br_qual = {'4k':'320','1080p':'256','720p':'192','480p':'128'}.get(quality, '320')
            ydl_opts = {
                'nocheckcertificate': True, 
                'impersonate': 'chrome',       # ใช้ curl_cffi ปลอมตัวเป็น Chrome เพื่อเลี่ยง SSL EOF
                'cache_dir': False,
                'retries': 3,
                'socket_timeout': 30,
                'quiet': False,
                'no_warnings': False,
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web', 'android'],
                    }
                }
            }

            if fmt == 'video':
                v_res = {'4k':'2160','1080p':'1080','720p':'720','480p':'480'}.get(quality, '1080')
                ydl_opts['format'] = f'bestvideo[height<={v_res}]+bestaudio/best'
                ydl_opts['postprocessors'] = [{'key':'FFmpegMetadata'},{'key':'EmbedThumbnail'}]
            else:
                ext = 'mp3' if fmt == 'audio' else 'wav'
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key':'FFmpegExtractAudio','preferredcodec':ext,'preferredquality':br_qual},
                    {'key':'FFmpegMetadata'}, {'key':'EmbedThumbnail'},
                ]

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    task['logs'].append("Starting media engine... (Check terminal for details)")
                    info = ydl.extract_info(url, download=True)
                    
                    entries = info.get('entries', [])
                    all_found = os.listdir(temp_dir)
                    task['logs'].append(f"Debug: Files in temp: {all_found}")

                    if len(entries) > 1 or (not entries and 'playlist' in url):
                        # กรณี Playlist
                        title = info.get('title', 'Playlist')
                        task['logs'].append(f"Zipping Playlist: {title}")
                        zip_name = f"Playlist_{int(time.time())}"
                        shutil.make_archive(os.path.join(abs_download_path, zip_name), 'zip', temp_dir)
                        task['filename'] = f"{zip_name}.zip"
                        task['download_url'] = f"/files/{zip_name}.zip"
                    else:
                        # กรณีไฟล์เดียว
                        if all_found:
                            # เลือกไฟล์ที่ขนาดใหญ่ที่สุด (มักจะเป็นไฟล์เพลงที่แปลงเสร็จแล้ว)
                            final_filename = max(all_found, key=lambda f: os.path.getsize(os.path.join(temp_dir, f)))
                            shutil.move(os.path.join(temp_dir, final_filename), os.path.join(abs_download_path, final_filename))
                            task['filename'] = final_filename
                            task['download_url'] = f"/files/{final_filename}"
                            task['logs'].append(f"Success: {final_filename}")
                        else:
                            raise Exception(f"Processor finished but {temp_dir} is empty! Check Terminal.")

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
