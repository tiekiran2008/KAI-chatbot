import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in environment.")
    exit(1)

try:
    # Uses google-genai SDK (v1+)
    from google import genai
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='Write a short greeting and verify you can respond.'
    )
    print("--- Using google.genai ---")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
