"""Quick test script to verify Gemini API connectivity."""
from src.config import AppConfig

print("Loading config...", flush=True)
config = AppConfig()
print(f"API key set: {bool(config.gemini_api_key)}", flush=True)
print(f"Model: {config.gemini_model}", flush=True)

if not config.gemini_api_key:
    print("ERROR: No GEMINI_API_KEY set in .env")
    exit(1)

print("\nTesting basic Gemini API call...", flush=True)
try:
    from google import genai
    from google.genai import types as genai_types
    
    client = genai.Client(api_key=config.gemini_api_key)
    print("Client created.", flush=True)
    
    print("Sending test prompt...", flush=True)
    response = client.models.generate_content(
        model=config.gemini_model,
        contents="Say 'hello' in one word.",
        config=genai_types.GenerateContentConfig(temperature=0.1),
    )
    print(f"Response: {response.text}", flush=True)
    print("Basic API call: SUCCESS", flush=True)
except Exception as e:
    print(f"Basic API call FAILED: {e}", flush=True)
    exit(1)

print("\nTesting Grounded Search...", flush=True)
try:
    tool = genai_types.Tool(google_search=genai_types.GoogleSearch())
    config_with_search = genai_types.GenerateContentConfig(
        tools=[tool],
        temperature=0.2,
    )
    
    print("Sending grounded search query...", flush=True)
    response = client.models.generate_content(
        model=config.gemini_model,
        contents="What documentary film grants are currently accepting applications?",
        config=config_with_search,
    )
    print(f"Response length: {len(response.text)} chars", flush=True)
    print(f"First 200 chars: {response.text[:200]}...", flush=True)
    print("Grounded search: SUCCESS", flush=True)
except Exception as e:
    print(f"Grounded search FAILED: {e}", flush=True)
    exit(1)

print("\n" + "="*50)
print("All tests passed! Your API is working.")
print("="*50)
