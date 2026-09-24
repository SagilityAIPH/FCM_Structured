"""Bedrock Runtime Converse transport for the native application."""
import os
import re
from types import SimpleNamespace
from urllib.parse import quote

import httpx

try:
    from .bedrock_core import *
except ImportError:
    from bedrock_core import *

DEFAULT_BEDROCK_MODEL = "openai.gpt-oss-120b-1:0"


def resolve_bedrock_api_key(manual_key=""):
    return (manual_key or os.getenv("AWS_BEARER_TOKEN_BEDROCK") or os.getenv("OPENAI_API_KEY") or "").strip()


def build_bedrock_base_url(region):
    region = (region or DEFAULT_BEDROCK_REGION).strip()
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", region):
        raise ValueError("Enter a valid AWS region, such as us-east-2.")
    return f"https://bedrock-runtime.{region}.amazonaws.com"


class RuntimeClient:
    """Adapt the shared extraction engine's calls to Runtime Converse requests."""
    def __init__(self, api_key, base_url, transport=None):
        if not api_key.strip():
            raise ValueError("Enter a Bedrock API key or set AWS_BEARER_TOKEN_BEDROCK.")
        self._key = api_key.strip()
        self._http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {self._key}"},
            timeout=httpx.Timeout(DEFAULT_REQUEST_TIMEOUT, connect=30),
            transport=transport,
        )
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._http.close()

    def create(self, *, model, messages, max_completion_tokens, temperature, top_p=None):
        payload = {
            "messages": [{"role": message["role"], "content": [{"text": message["content"]}]}
                         for message in messages if message["role"] != "system"],
            "inferenceConfig": {"maxTokens": max_completion_tokens, "temperature": temperature},
        }
        system = [{"text": message["content"]} for message in messages if message["role"] == "system"]
        if system:
            payload["system"] = system
        if top_p is not None:
            payload["inferenceConfig"]["topP"] = top_p
        response = self._http.post(f"/model/{quote(model.strip(), safe='')}/converse", json=payload)
        if response.is_error:
            detail = response.text.replace(self._key, "[redacted]")[:2000]
            raise RuntimeError(f"Bedrock Runtime HTTP {response.status_code}: {detail}")
        body = response.json()
        blocks = body.get("output", {}).get("message", {}).get("content", [])
        text = "\n".join(block["text"] for block in blocks if isinstance(block, dict) and block.get("text"))
        if not text.strip():
            raise RuntimeError("Bedrock Runtime returned no answer text. Try increasing output tokens or check the model settings.")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def create_bedrock_client(api_key, base_url):
    return RuntimeClient(api_key, base_url)
