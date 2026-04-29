import requests

url = "https://api.cobalt.tools/api/json"
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

# Test 1: V6 Payload
try:
    print("Testing V6 Payload (isAudioOnly):")
    res1 = requests.post(url, json={"url": "https://youtu.be/pc31uAeVANk", "isAudioOnly": True}, headers=headers)
    print(f"Status: {res1.status_code}")
    print(f"Response: {res1.text}\n")
except Exception as e:
    print(e)

# Test 2: V7 Payload
try:
    print("Testing V7 Payload (downloadMode='audio'):")
    res2 = requests.post(url, json={"url": "https://youtu.be/pc31uAeVANk", "downloadMode": "audio"}, headers=headers)
    print(f"Status: {res2.status_code}")
    print(f"Response: {res2.text}\n")
except Exception as e:
    print(e)

# Test 3: Minimal
try:
    print("Testing Minimal Payload:")
    res3 = requests.post(url, json={"url": "https://youtu.be/pc31uAeVANk"}, headers=headers)
    print(f"Status: {res3.status_code}")
    print(f"Response: {res3.text}\n")
except Exception as e:
    print(e)
