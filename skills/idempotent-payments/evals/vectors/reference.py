"""Reference implementation for the idempotent-payments vectors.

An in-memory idempotency store, a guarded payment state machine, a retry classifier and a
payment service against a scriptable fake processor. The point is the behavior the vectors pin:
one charge per key, unknown outcome on timeout, persist before call, first writer wins.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


class FingerprintMismatch(ValueError):
    pass


class InProgress(Exception):
    pass


class IllegalTransition(ValueError):
    pass


class ProcessorError(Exception):
    def __init__(self, status: int, message: str = ""):
        super().__init__(f"{status} {message}")
        self.status = status


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass
class Record:
    tenant: str
    operation: str
    key: str
    fingerprint: str
    status: str  # in_progress | done
    response: dict | None = None


class IdempotencyStore:
    """Unique on (tenant, operation, key). The first begin() wins; later ones replay or fail."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str], Record] = {}

    def begin(self, tenant: str, operation: str, key: str, payload: dict) -> tuple[str, dict | None]:
        fp = fingerprint(payload)
        row = self._rows.get((tenant, operation, key))
        if row is None:
            self._rows[(tenant, operation, key)] = Record(tenant, operation, key, fp, "in_progress")
            return ("new", None)
        if row.fingerprint != fp:
            raise FingerprintMismatch("same key, different request")
        if row.status == "in_progress":
            raise InProgress(key)
        return ("replay", dict(row.response or {}))

    def complete(self, tenant: str, operation: str, key: str, response: dict) -> None:
        row = self._rows[(tenant, operation, key)]
        row.response = dict(response)
        row.status = "done"

    def __len__(self) -> int:
        return len(self._rows)


TRANSITIONS = {
    ("created", "authorize"): "authorized",
    ("created", "fail"): "failed",
    ("authorized", "capture"): "captured",
    ("authorized", "void"): "voided",
    ("authorized", "fail"): "failed",
    ("captured", "settle"): "settled",
    ("captured", "refund"): "refunded",
    ("captured", "partial_refund"): "partially_refunded",
    ("settled", "refund"): "refunded",
    ("settled", "partial_refund"): "partially_refunded",
    ("partially_refunded", "refund"): "refunded",
    ("partially_refunded", "partial_refund"): "partially_refunded",
}


def transition(state: str, event: str) -> str:
    try:
        return TRANSITIONS[(state, event)]
    except KeyError:
        raise IllegalTransition(f"{event} is not allowed from {state}") from None


def is_retryable(status: int | None) -> bool:
    """None means a network error or timeout. 429 and 5xx retry; every 4xx is final."""
    if status is None:
        return True
    if status == 429:
        return True
    return 500 <= status <= 599


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.2
    max_delay: float = 5.0

    def delay(self, attempt: int) -> float:
        return min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))


class FakeProcessor:
    """Each call consumes one scripted outcome: ok, timeout, or an HTTP status such as 500 or 400.
    A timeout performs the charge and then raises, which is what makes the outcome unknown."""

    def __init__(self, script: list[str] | None = None) -> None:
        self.script = list(script or [])
        self.charges: dict[str, dict] = {}
        self.calls = 0

    def charge(self, idempotency_key: str, amount: int) -> dict:
        self.calls += 1
        outcome = self.script.pop(0) if self.script else "ok"
        if outcome == "timeout":
            self.charges.setdefault(idempotency_key, {"id": f"ch_{len(self.charges) + 1}", "amount": amount, "status": "succeeded"})
            raise TimeoutError("read timed out")
        if outcome != "ok":
            raise ProcessorError(int(outcome), "scripted")
        if idempotency_key in self.charges:
            return dict(self.charges[idempotency_key])
        self.charges[idempotency_key] = {"id": f"ch_{len(self.charges) + 1}", "amount": amount, "status": "succeeded"}
        return dict(self.charges[idempotency_key])

    def lookup(self, idempotency_key: str) -> dict | None:
        found = self.charges.get(idempotency_key)
        return dict(found) if found else None


@dataclass
class PaymentService:
    store: IdempotencyStore
    processor: FakeProcessor
    policy: RetryPolicy = field(default_factory=RetryPolicy)
    sleeper: object = staticmethod(lambda seconds: None)
    intents: dict[str, dict] = field(default_factory=dict)

    @staticmethod
    def operation_id(tenant: str, key: str) -> str:
        return f"{tenant}:charge:{key}"

    def persist_intent(self, tenant: str, key: str, payload: dict) -> str:
        op_id = self.operation_id(tenant, key)
        self.intents.setdefault(op_id, {"status": "pending", "amount": payload["amount"], "processor_ref": None})
        return op_id

    def charge(self, tenant: str, key: str, payload: dict) -> dict:
        try:
            kind, response = self.store.begin(tenant, "charge", key, payload)
        except InProgress:
            return self.resolve(tenant, key, payload)
        if kind == "replay":
            return response
        self.persist_intent(tenant, key, payload)
        return self._attempt(tenant, key, payload)

    def _attempt(self, tenant: str, key: str, payload: dict) -> dict:
        op_id = self.operation_id(tenant, key)
        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                result = self.processor.charge(op_id, payload["amount"])
            except TimeoutError:
                return {"status": "pending", "operation": op_id}  # unknown outcome: nothing is retried blindly
            except ProcessorError as exc:
                if not is_retryable(exc.status):
                    return self._finish(tenant, key, {"status": "failed", "error": exc.status})
                if attempt == self.policy.max_attempts:
                    return {"status": "pending", "operation": op_id}
                self.sleeper(self.policy.delay(attempt))
                continue
            return self._finish(tenant, key, {"status": "succeeded", "processor_ref": result["id"], "amount": result["amount"]})
        return {"status": "pending", "operation": op_id}

    def _finish(self, tenant: str, key: str, response: dict) -> dict:
        op_id = self.operation_id(tenant, key)
        self.intents[op_id].update({"status": response["status"], "processor_ref": response.get("processor_ref")})
        self.store.complete(tenant, "charge", key, response)
        return dict(response)

    def resolve(self, tenant: str, key: str, payload: dict) -> dict:
        """A retry on an in-progress key: ask the processor before doing anything."""
        op_id = self.operation_id(tenant, key)
        found = self.processor.lookup(op_id)
        if found is not None:
            return self._finish(tenant, key, {"status": "succeeded", "processor_ref": found["id"], "amount": found["amount"]})
        return self._attempt(tenant, key, payload)

    def reconcile_pending(self) -> dict:
        resolved, still_pending = 0, 0
        for op_id, intent in list(self.intents.items()):
            if intent["status"] != "pending":
                continue
            found = self.processor.lookup(op_id)
            if found is None:
                still_pending += 1
                continue
            tenant, _, key = op_id.split(":", 2)
            self._finish(tenant, key, {"status": "succeeded", "processor_ref": found["id"], "amount": found["amount"]})
            resolved += 1
        return {"resolved": resolved, "pending": still_pending}
