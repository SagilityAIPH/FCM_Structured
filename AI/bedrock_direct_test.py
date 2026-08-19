import requests
import getpass
# python -m pip install requests
# python bedrock_direct_test.py
REGION = "us-east-1"
MODEL_ID = "openai.gpt-oss-120b-1:0"

API_KEY = getpass.getpass("Paste NEW Bedrock API key (hidden): ").strip()

url = (
    f"https://bedrock-runtime.{REGION}.amazonaws.com/"
    f"model/{MODEL_ID}/converse"
)

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "messages": [
        {
            "role": "user",
            "content": [
                {"text": "Reply exactly with BEDROCK_OK"}
            ],
        }
    ],
    "inferenceConfig": {
        "maxTokens": 32,
        "temperature": 0
    },
}

print("\nTesting Bedrock Runtime...")
print(f"Region: {REGION}")
print(f"Model:  {MODEL_ID}")

try:
    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    print("\nHTTP STATUS:", response.status_code)

    try:
        print(response.json())
    except Exception:
        print(response.text)

except requests.exceptions.RequestException as exc:
    print("\nREQUEST ERROR:")
    print(exc)
