import json
import os

import httpx

DEFAULT_HOST = "http://localhost:11434"


class OllamaError(RuntimeError):
    pass


def generate_analysis(model: str, prompt: str, timeout: float = 300.0) -> dict:
    host = os.environ.get("OLLAMA_HOST", DEFAULT_HOST).rstrip("/")
    request = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "think": False,
        "options": {
            "temperature": 0.1,
            "num_ctx": 8192,
            "num_predict": 1400,
        },
    }

    try:
        response = httpx.post(
            f"{host}/api/generate",
            json=request,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("response", "")

        if not isinstance(content, str) or not content.strip():
            raise OllamaError("Ollama returned an empty response.")

        result = json.loads(content)

    except httpx.TimeoutException as exc:
        raise OllamaError(
            f"Ollama timed out after {timeout:g} seconds at {host}."
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:1000]
        raise OllamaError(
            f"Ollama returned HTTP {exc.response.status_code}: {detail}"
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaError(f"Could not connect to Ollama at {host}: {exc}") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise OllamaError(f"Ollama returned invalid JSON: {exc}") from exc

    if not isinstance(result, dict):
        raise OllamaError("Ollama response must be a JSON object.")

    return result


def check_ollama():
    host = os.environ.get("OLLAMA_HOST", DEFAULT_HOST).rstrip("/")
    try:
        response = httpx.get(f"{host}/api/tags", timeout=5.0)
        response.raise_for_status()
        names = [
            item.get("name", "unknown")
            for item in response.json().get("models", [])
        ]
        return True, ", ".join(names) if names else "Ollama is running; no models installed."
    except (httpx.HTTPError, ValueError):
        return False, f"Cannot reach Ollama at {host}."
