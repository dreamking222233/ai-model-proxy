"""Unified model, channel mapping, and override rule service."""
from __future__ import annotations

import fnmatch
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.model import UnifiedModel, ModelChannelMapping, ModelOverrideRule
from app.models.channel import Channel
from app.core.exceptions import ServiceException

logger = logging.getLogger(__name__)


class ModelService:
    """CRUD operations for models, mappings, override rules, and model resolution."""

    @staticmethod
    def _model_to_dict(model: UnifiedModel) -> dict:
        """Convert a UnifiedModel ORM instance to a serializable dict."""
        return {
            "id": model.id,
            "model_name": model.model_name,
            "display_name": model.display_name,
            "model_type": model.model_type,
            "protocol_type": model.protocol_type,
            "max_tokens": model.max_tokens,
            "input_price_per_million": float(model.input_price_per_million) if model.input_price_per_million is not None else 0,
            "output_price_per_million": float(model.output_price_per_million) if model.output_price_per_million is not None else 0,
            "billing_type": model.billing_type,
            "image_credit_multiplier": int(model.image_credit_multiplier or 1),
            "enabled": model.enabled,
            "description": model.description,
            "created_at": model.created_at.isoformat() if model.created_at else None,
            "updated_at": model.updated_at.isoformat() if model.updated_at else None,
        }

    @staticmethod
    def _mapping_to_dict(m: ModelChannelMapping) -> dict:
        """Convert a ModelChannelMapping ORM instance to a serializable dict."""
        return {
            "id": m.id,
            "unified_model_id": m.unified_model_id,
            "channel_id": m.channel_id,
            "actual_model_name": m.actual_model_name,
            "enabled": m.enabled,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }

    @staticmethod
    def _rule_to_dict(r: ModelOverrideRule) -> dict:
        """Convert a ModelOverrideRule ORM instance to a serializable dict."""
        return {
            "id": r.id,
            "name": r.name,
            "rule_type": r.rule_type,
            "source_pattern": r.source_pattern,
            "target_unified_model_id": r.target_unified_model_id,
            "enabled": r.enabled,
            "priority": r.priority,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }

    # -----------------------------------------------------------------------
    # Unified Model CRUD
    # -----------------------------------------------------------------------

    @staticmethod
    def create_model(db: Session, data) -> dict:
        """Create a new unified model."""
        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        # Check unique model_name
        existing = db.query(UnifiedModel).filter(UnifiedModel.model_name == d["model_name"]).first()
        if existing:
            raise ServiceException(400, f"Model name '{d['model_name']}' already exists", "DUPLICATE_MODEL")

        model = UnifiedModel(
            model_name=d["model_name"],
            display_name=d.get("display_name"),
            model_type=d.get("model_type", "chat"),
            protocol_type=d.get("protocol_type", "openai"),
            max_tokens=d.get("max_tokens"),
            input_price_per_million=d.get("input_price_per_million", 0),
            output_price_per_million=d.get("output_price_per_million", 0),
            billing_type=d.get("billing_type", "token"),
            image_credit_multiplier=d.get("image_credit_multiplier", 1),
            enabled=d.get("enabled", 1),
            description=d.get("description"),
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return ModelService._model_to_dict(model)

    @staticmethod
    def update_model(db: Session, model_id: int, data) -> dict:
        """Update an existing unified model."""
        model = db.query(UnifiedModel).filter(UnifiedModel.id == model_id).first()
        if not model:
            raise ServiceException(404, "Model not found", "MODEL_NOT_FOUND")

        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        updatable_fields = [
            "model_name", "display_name", "model_type", "protocol_type",
            "max_tokens", "input_price_per_million", "output_price_per_million",
            "billing_type", "image_credit_multiplier", "enabled", "description",
        ]
        for field in updatable_fields:
            value = d.get(field)
            if value is not None:
                # Validate unique model_name if changing
                if field == "model_name" and value != model.model_name:
                    existing = db.query(UnifiedModel).filter(UnifiedModel.model_name == value).first()
                    if existing:
                        raise ServiceException(400, f"Model name '{value}' already exists", "DUPLICATE_MODEL")
                setattr(model, field, value)

        db.commit()
        db.refresh(model)
        return ModelService._model_to_dict(model)

    @staticmethod
    def delete_model(db: Session, model_id: int) -> None:
        """Delete a unified model and its channel mappings."""
        model = db.query(UnifiedModel).filter(UnifiedModel.id == model_id).first()
        if not model:
            raise ServiceException(404, "Model not found", "MODEL_NOT_FOUND")

        # Delete related mappings
        db.query(ModelChannelMapping).filter(ModelChannelMapping.unified_model_id == model_id).delete()
        db.delete(model)
        db.commit()

    @staticmethod
    def get_model(db: Session, model_id: int) -> dict:
        """Get a single unified model by id."""
        model = db.query(UnifiedModel).filter(UnifiedModel.id == model_id).first()
        if not model:
            raise ServiceException(404, "Model not found", "MODEL_NOT_FOUND")
        return ModelService._model_to_dict(model)

    @staticmethod
    def list_models(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        """List unified models with pagination and optional keyword search."""
        query = db.query(UnifiedModel)

        if keyword:
            like_pattern = f"%{keyword}%"
            query = query.filter(
                or_(
                    UnifiedModel.model_name.like(like_pattern),
                    UnifiedModel.display_name.like(like_pattern),
                    UnifiedModel.description.like(like_pattern),
                )
            )

        total = query.count()
        models = (
            query.order_by(UnifiedModel.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [ModelService._model_to_dict(m) for m in models], total

    @staticmethod
    def get_model_with_mappings(db: Session, model_id: int) -> dict:
        """
        Get a unified model together with all its channel mappings.

        Returns:
            dict with ``model`` (UnifiedModel) and ``mappings`` (list of dicts with
            mapping info + channel_name).
        """
        model = db.query(UnifiedModel).filter(UnifiedModel.id == model_id).first()
        if not model:
            raise ServiceException(404, "Model not found", "MODEL_NOT_FOUND")

        mappings = (
            db.query(ModelChannelMapping)
            .filter(ModelChannelMapping.unified_model_id == model_id)
            .all()
        )

        mapping_list = []
        for m in mappings:
            channel = db.query(Channel).filter(Channel.id == m.channel_id).first()
            mapping_list.append({
                "id": m.id,
                "unified_model_id": m.unified_model_id,
                "channel_id": m.channel_id,
                "actual_model_name": m.actual_model_name,
                "enabled": m.enabled,
                "channel_name": channel.name if channel else None,
                "created_at": m.created_at,
            })

        return {
            "model": ModelService._model_to_dict(model),
            "mappings": mapping_list,
        }

    # -----------------------------------------------------------------------
    # Model Channel Mapping CRUD
    # -----------------------------------------------------------------------

    @staticmethod
    def create_mapping(db: Session, data) -> dict:
        """Create a model-channel mapping after validating references."""
        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        # Validate model exists
        model = db.query(UnifiedModel).filter(UnifiedModel.id == d["unified_model_id"]).first()
        if not model:
            raise ServiceException(404, "Unified model not found", "MODEL_NOT_FOUND")

        # Validate channel exists
        channel = db.query(Channel).filter(Channel.id == d["channel_id"]).first()
        if not channel:
            raise ServiceException(404, "Channel not found", "CHANNEL_NOT_FOUND")

        # Check duplicate
        existing = (
            db.query(ModelChannelMapping)
            .filter(
                ModelChannelMapping.unified_model_id == d["unified_model_id"],
                ModelChannelMapping.channel_id == d["channel_id"],
            )
            .first()
        )
        if existing:
            raise ServiceException(400, "Mapping already exists for this model and channel", "DUPLICATE_MAPPING")

        mapping = ModelChannelMapping(
            unified_model_id=d["unified_model_id"],
            channel_id=d["channel_id"],
            actual_model_name=d["actual_model_name"],
            enabled=d.get("enabled", 1),
        )
        db.add(mapping)
        db.commit()
        db.refresh(mapping)
        return ModelService._mapping_to_dict(mapping)

    @staticmethod
    def update_mapping(db: Session, mapping_id: int, data: dict) -> dict:
        """Update a model-channel mapping."""
        mapping = db.query(ModelChannelMapping).filter(ModelChannelMapping.id == mapping_id).first()
        if not mapping:
            raise ServiceException(404, "Mapping not found", "MAPPING_NOT_FOUND")

        for field in ("actual_model_name", "enabled"):
            value = data.get(field)
            if value is not None:
                setattr(mapping, field, value)

        db.commit()
        db.refresh(mapping)
        return ModelService._mapping_to_dict(mapping)

    @staticmethod
    def delete_mapping(db: Session, mapping_id: int) -> None:
        """Delete a model-channel mapping."""
        mapping = db.query(ModelChannelMapping).filter(ModelChannelMapping.id == mapping_id).first()
        if not mapping:
            raise ServiceException(404, "Mapping not found", "MAPPING_NOT_FOUND")

        db.delete(mapping)
        db.commit()

    @staticmethod
    def list_mappings(db: Session, unified_model_id: Optional[int] = None) -> list[dict]:
        """List mappings, optionally filtered by unified_model_id."""
        query = db.query(ModelChannelMapping)
        if unified_model_id is not None:
            query = query.filter(ModelChannelMapping.unified_model_id == unified_model_id)

        mappings = query.all()
        result = []
        for m in mappings:
            channel = db.query(Channel).filter(Channel.id == m.channel_id).first()
            result.append({
                "id": m.id,
                "unified_model_id": m.unified_model_id,
                "channel_id": m.channel_id,
                "actual_model_name": m.actual_model_name,
                "enabled": m.enabled,
                "channel_name": channel.name if channel else None,
                "created_at": m.created_at,
            })
        return result

    # -----------------------------------------------------------------------
    # Model Override Rule CRUD
    # -----------------------------------------------------------------------

    @staticmethod
    def create_override_rule(db: Session, data) -> dict:
        """Create a model override rule."""
        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        # Validate target model exists
        target = db.query(UnifiedModel).filter(UnifiedModel.id == d["target_unified_model_id"]).first()
        if not target:
            raise ServiceException(404, "Target unified model not found", "MODEL_NOT_FOUND")

        rule = ModelOverrideRule(
            name=d["name"],
            rule_type=d["rule_type"],
            source_pattern=d["source_pattern"],
            target_unified_model_id=d["target_unified_model_id"],
            enabled=d.get("enabled", 1),
            priority=d.get("priority", 10),
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return ModelService._rule_to_dict(rule)

    @staticmethod
    def update_override_rule(db: Session, rule_id: int, data) -> dict:
        """Update a model override rule."""
        rule = db.query(ModelOverrideRule).filter(ModelOverrideRule.id == rule_id).first()
        if not rule:
            raise ServiceException(404, "Override rule not found", "RULE_NOT_FOUND")

        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        updatable = ["name", "rule_type", "source_pattern", "target_unified_model_id", "enabled", "priority"]
        for field in updatable:
            value = d.get(field)
            if value is not None:
                if field == "target_unified_model_id":
                    target = db.query(UnifiedModel).filter(UnifiedModel.id == value).first()
                    if not target:
                        raise ServiceException(404, "Target unified model not found", "MODEL_NOT_FOUND")
                setattr(rule, field, value)

        db.commit()
        db.refresh(rule)
        return ModelService._rule_to_dict(rule)

    @staticmethod
    def delete_override_rule(db: Session, rule_id: int) -> None:
        """Delete a model override rule."""
        rule = db.query(ModelOverrideRule).filter(ModelOverrideRule.id == rule_id).first()
        if not rule:
            raise ServiceException(404, "Override rule not found", "RULE_NOT_FOUND")

        db.delete(rule)
        db.commit()

    @staticmethod
    def list_override_rules(db: Session, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        """List all override rules with target model name, paginated."""
        query = db.query(ModelOverrideRule).order_by(ModelOverrideRule.priority.asc())
        total = query.count()
        rules = query.offset((page - 1) * page_size).limit(page_size).all()
        result = []
        for r in rules:
            target = db.query(UnifiedModel).filter(UnifiedModel.id == r.target_unified_model_id).first()
            result.append({
                "id": r.id,
                "name": r.name,
                "rule_type": r.rule_type,
                "source_pattern": r.source_pattern,
                "target_unified_model_id": r.target_unified_model_id,
                "enabled": r.enabled,
                "priority": r.priority,
                "target_model_name": target.model_name if target else None,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            })
        return result, total

    # -----------------------------------------------------------------------
    # Model resolution & available channels
    # -----------------------------------------------------------------------

    @staticmethod
    def resolve_model(db: Session, requested_model_name: str) -> UnifiedModel | None:
        """
        Resolve a user-requested model name to a UnifiedModel.

        Steps:
            1. Check override rules (enabled, sorted by priority asc).
               If a rule matches (exact match or fnmatch pattern), redirect
               to the rule's target unified model.
            2. If no override rule matches, look up the model by exact name.

        Returns:
            The resolved UnifiedModel, or None if not found.
        """
        # Step 1: Check override rules
        rules = (
            db.query(ModelOverrideRule)
            .filter(ModelOverrideRule.enabled == 1)
            .order_by(ModelOverrideRule.priority.asc())
            .all()
        )
        for rule in rules:
            matched = False
            if rule.source_pattern == "*":
                matched = True
            elif rule.source_pattern == requested_model_name:
                matched = True
            elif "*" in rule.source_pattern or "?" in rule.source_pattern:
                matched = fnmatch.fnmatch(requested_model_name, rule.source_pattern)

            if matched:
                target = (
                    db.query(UnifiedModel)
                    .filter(
                        UnifiedModel.id == rule.target_unified_model_id,
                        UnifiedModel.enabled == 1,
                    )
                    .first()
                )
                if target:
                    logger.info(
                        "Model override matched: requested=%s rule=%s target=%s",
                        requested_model_name,
                        rule.source_pattern,
                        target.model_name,
                    )
                    return target

        # Step 2: Direct lookup
        model = (
            db.query(UnifiedModel)
            .filter(
                UnifiedModel.model_name == requested_model_name,
                UnifiedModel.enabled == 1,
            )
            .first()
        )
        return model

    @staticmethod
    def get_available_channels(
        db: Session, unified_model_id: int
    ) -> list[tuple[Channel, str]]:
        """
        Get available channels for a unified model, sorted by priority.

        Filters:
            - Mapping must be enabled.
            - Channel must be enabled.
            - Channel must be healthy.
            - Channel must not be in circuit-breaker state (i.e.
              circuit_breaker_until is None or in the past).

        Returns:
            List of (Channel, actual_model_name) tuples sorted by
            channel priority ascending (lower number = higher priority).
        """
        now = datetime.utcnow()

        mappings = (
            db.query(ModelChannelMapping)
            .filter(
                ModelChannelMapping.unified_model_id == unified_model_id,
                ModelChannelMapping.enabled == 1,
            )
            .all()
        )

        results: list[tuple[Channel, str]] = []
        for mapping in mappings:
            channel = (
                db.query(Channel)
                .filter(
                    Channel.id == mapping.channel_id,
                    Channel.enabled == 1,
                )
                .first()
            )
            if not channel:
                continue

            # Check circuit breaker
            if channel.circuit_breaker_until and channel.circuit_breaker_until > now:
                continue

            # If circuit breaker has expired, allow the channel through
            # (health check or successful request will reset it)
            if not channel.is_healthy:
                # If circuit_breaker_until has passed, allow it as a recovery attempt
                if channel.circuit_breaker_until and channel.circuit_breaker_until <= now:
                    pass  # allow recovery attempt
                else:
                    continue

            results.append((channel, mapping.actual_model_name))

        # Sort by channel priority (ascending: lower number = higher priority)
        results.sort(key=lambda x: x[0].priority)
        return results
