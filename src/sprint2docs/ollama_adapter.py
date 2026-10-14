"""Replaceable Ollama transport restricted to literal IPv4 loopback.

No proxy, DNS, redirect, tool execution, model downloads, or cloud model routing.
"""

import http.client
import json
import re
from typing import Any, Protocol

from .generation_models import GenerationSettings, response_schema


class OllamaError(Exception):
    """Safe category-only message; never expose HTTP bodies or source content."""


class WriterAdapter(Protocol):
    def models(self) -> dict[str, str]: ...

    def generate(self, system: str, context: str, settings: GenerationSettings) -> str: ...


def local_model_name(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", name)) and not (
        "cloud" in name.lower() or "://" in name or ".." in name
    )


class OllamaAdapter:
    def __init__(self, port: int = 11434) -> None:
        if not 1 <= port <= 65535:
            raise ValueError("Invalid local Ollama port.")
        self.port = port

    def _request(self, path: str, payload: dict[str, Any] | None, timeout: int) -> Any:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            data = json.dumps(payload).encode() if payload is not None else None
            connection.request(
                "POST" if payload is not None else "GET",
                path,
                body=data,
                headers={"Content-Type": "application/json"},
            )
            response = connection.getresponse()
            if response.status != 200:
                raise OllamaError("Ollama request failed (HTTP status).")
            body = response.read(256_001)
            if len(body) > 256_000:
                raise OllamaError("Ollama response exceeded size limit.")
            return json.loads(body)
        except TimeoutError:
            raise OllamaError("Local Ollama request timed out.") from None
        except (OSError, http.client.HTTPException):
            raise OllamaError("Local Ollama is unavailable.") from None
        except (ValueError, UnicodeError):
            raise OllamaError("Ollama returned invalid JSON.") from None
        finally:
            connection.close()

    def models(self) -> dict[str, str]:
        response = self._request("/api/tags", None, 5)
        if not isinstance(response, dict) or not isinstance(response.get("models"), list):
            raise OllamaError("Invalid Ollama model list.")
        models: dict[str, str] = {}
        for item in response["models"]:
            if not isinstance(item, dict):
                continue
            name, digest = item.get("name"), item.get("digest")
            if (
                isinstance(name, str)
                and local_model_name(name)
                and isinstance(digest, str)
                and re.fullmatch(r"[a-f0-9]{64}", digest)
                and not item.get("remote_host")
                and not item.get("remote_model")
            ):
                models[name] = digest
        return models

    def generate(self, system: str, context: str, settings: GenerationSettings) -> str:
        if not local_model_name(settings.model):
            raise OllamaError("Select a local model; cloud names are disabled.")
        result = self._request(
            "/api/chat",
            {
                "model": settings.model,
                "stream": False,
                "think": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": context},
                ],
                "format": response_schema(settings.batch_records),
                "options": {
                    "temperature": settings.temperature,
                    "seed": settings.seed,
                    "num_predict": settings.num_predict,
                    "num_ctx": settings.num_ctx,
                },
            },
            settings.timeout_seconds,
        )
        if not isinstance(result, dict) or result.get("done") is not True:
            raise OllamaError("Ollama returned an incomplete response.")
        message = result.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            if result.get("done_reason") == "length":
                raise OllamaError("Ollama reached the output limit.")
            raise OllamaError("Ollama returned an invalid message.")
        if not message["content"].strip() and message.get("thinking"):
            raise OllamaError(
                "Model returned reasoning without an answer. Select a non-thinking/instruct model; "
                "some Qwen3-VL thinking models ignore think=false."
            )
        if result.get("done_reason") == "length":
            raise OllamaError("Ollama reached the output limit.")
        if message.get("tool_calls"):
            raise OllamaError("Ollama returned an unexpected tool request.")
        return str(message["content"])
