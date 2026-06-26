import os
from dotenv import load_dotenv
import requests

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)
api_key = os.getenv("GEMINI_API_KEY")

# Try with x-goog-api-key header
url3 = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
headers3 = {"Content-Type": "application/json", "x-goog-api-key": api_key}
data = {"contents": [{"parts": [{"text": "Hello"}]}]}
r3 = requests.post(url3, headers=headers3, json=data)
print("x-goog-api-key header response:", r3.status_code, r3.text)
