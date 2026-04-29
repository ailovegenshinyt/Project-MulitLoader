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
        time.sleep(3600) # 60 นาที (1 ชั่วโมง)
        t = time.time()
        for root, dirs, files in os.walk(DOWNLOAD_FOLDER, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    # ลบไฟล์ที่เก่ากว่า 1 ชั่วโมง
                    if os.path.getmtime(fp) < t - 3600: os.unlink(fp)
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

            last_p = -10
            def progress_hook(d):
                nonlocal last_p
                if d['status'] == 'downloading':
                    try:
                        p_str = d.get('_percent_str', '0.0%')
                        clean_p = re.sub(r'\x1b\[[0-9;]*m', '', p_str).replace('%', '').strip()
                        p = float(clean_p)
                        if p - last_p >= 5 or p >= 100:
                            s = d.get('_speed_str', '0.00KiB/s')
                            clean_s = re.sub(r'\x1b\[[0-9;]*m', '', s).strip()
                            task['logs'].append(f"Downloading... {p:.1f}% (Speed: {clean_s})")
                            last_p = p
                    except Exception:
                        pass
                elif d['status'] == 'finished':
                    task['logs'].append("Download complete, merging files...")

            def pp_hook(d):
                if d['status'] == 'started':
                    task['logs'].append(f"Stage: {d['postprocessor']} started...")
                elif d['status'] == 'finished':
                    task['logs'].append(f"Stage: {d['postprocessor']} completed.")

            # --- เริ่มต้นกระบวนการ ---
            # 🔎 ถ้าเป็น Spotify หรือค้นหา ให้หา URL YouTube มาก่อน
            final_yt_url = url
            if 'spotify.com' in url or url.startswith('ytsearch'):
                task['logs'].append("Searching for YouTube source...")
                search_opts = {
                    'quiet': True, 
                    'extract_flat': True, 
                    'nocheckcertificate': True,
                    'legacy_server_connect': True,
                    'source_address': '0.0.0.0'
                }
                with yt_dlp.YoutubeDL(search_opts) as ydl:
                    try:
                        search_info = ydl.extract_info(url, download=False)
                        if 'entries' in search_info and search_info['entries']:
                            final_yt_url = search_info['entries'][0]['url']
                            task['logs'].append(f"Found: {final_yt_url}")
                        else:
                            final_yt_url = search_info.get('webpage_url', url)
                    except Exception as e:
                        task['logs'].append(f"Search Warning: {str(e)[:100]}")

            # 🛡️ ขั้นตอนสุดท้าย: ดาวน์โหลดด้วย Core Engine (Urllib3 Downgrade Mode)
            task['logs'].append("Core Engine starting...")
            temp_dir = os.path.join(os.path.abspath(DOWNLOAD_FOLDER), f"fallback_{uuid.uuid4().hex[:6]}")
            os.makedirs(temp_dir, exist_ok=True)
            
            ydl_opts = {
                'nocheckcertificate': True, 
                'legacy_server_connect': True,
                'source_address': '0.0.0.0',
                'cache_dir': False,
                'quiet': True,
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'format': 'bestaudio/best' if fmt == 'audio' else 'bestvideo+bestaudio/best',
                'progress_hooks': [progress_hook],
                'postprocessor_hooks': [pp_hook],
            }
            if fmt != 'video':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3' if fmt == 'audio' else 'wav',
                    'preferredquality': '320',
                }]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(final_yt_url, download=True)
                all_found = os.listdir(temp_dir)
                if all_found:
                    final_filename = max(all_found, key=lambda f: os.path.getsize(os.path.join(temp_dir, f)))
                    shutil.move(os.path.join(temp_dir, final_filename), os.path.join(DOWNLOAD_FOLDER, final_filename))
                    task['filename'] = final_filename
                    task['download_url'] = f"/files/{final_filename}"
                    task['status'] = 'completed'
                else:
                    raise Exception("All engines failed.")

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
