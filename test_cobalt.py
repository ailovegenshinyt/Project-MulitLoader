import requests
import json

def test_cobalt(url, is_audio=False):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    data = {
        "url": url,
        "isAudioOnly": is_audio
    }
    print(f"Testing URL: {url}")
    try:
        res = requests.post("https://api.cobalt.tools/api/json", json=data, headers=headers)
        print(f"Status Code: {res.status_code}")
        print(f"Response: {res.text}")
    except Exception as e:
        print(f"Error: {e}")

test_cobalt("https://www.youtube.com/watch?v=dQw4w9WgXcQ", False)
