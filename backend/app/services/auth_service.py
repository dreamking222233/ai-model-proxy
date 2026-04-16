"""Authentication service: register, login, current user info."""
from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.cache_log import CacheLog
from app.models.log import ConversationCheckpoint, ConversationSession, UserBalance, UserImageBalance, UserSubscription
from app.models.user import SysUser
from app.models.user import UserApiKey
from app.core.security import hash_password, verify_password, create_access_token
from app.core.exceptions import ServiceException
from sqlalchemy import func, or_


class AuthService:
    """Stateless authentication service."""

    @staticmethod
    def register(db: Session, username: str, email: str, password: str) -> dict:
        """
        Register a new user.

        Returns:
            dict with ``token`` and ``user`` keys.

        Raises:
            ServiceException: if username or email is already taken.
        """
        # Check unique username
        if db.query(SysUser).filter(SysUser.username == username).first():
            raise ServiceException(400, "Username already taken", "DUPLICATE_USERNAME")

        # Check unique email
        if db.query(SysUser).filter(SysUser.email == email).first():
            raise ServiceException(400, "Email already registered", "DUPLICATE_EMAIL")

        # Create user
        user = SysUser(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role="user",
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
                "avatar": user.avatar,
            },
        }

    @staticmethod
    def login(db: Session, username: str, password: str, client_ip: Optional[str] = None) -> dict:
        """
        Authenticate a user by username and password.

        Returns:
            dict with ``token`` and ``user`` keys.

        Raises:
            ServiceException: on invalid credentials or disabled account.
        """
        user = db.query(SysUser).filter(SysUser.username == username).first()
        if not user:
            raise ServiceException(401, "Invalid username or password", "AUTH_FAILED")

        if not verify_password(password, user.password_hash):
            raise ServiceException(401, "Invalid username or password", "AUTH_FAILED")

        if user.status != 1:
            raise ServiceException(403, "User account is disabled", "ACCOUNT_DISABLED")

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
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")

        # Fetch balances
        balance = db.query(UserBalance).filter(UserBalance.user_id == user_id).first()
        image_balance = db.query(UserImageBalance).filter(UserImageBalance.user_id == user_id).first()

        # Calculate total tokens from request logs
        total_tokens = db.query(
            func.coalesce(func.sum(RequestLog.total_tokens), 0)
        ).filter(RequestLog.user_id == user_id).scalar() or 0

        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "status": user.status,
            "avatar": user.avatar,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "balance": float(balance.balance) if balance else 0,
            "total_consumed": float(balance.total_consumed) if balance else 0,
            "total_recharged": float(balance.total_recharged) if balance else 0,
            "image_credit_balance": int(image_balance.balance) if image_balance else 0,
            "image_credit_total_consumed": int(image_balance.total_consumed) if image_balance else 0,
            "image_credit_total_recharged": int(image_balance.total_recharged) if image_balance else 0,
            "total_tokens": int(total_tokens),
        }

    @staticmethod
    def list_users(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        keyword: str = None,
        sort_by: str = "id",
        sort_order: str = "desc",
    ) -> tuple:
        query = db.query(SysUser, UserBalance.balance.label("balance")).outerjoin(
            UserBalance, UserBalance.user_id == SysUser.id
        )
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(or_(SysUser.username.like(like), SysUser.email.like(like)))
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
        result = []
        for u, balance in users:
            image_bal = db.query(UserImageBalance).filter(UserImageBalance.user_id == u.id).first()
            result.append({
                "id": u.id, "username": u.username, "email": u.email,
                "role": u.role, "status": u.status, "avatar": u.avatar,
                "last_login": u.last_login_at.isoformat() if u.last_login_at else None,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "balance": float(balance) if balance is not None else 0,
                "image_credit_balance": int(image_bal.balance) if image_bal else 0,
                "subscription_type": u.subscription_type,
                "subscription_expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
            })
        return result, total

    @staticmethod
    def get_user_detail(db: Session, user_id: int) -> dict:
        return AuthService.get_current_user_info(db, user_id)

    @staticmethod
    def update_user(db: Session, user_id: int, data) -> dict:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found")
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
            raise ServiceException(404, "User not found")
        user.status = 0 if user.status == 1 else 1
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def delete_user(db: Session, user_id: int, operator_user_id: int) -> None:
        user = db.query(SysUser).filter(SysUser.id == user_id).first()
        if not user:
            raise ServiceException(404, "User not found", "USER_NOT_FOUND")
        if user.id == operator_user_id:
            raise ServiceException(403, "You cannot delete your own account", "DELETE_SELF_FORBIDDEN")

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
            raise ServiceException(404, "User not found")
        if not verify_password(old_password, user.password_hash):
            raise ServiceException(400, "Incorrect old password")
        user.password_hash = hash_password(new_password)
        db.commit()
