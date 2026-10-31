"""Bounded provider transport. Importing this module never imports the SDK."""
from __future__ import annotations

import copy
import getpass
from decimal import Decimal
import json
import os
import sys
from importlib import metadata
from pathlib import Path
import time
from types import SimpleNamespace
from datetime import datetime, timezone

from agent import digest


class PilotStopped(RuntimeError):
    """Safe failure message; provider exception text is never propagated."""


def now():
    return datetime.now(timezone.utc).isoformat()


def append_record(handle, value):
    handle.write(json.dumps(value, ensure_ascii=False) + "\n")
    handle.flush()
    os.fsync(handle.fileno())


class ReservationBudget:
    """No refunds after dispatch: a timeout can still have incurred charges."""
    def __init__(self, plan, ceiling):
        self.ceiling = Decimal(str(ceiling))
        self.per_call = Decimal(plan["budget"]["reserved_usd_per_call"])
        if not self.ceiling.is_finite() or self.ceiling <= 0:
            raise ValueError("Budget must be positive and finite")
        self.max_calls = plan["max_provider_calls"]
        self.calls = 0
        self.reserved = Decimal("0")

    def reserve(self):
        if self.calls >= self.max_calls or self.reserved + self.per_call > self.ceiling:
            raise PilotStopped("Call or spending reservation limit reached")
        self.calls += 1
        self.reserved += self.per_call
        return self.calls


def build_sdk_client(plan, *, prompt_key=False):
    """Called only after live CLI approval checks and output validation."""
    if os.environ.get("OPENAI_LOG"):
        raise PilotStopped("Disable OPENAI_LOG before using the research runner")
    if os.environ.get("OPENAI_BASE_URL"):
        raise PilotStopped("Remove OPENAI_BASE_URL; the pilot uses the approved endpoint only")
    locked = Path(__file__).resolve().parents[1] / "requirements-lock.txt"
    for line in locked.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, wanted = line.split("==", 1)
        try:
            installed = metadata.version(name)
        except metadata.PackageNotFoundError:
            raise PilotStopped("Install the locked dependencies in a fresh environment first") from None
        if installed != wanted:
            raise PilotStopped("Installed dependencies differ from requirements-lock.txt")
    if prompt_key:
        if not sys.stdin.isatty():
            raise PilotStopped("Private key entry requires an interactive local terminal")
        key = getpass.getpass("OpenAI API key (hidden, not saved): ")
    else:
        key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise PilotStopped("Set OPENAI_API_KEY privately in the local environment")
    import httpx
    from openai import OpenAI
    # Do not inherit proxy/CA environment overrides or follow endpoint redirects.
    http_client = httpx.Client(timeout=plan["timeout_seconds"], follow_redirects=False,
                               trust_env=False)
    try:
        return OpenAI(api_key=key, base_url="https://api.openai.com/v1",
                      max_retries=0, timeout=plan["timeout_seconds"], http_client=http_client)
    except Exception:
        http_client.close()
        raise PilotStopped("SDK setup failed") from None


class GuardedClient:
    def __init__(self, provider, plan, *, mode, ceiling, ledger):
        if mode not in ("offline", "live"):
            raise ValueError("Unknown mode")
        self.provider, self.plan, self.mode, self.ledger = provider, copy.deepcopy(plan), mode, ledger
        self.budget = ReservationBudget(plan, ceiling)
        self.trial_id = None
        self.dispatched = 0
        self.known_cost = Decimal("0")
        self.unknown_usage_calls = 0
        self.halted = False
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        if self.halted:
            raise PilotStopped("Transport already stopped")
        expected = {"model": self.plan["model"], **self.plan["settings"]}
        if {k: v for k, v in request.items() if k != "messages"} != expected:
            self.halted = True
            raise PilotStopped("Request differs from the frozen model/settings")
        messages = request.get("messages")
        if (not isinstance(messages, list) or not 1 <= len(messages) <= 16
                or any(not isinstance(m, dict) or set(m) != {"role", "content"}
                       or m["role"] not in ("system", "user", "assistant")
                       or not isinstance(m["content"], str) for m in messages)
                or len(json.dumps(request, ensure_ascii=False).encode()) > self.plan["max_request_bytes"]):
            self.halted = True
            raise PilotStopped("Request shape or size exceeds the pilot bounds")
        try:
            number = self.budget.reserve()
        except PilotStopped:
            self.halted = True
            raise
        # A failed journal write must prevent dispatch. No response is needed
        # to know that an already-written reservation may have been charged.
        start = {"kind": "call_reserved", "call_number": number, "trial_id": self.trial_id,
                 "mode": self.mode, "timestamp": now(), "request": copy.deepcopy(request),
                 "request_sha256": digest(request), "reserved_usd": str(self.budget.reserved)}
        try:
            append_record(self.ledger, start)
        except BaseException:
            self.halted = True
            raise
        self.dispatched += 1
        started = time.perf_counter()
        end = {"kind": "call_result", "call_number": number, "trial_id": self.trial_id,
               "mode": self.mode, "status": "error", "error_type": None,
               "response": None, "usage_cost_estimate_usd": None}
        try:
            response = self.provider.chat.completions.create(**request)
            choices = response.choices
            if len(choices) != 1:
                raise ValueError("Expected exactly one completion")
            choice = choices[0]
            if choice.message.content is not None and not isinstance(choice.message.content, str):
                raise ValueError("Expected text or a null refused completion")
            usage = getattr(response, "usage", None)
            token_counts = ({k: getattr(usage, k, None)
                             for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
                            if usage is not None else None)
            end["response"] = {
                "returned_model": getattr(response, "model", None), "usage": token_counts,
                "response_text": choice.message.content,
                "finish_reason": getattr(choice, "finish_reason", None),
                "refusal": getattr(choice.message, "refusal", None),
                "system_fingerprint": getattr(response, "system_fingerprint", None),
                "request_id": getattr(response, "_request_id", None),
            }
            if self.mode == "live":
                if response.model != self.plan["model"]:
                    raise ValueError("Returned model differs from the approved snapshot")
                if token_counts is None or any(type(v) is not int or v < 0 for v in token_counts.values()):
                    raise ValueError("Missing or invalid token usage")
                p, c, t = (token_counts[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
                limits = self.plan["budget"]
                if p > limits["reserved_input_tokens_per_call"] or c > limits["max_output_tokens_per_call"] or t != p + c:
                    raise ValueError("Token usage exceeds approved limits or is inconsistent")
                cost = (p * Decimal(limits["input_usd_per_million_tokens"])
                        + c * Decimal(limits["output_usd_per_million_tokens"])) / 1000000
                self.known_cost += cost
                end["usage_cost_estimate_usd"] = str(cost)
            end["status"] = "completed"
            return response
        except BaseException as error:
            self.halted = True
            self.unknown_usage_calls += self.mode == "live"
            end["error_type"] = type(error).__name__
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
            raise PilotStopped("Provider call failed; see redacted journal metadata") from None
        finally:
            end["timestamp"] = now()
            end["latency_seconds"] = time.perf_counter() - started
            try:
                append_record(self.ledger, end)
            except BaseException:
                self.halted = True
                raise

    def accounting(self):
        return {"mode": self.mode, "dispatched_calls": self.dispatched,
                "provider_calls": self.dispatched if self.mode == "live" else 0,
                "stub_calls": self.dispatched if self.mode == "offline" else 0,
                "reserved_cost_usd": str(self.budget.reserved) if self.mode == "live" else "0",
                "simulated_reservation_usd": str(self.budget.reserved) if self.mode == "offline" else None,
                "known_usage_cost_estimate_usd": str(self.known_cost) if self.mode == "live" else "0",
                "unknown_usage_calls": self.unknown_usage_calls,
                "total_cost_estimate_usd": None if self.unknown_usage_calls else str(self.known_cost),
                "note": "Usage-based estimate at registered prices, not an account billing statement."}
