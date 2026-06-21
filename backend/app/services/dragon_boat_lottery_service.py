"""Dragon Boat Festival lottery activity service."""
from __future__ import annotations

import random
from datetime import datetime
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ServiceException
from app.models.activity import DragonBoatLotteryEntry
from app.models.log import ConsumptionRecord, OperationLog, SubscriptionPlan, UserBalance, UserSubscription
from app.models.user import SysUser


class DragonBoatLotteryService:
    """Registration, qualification, and draw operations for the activity."""

    ACTIVITY_NAME = "端午节抽奖"
    DEFAULT_TIMEZONE = "Asia/Shanghai"
    REGISTER_START = datetime(2026, 6, 19, 0, 0, 0)
    REGISTER_END = datetime(2026, 6, 21, 20, 0, 0)
    DRAW_START = datetime(2026, 6, 21, 23, 0, 0)
    QUALIFICATION_AMOUNT = Decimal("100")
    PRIZE_BY_RANK = {
        1: Decimal("300"),
        2: Decimal("200"),
        3: Decimal("100"),
        4: Decimal("50"),
        5: Decimal("50"),
        6: Decimal("50"),
        7: Decimal("50"),
        8: Decimal("50"),
        9: Decimal("50"),
        10: Decimal("50"),
    }

    @staticmethod
    def get_current_time() -> datetime:
        zone = ZoneInfo(DragonBoatLotteryService.DEFAULT_TIMEZONE)
        return datetime.now(zone).replace(tzinfo=None)

    @staticmethod
    def get_activity_config() -> dict:
        return {
            "name": DragonBoatLotteryService.ACTIVITY_NAME,
            "timezone": DragonBoatLotteryService.DEFAULT_TIMEZONE,
            "time_label": "北京时间",
            "register_start": DragonBoatLotteryService.REGISTER_START.isoformat(),
            "register_end": DragonBoatLotteryService.REGISTER_END.isoformat(),
            "draw_start": DragonBoatLotteryService.DRAW_START.isoformat(),
            "qualification_amount": float(DragonBoatLotteryService.QUALIFICATION_AMOUNT),
            "prize_by_rank": {
                str(rank): float(amount)
                for rank, amount in DragonBoatLotteryService.PRIZE_BY_RANK.items()
            },
        }

    @staticmethod
    def _to_float(value) -> float:
        return float(Decimal(str(value or 0)))

    @staticmethod
    def _iso(value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None

    @staticmethod
    def _get_phase(now: datetime) -> str:
        if now < DragonBoatLotteryService.REGISTER_START:
            return "pending"
        if DragonBoatLotteryService.REGISTER_START <= now <= DragonBoatLotteryService.REGISTER_END:
            return "registering"
        if now < DragonBoatLotteryService.DRAW_START:
            return "waiting_draw"
        return "drawable"

    @staticmethod
    def get_activity_status(now: Optional[datetime] = None) -> dict:
        current = now or DragonBoatLotteryService.get_current_time()
        phase = DragonBoatLotteryService._get_phase(current)
        return {
            "name": DragonBoatLotteryService.ACTIVITY_NAME,
            "timezone": DragonBoatLotteryService.DEFAULT_TIMEZONE,
            "time_label": "北京时间",
            "register_start": DragonBoatLotteryService.REGISTER_START.isoformat(),
            "register_end": DragonBoatLotteryService.REGISTER_END.isoformat(),
            "draw_start": DragonBoatLotteryService.DRAW_START.isoformat(),
            "now": current.isoformat(),
            "phase": phase,
            "can_register": phase == "registering",
            "can_draw": phase == "drawable",
            "prizes": [
                {"rank": 1, "amount": 300},
                {"rank": 2, "amount": 200},
                {"rank": 3, "amount": 100},
                {"rank": "4-10", "amount": 50},
            ],
        }

    @staticmethod
    def _serialize_entry(entry: Optional[DragonBoatLotteryEntry]) -> dict:
        if not entry:
            return {
                "registered": False,
                "id": None,
                "user_id": None,
                "username": None,
                "email": None,
                "agent_id": None,
                "qualification_type": None,
                "qualification_detail": None,
                "total_recharged": 0.0,
                "total_consumed": 0.0,
                "subscription_id": None,
                "status": None,
                "prize_rank": None,
                "prize_amount": 0.0,
                "drawn_at": None,
                "created_at": None,
            }

        return {
            "registered": True,
            "id": entry.id,
            "user_id": entry.user_id,
            "username": entry.username,
            "email": entry.email,
            "agent_id": entry.agent_id,
            "qualification_type": entry.qualification_type,
            "qualification_detail": entry.qualification_detail,
            "total_recharged": DragonBoatLotteryService._to_float(entry.total_recharged_snapshot),
            "total_consumed": DragonBoatLotteryService._to_float(entry.total_consumed_snapshot),
            "subscription_id": entry.subscription_id_snapshot,
            "status": entry.status,
            "prize_rank": int(entry.prize_rank) if entry.prize_rank else None,
            "prize_amount": DragonBoatLotteryService._to_float(entry.prize_amount),
            "drawn_by_user_id": entry.drawn_by_user_id,
            "drawn_at": DragonBoatLotteryService._iso(entry.drawn_at),
            "created_at": DragonBoatLotteryService._iso(entry.created_at),
            "updated_at": DragonBoatLotteryService._iso(entry.updated_at),
        }

    @staticmethod
    def _get_balance_snapshot(db: Session, user_id: int) -> tuple[Decimal, Decimal]:
        balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        total_recharged = Decimal(str(balance.total_recharged or 0)) if balance else Decimal("0")
        request_consumed = (
            db.query(func.coalesce(func.sum(ConsumptionRecord.total_cost), 0))
            .filter(
                ConsumptionRecord.user_id == user_id,
                ConsumptionRecord.total_cost > 0,
                ConsumptionRecord.request_id.isnot(None),
                ConsumptionRecord.request_id != "",
                ConsumptionRecord.model_name.isnot(None),
                ConsumptionRecord.model_name != "",
            )
            .scalar()
            or Decimal("0")
        )
        return total_recharged, Decimal(str(request_consumed or 0))

    @staticmethod
    def _assert_terminal_user(user: SysUser) -> None:
        if user.role != "user":
            raise ServiceException(403, "只有用户账号可以参与端午节抽奖", "LOTTERY_USER_ONLY")

    @staticmethod
    def _find_qualified_subscription(db: Session, user_id: int) -> Optional[UserSubscription]:
        duration_expr = func.coalesce(func.nullif(UserSubscription.duration_days_snapshot, 0), SubscriptionPlan.duration_days, 0)
        return (
            db.query(UserSubscription)
            .outerjoin(SubscriptionPlan, SubscriptionPlan.id == UserSubscription.plan_id)
            .filter(
                UserSubscription.user_id == user_id,
                duration_expr >= 1,
            )
            .order_by(UserSubscription.id.desc())
            .first()
        )

    @staticmethod
    def check_qualification(db: Session, user_id: int) -> dict:
        total_recharged, total_consumed = DragonBoatLotteryService._get_balance_snapshot(db, user_id)
        subscription = DragonBoatLotteryService._find_qualified_subscription(db, user_id)

        if subscription:
            duration_days = int(
                getattr(subscription, "duration_days_snapshot", None)
                or 0
            )
            detail = f"已开通过 {subscription.plan_name} 套餐"
            if duration_days > 0:
                detail = f"{detail}（{duration_days} 天）"
            return {
                "eligible": True,
                "qualification_type": "subscription",
                "qualification_detail": detail,
                "total_recharged": float(total_recharged),
                "total_consumed": float(total_consumed),
                "subscription_id": subscription.id,
            }

        if total_recharged > DragonBoatLotteryService.QUALIFICATION_AMOUNT:
            return {
                "eligible": True,
                "qualification_type": "recharge",
                "qualification_detail": f"累计充值 ${total_recharged.quantize(Decimal('0.0001'))}",
                "total_recharged": float(total_recharged),
                "total_consumed": float(total_consumed),
                "subscription_id": None,
            }

        if total_consumed > DragonBoatLotteryService.QUALIFICATION_AMOUNT:
            return {
                "eligible": True,
                "qualification_type": "consume",
                "qualification_detail": f"累计模型消费 ${total_consumed.quantize(Decimal('0.0001'))}",
                "total_recharged": float(total_recharged),
                "total_consumed": float(total_consumed),
                "subscription_id": None,
            }

        return {
            "eligible": False,
            "qualification_type": None,
            "qualification_detail": "未开通过日卡及以上套餐，且累计充值/消费均未大于 $100",
            "total_recharged": float(total_recharged),
            "total_consumed": float(total_consumed),
            "subscription_id": None,
        }

    @staticmethod
    def get_user_status(db: Session, user: SysUser) -> dict:
        DragonBoatLotteryService._assert_terminal_user(user)
        entry = db.query(DragonBoatLotteryEntry).filter(DragonBoatLotteryEntry.user_id == user.id).first()
        return {
            "activity": DragonBoatLotteryService.get_activity_status(),
            "qualification": DragonBoatLotteryService.check_qualification(db, user.id),
            "entry": DragonBoatLotteryService._serialize_entry(entry),
        }

    @staticmethod
    def register(db: Session, user: SysUser) -> dict:
        DragonBoatLotteryService._assert_terminal_user(user)
        now = DragonBoatLotteryService.get_current_time()
        if now < DragonBoatLotteryService.REGISTER_START:
            raise ServiceException(400, "端午节抽奖报名尚未开始", "LOTTERY_REGISTER_NOT_STARTED")
        if now > DragonBoatLotteryService.REGISTER_END:
            raise ServiceException(400, "端午节抽奖报名已结束", "LOTTERY_REGISTER_ENDED")

        existing = db.query(DragonBoatLotteryEntry).filter(DragonBoatLotteryEntry.user_id == user.id).first()
        if existing:
            return DragonBoatLotteryService.get_user_status(db, user)

        qualification = DragonBoatLotteryService.check_qualification(db, user.id)
        if not qualification["eligible"]:
            raise ServiceException(403, qualification["qualification_detail"], "LOTTERY_NOT_ELIGIBLE")

        entry = DragonBoatLotteryEntry(
            user_id=user.id,
            username=user.username,
            email=user.email,
            agent_id=user.agent_id,
            qualification_type=qualification["qualification_type"],
            qualification_detail=qualification["qualification_detail"],
            total_recharged_snapshot=Decimal(str(qualification["total_recharged"])),
            total_consumed_snapshot=Decimal(str(qualification["total_consumed"])),
            subscription_id_snapshot=qualification["subscription_id"],
            status="registered",
            prize_amount=Decimal("0"),
            created_at=now,
            updated_at=now,
        )
        db.add(entry)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            existing = db.query(DragonBoatLotteryEntry).filter(DragonBoatLotteryEntry.user_id == user.id).first()
            if existing:
                return DragonBoatLotteryService.get_user_status(db, user)
            raise ServiceException(409, "报名记录保存冲突，请刷新后重试", "LOTTERY_REGISTER_CONFLICT") from exc

        return DragonBoatLotteryService.get_user_status(db, user)

    @staticmethod
    def list_entries(
        db: Session,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        query = db.query(DragonBoatLotteryEntry)
        if keyword:
            keyword_text = keyword.strip()
            like = f"%{keyword_text}%"
            conditions = [
                DragonBoatLotteryEntry.username.ilike(like),
                DragonBoatLotteryEntry.email.ilike(like),
            ]
            if keyword_text.isdigit():
                conditions.append(DragonBoatLotteryEntry.user_id == int(keyword_text))
            query = query.filter(or_(*conditions))
        if status:
            if status == "winner":
                query = query.filter(DragonBoatLotteryEntry.prize_rank.isnot(None))
            else:
                query = query.filter(DragonBoatLotteryEntry.status == status)

        total = query.count()
        items = (
            query.order_by(
                DragonBoatLotteryEntry.prize_rank.is_(None).asc(),
                DragonBoatLotteryEntry.prize_rank.asc(),
                DragonBoatLotteryEntry.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [DragonBoatLotteryService._serialize_entry(item) for item in items], total

    @staticmethod
    def _get_winners(db: Session) -> list[dict]:
        winners = (
            db.query(DragonBoatLotteryEntry)
            .filter(DragonBoatLotteryEntry.prize_rank.isnot(None))
            .order_by(DragonBoatLotteryEntry.prize_rank.asc())
            .all()
        )
        return [DragonBoatLotteryService._serialize_entry(item) for item in winners]

    @staticmethod
    def get_summary(db: Session) -> dict:
        entry_count = db.query(func.count(DragonBoatLotteryEntry.id)).scalar() or 0
        winner_count = (
            db.query(func.count(DragonBoatLotteryEntry.id))
            .filter(DragonBoatLotteryEntry.prize_rank.isnot(None))
            .scalar()
            or 0
        )
        winners = DragonBoatLotteryService._get_winners(db)
        return {
            "activity": DragonBoatLotteryService.get_activity_status(),
            "entry_count": int(entry_count),
            "winner_count": int(winner_count),
            "drawn": bool(winner_count),
            "winners": winners,
        }

    @staticmethod
    def draw(db: Session, operator: SysUser) -> dict:
        now = DragonBoatLotteryService.get_current_time()
        if now < DragonBoatLotteryService.DRAW_START:
            raise ServiceException(400, "尚未到抽奖时间，2026-06-21 23:00:00 后可抽奖", "LOTTERY_DRAW_NOT_STARTED")

        entries = (
            db.query(DragonBoatLotteryEntry)
            .order_by(DragonBoatLotteryEntry.id.asc())
            .with_for_update()
            .all()
        )
        if not entries:
            raise ServiceException(400, "暂无报名用户，无法抽奖", "LOTTERY_NO_ENTRIES")

        existing_winners = [entry for entry in entries if entry.prize_rank is not None]
        if existing_winners:
            return {
                "drawn": True,
                "already_drawn": True,
                "winner_count": len(existing_winners),
                "winners": sorted(
                    [DragonBoatLotteryService._serialize_entry(entry) for entry in existing_winners],
                    key=lambda item: item["prize_rank"] or 999,
                ),
            }

        draw_count = min(10, len(entries))
        selected = random.SystemRandom().sample(entries, draw_count)
        drawn_at = now
        for rank, entry in enumerate(selected, start=1):
            entry.status = "winner"
            entry.prize_rank = rank
            entry.prize_amount = DragonBoatLotteryService.PRIZE_BY_RANK[rank]
            entry.drawn_by_user_id = operator.id
            entry.drawn_at = drawn_at
            entry.updated_at = drawn_at

        db.add(OperationLog(
            user_id=operator.id,
            username=operator.username,
            action="dragon_boat_lottery_draw",
            target_type="dragon_boat_lottery",
            target_id=None,
            description=f"端午节抽奖，抽出 {draw_count} 名中奖用户",
            agent_id=None,
        ))
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise ServiceException(409, "抽奖结果保存冲突，请刷新后查看中奖名单", "LOTTERY_DRAW_CONFLICT") from exc

        winners = DragonBoatLotteryService._get_winners(db)
        return {
            "drawn": True,
            "already_drawn": False,
            "winner_count": len(winners),
            "winners": winners,
        }
