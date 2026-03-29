"""SQLAlchemy ORM 資料模型定義。

【新手導讀】這個檔案定義了資料庫中所有「表」的結構。
每個 class 就是一張表，class 裡的變數就是表的欄位。
SQLAlchemy 會自動根據這些 class 建立對應的資料庫表。

術語解釋：
- ORM（Object-Relational Mapping）：讓你用 Python 物件操作資料庫，不需要寫 SQL 語法。
- Mapped[type]：告訴 SQLAlchemy 這個欄位的 Python 型別。
- mapped_column(...)：定義這個欄位在資料庫中的細節（型別、是否可為空、預設值等）。
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """使用者資料模型。

    【新手導讀】這張表存放所有註冊使用者的資訊。
    注意 password_hash 欄位：我們永遠不會儲存使用者的原始密碼，
    只存經過 bcrypt 雜湊（hash）後的結果。就像碎紙機——
    你可以把紙變成碎片，但無法把碎片還原成紙。

    Attributes:
        id: 使用者的唯一識別碼（UUID 格式）。
        username: 帳號名稱，同時作為顯示名稱，全系統唯一。
        password_hash: 密碼經過 bcrypt 雜湊後的結果。
        is_active: 帳號是否啟用（為未來停權功能預留）。
        created_at: 帳號建立時間。
        updated_at: 最後更新時間。
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class MeetingStatus(str, enum.Enum):
    """會議處理狀態。"""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Meeting(Base):
    """會議紀錄資料模型。"""

    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus), nullable=False, default=MeetingStatus.PROCESSING
    )
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    annotation_files: Mapped[list["AnnotationFile"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class ActionItem(Base):
    """待辦事項資料模型。"""

    __tablename__ = "action_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    assignee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    meeting: Mapped["Meeting"] = relationship(back_populates="action_items")


class AnnotationFile(Base):
    """標註檔案資料模型（TextGrid / RTTM）。"""

    __tablename__ = "annotation_files"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    meeting_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False
    )
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parsed_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    meeting: Mapped["Meeting"] = relationship(back_populates="annotation_files")
