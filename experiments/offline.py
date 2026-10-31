"""Deterministic transport stub. No SDK import, credentials, or networking."""
from types import SimpleNamespace


class OfflineClient:
    offline_only = True

    def __init__(self, fail_on_call=None):
        self.calls = 0
        self.fail_on_call = fail_on_call
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **request):
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise RuntimeError("Synthetic transport failure")
        is_summary = (
            len(request["messages"]) == 1
            and request["messages"][0]["content"].startswith("Summarize the following conversation.")
        )
        text = (
            "[OFFLINE STUB SUMMARY: no model inference]"
            if is_summary else "[OFFLINE STUB REPLY: no model inference]"
        )
        return SimpleNamespace(
            model="offline-stub-v1", usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
        )
