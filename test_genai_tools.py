import asyncio
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv()

async def main():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    def get_current_time() -> str:
        """Returns the current time."""
        return "12:00 PM"
        
    config = types.GenerateContentConfig(
        tools=[get_current_time],
        temperature=0.0
    )
    
    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents="What time is it?",
        config=config
    )
    
    print("Response parts:", response.candidates[0].content.parts)
    for part in response.candidates[0].content.parts:
        if part.function_call:
            print("Function call:", part.function_call.name, part.function_call.args)
            
            try:
                function_response = types.Part.from_function_response(
                    name=part.function_call.name,
                    response={"result": "12:00 PM"}
                )
                print("Function response part:", function_response)
            except AttributeError:
                print("from_function_response not found, trying Part(function_response=...)")
                function_response = types.Part(
                    function_response=types.FunctionResponse(
                        name=part.function_call.name,
                        response={"result": "12:00 PM"}
                    )
                )
                print("Function response part:", function_response)

if __name__ == "__main__":
    asyncio.run(main())
