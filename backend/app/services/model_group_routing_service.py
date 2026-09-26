"""Resolve API-key model-group routing and keep candidate selection in one place."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.model import UnifiedModel, ModelChannelMapping
from app.models.user import UserApiKey


GROUP_MODE_UNIFIED = "unified"
GROUP_MODE_SPECIAL = "special"


@dataclass(frozen=True)
class ModelGroupRouteContext:
    """Frozen routing identity for one request/session."""

    model_id: int
    model_name: str
    model_series: str
    group_id: Optional[int]
    group_name: Optional[str]
    group_multiplier: Any
    group_mode: str


class ModelGroupRoutingService:
    """Validate key scope, resolve the effective group, and filter mappings."""

    @staticmethod
    def _normalise_mode(api_key_record: Optional[UserApiKey]) -> str:
        mode = str(getattr(api_key_record, "group_mode", None) or GROUP_MODE_UNIFIED).lower()
        return mode if mode in {GROUP_MODE_UNIFIED, GROUP_MODE_SPECIAL} else GROUP_MODE_UNIFIED

    @staticmethod
    def _series(model: UnifiedModel) -> str:
        raw_series = str(getattr(model, "model_series", None) or "").strip().lower()
        if raw_series:
            return raw_series
        # ORM defaults are not materialized until flush; tests and migration
        # tools often construct a model object directly. Infer the same series
        # used by model management in that case.
        from app.core.model_series import infer_model_series
        return infer_model_series(getattr(model, "model_name", None))

    @staticmethod
    def resolve_context(
        db: Session,
        api_key_record: Optional[UserApiKey],
        unified_model: UnifiedModel,
        *,
        allow_unresolved_group: bool = False,
    ) -> ModelGroupRouteContext:
        """Resolve one immutable route context.

        ``allow_unresolved_group`` preserves compatibility while a database is being
        upgraded: if no group table/rows exist, the legacy ungrouped mapping path is
        still usable. Once groups exist, a missing default is reported explicitly.
        """
        mode = ModelGroupRoutingService._normalise_mode(api_key_record)
        series = ModelGroupRoutingService._series(unified_model)

        # Import lazily so model metadata can be loaded by migration/bootstrap code.
        try:
            from app.models.model import ModelGroup
        except ImportError:
            ModelGroup = None  # type: ignore[assignment]

        group = None
        # Keep legacy unit tests and pre-migration callers usable when they pass
        # a lightweight DB stub rather than a SQLAlchemy Session.
        if not hasattr(db, "query"):
            return ModelGroupRouteContext(
                model_id=int(unified_model.id),
                model_name=str(unified_model.model_name),
                model_series=series,
                group_id=None,
                group_name=None,
                group_multiplier=1,
                group_mode=mode,
            )
        if mode == GROUP_MODE_SPECIAL:
            key_series = str(getattr(api_key_record, "group_model_series", None) or "").strip().lower()
            key_group_id = getattr(api_key_record, "group_id", None)
            if not key_series or not key_group_id or key_series != series:
                raise ServiceException(
                    403,
                    "当前 API Key 不允许访问该模型系列",
                    "API_KEY_MODEL_GROUP_MISMATCH",
                )
            if ModelGroup is not None:
                group = db.query(ModelGroup).filter(ModelGroup.id == key_group_id).first()
                if group is None or str(getattr(group, "model_series", "")).lower() != series or not getattr(group, "enabled", 0):
                    raise ServiceException(
                        403,
                        "当前分组暂不可用，请先切换其他分组",
                        "MODEL_GROUP_UNAVAILABLE",
                    )
        elif ModelGroup is not None:
            # A unified key always follows the current default group for this series.
            group = (
                db.query(ModelGroup)
                .filter(
                    ModelGroup.model_series == series,
                    ModelGroup.enabled == 1,
                    ModelGroup.is_default == 1,
                )
                .order_by(ModelGroup.sort_order, ModelGroup.id)
                .first()
            )
            if group is None:
                # Once a series has been configured with groups, never fall back to
                # unfiltered legacy mappings. This also covers the case where every
                # group was disabled and prevents a disabled route from being used.
                any_group = (
                    db.query(ModelGroup)
                    .filter(ModelGroup.model_series == series)
                    .first()
                )
                if any_group is not None and not allow_unresolved_group:
                    raise ServiceException(
                        503,
                        "当前模型系列未设置默认分组",
                        "MODEL_GROUP_DEFAULT_REQUIRED",
                    )

        return ModelGroupRouteContext(
            model_id=int(unified_model.id),
            model_name=str(unified_model.model_name),
            model_series=series,
            group_id=int(group.id) if group is not None else None,
            group_name=getattr(group, "name", None) if group is not None else None,
            group_multiplier=getattr(group, "multiplier", 1) if group is not None else 1,
            group_mode=mode,
        )

    @staticmethod
    def assert_group_available(
        db: Session,
        context: ModelGroupRouteContext,
    ) -> None:
        """Raise the user-facing unavailable error when a selected group has no mapping."""
        from app.services.model_service import ModelService

        channels = ModelService.get_available_channels(db, context.model_id, group_id=context.group_id)
        if not channels:
            if context.group_id is not None:
                raise ServiceException(
                    503,
                    "当前分组暂无可用渠道，请先切换其他分组",
                    "MODEL_GROUP_NO_AVAILABLE_CHANNEL",
                )
            raise ServiceException(503, "当前模型暂无可用渠道", "NO_AVAILABLE_CHANNEL")

    @staticmethod
    def get_available_channels(
        db: Session,
        api_key_record: Optional[UserApiKey],
        unified_model: UnifiedModel,
    ) -> tuple[ModelGroupRouteContext, list[tuple[Any, str]]]:
        context = ModelGroupRoutingService.resolve_context(db, api_key_record, unified_model)
        from app.services.model_service import ModelService

        channels = ModelService.get_available_channels(db, unified_model.id, group_id=context.group_id)
        if not channels:
            ModelGroupRoutingService.assert_group_available(db, context)
        return context, channels

    @staticmethod
    def list_available_models(
        db: Session,
        api_key_record: Optional[UserApiKey],
    ) -> list[tuple[UnifiedModel, ModelGroupRouteContext]]:
        """Return models whose selected group contains at least one live mapping."""
        query = db.query(UnifiedModel).filter(UnifiedModel.enabled == 1)
        mode = ModelGroupRoutingService._normalise_mode(api_key_record)
        if mode == GROUP_MODE_SPECIAL:
            series = str(getattr(api_key_record, "group_model_series", None) or "").strip().lower()
            query = query.filter(UnifiedModel.model_series == series)

        result: list[tuple[UnifiedModel, ModelGroupRouteContext]] = []
        for model in query.order_by(UnifiedModel.model_name).all():
            try:
                context = ModelGroupRoutingService.resolve_context(
                    db, api_key_record, model, allow_unresolved_group=False
                )
                from app.services.model_service import ModelService

                if ModelService.get_available_channels(db, model.id, group_id=context.group_id):
                    result.append((model, context))
            except ServiceException:
                continue
        return result

    @staticmethod
    def mapping_query(db: Session, unified_model_id: int, group_id: Optional[int] = None):
        """Build the mapping query used by admin and dispatch code."""
        query = db.query(ModelChannelMapping).filter(
            ModelChannelMapping.unified_model_id == unified_model_id,
            ModelChannelMapping.enabled == 1,
        )
        if group_id is not None:
            query = query.filter(ModelChannelMapping.group_id == group_id)
        return query
