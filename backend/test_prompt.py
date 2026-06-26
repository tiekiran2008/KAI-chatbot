import os
import sys
import asyncio
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=env_path)

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

os.environ["POSTGRES_PASSWORD"] = "dummy"
os.environ["SUPABASE_JWT_SECRET"] = "dummy"

import importlib.util
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

prompt_builder_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../app/services/prompt_builder.py'))
spec = importlib.util.spec_from_file_location("prompt_builder", prompt_builder_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
prompt_builder = module.prompt_builder
from google import genai
from google.genai import types

async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    system_prompt = prompt_builder.build_system_prompt()
    
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
    )
    
    print("Sending query: 'What is AI?'")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='What is AI?',
        config=config,
    )
    print("--- Response ---")
    print(response.text)

if __name__ == "__main__":
    asyncio.run(main())
