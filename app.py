import os, time, shutil, threading, uuid, re, json, traceback
import subprocess
import yt_dlp
from flask import Flask, request, jsonify, send_file, Response

# Load .env for local dev
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Spotify API setup (For spotdl performance) ───────────────────────────────
_cid = os.environ.get('SPOTIFY_CLIENT_ID', '')
_sec = os.environ.get('SPOTIFY_CLIENT_SECRET', '')
if _cid and _sec:
    os.environ['SPOTIPY_CLIENT_ID'] = _cid
    os.environ['SPOTIPY_CLIENT_SECRET'] = _sec
    print("✅ Spotify API configured for background tasks.")
else:
    print("⚠️  Spotify credentials missing.")

app = Flask(__name__, static_folder='.', static_url_path='')
DOWNLOAD_FOLDER = 'downloads'
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
tasks = {}

# ── Background cleanup ────────────────────────────────────────────────────────
def background_cleanup():
    while True:
        time.sleep(300)
        t = time.time()
        for root, dirs, files in os.walk(DOWNLOAD_FOLDER, topdown=False):
            for f in files:
                fp = os.path.join(root, f)
                try:
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

            # ── Spotify path ─────────────────────────────────────────────────
            if 'spotify.com' in url:
                task['logs'].append("Analysis Link....... Spotify")
                task['logs'].append("Starting Spotify download.......")
                temp_dir = f"{DOWNLOAD_FOLDER}/spot_{int(time.time())}"
                os.makedirs(temp_dir, exist_ok=True)
                ext = 'mp3' if fmt == 'audio' else 'wav'
                cmd = ['spotdl', 'download', url, '--output', f'{temp_dir}/', '--format', ext]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                track_num = 0
                for line in proc.stdout:
                    line = line.strip()
                    if not line: continue
                    if 'Downloading' in line or 'Downloaded' in line or 'Found' in line or 'Skipping' in line:
                        track_num += 1
                        task['logs'].append(f"Track {track_num}: {line}")
                proc.wait()

                files = os.listdir(temp_dir)
                if len(files) == 1:
                    fp = os.path.join(temp_dir, files[0])
                    shutil.move(fp, os.path.join(DOWNLOAD_FOLDER, files[0]))
                    task['filename'] = files[0]
                    task['download_url'] = f"/files/{files[0]}"
                elif len(files) > 1:
                    zip_name = f"Spotify_{int(time.time())}"
                    shutil.make_archive(f"{DOWNLOAD_FOLDER}/{zip_name}", 'zip', temp_dir)
                    task['filename'] = f"{zip_name}.zip"
                    task['download_url'] = f"/files/{zip_name}.zip"
                else:
                    raise Exception("Spotify download produced no files.")

            # ── YouTube path ─────────────────────────────────────────────────
            else:
                task['logs'].append("Analysis Link....... YouTube")

                def pp_hook(d):
                    if d['status'] == 'started':
                        task['logs'].append(f"Stage: {d['postprocessor']} started...")
                    elif d['status'] == 'finished':
                        task['logs'].append(f"Stage: {d['postprocessor']} completed.")

                ydl_opts = {
                    'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
                    'quiet': True, 'no_warnings': True,
                    'progress_hooks': [lambda d: None],
                    'postprocessor_hooks': [pp_hook],
                    'overwrites': True, 'nooverwrites': False,
                    'nocheckcertificate': True, 
                    'cache_dir': False,
                    'legacy_server_connect': True, # Fix SSL issues
                    'retries': 10,                 # Fight against EOF drops
                    'fragment_retries': 10,
                    'extractor_args': {'youtube': {'player_client': ['android']}},
                    'youtube_include_dash_manifest': False,
                    'sleep_requests': 1,           # Add small delay
                }

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
