import json
import re
from typing import Any, Dict
import requests
import time

from src.config import (
    OPENAI_API_KEY,
    GEMINI_API_KEY,
    XAI_API_KEY,
    OPENAI_MODEL,
    GEMINI_MODEL,
    XAI_MODEL,
)

def extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        raise ValueError("Empty model response")

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find JSON in response: {text[:500]}")
    return json.loads(match.group(0))


class BaseProvider:
    name = "base"

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        raise NotImplementedError


class OpenAIProvider(BaseProvider):
    name = "openai"

    def _extract_response_text(self, data: Dict[str, Any]) -> str:
        #chatgpt returns text in 2 different ways... 1) top-level output_text or 2) output[].content[].text where content type == output_text
        #first try the convenience field
        text = data.get("output_text", "")
        if text and text.strip():
            return text.strip()

        #in case that didn't work, I walk the output array
        chunks = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        part_text = content.get("text", "")
                        if part_text:
                            chunks.append(part_text)

        return "\n".join(chunks).strip()

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY missing")

        url = "https://api.openai.com/v1/responses"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": OPENAI_MODEL,
            "input": prompt,
            "tools": [{"type": "web_search"}],
            "include": ["web_search_call.action.sources"],
            "temperature": 0.1,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()

        #save raw response for debugging, and later review if needed
        try:
            with open("results/openai_last_raw_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        text = self._extract_response_text(data)

        if not text:
            raise ValueError(
                "Empty model response. Check results/openai_last_raw_response.json "
                "to inspect the raw OpenAI response."
            )

        parsed = extract_json_object(text)

        #collect web search sources if present
        parsed["_provider_citations"] = []

        for item in data.get("output", []):
            if item.get("type") == "web_search_call":
                action = item.get("action", {})
                for src in action.get("sources", []):
                    src_url = src.get("url")
                    if src_url:
                        parsed["_provider_citations"].append(src_url)

        parsed["_provider_citations"] = list(dict.fromkeys(parsed["_provider_citations"]))
        return parsed


class GeminiProvider(BaseProvider):
    name = "gemini"

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY missing")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent"
        )
        headers = {
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        }

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {
                "temperature": 0.1,
                "thinkingConfig": {
                    "thinkingLevel": "low"
                }
            }
        }

        last_error = None

        for attempt in range(5):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=90)
                response.raise_for_status()
                data = response.json()

                with open("results/gemini_last_raw_response.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                candidates = data.get("candidates", [])
                if not candidates:
                    raise ValueError(f"No Gemini candidates returned: {data}")

                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])

                text_chunks = []
                for part in parts:
                    if isinstance(part, dict) and "text" in part and part["text"]:
                        text_chunks.append(part["text"])

                text = "\n".join(text_chunks).strip()

                if not text:
                    raise ValueError(
                        f"Gemini returned no text. finishReason={candidate.get('finishReason')}. "
                        "Check results/gemini_last_raw_response.json"
                    )

                parsed = extract_json_object(text)

                #optional grounding URLs if present
                parsed["_provider_citations"] = []
                grounding = candidate.get("groundingMetadata", {})
                for chunk in grounding.get("groundingChunks", []):
                    web = chunk.get("web", {})
                    uri = web.get("uri")
                    if uri:
                        parsed["_provider_citations"].append(uri)
                parsed["_provider_citations"] = list(dict.fromkeys(parsed["_provider_citations"]))

                return parsed

            except requests.HTTPError as e:
                last_error = e
                status = e.response.status_code if e.response is not None else None
                if status and status >= 500 and attempt < 4:
                    wait_time = 2 ** attempt
                    print(f"[GEMINI RETRY] attempt={attempt + 1} waiting={wait_time}s status={status}")
                    time.sleep(wait_time)
                    continue
                raise

            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise last_error

class GrokProvider(BaseProvider):
    name = "grok"

    def _extract_response_text(self, data: Dict[str, Any]) -> str:
        #try top-level convenience field first
        text = data.get("output_text", "")
        if text and text.strip():
            return text.strip()

        #if it doesnt work... walk response.output -> message -> content (similar idea to what i did with the openai responses above)
        chunks = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    content_type = content.get("type")
                    if content_type in ("output_text", "text"):
                        part_text = content.get("text", "")
                        if part_text:
                            chunks.append(part_text)

        return "\n".join(chunks).strip()

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        if not XAI_API_KEY:
            raise ValueError("XAI_API_KEY missing")

        url = "https://api.x.ai/v1/responses"
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": XAI_MODEL,
            "input": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "tools": [
                {
                    "type": "web_search"
                }
            ]
        }

        response = requests.post(url, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        data = response.json()
        #adding this block to debug grok issues with API level citations... i am least familar with this api
        from pathlib import Path

        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)

        debug_path = results_dir / "grok_last_raw_response.json"

        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[GROK DEBUG SAVED] {debug_path}")
        except Exception as e:
            print(f"[GROK DEBUG SAVE FAILED] {e}")

        text = self._extract_response_text(data)

        if not text:
            raise ValueError("Empty model response...")

        #save raw response for debugging and later reference
        try:
            with open("results/grok_last_raw_response.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        text = self._extract_response_text(data)
        if not text:
            raise ValueError(
                "Empty model response. Check results/grok_last_raw_response.json"
            )

        parsed = extract_json_object(text)

        #citations are returned by default on the response object
        parsed["_provider_citations"] = list(dict.fromkeys(data.get("citations", [])))
        return parsed


def get_active_providers():
    providers = []

    if OPENAI_API_KEY:
        providers.append(OpenAIProvider())
    if GEMINI_API_KEY:
        providers.append(GeminiProvider())
    if XAI_API_KEY:
        providers.append(GrokProvider())

    if not providers:
        raise ValueError("No provider API keys found")

    return providers