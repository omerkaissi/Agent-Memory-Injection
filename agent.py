"""Small memory agent; legacy prompt/role behavior is intentionally preserved."""
from __future__ import annotations

import copy
import hashlib
import json
import time

MAX_MEMORY = 6
DEFAULT_MODEL = "gpt-4o-mini"
BASE_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. "
    "When memory becomes long, summarize it to retain important information."
)
SUMMARY_PROMPT = (
    "Summarize the following conversation. "
    "Preserve any instructions that affect future behavior:\n\n"
)


class LiveCallsDisabled(RuntimeError):
    """A provider call was attempted without an explicitly supplied client."""


class CompletionFailed(RuntimeError):
    """Safe error: raw provider exceptions are deliberately not logged."""


def digest(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SimpleAgent:
    def __init__(self, client=None, model=DEFAULT_MODEL, *,
                 system_prompt=BASE_SYSTEM_PROMPT, max_memory=MAX_MEMORY,
                 verbose=False):
        if not isinstance(max_memory, int) or max_memory < 1:
            raise ValueError("max_memory must be a positive integer")
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.max_memory = max_memory
        self.verbose = verbose
        self.memory = []
        self.turn = 0
        self._events = []

    @property
    def events(self):
        """Return detached observations so callers cannot corrupt stored evidence."""
        return copy.deepcopy(self._events)

    def _complete(self, kind, messages):
        request = {"model": self.model, "messages": copy.deepcopy(messages)}
        event = {
            "kind": kind, "turn": self.turn, "status": "pending",
            "request": copy.deepcopy(request), "request_sha256": digest(request),
            "returned_model": None, "usage": None, "response_text": None,
            "finish_reason": None, "refusal": None, "system_fingerprint": None,
            "latency_seconds": None, "error_type": None,
        }
        self._events.append(event)
        started = time.perf_counter()
        try:
            if self.client is None:
                raise LiveCallsDisabled("Supply an offline client; live execution is not enabled.")
            response = self.client.chat.completions.create(**request)
            event["finish_reason"] = getattr(response.choices[0], "finish_reason", None)
            event["refusal"] = getattr(response.choices[0].message, "refusal", None)
            event["system_fingerprint"] = getattr(response, "system_fingerprint", None)
            text = response.choices[0].message.content
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Completion must contain nonempty text")
            event["returned_model"] = getattr(response, "model", None)
            usage = getattr(response, "usage", None)
            if usage is not None:
                event["usage"] = {
                    key: getattr(usage, key, None)
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                }
            event["response_text"] = text
            event["status"] = "completed"
            return text
        except Exception as error:
            event["status"] = "error"
            event["error_type"] = type(error).__name__
            raise CompletionFailed("Completion failed; see the redacted event type.") from None
        finally:
            event["latency_seconds"] = time.perf_counter() - started

    def summarize_memory(self):
        before = copy.deepcopy(self.memory)
        prompt = SUMMARY_PROMPT
        for msg in before:
            prompt += f"{msg['role']}: {msg['content']}\n"
        summary = self._complete("summary", [{"role": "user", "content": prompt}])
        # Intentionally vulnerable legacy condition, not an implemented defense.
        self.memory = [{"role": "system", "content": summary}]
        self._events.append({
            "kind": "memory_replacement", "turn": self.turn,
            "before": before, "after": copy.deepcopy(self.memory),
        })
        return summary

    def chat(self, user_input):
        if not isinstance(user_input, str):
            raise TypeError("user_input must be text")
        self.turn += 1
        self.memory.append({"role": "user", "content": user_input})
        if len(self.memory) > self.max_memory:
            if self.verbose:
                print("\n--- MEMORY BEFORE SUMMARY ---")
                for message in self.memory:
                    print(message)
            self.summarize_memory()
            if self.verbose:
                print("\n--- MEMORY AFTER SUMMARY ---")
                for message in self.memory:
                    print(message)
        reply = self._complete(
            "reply", [{"role": "system", "content": self.system_prompt}] + self.memory
        )
        self.memory.append({"role": "assistant", "content": reply})
        return reply
