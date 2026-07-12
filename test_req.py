import requests

req = {
    "text": "Hello world.",
}

try:
    response = requests.post("http://127.0.0.1:8880/v1/tts", json=req)
    print(response.status_code)
except Exception as e:
    print(e)
