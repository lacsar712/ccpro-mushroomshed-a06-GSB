from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SpawnWindow(Base):
    """挂在菇房（Shed）上的扩培接种窗，不是通用日历。

    每个 Shed 同时只允许一条 status='open' 的窗；
    该不变量在服务层开窗事务内对 shed 行加锁（FOR UPDATE）后检查。
    接种（SpawnInoculation）必须落到同棚 Room。
    """

    __tablename__ = "spawn_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shed_id: Mapped[int] = mapped_column(ForeignKey("sheds.id"), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    cap_bags: Mapped[int] = mapped_column(Integer, nullable=False)

    shed: Mapped["Shed"] = relationship("Shed", back_populates="spawn_windows")
    inoculations: Mapped[List["SpawnInoculation"]] = relationship(
        "SpawnInoculation", back_populates="window", cascade="all, delete-orphan"
    )
