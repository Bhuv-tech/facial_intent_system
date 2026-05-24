import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DEEPSEEK_API_KEY")
# Try different URLs
URLS = [
    "https://integrate.api.nvidia.com/v1/chat/completions",
    "https://ai.api.nvidia.com/v1/chat/completions",
]

# Try different model IDs
MODELS = [
    "deepseek-ai/deepseek-v3.2",
    "deepseek-ai/deepseek-v3.1",
    "deepseek-ai/deepseek-v3.1-terminus",
    "deepseek-ai/deepseek-r1-distill-llama-8b",
]

def test_endpoints():
    for url in URLS:
        for model in MODELS:
            print(f"Testing URL: {url} | Model: {model}")
            headers = {
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 10
            }
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                print(f"Status: {response.status_code}")
                if response.status_code == 200:
                    print("SUCCESS!")
                    return url, model
                else:
                    print(f"Body: {response.text[:200]}")
            except Exception as e:
                print(f"Error: {e}")
            print("-" * 20)
    return None, None

if __name__ == "__main__":
    url, model = test_endpoints()
    if url:
        print(f"\nRecommended Config:")
        print(f"DEEPSEEK_URL={url}")
        print(f"DEEPSEEK_MODEL={model}")
