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



def get_youtube_metadata(url):
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={requests.utils.quote(url)}&format=json"
        res = requests.get(oembed_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            return {
                'title': data.get('title'),
                'artist': data.get('author_name'),
                'album': 'YouTube',
                'cover_url': data.get('thumbnail_url')
            }
    except Exception as e:
        print(f"DEBUG: Failed to get YouTube oEmbed metadata: {e}")
    
    try:
        video_id = None
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0].split('&')[0]
        elif 'v=' in url:
            video_id = url.split('v=')[1].split('&')[0].split('?')[0]
            
        if video_id:
            return {
                'title': None,
                'artist': None,
                'album': 'YouTube',
                'cover_url': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            }
    except:
        pass
    return None

def embed_metadata(filepath, metadata):
    if not metadata:
        return
        
    title = metadata.get('title')
    artist = metadata.get('artist')
    album = metadata.get('album', '')
    cover_url = metadata.get('cover_url')
    
    if not title and not artist:
        return
        
    print(f"DEBUG: Embedding metadata into {filepath}: Title='{title}', Artist='{artist}', Album='{album}'")
    
    base, ext = os.path.splitext(filepath)
    temp_out = base + "_tagged" + ext
    cover_temp = None
    
    try:
        if cover_url:
            try:
                cover_res = requests.get(cover_url, timeout=10)
                if cover_res.status_code == 200:
                    cover_temp = base + "_cover.jpg"
                    with open(cover_temp, 'wb') as f:
                        f.write(cover_res.content)
            except Exception as e:
                print(f"DEBUG: Failed to download cover art: {e}")
                
        cmd = ['ffmpeg', '-y', '-i', filepath]
        
        ext_lower = ext.lower()
        if ext_lower == '.mp3':
            if cover_temp:
                cmd.extend(['-i', cover_temp, '-map', '0:a', '-map', '1:0', '-c:a', 'copy', '-c:v', 'mjpeg', '-id3v2_version', '3'])
            else:
                cmd.extend(['-c:a', 'copy'])
            
            if title: cmd.extend(['-metadata', f'title={title}'])
            if artist: cmd.extend(['-metadata', f'artist={artist}'])
            if album: cmd.extend(['-metadata', f'album={album}'])
            
        elif ext_lower == '.mp4':
            if cover_temp:
                cmd.extend(['-i', cover_temp, '-map', '0', '-map', '1', '-c', 'copy', '-disposition:v:1', 'attached_pic'])
            else:
                cmd.extend(['-c', 'copy'])
                
            if title: cmd.extend(['-metadata', f'title={title}'])
            if artist: cmd.extend(['-metadata', f'artist={artist}'])
            if album: cmd.extend(['-metadata', f'album={album}'])
            
        elif ext_lower == '.wav':
            if cover_temp:
                cmd.extend(['-i', cover_temp, '-map', '0:a', '-map', '1:0', '-c:a', 'copy', '-c:v', 'mjpeg', '-write_id3v2', '1'])
            else:
                cmd.extend(['-c:a', 'copy', '-write_id3v2', '1'])
            if title: cmd.extend(['-metadata', f'title={title}'])
            if artist: cmd.extend(['-metadata', f'artist={artist}'])
            if album: cmd.extend(['-metadata', f'album={album}'])
        else:
            cmd.extend(['-c', 'copy'])
            if title: cmd.extend(['-metadata', f'title={title}'])
            if artist: cmd.extend(['-metadata', f'artist={artist}'])
            if album: cmd.extend(['-metadata', f'album={album}'])
            
        cmd.append(temp_out)
        
        print(f"DEBUG: Running ffmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            shutil.move(temp_out, filepath)
            print("DEBUG: Metadata embedded successfully.")
        else:
            print(f"DEBUG: ffmpeg metadata embedding failed with code {result.returncode}. Error: {result.stderr}")
            if os.path.exists(temp_out):
                os.remove(temp_out)
    except Exception as e:
        print(f"DEBUG: Error embedding metadata: {e}")
        if os.path.exists(temp_out):
            os.remove(temp_out)
    finally:
        if cover_temp and os.path.exists(cover_temp):
            os.remove(cover_temp)

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

            # Initialize metadata
            task['metadata'] = {}

            # ── Spotify Identity Resolver (Direct Metadata API) ──────────────────────
            if 'spotify.com' in url:
                task['logs'].append("Analysis Link....... Spotify (API Identity Mode)")
                task['logs'].append("Resolving track identity via Global Metadata API...")
                
                search_query = ""
                try:
                    # ดึง ID จากลิงก์
                    track_id = url.split('track/')[1].split('?')[0]
                    # ใช้ API ของ SpotifyDown พร้อม Browser Headers เพื่อป้องกัน 403
                    api_url = f"https://api.spotifydown.com/metadata/track/{track_id}"
                    sp_headers = {
                        "Origin": "https://spotifydown.com",
                        "Referer": "https://spotifydown.com/",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    }
                    res = requests.get(api_url, headers=sp_headers, timeout=15)
                    if res.status_code == 200:
                        data = res.json()
                        if data.get('success'):
                            title = data.get('title', 'Unknown')
                            artist = data.get('artists', data.get('artist', 'Unknown'))
                            album = data.get('album', 'Unknown')
                            cover_url = data.get('cover', data.get('cover_url', ''))
                            task['metadata'] = {
                                'title': title,
                                'artist': artist,
                                'album': album,
                                'cover_url': cover_url
                            }
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
                            o_data = o_res.json()
                            raw_title = o_data.get('title', 'Unknown')
                            thumbnail = o_data.get('thumbnail_url', '')
                            author = o_data.get('author_name', '')
                            # ตัว Spotify oEmbed title มักจะมาในรูปแบบ "Song - Artist"
                            if ' - ' in raw_title:
                                parts = raw_title.rsplit(' - ', 1)
                                clean_title = parts[0].strip()
                                clean_artist = parts[1].strip() if not author else author
                            else:
                                clean_title = raw_title
                                clean_artist = author if author else 'Unknown Artist'
                            task['metadata'] = {
                                'title': clean_title,
                                'artist': clean_artist,
                                'album': 'Spotify',
                                'cover_url': thumbnail
                            }
                            search_query = f"{clean_title} {clean_artist}".strip()
                    except: pass
                
                if not search_query:
                    raise Exception("Could not identify Spotify track. Please check the link or try a YouTube link.")

                # แปลงร่างเป็นคำค้นหา YouTube (ห้ามส่งลิงก์ Spotify ให้ yt-dlp เด็ดขาด!)
                url = f"ytsearch1:{search_query}"
                task['logs'].append(f"Redirecting to YouTube Engine: {search_query}")
            elif 'youtube.com' in url or 'youtu.be' in url:
                yt_meta = get_youtube_metadata(url)
                if yt_meta:
                    task['metadata'] = yt_meta

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
                'retries': 5,
                'fragment_retries': 5,
                'socket_timeout': 20,
                # tv_embedded ไม่ต้องใช้ n challenge — เหมาะสำหรับ DASH โดยไม่ต้อง JS runtime
                'extractor_args': {
                    'youtube': {
                        'player_client': ['tv_embedded', 'ios', 'android', 'web'],
                    }
                },
                'youtube_include_dash_manifest': True,
            }
                
            task['logs'].append("🌐 [Direct Mode] Active.")

            if fmt == 'video':
                res = {'4k':'2160','1080p':'1080','720p':'720','480p':'480'}.get(quality, '1080')
                # cascade: DASH สูง → DASH ใดก็ได้ → combined stream (format 18/22)
                ydl_opts['format'] = f'bestvideo[height<={res}]+bestaudio/bestvideo+bestaudio/best[height<={res}]/best'
                ydl_opts['merge_output_format'] = 'mp4'
                # yt-dlp จัดการ metadata และ thumbnail ให้แล้ว ไม่ต้องรัน embed_metadata ซ้ำ
                ydl_opts['writethumbnail'] = True
                ydl_opts['postprocessors'] = [{'key':'FFmpegMetadata'},{'key':'EmbedThumbnail'}]
            else:
                br = {'4k':'320','1080p':'256','720p':'192','480p':'128'}.get(quality, '320')
                ext = 'mp3' if fmt == 'audio' else 'wav'
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [
                    {'key':'FFmpegExtractAudio','preferredcodec':ext,'preferredquality':br},
                    {'key':'FFmpegMetadata'}, {'key':'EmbedThumbnail'},
                ]

            # --- ระบบดาวน์โหลด (Debug Mode) ---
            abs_download_path = os.path.abspath(DOWNLOAD_FOLDER)
            temp_dir_name = f"yt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
            temp_dir = os.path.join(abs_download_path, temp_dir_name)
            os.makedirs(temp_dir, exist_ok=True)
            
            # ปิด Quiet เพื่อดู Log ใน Terminal
            ydl_opts['quiet'] = False
            ydl_opts['no_warnings'] = False
            ydl_opts['outtmpl'] = os.path.join(temp_dir, '%(title)s.%(ext)s')

            try:
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
            except Exception as e:
                print(f"DEBUG: Local engine failed: {e}")
                raise

            # Embed metadata — ข้าม video เพราะ yt-dlp จัดการ EmbedThumbnail ให้แล้ว
            if fmt != 'video' and task.get('filename') and not task['filename'].endswith('.zip'):
                filepath = os.path.join(abs_download_path, task['filename'])
                if os.path.exists(filepath):
                    task['logs'].append("Embedding Media Tags & Cover Art...")
                    meta = task.get('metadata', {})
                    if not meta.get('title'):
                        clean_title = os.path.splitext(task['filename'])[0]
                        clean_title = re.sub(r'\s*\[[a-zA-Z0-9_-]{11}\]$', '', clean_title)
                        meta['title'] = clean_title
                    if not meta.get('artist'):
                        meta['artist'] = 'MultiLoader'
                    embed_metadata(filepath, meta)

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
