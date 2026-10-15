"""Scoped, privacy-preserving conversation identity and conservative continuation."""
from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from typing import Any

from app.config import settings
from app.services.cache_simulation_state_service import CacheSimulationStateService, canonical_json


class CacheSimulationIdentityService:
    MAX_MESSAGES = 2048
    MAX_BYTES = 4 * 1024 * 1024
    SESSION_HEADERS = ("x-claude-code-session-id", "x-relay-session-id", "x-conversation-id",
                       "x-claude-conversation-id")

    @staticmethod
    def valid_id(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        if not value or len(value) > 128 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            return None
        return value

    @staticmethod
    def digest(value: Any) -> str:
        key = settings.CACHE_SIMULATION_HMAC_KEY.encode()
        if len(key) < 32:
            raise ValueError("cache simulation HMAC key requires at least 32 bytes")
        return hmac.new(key, canonical_json(value).encode(), hashlib.sha256).hexdigest()

    @classmethod
    def capture(cls, protocol: str, data: dict, headers: dict | None = None,
                *, parent_id: str | None = None) -> dict:
        headers = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        supplied = [(key, headers[key]) for key in cls.SESSION_HEADERS if key in headers]
        supplied += [(key, data[key]) for key in ("conversation_id", "session_id", "thread_id") if key in data]
        metadata = data.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("user_id"), str):
            # Claude Code's documented metadata format, not an arbitrary user_id.
            match = re.fullmatch(r"user_[0-9a-f]+_account_[^\s]*_session_([0-9a-fA-F-]{36})", metadata["user_id"])
            if match:
                supplied.append(("claude_metadata", match.group(1)))
        valid = [(source, cls.valid_id(value)) for source, value in supplied]
        ambiguous = bool(valid) and (any(value is None for _, value in valid)
                                    or len({value for _, value in valid}) != 1)
        session = valid[0][1] if valid and not ambiguous else None
        agent_raw = headers.get("x-claude-code-agent-id") or data.get("branch_id")
        agent = cls.valid_id(agent_raw) if agent_raw is not None else None
        if agent_raw is not None and agent is None:
            ambiguous = True
        source = valid[0][0] if session else "content_prefix"
        messages = data.get("input") if protocol == "responses" else data.get("messages")
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            messages = [messages]
        messages = messages if isinstance(messages, list) else []

        def strip_cache(value):
            if isinstance(value, dict):
                return {k: strip_cache(v) for k, v in value.items() if k != "cache_control"}
            if isinstance(value, list):
                return [strip_cache(v) for v in value]
            return value

        normalized = strip_cache(messages)
        encoded = canonical_json(normalized).encode()
        complete = bool(messages) and len(messages) <= cls.MAX_MESSAGES and len(encoded) <= cls.MAX_BYTES
        hashes = [hashlib.sha256(canonical_json(m).encode()).hexdigest() for m in normalized] if complete else []
        # System/tool changes must not make unrelated conversations share a prefix.
        system = data.get("instructions") if protocol == "responses" else data.get("system")
        context_hash = hashlib.sha256(canonical_json(strip_cache([system, data.get("tools")])).encode()).hexdigest()
        last = messages[-1] if messages else {}
        end_role = last.get("role") if isinstance(last, dict) else "user"
        end_type = last.get("type") if isinstance(last, dict) else ""
        has_new_turn = end_role in {"user", "tool"} or end_type == "function_call_output"
        fingerprint = hashlib.sha256(canonical_json([context_hash, hashes]).encode()).hexdigest()
        return {"session": session, "agent": agent, "source": source, "ambiguous": ambiguous,
                "parent_id": cls.valid_id(parent_id or data.get("previous_response_id")),
                "hashes": hashes, "context_hash": context_hash, "fingerprint": fingerprint,
                "complete": complete, "has_new_turn": has_new_turn, "protocol": protocol}

    @staticmethod
    def is_prefix(identity: dict, state: dict) -> bool:
        old = state.get("hashes") or []
        new = identity.get("hashes") or []
        return bool(old and identity.get("complete") and identity.get("has_new_turn")
                    and identity.get("context_hash") == state.get("context_hash")
                    and len(new) > len(old) and new[:len(old)] == old)

    @classmethod
    def bind(cls, identity: dict, scope_data: dict, state_service: CacheSimulationStateService) -> dict:
        identity = dict(identity)
        scope = cls.digest({**scope_data, "key_version": settings.CACHE_SIMULATION_KEY_VERSION,
                            "agent": cls.digest(identity["agent"]) if identity.get("agent") else None})
        result = {"scope": scope, "identity": {k: v for k, v in identity.items()
                                              if k not in {"session", "agent", "parent_id"}},
                  "source": identity.get("source", "content_prefix"), "strong": False,
                  "expected_revision": 0, "expected_window_id": None, "entry_status": "ok"}
        if not identity.get("complete") or not identity.get("has_new_turn"):
            return {**result, "entry_status": "incomplete_context"}
        if identity.get("ambiguous"):
            return {**result, "entry_status": "ambiguous_identity"}
        digest = None
        lineage = None
        if identity.get("session"):
            digest = cls.digest([scope, identity["session"], identity.get("agent")])
            result["strong"] = True
            if identity.get("parent_id"):
                lineage = state_service.parent(scope, cls.digest(identity["parent_id"]))
        elif identity.get("parent_id"):
            lineage = state_service.parent(scope, cls.digest(identity["parent_id"]))
            if lineage:
                digest = lineage["digest"]
                result["source"] = "response_lineage"
                result["strong"] = True
            else:
                # Unresolved lineage is not proof of a continuation or compaction.
                digest = cls.digest([scope, "new", str(uuid.uuid4())])
        else:
            candidates = state_service.candidates(scope)
            if candidates is None:
                return {**result, "entry_status": "redis_unavailable"}
            if len(candidates) <= state_service.INDEX_LIMIT and identity.get("complete"):
                matches = []
                for candidate in candidates:
                    loaded = state_service.load(candidate)
                    if loaded.status == "unavailable":
                        return {**result, "entry_status": "redis_unavailable"}
                    if loaded.state and cls.is_prefix(identity, loaded.state):
                        matches.append(candidate)
                if len(matches) == 1:
                    digest = matches[0]
            if digest is None:
                digest = cls.digest([scope, "new", str(uuid.uuid4())])
        loaded = state_service.load(digest)
        result.update(digest=digest, expected_revision=int((loaded.state or {}).get("revision", 0)),
                      expected_window_id=(loaded.state or {}).get("window_id"))
        if loaded.status == "unavailable":
            result["entry_status"] = "redis_unavailable"
        elif identity.get("parent_id") and identity.get("session") and not lineage and loaded.state:
            # An unmapped fork response must not borrow the explicit session's main branch.
            result["entry_status"] = "unresolved_lineage"
        elif lineage and (lineage["digest"] != digest or not loaded.state
                          or lineage["revision"] != result["expected_revision"]
                          or lineage.get("window_id") != result["expected_window_id"]):
            result["entry_status"] = "lineage_conflict"
        if lineage and result["entry_status"] == "ok":
            # Equal incremental text with a new, verified parent is a new turn.
            result["identity"]["fingerprint"] = cls.digest([
                identity["fingerprint"], cls.digest(identity["parent_id"]),
                lineage["window_id"], lineage["revision"],
            ])
        return result
