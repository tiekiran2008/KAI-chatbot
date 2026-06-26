import os
from dotenv import load_dotenv
from google import genai

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path, override=True)
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

try:
    models = client.models.list()
    print("Available models:")
    for m in models:
        print(m.name)
except Exception as e:
    print(f"Error: {e}")
