import os
from dotenv import load_dotenv
import requests

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)
api_key = os.getenv("GEMINI_API_KEY")

print("Key:", api_key[:10])

# Try as API Key
url1 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
headers1 = {"Content-Type": "application/json"}
data = {"contents": [{"parts": [{"text": "Hello"}]}]}
r1 = requests.post(url1, headers=headers1, json=data)
print("API Key URL param response:", r1.status_code, r1.text)

# Try as Bearer Token
url2 = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
headers2 = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
r2 = requests.post(url2, headers=headers2, json=data)
print("Bearer Token response:", r2.status_code, r2.text)

