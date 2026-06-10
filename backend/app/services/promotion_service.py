"""User promotion link, relation, and reward service."""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import ServiceException
from app.models.agent import Agent
from app.models.log import ConsumptionRecord, ImageCreditRecord, UserBalance, UserImageBalance
from app.models.payment import PaymentRechargeOrder
from app.models.promotion import UserPromotionLink, UserPromotionRelation, UserPromotionReward
from app.models.user import SysUser
from app.services.agent_service import AgentService, AgentSiteContext


class PromotionService:
    """Promotion link generation, binding, reward settlement, and queries."""

    REWARD_RATE = Decimal("0.5")
    USD_SCALE = Decimal("0.000001")
    IMAGE_SCALE = Decimal("0.001")
    CNY_SCALE = Decimal("0.01")
    INVITE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    INVITE_CODE_LENGTH = 8
    MAX_CODE_RETRIES = 5

    @staticmethod
    def _normalize_invite_code(invite_code: str | None) -> str:
        return str(invite_code or "").strip().upper()

    @staticmethod
    def _decimal(value, scale: Decimal) -> Decimal:
        return Decimal(str(value or 0)).quantize(scale, rounding=ROUND_HALF_UP)

    @staticmethod
    def _num(value, scale: Decimal = USD_SCALE) -> float:
        return float(PromotionService._decimal(value, scale))

    @staticmethod
    def _serialize_dt(value) -> str | None:
        return value.isoformat() if value else None

    @staticmethod
    def _platform_frontend_host() -> str:
        for item in settings.PLATFORM_FRONTEND_HOSTS:
            host = AgentService.normalize_host(item)
            if host and not AgentService.is_platform_api_host(host):
                return host
        return "www.xiaoleai.team"

    @staticmethod
    def _is_local_host(host: str | None) -> bool:
        normalized = AgentService.normalize_host(host)
        return normalized in {"localhost", "127.0.0.1"} or normalized.endswith(".localhost") or normalized.endswith(".local")

    @staticmethod
    def _scheme_for_host(host: str) -> str:
        return "http" if PromotionService._is_local_host(host) else "https"

    @staticmethod
    def _site_scope_for_user(user: SysUser) -> str:
        return "agent" if getattr(user, "agent_id", None) else "platform"

    @staticmethod
    def _resolve_site_host(db: Session, user: SysUser, site_context: AgentSiteContext | None = None) -> str:
        if getattr(user, "agent_id", None):
            agent = getattr(site_context, "agent", None)
            if not agent or int(getattr(agent, "id", 0) or 0) != int(user.agent_id):
                agent = db.query(Agent).filter(Agent.id == int(user.agent_id)).first()
            if agent and AgentService.normalize_host(agent.frontend_domain):
                return AgentService.normalize_host(agent.frontend_domain)
            context_host = AgentService.normalize_host(getattr(site_context, "host", None))
            if PromotionService._is_local_host(context_host):
                return context_host
            raise ServiceException(500, "代理站点缺少前台域名，无法生成推广链接", "PROMOTION_AGENT_FRONTEND_DOMAIN_MISSING")

        return PromotionService._platform_frontend_host()

    @staticmethod
    def _build_invite_url(site_host: str, invite_code: str) -> str:
        host = AgentService.normalize_host(site_host)
        if not host:
            raise ServiceException(500, "推广链接域名缺失", "PROMOTION_SITE_HOST_MISSING")
        return f"{PromotionService._scheme_for_host(host)}://{host}/register?{urlencode({'invite_code': invite_code})}"

    @staticmethod
    def _generate_invite_code() -> str:
        return "".join(secrets.choice(PromotionService.INVITE_ALPHABET) for _ in range(PromotionService.INVITE_CODE_LENGTH))

    @staticmethod
    def get_or_create_user_link(db: Session, user: SysUser, site_context: AgentSiteContext | None = None) -> UserPromotionLink:
        if getattr(user, "role", "") != "user":
            raise ServiceException(403, "只有普通用户可以生成推广链接", "PROMOTION_USER_ROLE_INVALID")

        link = db.query(UserPromotionLink).filter(UserPromotionLink.user_id == user.id).first()
        site_host = PromotionService._resolve_site_host(db, user, site_context)
        site_scope = PromotionService._site_scope_for_user(user)
        if link:
            changed = False
            if link.site_host != site_host:
                link.site_host = site_host
                changed = True
            if link.site_scope != site_scope:
                link.site_scope = site_scope
                changed = True
            if link.agent_id != user.agent_id:
                link.agent_id = user.agent_id
                changed = True
            if changed:
                db.flush()
            return link

        for _ in range(PromotionService.MAX_CODE_RETRIES):
            link = UserPromotionLink(
                user_id=user.id,
                agent_id=user.agent_id,
                site_scope=site_scope,
                site_host=site_host,
                invite_code=PromotionService._generate_invite_code(),
                status="active",
                register_count=0,
                recharge_user_count=0,
                total_reward_usd=Decimal("0"),
                total_reward_image_credits=Decimal("0"),
            )
            try:
                with db.begin_nested():
                    db.add(link)
                    db.flush()
                return link
            except IntegrityError:
                continue
        raise ServiceException(500, "推广码生成失败，请稍后重试", "PROMOTION_CODE_GENERATE_FAILED")

    @staticmethod
    def serialize_link(link: UserPromotionLink) -> dict:
        return {
            "id": int(link.id),
            "invite_code": link.invite_code,
            "invite_url": PromotionService._build_invite_url(link.site_host, link.invite_code),
            "site_scope": link.site_scope,
            "site_host": link.site_host,
            "status": link.status,
            "register_count": int(link.register_count or 0),
            "recharge_user_count": int(link.recharge_user_count or 0),
            "total_reward_usd": PromotionService._num(link.total_reward_usd, PromotionService.USD_SCALE),
            "total_reward_image_credits": PromotionService._num(link.total_reward_image_credits, PromotionService.IMAGE_SCALE),
            "created_at": PromotionService._serialize_dt(link.created_at),
            "updated_at": PromotionService._serialize_dt(link.updated_at),
        }

    @staticmethod
    def bind_invited_user(
        db: Session,
        invited_user: SysUser,
        invite_code: str | None,
        site_context: AgentSiteContext,
    ) -> None:
        code = PromotionService._normalize_invite_code(invite_code)
        if not code:
            return
        if getattr(invited_user, "role", "") != "user":
            raise ServiceException(400, "当前账号类型不支持推广绑定", "PROMOTION_INVITED_ROLE_INVALID")

        link = (
            db.query(UserPromotionLink)
            .filter(UserPromotionLink.invite_code == code)
            .with_for_update()
            .first()
        )
        if not link or link.status != "active":
            raise ServiceException(400, "推广链接无效或已停用", "PROMOTION_CODE_INVALID")

        promoter = db.query(SysUser).filter(SysUser.id == link.user_id).first()
        if not promoter or promoter.role != "user" or promoter.status != 1:
            raise ServiceException(400, "推广用户状态无效", "PROMOTION_PROMOTER_INVALID")
        if int(promoter.id) == int(invited_user.id):
            raise ServiceException(400, "不能使用自己的推广链接注册", "PROMOTION_SELF_BIND_INVALID")

        invited_scope = PromotionService._site_scope_for_user(invited_user)
        if link.site_scope != invited_scope or (link.agent_id or None) != (invited_user.agent_id or None):
            raise ServiceException(400, "推广链接与当前站点不匹配", "PROMOTION_SITE_MISMATCH")
        if site_context.site_scope != invited_scope or (site_context.agent_id or None) != (invited_user.agent_id or None):
            raise ServiceException(400, "推广链接与当前注册站点不匹配", "PROMOTION_REGISTER_SITE_MISMATCH")

        existing = db.query(UserPromotionRelation.id).filter(UserPromotionRelation.invited_user_id == invited_user.id).first()
        if existing:
            raise ServiceException(400, "当前用户已绑定推广关系", "PROMOTION_RELATION_EXISTS")

        relation = UserPromotionRelation(
            promoter_user_id=promoter.id,
            promoter_agent_id=promoter.agent_id,
            invite_code=link.invite_code,
            invite_link_id=link.id,
            invited_user_id=invited_user.id,
            invited_agent_id=invited_user.agent_id,
            site_scope=invited_scope,
            site_host=site_context.host or link.site_host,
            first_recharged_at=None,
            total_recharge_cny=Decimal("0"),
            total_reward_usd=Decimal("0"),
            total_reward_image_credits=Decimal("0"),
        )
        db.add(relation)
        link.register_count = int(link.register_count or 0) + 1
        db.flush()

    @staticmethod
    def _get_or_create_user_image_balance_for_update(db: Session, user_id: int) -> UserImageBalance:
        balance = (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )
        if balance:
            return balance
        balance = UserImageBalance(user_id=user_id, balance=0, total_recharged=0, total_consumed=0)
        db.add(balance)
        db.flush()
        return (
            db.query(UserImageBalance)
            .filter(UserImageBalance.user_id == user_id)
            .with_for_update()
            .first()
        )

    @staticmethod
    def _insert_reward_once(db: Session, reward: UserPromotionReward) -> bool:
        try:
            with db.begin_nested():
                db.add(reward)
                db.flush()
            return True
        except IntegrityError:
            return False

    @staticmethod
    def apply_recharge_reward(db: Session, order: PaymentRechargeOrder) -> None:
        relation = (
            db.query(UserPromotionRelation)
            .filter(UserPromotionRelation.invited_user_id == order.user_id)
            .with_for_update()
            .first()
        )
        if not relation:
            return

        recharge_type = str(order.recharge_type or "balance").strip().lower()
        if recharge_type == "image_credit":
            reward_asset_type = "image_credit"
            reward_amount = (PromotionService._decimal(order.credited_image_credits, PromotionService.IMAGE_SCALE) * PromotionService.REWARD_RATE).quantize(PromotionService.IMAGE_SCALE, rounding=ROUND_HALF_UP)
            if reward_amount <= 0:
                return
        else:
            reward_asset_type = "balance"
            reward_amount = (PromotionService._decimal(order.credited_usd, PromotionService.USD_SCALE) * PromotionService.REWARD_RATE).quantize(PromotionService.USD_SCALE, rounding=ROUND_HALF_UP)
            if reward_amount <= 0:
                return

        reward = UserPromotionReward(
            relation_id=relation.id,
            promoter_user_id=relation.promoter_user_id,
            promoter_agent_id=relation.promoter_agent_id,
            invited_user_id=relation.invited_user_id,
            invite_code=relation.invite_code,
            order_id=order.id,
            order_no=order.order_no,
            recharge_type=recharge_type,
            amount_cny=PromotionService._decimal(order.amount_cny, PromotionService.CNY_SCALE),
            credited_usd=PromotionService._decimal(order.credited_usd, PromotionService.USD_SCALE),
            credited_image_credits=PromotionService._decimal(order.credited_image_credits, PromotionService.IMAGE_SCALE),
            reward_asset_type=reward_asset_type,
            reward_amount=reward_amount,
            reward_rate=PromotionService.REWARD_RATE,
            status="applied",
        )
        if not PromotionService._insert_reward_once(db, reward):
            return

        invited = db.query(SysUser).filter(SysUser.id == order.user_id).first()
        invited_name = getattr(invited, "username", None) or str(order.user_id)
        remark = f"推广返现：{invited_name} 在线充值"

        if reward_asset_type == "image_credit":
            image_balance = PromotionService._get_or_create_user_image_balance_for_update(db, int(relation.promoter_user_id))
            balance_before = PromotionService._decimal(image_balance.balance, PromotionService.IMAGE_SCALE)
            image_balance.balance = balance_before + reward_amount
            db.add(ImageCreditRecord(
                user_id=relation.promoter_user_id,
                agent_id=relation.promoter_agent_id,
                request_id=order.order_no,
                model_name="推广返现",
                change_amount=reward_amount,
                balance_before=balance_before,
                balance_after=image_balance.balance,
                multiplier=PromotionService.REWARD_RATE,
                action_type="promotion_reward",
                operator_id=None,
                remark=remark,
            ))
            relation.total_reward_image_credits = PromotionService._decimal(relation.total_reward_image_credits, PromotionService.IMAGE_SCALE) + reward_amount
        else:
            balance = (
                db.query(UserBalance)
                .filter(UserBalance.user_id == relation.promoter_user_id)
                .with_for_update()
                .first()
            )
            if not balance:
                raise ServiceException(404, "推广用户余额记录不存在", "PROMOTION_PROMOTER_BALANCE_NOT_FOUND")
            balance_before = PromotionService._decimal(balance.balance, PromotionService.USD_SCALE)
            balance.balance = balance_before + reward_amount
            db.add(ConsumptionRecord(
                user_id=relation.promoter_user_id,
                agent_id=relation.promoter_agent_id,
                request_id=order.order_no,
                model_name="推广返现",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                input_cost=Decimal("0"),
                output_cost=Decimal("0"),
                total_cost=-reward_amount,
                balance_before=balance_before,
                balance_after=balance.balance,
                billing_mode="balance",
                operator_id=None,
                remark=remark,
            ))
            relation.total_reward_usd = PromotionService._decimal(relation.total_reward_usd, PromotionService.USD_SCALE) + reward_amount

        first_recharge = relation.first_recharged_at is None
        if first_recharge:
            relation.first_recharged_at = datetime.now(timezone.utc).replace(tzinfo=None)
        relation.total_recharge_cny = PromotionService._decimal(relation.total_recharge_cny, PromotionService.CNY_SCALE) + PromotionService._decimal(order.amount_cny, PromotionService.CNY_SCALE)

        link = (
            db.query(UserPromotionLink)
            .filter(UserPromotionLink.id == relation.invite_link_id)
            .with_for_update()
            .first()
        )
        if link:
            if first_recharge:
                link.recharge_user_count = int(link.recharge_user_count or 0) + 1
            if reward_asset_type == "image_credit":
                link.total_reward_image_credits = PromotionService._decimal(link.total_reward_image_credits, PromotionService.IMAGE_SCALE) + reward_amount
            else:
                link.total_reward_usd = PromotionService._decimal(link.total_reward_usd, PromotionService.USD_SCALE) + reward_amount
        db.flush()

    @staticmethod
    def get_user_overview(db: Session, user: SysUser, site_context: AgentSiteContext | None = None) -> dict:
        link = PromotionService.get_or_create_user_link(db, user, site_context)
        db.commit()
        db.refresh(link)
        return PromotionService.serialize_link(link)

    @staticmethod
    def _relation_query(db: Session):
        promoter = SysUser
        invited = SysUser
        return db.query(UserPromotionRelation, promoter, invited).join(
            promoter,
            promoter.id == UserPromotionRelation.promoter_user_id,
        ).join(
            invited,
            invited.id == UserPromotionRelation.invited_user_id,
        )

    @staticmethod
    def _serialize_relation(relation: UserPromotionRelation, promoter: SysUser, invited: SysUser, agent_map: dict[int, Agent] | None = None) -> dict:
        agent = agent_map.get(int(relation.promoter_agent_id)) if agent_map and relation.promoter_agent_id else None
        return {
            "relation_id": int(relation.id),
            "invite_code": relation.invite_code,
            "site_scope": relation.site_scope,
            "site_host": relation.site_host,
            "promoter_user_id": int(promoter.id),
            "promoter_username": promoter.username,
            "promoter_email": promoter.email,
            "promoter_agent_id": relation.promoter_agent_id,
            "agent_id": relation.promoter_agent_id,
            "agent_name": getattr(agent, "agent_name", None),
            "agent_code": getattr(agent, "agent_code", None),
            "invited_user_id": int(invited.id),
            "invited_username": invited.username,
            "invited_email": invited.email,
            "registered_at": PromotionService._serialize_dt(relation.created_at),
            "has_recharged": relation.first_recharged_at is not None,
            "first_recharged_at": PromotionService._serialize_dt(relation.first_recharged_at),
            "total_recharge_cny": PromotionService._num(relation.total_recharge_cny, PromotionService.CNY_SCALE),
            "total_reward_usd": PromotionService._num(relation.total_reward_usd, PromotionService.USD_SCALE),
            "total_reward_image_credits": PromotionService._num(relation.total_reward_image_credits, PromotionService.IMAGE_SCALE),
        }

    @staticmethod
    def list_user_invited_users(db: Session, promoter_user_id: int, page: int = 1, page_size: int = 20) -> tuple[list[dict], int]:
        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 20), 1), 100)
        query = db.query(UserPromotionRelation, SysUser).join(
            SysUser,
            SysUser.id == UserPromotionRelation.invited_user_id,
        ).filter(UserPromotionRelation.promoter_user_id == promoter_user_id)
        total = query.count()
        rows = (
            query.order_by(UserPromotionRelation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        promoter = db.query(SysUser).filter(SysUser.id == promoter_user_id).first()
        items = [PromotionService._serialize_relation(relation, promoter, invited) for relation, invited in rows]
        return items, int(total)

    @staticmethod
    def list_relations(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        site_scope: str | None = None,
        agent_id: int | None = None,
        has_recharged: str | None = None,
    ) -> tuple[list[dict], int]:
        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 20), 1), 100)
        # Subquery ORM rows are awkward to serialize; use explicit aliases through aliased.
        from sqlalchemy.orm import aliased
        Promoter = aliased(SysUser)
        Invited = aliased(SysUser)
        query = db.query(UserPromotionRelation, Promoter, Invited).join(
            Promoter,
            Promoter.id == UserPromotionRelation.promoter_user_id,
        ).join(
            Invited,
            Invited.id == UserPromotionRelation.invited_user_id,
        )
        if keyword:
            like = f"%{str(keyword).strip()}%"
            query = query.filter(or_(
                Promoter.username.like(like),
                Promoter.email.like(like),
                Invited.username.like(like),
                Invited.email.like(like),
                UserPromotionRelation.invite_code.like(like),
            ))
        if site_scope in {"platform", "agent"}:
            query = query.filter(UserPromotionRelation.site_scope == site_scope)
        if agent_id is not None:
            if int(agent_id) == 0:
                query = query.filter(UserPromotionRelation.promoter_agent_id.is_(None))
            else:
                query = query.filter(UserPromotionRelation.promoter_agent_id == int(agent_id))
        if has_recharged == "yes":
            query = query.filter(UserPromotionRelation.first_recharged_at.isnot(None))
        elif has_recharged == "no":
            query = query.filter(UserPromotionRelation.first_recharged_at.is_(None))
        total = query.count()
        rows = (
            query.order_by(UserPromotionRelation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        agent_ids = sorted({int(relation.promoter_agent_id) for relation, _p, _i in rows if relation.promoter_agent_id})
        agent_map = {}
        if agent_ids:
            agent_map = {int(agent.id): agent for agent in db.query(Agent).filter(Agent.id.in_(agent_ids)).all()}
        return [PromotionService._serialize_relation(relation, promoter, invited, agent_map) for relation, promoter, invited in rows], int(total)

    @staticmethod
    def _serialize_reward(reward: UserPromotionReward, promoter: SysUser, invited: SysUser, order: PaymentRechargeOrder | None) -> dict:
        return {
            "id": int(reward.id),
            "relation_id": int(reward.relation_id),
            "invite_code": reward.invite_code,
            "site_scope": "agent" if reward.promoter_agent_id else "platform",
            "agent_id": reward.promoter_agent_id,
            "promoter_user_id": int(promoter.id),
            "promoter_username": promoter.username,
            "promoter_email": promoter.email,
            "invited_user_id": int(invited.id),
            "invited_username": invited.username,
            "invited_email": invited.email,
            "order_id": int(reward.order_id),
            "order_no": reward.order_no,
            "payment_channel": getattr(order, "payment_channel", None),
            "recharge_type": reward.recharge_type,
            "amount_cny": PromotionService._num(reward.amount_cny, PromotionService.CNY_SCALE),
            "credited_usd": PromotionService._num(reward.credited_usd, PromotionService.USD_SCALE),
            "credited_image_credits": PromotionService._num(reward.credited_image_credits, PromotionService.IMAGE_SCALE),
            "reward_asset_type": reward.reward_asset_type,
            "reward_amount": PromotionService._num(reward.reward_amount, PromotionService.IMAGE_SCALE if reward.reward_asset_type == "image_credit" else PromotionService.USD_SCALE),
            "reward_rate": PromotionService._num(reward.reward_rate, PromotionService.USD_SCALE),
            "paid_at": PromotionService._serialize_dt(getattr(order, "paid_at", None)),
            "created_at": PromotionService._serialize_dt(reward.created_at),
        }

    @staticmethod
    def list_rewards(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        agent_id: int | None = None,
        reward_asset_type: str | None = None,
        recharge_type: str | None = None,
    ) -> tuple[list[dict], int]:
        from sqlalchemy.orm import aliased
        Promoter = aliased(SysUser)
        Invited = aliased(SysUser)
        page = max(int(page or 1), 1)
        page_size = min(max(int(page_size or 20), 1), 100)
        query = db.query(UserPromotionReward, Promoter, Invited, PaymentRechargeOrder).join(
            Promoter,
            Promoter.id == UserPromotionReward.promoter_user_id,
        ).join(
            Invited,
            Invited.id == UserPromotionReward.invited_user_id,
        ).outerjoin(
            PaymentRechargeOrder,
            PaymentRechargeOrder.order_no == UserPromotionReward.order_no,
        )
        if keyword:
            like = f"%{str(keyword).strip()}%"
            query = query.filter(or_(
                Promoter.username.like(like),
                Promoter.email.like(like),
                Invited.username.like(like),
                Invited.email.like(like),
                UserPromotionReward.invite_code.like(like),
                UserPromotionReward.order_no.like(like),
            ))
        if agent_id is not None:
            if int(agent_id) == 0:
                query = query.filter(UserPromotionReward.promoter_agent_id.is_(None))
            else:
                query = query.filter(UserPromotionReward.promoter_agent_id == int(agent_id))
        if reward_asset_type in {"balance", "image_credit"}:
            query = query.filter(UserPromotionReward.reward_asset_type == reward_asset_type)
        if recharge_type in {"balance", "image_credit"}:
            query = query.filter(UserPromotionReward.recharge_type == recharge_type)
        total = query.count()
        rows = (
            query.order_by(UserPromotionReward.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [PromotionService._serialize_reward(reward, promoter, invited, order) for reward, promoter, invited, order in rows], int(total)

    @staticmethod
    def get_admin_summary(db: Session, agent_id: int | None = None) -> dict:
        relation_query = db.query(UserPromotionRelation)
        reward_query = db.query(UserPromotionReward)
        if agent_id is not None:
            relation_query = relation_query.filter(UserPromotionRelation.promoter_agent_id == int(agent_id))
            reward_query = reward_query.filter(UserPromotionReward.promoter_agent_id == int(agent_id))
        reward_totals = reward_query.with_entities(
            func.coalesce(func.sum(UserPromotionReward.reward_amount), 0),
        ).first()
        return {
            "relation_count": int(relation_query.count()),
            "reward_count": int(reward_query.count()),
            "reward_amount_total": float(reward_totals[0] or 0),
        }
