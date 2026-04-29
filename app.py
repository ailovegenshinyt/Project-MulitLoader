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

            # ── 🛠️ ระบบดาวน์โหลดใหม่ (Cobalt + yt-dlp Hybrid) ──────────────────
            def download_via_cobalt(target_url, is_audio=True):
                task['logs'].append(f"Cobalt Engine: Requesting stream...")
                try:
                    c_headers = {"Accept": "application/json", "Content-Type": "application/json"}
                    c_data = {"url": target_url, "isAudioOnly": is_audio, "downloadMode": "auto"}
                    c_res = requests.post("https://api.cobalt.tools/api/json", json=c_data, headers=c_headers, timeout=30)
                    
                    if c_res.status_code == 200:
                        res_json = c_res.json()
                        if res_json.get('status') == 'stream' or res_json.get('status') == 'redirect':
                            stream_url = res_json.get('url')
                            task['logs'].append("Stream link acquired! Pulling media...")
                            
                            # ดึงไฟล์จาก Cobalt มาเก็บที่เครื่อง
                            f_res = requests.get(stream_url, stream=True, timeout=120)
                            if f_res.status_code == 200:
                                # พยายามดึงชื่อไฟล์จาก Header หรือตั้งชื่อใหม่
                                filename = f"Downloaded_{int(time.time())}.{'mp3' if is_audio else 'mp4'}"
                                f_path = os.path.join(DOWNLOAD_FOLDER, filename)
                                
                                with open(f_path, 'wb') as f:
                                    for chunk in f_res.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                
                                task['filename'] = filename
                                task['download_url'] = f"/files/{filename}"
                                task['logs'].append(f"Success: {filename}")
                                task['status'] = 'completed'
                                return True
                    task['logs'].append(f"Cobalt Status: {c_res.status_code} - {c_res.text[:100]}")
                except Exception as e:
                    task['logs'].append(f"Cobalt Error: {str(e)}")
                return False

            # --- เริ่มต้นกระบวนการ ---
            final_yt_url = url
            # ถ้าเป็น Spotify หรือคำค้นหา ให้หา URL YouTube มาก่อน
            if 'spotify.com' in url or url.startswith('ytsearch'):
                task['logs'].append("Searching for YouTube source...")
                search_opts = {'quiet': True, 'extract_flat': True, 'nocheckcertificate': True}
                with yt_dlp.YoutubeDL(search_opts) as ydl:
                    try:
                        search_info = ydl.extract_info(url, download=False)
                        if 'entries' in search_info and search_info['entries']:
                            final_yt_url = search_info['entries'][0]['url']
                        else:
                            final_yt_url = search_info.get('webpage_url', url)
                    except Exception as e:
                        task['logs'].append(f"Search Warning: {e}")

            # 🚀 ลองใช้ Cobalt ก่อน (เพราะมันเทพบน Server)
            if download_via_cobalt(final_yt_url, is_audio=(fmt == 'audio')):
                task['logs'].append("Cobalt Engine: Task completed successfully.")
                return 

            # 🛡️ ถ้า Cobalt วืด ค่อยกลับมาใช้ yt-dlp (แบบถึกทน)
            task['logs'].append("Cobalt failed. Falling back to Core Engine (Bypass Mode)...")
            temp_dir = os.path.join(os.path.abspath(DOWNLOAD_FOLDER), f"fallback_{uuid.uuid4().hex[:6]}")
            os.makedirs(temp_dir, exist_ok=True)
            
            ydl_opts = {
                'nocheckcertificate': True, 
                'legacy_server_connect': True,
                'impersonate': 'chrome120',    # ระบุเวอร์ชั่นเจาะจงเพื่อความชัวร์
                'source_address': '0.0.0.0',
                'cache_dir': False,
                'quiet': False,
                'check_formats': False,        # ลดจำนวนการเช็คไฟล์เพื่อเลี่ยงการโดนบล็อก
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'format': 'bestaudio/best' if fmt == 'audio' else 'bestvideo+bestaudio/best',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios'], # ใช้มือถือเท่านั้น
                        'player_skip': ['web', 'web_embedded'] # สั่งข้ามระบบเว็บที่มักจะโดนบล็อก
                    }
                }
            }
            if fmt != 'video':
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3' if fmt == 'audio' else 'wav',
                    'preferredquality': '320',
                }]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                task['logs'].append("Requesting media via Android Client...")
                info = ydl.extract_info(final_yt_url, download=True)
                all_found = os.listdir(temp_dir)
                if all_found:
                    final_filename = max(all_found, key=lambda f: os.path.getsize(os.path.join(temp_dir, f)))
                    shutil.move(os.path.join(temp_dir, final_filename), os.path.join(DOWNLOAD_FOLDER, final_filename))
                    task['filename'] = final_filename
                    task['download_url'] = f"/files/{final_filename}"
                    task['status'] = 'completed'
                else:
                    raise Exception("Fallback engine failed to retrieve file.")

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
