"""Configuration, durable decisions and conversation simulation coordinator."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import logging
import secrets
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import ServiceException
from app.database import session_scope
from app.models.cache_simulation import CacheSimulationDecision, CacheSimulationRule
from app.models.log import SystemConfig
from app.models.model import ModelGroup
from app.models.user import SysUser
from app.services.cache_simulation_allocator import Allocation, CacheSimulationAllocator, TokenBuckets
from app.services.cache_simulation_identity_service import CacheSimulationIdentityService as Identity
from app.services.cache_simulation_state_service import CacheSimulationStateService, canonical_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AccountingResult:
    success: bool
    request_id: str
    decision_id: str | None = None
    receipt: dict | None = None


class CacheSimulationService:
    BEIJING_TZ = timezone(timedelta(hours=8))
    CONFIG_KEY = "cache_simulation_config"
    DEFAULT_CONFIG = {"enabled": False, "ttl_seconds": 300, "version": 1, "enable_epoch": 1}
    MAX_RECOVERY_ATTEMPTS = 5

    @classmethod
    def get_config(cls, db: Session, *, lock: bool = False) -> dict:
        query = db.query(SystemConfig).filter(SystemConfig.config_key == cls.CONFIG_KEY)
        row = query.with_for_update().first() if lock else query.first()
        try:
            config = json.loads(row.config_value) if row else dict(cls.DEFAULT_CONFIG)
            if (type(config["enabled"]) is not bool or type(config["ttl_seconds"]) is not int
                    or not 60 <= config["ttl_seconds"] <= 86400 or config["ttl_seconds"] % 60
                    or any(type(config[k]) is not int or config[k] < 1 for k in ("version", "enable_epoch"))):
                raise ValueError("invalid config")
        except (ValueError, TypeError, KeyError):
            raise ServiceException(503, "模拟缓存配置无效，请修复配置后启用", "CACHE_SIMULATION_CONFIG_INVALID")
        return config

    @classmethod
    def config_dto(cls, db: Session) -> dict:
        config = cls.get_config(db)
        return {**config, "ttl_minutes": config["ttl_seconds"] // 60,
                "threshold": 0.8, "coefficient_min": 0.8, "coefficient_max": 0.95,
                "observation_count": 2, "hmac_ready": len(settings.CACHE_SIMULATION_HMAC_KEY.encode()) >= 32}

    @classmethod
    def update_config(cls, db: Session, data, operator_id: int) -> dict:
        if data.enabled and len(settings.CACHE_SIMULATION_HMAC_KEY.encode()) < 32:
            raise ServiceException(400, "请先配置至少32字节的模拟缓存会话密钥", "CACHE_SIMULATION_KEY_MISSING")
        # An insert-if-absent handles upgrades with no config row yet.
        if not db.query(SystemConfig.id).filter(SystemConfig.config_key == cls.CONFIG_KEY).first():
            try:
                with db.begin_nested():
                    db.add(SystemConfig(config_key=cls.CONFIG_KEY, config_value=canonical_json(cls.DEFAULT_CONFIG),
                                        config_type="json", description="模拟缓存：请在专用管理页面编辑"))
                    db.flush()
            except IntegrityError:
                pass
        config = cls.get_config(db, lock=True)
        if config["version"] != data.version:
            raise ServiceException(409, "配置已被修改，请刷新后重试", "CACHE_SIMULATION_CONFIG_CONFLICT")
        updated = {**config, "enabled": data.enabled, "ttl_seconds": data.ttl_minutes * 60,
                   "version": config["version"] + 1,
                   "enable_epoch": config["enable_epoch"] + int(data.enabled and not config["enabled"])}
        row = db.query(SystemConfig).filter(SystemConfig.config_key == cls.CONFIG_KEY).first()
        row.config_value = canonical_json(updated)
        db.commit()
        return cls.config_dto(db)

    @staticmethod
    def rule_dto(rule, user=None, group=None) -> dict:
        return {"id": rule.id, "user_id": rule.user_id, "group_id": rule.group_id,
                "username": user.username if user else None, "group_name": group.name if group else None,
                "model_series": group.model_series if group else None,
                "enabled": bool(rule.enabled), "generation": rule.generation,
                "updated_at": rule.updated_at.isoformat() if rule.updated_at else None}

    @classmethod
    def list_rules(cls, db: Session, page: int, size: int) -> dict:
        query = db.query(CacheSimulationRule, SysUser, ModelGroup).outerjoin(
            SysUser, SysUser.id == CacheSimulationRule.user_id).outerjoin(
            ModelGroup, ModelGroup.id == CacheSimulationRule.group_id)
        return {"total": query.count(), "items": [cls.rule_dto(*row) for row in
                query.order_by(CacheSimulationRule.id.desc()).offset((page - 1) * size).limit(size).all()]}

    @classmethod
    def create_rule(cls, db: Session, data, operator_id: int) -> dict:
        user = db.query(SysUser).filter(SysUser.id == data.user_id, SysUser.status == 1).first()
        group = db.query(ModelGroup).filter(ModelGroup.id == data.group_id, ModelGroup.enabled == 1).first()
        if not user or not group:
            raise ServiceException(400, "请选择有效用户和启用的模型分组", "CACHE_SIMULATION_INVALID_PAIR")
        rule = CacheSimulationRule(user_id=user.id, group_id=group.id, enabled=int(data.enabled),
                                   generation=1, operator_id=operator_id)
        try:
            db.add(rule)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ServiceException(409, "该用户和分组已有规则，请修改已有规则", "CACHE_SIMULATION_DUPLICATE_PAIR")
        db.refresh(rule)
        return cls.rule_dto(rule, user, group)

    @classmethod
    def update_rule(cls, db: Session, rule_id: int, data, operator_id: int) -> dict:
        rule = db.query(CacheSimulationRule).filter(CacheSimulationRule.id == rule_id).with_for_update().first()
        if not rule:
            raise ServiceException(404, "模拟缓存规则不存在", "CACHE_SIMULATION_RULE_NOT_FOUND")
        if data.generation != rule.generation:
            raise ServiceException(409, "规则已被修改，请刷新后重试", "CACHE_SIMULATION_RULE_CONFLICT")
        if data.enabled:
            user = db.query(SysUser).filter(SysUser.id == rule.user_id, SysUser.status == 1).first()
            group = db.query(ModelGroup).filter(ModelGroup.id == rule.group_id, ModelGroup.enabled == 1).first()
            if not user or not group:
                raise ServiceException(400, "用户或分组已停用", "CACHE_SIMULATION_INVALID_PAIR")
        if bool(rule.enabled) != data.enabled:
            rule.generation += 1
        rule.enabled = int(data.enabled)
        rule.operator_id = operator_id
        db.commit()
        db.refresh(rule)
        return cls.rule_dto(rule)

    @classmethod
    def bind_context(cls, db: Session, user, model, context: dict) -> dict:
        context = dict(context)
        context.pop("cache_simulation_binding", None)
        if str(getattr(model, "billing_type", "token")) != "token":
            return context
        identity = context.get("cache_simulation_identity")
        group_id = context.get("group_id_snapshot") or context.get("group_id")
        if not identity or not group_id:
            return context
        try:
            config = cls.get_config(db)
            if not config["enabled"]:
                return context
            rule = db.query(CacheSimulationRule).filter(CacheSimulationRule.user_id == user.id,
                CacheSimulationRule.group_id == group_id, CacheSimulationRule.enabled == 1).first()
            group = db.query(ModelGroup).filter(ModelGroup.id == group_id, ModelGroup.enabled == 1).first()
            if not rule or not group or not getattr(user, "status", 1):
                return context
            scope_data = {"user_id": user.id, "group_id": group_id, "model_id": model.id,
                          "protocol": identity["protocol"], "rule_generation": rule.generation,
                          "enable_epoch": config["enable_epoch"]}
            binding = Identity.bind(identity, scope_data, CacheSimulationStateService())
            context["cache_simulation_binding"] = {**binding, "rule_id": rule.id,
                "rule_generation": rule.generation, "group_id": group_id, "group_name": group.name,
                "config": config}
        except Exception as exc:
            logger.warning("Cache simulation identity/config unavailable: %s", type(exc).__name__)
        # Raw client IDs live only until binding; durable snapshots contain HMACs.
        context.pop("cache_simulation_identity", None)
        return context

    @staticmethod
    def usage_evidence(cache_info: dict | None) -> dict:
        return (cache_info or {}).get("_cache_simulation_usage") or {}

    @staticmethod
    def propose(binding: dict, state: dict | None, now: float, raw: TokenBuckets,
                allocation: Allocation, request_id: str, ttl: int) -> tuple[dict | None, str, str | None]:
        """No committed state changes until a durable prepared decision exists."""
        if binding.get("entry_status") != "ok":
            return None, "skipped", binding.get("entry_status")
        identity = binding["identity"]
        # Revisions restart after expiration; the window ID prevents an ABA match.
        if state and (state.get("revision") != binding["expected_revision"]
                      or state.get("window_id") != binding.get("expected_window_id")):
            return None, "skipped", "concurrent_revision"
        if not state and binding["expected_revision"] != 0:
            # A window expiring while the model runs starts observation afresh.
            binding = {**binding, "expected_revision": 0}
        if state and state.get("fingerprint") == identity.get("fingerprint"):
            return None, "skipped", "duplicate_context"
        prefix = bool(state and Identity.is_prefix(identity, state))
        if state and not prefix and not identity.get("has_new_turn"):
            # A session-only match cannot replace either an observing or an
            # active history without proof of a new turn.
            return None, "skipped", "non_continuation"
        lineage = binding.get("source") == "response_lineage"
        strong = binding.get("strong", False)
        compression = bool(state and strong and raw.context < state["previous_L"])
        # Strict prefix growth is sufficient evidence of a new request. Keep
        # the turn check for session-only matches and compaction without it.
        continuation = bool(state and (prefix or identity.get("has_new_turn")) and (
            compression or (raw.context > state["previous_L"] and (prefix or strong or lineage))))
        good = raw.read * 1000 >= raw.total * 800
        if state and state.get("stage") == "active" and not good and not continuation:
            return None, "skipped", "non_continuation"
        if state is None:
            proposed = {"stage": "observing", "low_count": 0, "revision": 0,
                        "window_id": str(uuid.uuid4()), "started_at": now,
                        "expires_at": now + ttl, "ttl_seconds": ttl}
        else:
            proposed = dict(state)
        if good:
            if proposed["stage"] == "observing":
                proposed["low_count"] = 0
            outcome, reason = "upstream_good", None
        else:
            count = min(2, int(proposed.get("low_count", 0)))
            eligible = proposed["stage"] == "active" or (continuation and count >= 2)
            if eligible and allocation.coefficient is not None:
                if proposed["stage"] != "active":
                    proposed.update(stage="active", window_id=str(uuid.uuid4()), started_at=now,
                                    expires_at=now + ttl, ttl_seconds=ttl)
                outcome, reason = "simulated", "confirmed_compaction" if compression else "low_hit_ratio"
            elif eligible:
                outcome, reason = "skipped", allocation.reason or "unreachable_floor"
            else:
                proposed["low_count"] = min(2, count + 1) if continuation else 1
                outcome, reason = "observing", "confirmed_compaction" if compression else "collecting_samples"
        proposed.update(revision=int(proposed["revision"]) + 1, previous_L=raw.context,
                        fingerprint=identity["fingerprint"], context_hash=identity["context_hash"],
                        hashes=identity["hashes"], last_request_id=request_id)
        return proposed, outcome, reason

    @staticmethod
    def local_cost(buckets: TokenBuckets, prices: dict, *, quota: bool = False) -> Decimal:
        factor = Decimal(prices["official_quota_multiplier"] if quota else prices["effective_price_multiplier"])
        return sum((Decimal(n) * Decimal(prices[key + "_price"]) for key, n in buckets.to_dict().items()),
                   Decimal("0")) * factor / Decimal(1000000)

    @classmethod
    def prepare(cls, *, request_id: str, user, api_key_id: int | None, model, channel,
                requested_model: str, input_tokens: int, output_tokens: int,
                cache_info: dict | None, billing_context: dict, params: dict,
                snapshot_builder) -> str | None:
        binding = billing_context.get("cache_simulation_binding")
        if not binding:
            return None
        state_service = CacheSimulationStateService()
        raw = TokenBuckets(int(input_tokens), int(output_tokens),
            int((cache_info or {}).get("upstream_cache_read_input_tokens", 0)),
            int((cache_info or {}).get("upstream_cache_creation_input_tokens", 0)))

        def validate_existing(decision):
            snapshot = json.loads(decision.snapshot_json)
            if (decision.user_id != user.id or decision.user_api_key_id != api_key_id
                    or decision.unified_model_id != model.id or decision.group_id != binding["group_id"]
                    or decision.requested_model != requested_model
                    or decision.protocol != binding["identity"]["protocol"]
                    or json.loads(decision.usage_json)["raw"] != raw.to_dict()
                    or snapshot["binding"]["identity"]["fingerprint"] != binding["identity"]["fingerprint"]):
                # Reject reuse before delivering any previously frozen conversation state.
                raise ServiceException(409, "请求与已有模拟缓存决策不一致", "CACHE_SIMULATION_REQUEST_CONFLICT")

        # Saving the candidate once precedes any Redis reservation.
        try:
            with session_scope() as db:
                decision = db.query(CacheSimulationDecision).filter(
                    CacheSimulationDecision.request_id == request_id).first()
                if not decision:
                    prices = snapshot_builder(db, raw)
                    baseline = TokenBuckets(**prices["baseline"])
                    upper = CacheSimulationAllocator.feasible_range(raw, baseline)
                    candidate = 800 + secrets.randbelow(upper - 799) if upper >= 800 else None
                    original = CacheSimulationAllocator.original(raw, baseline)
                    # The snapshot contains no request content, raw session IDs or keys.
                    safe_context = {k: v for k, v in billing_context.items()
                                    if k not in {"cache_simulation_identity", "cache_simulation_binding"}}
                    snapshot = {"prices": prices, "binding": binding, "params": params,
                                "billing_context": safe_context, "cache_info": cls.safe_cache_info(cache_info),
                                "model": cls.model_snapshot(model),
                                "channel": {"id": channel.id, "name": channel.name, "protocol_type": channel.protocol_type},
                                "candidate": candidate, "evidence": cls.usage_evidence(cache_info)}
                    decision = CacheSimulationDecision(request_id=request_id, decision_id=str(uuid.uuid4()),
                        user_id=user.id, user_api_key_id=api_key_id,
                        group_id=binding["group_id"], unified_model_id=model.id,
                        username_snapshot=user.username, group_name_snapshot=binding["group_name"],
                        requested_model=requested_model, protocol=binding["identity"]["protocol"],
                        rule_id=binding["rule_id"], rule_generation=binding["rule_generation"],
                        config_version=binding["config"]["version"], enable_epoch=binding["config"]["enable_epoch"],
                        session_digest=binding.get("digest"), identity_source=binding["source"],
                        identity_confidence="strong" if binding["strong"] else "prefix",
                        usage_source=cls.usage_evidence(cache_info).get("source", "unknown"),
                        total_tokens=raw.total, context_tokens=raw.context,
                        usage_json=canonical_json(original.to_dict()), snapshot_json=canonical_json(snapshot),
                        next_retry_at=datetime.utcnow() + timedelta(seconds=120))
                    db.add(decision)
                    db.flush()
                else:
                    validate_existing(decision)
                decision_id = decision.decision_id
        except IntegrityError:
            with session_scope() as db:
                decision = db.query(CacheSimulationDecision).filter(
                    CacheSimulationDecision.request_id == request_id).one()
                validate_existing(decision)
                decision_id = decision.decision_id
        cls.prepare_draft(decision_id, state_service)
        cls.deliver_state(decision_id, state_service)
        return decision_id

    @staticmethod
    def safe_cache_info(cache_info: dict | None) -> dict:
        keys = ("logical_input_tokens", "upstream_input_tokens", "upstream_cache_read_input_tokens",
                "upstream_cache_creation_input_tokens", "upstream_cache_creation_5m_input_tokens",
                "upstream_cache_creation_1h_input_tokens", "upstream_prompt_cache_status",
                "cache_status", "request_format", "ttl_seconds", "_cache_simulation_usage")
        return {key: cache_info[key] for key in keys if key in (cache_info or {})}

    @staticmethod
    def model_snapshot(model) -> dict:
        keys = ("id", "model_name", "model_series", "model_type", "protocol_type", "billing_type",
                "bonus_quota_enabled", "input_price_per_million", "output_price_per_million",
                "cache_read_price_per_million", "cache_creation_price_per_million", "request_price",
                "long_context_billing_enabled", "long_context_token_threshold")
        return {k: str(getattr(model, k)) if isinstance(getattr(model, k, None), Decimal)
                else getattr(model, k, None) for k in keys}

    @classmethod
    def prepare_draft(cls, decision_id: str, state_service: CacheSimulationStateService,
                      *, recovering: bool = False) -> bool:
        reservation = None
        digest = None
        try:
            with session_scope() as db:
                decision = db.query(CacheSimulationDecision).filter(
                    CacheSimulationDecision.decision_id == decision_id).with_for_update().one()
                if decision.decision_status != "draft":
                    return decision.decision_status == "prepared"
                snapshot = json.loads(decision.snapshot_json)
                binding = snapshot["binding"]
                digest = binding.get("digest")
                if recovering and digest and state_service.reservation_status(digest) != "missing":
                    return False
                usage = json.loads(decision.usage_json)
                raw, baseline = TokenBuckets(**usage["raw"]), TokenBuckets(**usage["baseline"])
                allocation = CacheSimulationAllocator.original(raw, baseline)
                outcome, reason, proposed = "skipped", "expired_draft" if recovering else None, None
                evidence = snapshot["evidence"]
                config = cls.get_config(db, lock=True)
                rule = db.query(CacheSimulationRule).filter(CacheSimulationRule.id == decision.rule_id).with_for_update().first()
                group = db.query(ModelGroup).filter(ModelGroup.id == decision.group_id, ModelGroup.enabled == 1).first()
                user = db.query(SysUser).filter(SysUser.id == decision.user_id, SysUser.status == 1).first()
                allowed = bool(config["enabled"] and config["enable_epoch"] == decision.enable_epoch
                               and rule and rule.enabled and rule.generation == decision.rule_generation and group and user)
                if not recovering:
                    if not allowed:
                        reason = "rule_disabled"
                    elif not (evidence.get("valid") and evidence.get("input_present") and evidence.get("output_present")
                              and evidence.get("source") == "upstream" and snapshot["params"].get("simulation_success", True)):
                        reason = "incomplete_or_failed_usage"
                    elif raw.total <= 0 or raw.context <= 0:
                        reason = "empty_context"
                    elif digest is None:
                        reason = binding.get("entry_status", "ambiguous_identity")
                    else:
                        loaded = state_service.load(digest)
                        if loaded.status == "unavailable":
                            reason = "redis_unavailable"
                        else:
                            if snapshot["candidate"] is not None:
                                allocation = CacheSimulationAllocator.allocate(raw, baseline,
                                    Decimal(snapshot["prices"]["token_multiplier"]), coefficient=snapshot["candidate"])
                            else:
                                allocation = CacheSimulationAllocator.original(raw, baseline, "unreachable_floor")
                            proposed, outcome, reason = cls.propose(binding, loaded.state, loaded.now, raw,
                                allocation, decision.request_id, config["ttl_seconds"])
                            if proposed:
                                base_revision = int((loaded.state or {}).get("revision", 0))
                                reserved = state_service.reserve(digest, decision.request_id, base_revision, proposed,
                                    expected_window_id=(loaded.state or {}).get("window_id"))
                                if reserved.status == "reserved":
                                    reservation = reserved.reservation
                                else:
                                    proposed, outcome, reason = None, "skipped", "redis_" + reserved.status
                if reservation:
                    validation = state_service.validate_reservation(digest, reservation, proposed)
                    if validation != "valid":
                        # Only a durably prepared decision may keep its result after fence loss.
                        state_service.release(digest, reservation)
                        proposed, reservation = None, None
                        outcome, reason = "skipped", "redis_" + validation
                if outcome != "simulated":
                    allocation = CacheSimulationAllocator.original(raw, baseline, reason)
                decision.usage_json = canonical_json(allocation.to_dict())
                decision.coefficient = allocation.coefficient
                decision.transferred_tokens = allocation.effective.read - raw.read
                decision.outcome, decision.reason = outcome, reason
                decision.original_cost = cls.local_cost(baseline, snapshot["prices"])
                decision.effective_cost = cls.local_cost(allocation.billed, snapshot["prices"])
                decision.fee_delta = decision.original_cost - decision.effective_cost
                decision.proposed_state_json = canonical_json(proposed) if proposed else None
                decision.reservation_json = canonical_json(reservation) if reservation else None
                if proposed:
                    decision.window_id = proposed["window_id"]
                    decision.window_started_at = datetime.utcfromtimestamp(proposed["started_at"])
                    decision.window_expires_at = datetime.utcfromtimestamp(proposed["expires_at"])
                decision.decision_hash = hashlib.sha256(canonical_json({"request_id": decision.request_id,
                    "usage": allocation.to_dict(), "proposed": proposed}).encode()).hexdigest()
                decision.decision_status = "prepared"
                decision.state_delivery = "pending" if reservation else "skipped"
                decision.next_retry_at = datetime.utcnow() + timedelta(seconds=60)
            return True
        except Exception:
            if digest and reservation:
                state_service.release(digest, reservation)
            raise

    @classmethod
    def deliver_state(cls, decision_id: str, state_service: CacheSimulationStateService | None = None) -> None:
        state_service = state_service or CacheSimulationStateService()
        with session_scope() as db:
            decision = db.query(CacheSimulationDecision).filter(
                CacheSimulationDecision.decision_id == decision_id).with_for_update().one()
            if decision.decision_status != "prepared" or decision.state_delivery != "pending":
                return
            snapshot = json.loads(decision.snapshot_json)
            proposed = json.loads(decision.proposed_state_json)
            reservation = json.loads(decision.reservation_json)
            status = state_service.commit(decision.session_digest, decision.request_id, reservation,
                                          proposed, decision.decision_hash)
            decision.state_delivery = "committed" if status == "committed" else "lost"
            if status == "committed":
                state_service.index(snapshot["binding"]["scope"], decision.session_digest, proposed["expires_at"])
                response_id = snapshot["params"].get("response_id")
                if response_id:
                    state_service.remember_response(snapshot["binding"]["scope"], Identity.digest(response_id),
                        decision.session_digest, proposed["revision"], proposed["fingerprint"], proposed["expires_at"],
                        proposed["window_id"])
            else:
                state_service.release(decision.session_digest, reservation)

    @classmethod
    def mark_accounting_failure(cls, decision_id: str, exc: Exception) -> None:
        with session_scope() as db:
            decision = db.query(CacheSimulationDecision).filter(
                CacheSimulationDecision.decision_id == decision_id).with_for_update().first()
            if decision and decision.accounting_status != "settled":
                decision.accounting_status = "failed"
                decision.last_error = (type(exc).__name__ + ": " + str(exc))[:512]

    @classmethod
    def lock_for_accounting(cls, db: Session, decision_id: str, request_id: str, user_id: int,
                            api_key_id: int | None) -> CacheSimulationDecision:
        decision = db.query(CacheSimulationDecision).filter(
            CacheSimulationDecision.decision_id == decision_id).with_for_update().one()
        if (decision.request_id != request_id or decision.user_id != user_id
                or decision.user_api_key_id != api_key_id or decision.decision_status != "prepared"):
            raise ServiceException(409, "模拟缓存结算凭据冲突", "CACHE_SIMULATION_ACCOUNTING_CONFLICT")
        return decision

    @classmethod
    def recover_due(cls, limit: int = 50) -> int:
        now = datetime.utcnow()
        with session_scope() as db:
            ids = [row[0] for row in db.query(CacheSimulationDecision.decision_id).filter(
                CacheSimulationDecision.decision_status.in_(["draft", "prepared"]),
                CacheSimulationDecision.accounting_status != "settled",
                CacheSimulationDecision.next_retry_at <= now).order_by(CacheSimulationDecision.id).limit(limit).all()]
        completed = 0
        for decision_id in ids:
            try:
                with session_scope() as db:
                    decision = db.query(CacheSimulationDecision).filter(
                        CacheSimulationDecision.decision_id == decision_id).with_for_update().one()
                    if (decision.accounting_status == "settled" or decision.next_retry_at > now
                            or decision.decision_status == "manual_review"):
                        continue
                    if decision.recovery_attempts >= cls.MAX_RECOVERY_ATTEMPTS:
                        decision.decision_status = "manual_review"
                        continue
                    if (decision.decision_status == "draft" and decision.session_digest
                            and CacheSimulationStateService().reservation_status(decision.session_digest) != "missing"):
                        # Redis cannot confirm ownership loss yet; defer without spending a retry.
                        decision.next_retry_at = now + timedelta(seconds=60)
                        continue
                    decision.recovery_attempts += 1
                    decision.next_retry_at = now + timedelta(seconds=min(3600, 60 * 2 ** decision.recovery_attempts))
                if not cls.prepare_draft(decision_id, CacheSimulationStateService(), recovering=True):
                    continue
                cls.deliver_state(decision_id)
                cls.recover_accounting(decision_id)
                completed += 1
            except Exception as exc:
                logger.warning("Cache simulation accounting recovery failed decision=%s: %s", decision_id, type(exc).__name__)
                cls.mark_accounting_failure(decision_id, exc)
        return completed

    @classmethod
    def recover_accounting(cls, decision_id: str) -> None:
        from types import SimpleNamespace
        from app.services.proxy_service import ProxyService
        with session_scope() as db:
            decision = db.query(CacheSimulationDecision).filter(
                CacheSimulationDecision.decision_id == decision_id).one()
            snapshot = json.loads(decision.snapshot_json)
            raw = json.loads(decision.usage_json)["raw"]
            params = snapshot["params"]
            context = {**snapshot["billing_context"], "cache_simulation_decision_id": decision_id}
            ProxyService._deduct_balance_and_log(db, SimpleNamespace(id=decision.user_id),
                SimpleNamespace(id=decision.user_api_key_id), SimpleNamespace(**snapshot["model"]),
                decision.request_id, decision.requested_model, raw["input"], raw["output"],
                SimpleNamespace(**snapshot["channel"]), params.get("client_ip"), params["response_time_ms"],
                is_stream=params["is_stream"], request_type=params["request_type"],
                actual_model=params.get("actual_model"), cache_info=snapshot["cache_info"], billing_context=context)

    @staticmethod
    def record_dto(decision: CacheSimulationDecision, *, detail: bool = False) -> dict:
        usage = json.loads(decision.usage_json)
        total = decision.total_tokens
        result = {key: getattr(decision, key) for key in (
            "request_id", "decision_id", "user_id", "group_id", "requested_model", "protocol",
            "session_digest", "outcome", "reason", "decision_status", "accounting_status", "state_delivery",
            "coefficient", "transferred_tokens", "total_tokens", "context_tokens", "window_id",
            "identity_source", "identity_confidence", "usage_source", "last_error", "recovery_attempts")}
        result.update(username=decision.username_snapshot, group_name=decision.group_name_snapshot,
                      original_hit_ratio=usage["raw"]["read"] / total if total else 0,
                      effective_hit_ratio=usage["effective"]["read"] / total if total else 0)
        for key in ("created_at", "settled_at", "window_started_at", "window_expires_at"):
            value = getattr(decision, key)
            # created_at comes from MySQL NOW() in +08:00; settlement/window
            # timestamps are written by Python in UTC. Preserve both instants.
            stored_tz = CacheSimulationService.BEIJING_TZ if key == "created_at" else timezone.utc
            if value is not None:
                value = value.replace(tzinfo=stored_tz) if value.tzinfo is None else value.astimezone(stored_tz)
            result[key] = value.isoformat().replace("+00:00", "Z") if value else None
        for key in ("original_cost", "effective_cost", "fee_delta"):
            result[key] = float(getattr(decision, key) or 0)
        if detail:
            snapshot = json.loads(decision.snapshot_json)
            result.update(usage=usage, prices=snapshot["prices"],
                          creation_5m=snapshot["cache_info"].get("upstream_cache_creation_5m_input_tokens", 0),
                          creation_1h=snapshot["cache_info"].get("upstream_cache_creation_1h_input_tokens", 0),
                          receipt=json.loads(decision.receipt_json) if decision.receipt_json else None)
        return result

    @classmethod
    def list_records(cls, db: Session, page: int, size: int, *, user_id=None, group_id=None,
                     model=None, outcome="simulated", accounting_status="settled", start=None, end=None) -> dict:
        query = db.query(CacheSimulationDecision)
        for field, value in (("user_id", user_id), ("group_id", group_id), ("outcome", outcome),
                             ("accounting_status", accounting_status), ("requested_model", model)):
            if value is not None:
                query = query.filter(getattr(CacheSimulationDecision, field) == value)
        if start:
            query = query.filter(CacheSimulationDecision.created_at >= start)
        if end:
            query = query.filter(CacheSimulationDecision.created_at <= end)
        return {"total": query.count(), "items": [cls.record_dto(row) for row in query.order_by(
            CacheSimulationDecision.id.desc()).offset((page - 1) * size).limit(size).all()]}

    @classmethod
    def record_detail(cls, db: Session, request_id: str) -> dict:
        decision = db.query(CacheSimulationDecision).filter(CacheSimulationDecision.request_id == request_id).first()
        if not decision:
            raise ServiceException(404, "模拟缓存记录不存在", "CACHE_SIMULATION_RECORD_NOT_FOUND")
        return cls.record_dto(decision, detail=True)
