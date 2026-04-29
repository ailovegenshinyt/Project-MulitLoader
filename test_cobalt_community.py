import requests

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
    instances = [
        "https://co.wuk.sh/api/json",
        "https://cobalt.q0.uk/api/json",
        "https://cobalt.kwiatektv.me/api/json"
    ]
    
    for instance in instances:
        print(f"Testing instance: {instance}")
        try:
            res = requests.post(instance, json=data, headers=headers, timeout=10)
            print(f"Status Code: {res.status_code}")
            print(f"Response: {res.text[:200]}")
        except Exception as e:
            print(f"Error: {e}")

test_cobalt("https://www.youtube.com/watch?v=dQw4w9WgXcQ", False)
