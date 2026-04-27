"""Authentication service: register, login, current user info."""
from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.cache_log import CacheLog
from app.models.log import ConversationCheckpoint, ConversationSession, UserBalance, UserImageBalance, UserSubscription
from app.models.agent import Agent
from app.models.user import SysUser
from app.models.user import UserApiKey
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import ServiceException
from sqlalchemy import func, or_
from app.services.agent_service import AgentService


class AuthService:
    """Stateless authentication service."""

    @staticmethod
    def _build_agent_meta_map(db: Session, agent_ids: list[int]) -> dict[int, dict]:
        normalized_ids = sorted({int(agent_id) for agent_id in agent_ids if agent_id})
        if not normalized_ids:
            return {}
        rows = db.query(Agent).filter(Agent.id.in_(normalized_ids)).all()
        return {
            int(agent.id): {
                "agent_id": int(agent.id),
                "agent_code": agent.agent_code,
                "agent_name": agent.agent_name,
                "agent_frontend_domain": agent.frontend_domain,
            }
            for agent in rows
        }

    @staticmethod
    def register(
        db: Session,
        username: str,
        email: str,
        password: str,
        request_host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> dict:
        """
        Register a new user.

        Returns:
            dict with ``token`` and ``user`` keys.

        Raises:
            ServiceException: if username or email is already taken.
        """
        if not AgentService.is_self_register_allowed(
            db,
            host=request_host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        ):
            raise ServiceException(403, "当前站点已关闭注册", "REGISTRATION_DISABLED")

        site_context = AgentService.get_site_context_from_request(
            db,
            host=request_host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )

        # Check unique username
        if db.query(SysUser).filter(SysUser.username == username).first():
            raise ServiceException(400, "用户名已存在", "DUPLICATE_USERNAME")

        # Check unique email
        if db.query(SysUser).filter(SysUser.email == email).first():
            raise ServiceException(400, "邮箱已被注册", "DUPLICATE_EMAIL")

        # Create user
        user = SysUser(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="user",
            agent_id=site_context.agent_id,
            source_domain=site_context.host or AgentService.normalize_host(request_host),
            status=1,
        )
        db.add(user)
        db.flush()  # get user.id

        # Create initial balance record
        balance = UserBalance(
            user_id=user.id,
            balance=0,
            total_recharged=0,
            total_consumed=0,
        )
        db.add(balance)
        db.add(UserImageBalance(user_id=user.id, balance=0, total_recharged=0, total_consumed=0))
        db.commit()
        db.refresh(user)

        # Generate JWT
        token = create_access_token({"sub": str(user.id)})

        return {
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "agent_id": user.agent_id,
                "avatar": user.avatar,
            },
        }

    @staticmethod
    def login(
        db: Session,
        username: str,
        password: str,
        client_ip: Optional[str] = None,
        request_host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> dict:
        """
        Authenticate a user by username and password.

        Returns:
            dict with ``token`` and ``user`` keys.

        Raises:
            ServiceException: on invalid credentials or disabled account.
        """
        user = db.query(SysUser).filter(SysUser.username == username).first()
        if not user:
            raise ServiceException(401, "用户名或密码错误", "AUTH_FAILED")

        if not verify_password(password, user.password_hash):
            raise ServiceException(401, "用户名或密码错误", "AUTH_FAILED")

        if user.status != 1:
            raise ServiceException(403, "账号已被禁用", "ACCOUNT_DISABLED")

        AgentService.assert_user_matches_site(
            db,
            user,
            host=request_host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )

        # Update login metadata
        user.last_login_at = datetime.utcnow()
        if client_ip:
            user.last_login_ip = client_ip
        db.commit()

        token = create_access_token({"sub": str(user.id)})

        return {
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "agent_id": user.agent_id,
                "avatar": user.avatar,
            },
        }

    @staticmethod
    def get_current_user_info(db: Session, user_id: int) -> dict:
        """
        Return full profile information for the given user.

        Raises:
            ServiceException: if user not found.
        """
        from app.models.log import RequestLog
        from sqlalchemy import func

        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")

        # Fetch balances
        balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        image_balance = db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).first()
        from app.services.subscription_service import SubscriptionService

        # Calculate total tokens from request logs
        total_tokens = db.query(
            func.coalesce(func.sum(RequestLog.total_tokens), 0)
        ).filter(RequestLog.user_id == user_id).scalar() or 0
        agent_meta = {}
        if user.agent_id:
            agent_meta = AuthService._build_agent_meta_map(db, [int(user.agent_id)]).get(int(user.agent_id), {})

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "agent_id": user.agent_id,
            "agent_code": agent_meta.get("agent_code"),
            "agent_name": agent_meta.get("agent_name"),
            "agent_frontend_domain": agent_meta.get("agent_frontend_domain"),
            "source_domain": user.source_domain,
            "status": user.status,
            "avatar": user.avatar,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "balance": float(balance.balance) if balance else 0,
            "total_consumed": float(balance.total_consumed) if balance else 0,
            "total_recharged": float(balance.total_recharged) if balance else 0,
            "image_credit_balance": float(image_balance.balance) if image_balance else 0,
            "image_credit_total_consumed": float(image_balance.total_consumed) if image_balance else 0,
            "image_credit_total_recharged": float(image_balance.total_recharged) if image_balance else 0,
            "total_tokens": int(total_tokens),
            "subscription_summary": SubscriptionService.get_current_subscription_summary(db, user_id),
        }

    @staticmethod
    def list_users(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: str = None,
        sort_by: str = "id",
        sort_order: str = "desc",
        agent_id: Optional[int] = None,
        roles: Optional[list[str]] = None,
    ) -> tuple:
        query = db.query(SysUser, UserBalance.balance.label("balance")).outerjoin(
            UserBalance, UserBalance.user_id == SysUser.id
        )
        if agent_id is None:
            pass
        elif agent_id == 0:
            query = query.filter(SysUser.agent_id.is_(None))
        else:
            query = query.filter(SysUser.agent_id == agent_id)
        if roles:
            query = query.filter(SysUser.role.in_(roles))
        if keyword:
            keyword_text = str(keyword).strip()
            like = f"%{keyword_text}%"
            conditions = [SysUser.username.like(like), SysUser.email.like(like)]
            if keyword_text.isdigit():
                conditions.append(SysUser.id == int(keyword_text))
            query = query.filter(or_(*conditions))
        sort_dir = sort_order.lower() if sort_order else "desc"
        if sort_by == "balance":
            order_column = func.coalesce(UserBalance.balance, 0)
        elif sort_by == "last_login":
            order_column = SysUser.last_login_at
        else:
            order_column = SysUser.id
            sort_dir = "desc"

        if sort_dir == "asc":
            query = query.order_by(order_column.asc(), SysUser.id.asc())
        else:
            query = query.order_by(order_column.desc(), SysUser.id.desc())

        total = query.count()
        users = query.offset((page - 1) * page_size).limit(page_size).all()
        agent_meta_map = AuthService._build_agent_meta_map(
            db,
            [int(u.agent_id) for u, _balance in users if getattr(u, "agent_id", None)],
        )
        result = []
        for u, balance in users:
            image_bal = db.query(UserImageBalance).filter(UserImageBalance.user_id == u.id).first()
            from app.services.subscription_service import SubscriptionService
            subscription_summary = SubscriptionService.get_current_subscription_summary(db, u.id)
            agent_meta = agent_meta_map.get(int(u.agent_id), {}) if u.agent_id else {}
            result.append({
                "id": u.id, "username": u.username, "email": u.email,
                "role": u.role, "status": u.status, "avatar": u.avatar,
                "agent_id": u.agent_id,
                "agent_code": agent_meta.get("agent_code"),
                "agent_name": agent_meta.get("agent_name"),
                "agent_frontend_domain": agent_meta.get("agent_frontend_domain"),
                "source_domain": u.source_domain,
                "last_login": u.last_login_at.isoformat() if u.last_login_at else None,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "balance": float(balance) if balance is not None else 0,
                "image_credit_balance": float(image_bal.balance) if image_bal else 0,
                "subscription_type": u.subscription_type,
                "subscription_expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
                "subscription_summary": subscription_summary,
            })
        return result, total

    @staticmethod
    def get_user_detail(db: Session, user_id: int, agent_id: Optional[int] = None) -> dict:
        info = AuthService.get_current_user_info(db, user_id)
        if agent_id is not None and int(info.get("agent_id") or 0) != int(agent_id):
            raise ServiceException(403, "目标用户不在当前代理范围内", "AGENT_SCOPE_VIOLATION")
        return info

    @staticmethod
    def update_user(db: Session, user_id: int, data) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在")
        d = data if isinstance(data, dict) else data.model_dump(exclude_unset=True)
        for field in ("email", "avatar", "status", "role"):
            if field in d and d[field] is not None:
                setattr(user, field, d[field])
        db.commit()
        db.refresh(user)
        return AuthService.get_current_user_info(db, user_id)

    @staticmethod
    def toggle_user_status(db: Session, user_id: int) -> SysUser:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在")
        user.status = 0 if user.status == 1 else 1
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: int, operator_user_id: int) -> None:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在", "USER_NOT_FOUND")
        if user.id == operator_user_id:
            raise ServiceException(403, "不能删除当前登录账号", "DELETE_SELF_FORBIDDEN")

        db.query(CacheLog).filter(CacheLog.user_id == user_id).delete(synchronize_session=False)
        session_ids = [
            row[0]
            for row in db.query(ConversationSession.session_id).filter(ConversationSession.user_id == user_id).all()
        ]
        if session_ids:
            db.query(ConversationCheckpoint).filter(ConversationCheckpoint.session_id.in_(session_ids)).delete(
                synchronize_session=False
            )
        db.query(ConversationSession).filter(ConversationSession.user_id == user_id).delete(synchronize_session=False)
        db.query(UserSubscription).filter(UserSubscription.user_id == user_id).delete(synchronize_session=False)
        db.query(UserApiKey).filter(UserApiKey.user_id == user_id).delete(synchronize_session=False)
        db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).delete(synchronize_session=False)
        db.query(UserBalance).filter(UserBalance.user_id == user_id).delete(synchronize_session=False)
        db.delete(user)
        db.commit()

    @staticmethod
    def change_password(db: Session, user_id: int, old_password: str, new_password: str):
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "用户不存在")
        if not verify_password(old_password, user.password_hash):
            raise ServiceException(400, "旧密码错误")
        user.password_hash = hash_password(new_password)
        db.commit()

    @staticmethod
    def _get_user_for_password_reset(
        db: Session,
        username: str,
        email: str,
        request_host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> SysUser:
        normalized_username = str(username).strip()
        normalized_email = str(email).strip().lower()
        context = AgentService.get_site_context_from_request(
            db,
            host=request_host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )
        query = db.query(SysUser).filter(
            SysUser.username == normalized_username,
            func.lower(SysUser.email) == normalized_email,
        )
        if not AgentService.is_local_dev_host(context.host or context.request_host):
            if context.site_scope == "agent":
                query = query.filter(SysUser.agent_id == int(context.agent_id or 0))
            else:
                query = query.filter(SysUser.agent_id.is_(None))
        user = query.first()
        if not user:
            raise ServiceException(400, "账号或邮箱不匹配", "IDENTITY_MISMATCH")
        if user.status != 1:
            raise ServiceException(403, "账号已被禁用", "ACCOUNT_DISABLED")
        return user

    @staticmethod
    def verify_password_reset_identity(
        db: Session,
        username: str,
        email: str,
        request_host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> None:
        AuthService._get_user_for_password_reset(
            db,
            username=username,
            email=email,
            request_host=request_host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )

    @staticmethod
    def reset_password_by_identity(
        db: Session,
        username: str,
        email: str,
        new_password: str,
        request_host: Optional[str] = None,
        x_site_host: Optional[str] = None,
        origin: Optional[str] = None,
        referer: Optional[str] = None,
    ) -> None:
        user = AuthService._get_user_for_password_reset(
            db,
            username=username,
            email=email,
            request_host=request_host,
            x_site_host=x_site_host,
            origin=origin,
            referer=referer,
        )
        user.password_hash = hash_password(new_password)
        db.commit()
