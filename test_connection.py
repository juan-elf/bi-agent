import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("MINIMAX_API_KEY")
if not api_key:
    print("ERROR: MINIMAX_API_KEY not found in .env file")
    print("   Make sure .env exists in the same folder and contains:")
    print("   MINIMAX_API_KEY=your_key_here")
    exit(1)

client = OpenAI(
    api_key=api_key,
    base_url="https://api.minimax.io/v1"
)

print("Connecting to MiniMax API...\n")

try:
    response = client.chat.completions.create(
        model="MiniMax-M2.1",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. Reply briefly."},
            {"role": "user", "content": "Hello! List 3 things you can do."}
        ],
        max_tokens=300
    )

    print("Connection successful\n")
    print("Response from MiniMax:")
    print("-" * 50)
    print(response.choices[0].message.content)
    print("-" * 50)
    print(f"\nToken usage: {response.usage.total_tokens} tokens")

except Exception as e:
    print(f"ERROR calling the API:")
    print(f"   {type(e).__name__}: {e}")
    print("\nCheck the following:")
    print("   - API key is valid and has credit")
    print("   - Internet connection is OK")
    print("   - Model name is correct (MiniMax-M2.1)")
