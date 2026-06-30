import sys
# Reconfigure stdout to use UTF-8 encoding to prevent Windows console encoding errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from google import genai
from google.genai import types

import config

def test_query():
    config.validate_config()
    client = genai.Client(api_key=config.API_KEY)
    
    # 1. Find the store
    print("Finding File Search Store...")
    stores = client.file_search_stores.list()
    store_name = None
    for store in stores:
        if store.display_name == config.VECTOR_STORE_NAME:
            store_name = store.name
            break
            
    if not store_name:
        print(f"Error: Store '{config.VECTOR_STORE_NAME}' not found. Please run main.py first.")
        sys.exit(1)
        
    print(f"Found store: {store_name}")
    
    # 2. Query the model with File Search enabled
    prompt = "How do I add a YouTube video?"
    print(f"\nQuerying Gemini with prompt: '{prompt}'...")
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are OptiBot, the customer-support bot for OptiSigns.com.\n"
                    "• Tone: helpful, factual, concise.\n"
                    "• Only answer using the uploaded docs.\n"
                    "• Max 5 bullet points; else link to the doc.\n"
                    "• Cite up to 3 \"Article URL:\" lines per reply."
                ),
                temperature=0.0,
                tools=[
                    types.Tool(
                        file_search=types.FileSearch(
                            file_search_store_names=[store_name]
                        )
                    )
                ]
            )
        )
        
        print("\n=== Gemini Response ===")
        print(response.text)
        print("=======================")
        
    except Exception as e:
        print(f"Error querying model: {e}")

if __name__ == "__main__":
    test_query()
