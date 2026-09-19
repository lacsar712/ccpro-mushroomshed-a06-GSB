from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SpawnInoculation(Base):
    """扩培接种记录。

    必须挂接到某条 SpawnWindow，且 room 必须与 window 属于同一 Shed；
    不允许脱离 Room 的纯计数。
    inoculatedAt 必须落在 window 的 open 区间内。
    成功接种会同事务写入该 room 的一条 ClimateLog（climate_log_id 回指）。
    """

    __tablename__ = "spawn_inoculations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    window_id: Mapped[int] = mapped_column(
        ForeignKey("spawn_windows.id"), nullable=False, index=True
    )
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False, index=True)
    bag_count: Mapped[int] = mapped_column(Integer, nullable=False)
    inoculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operator_name: Mapped[str] = mapped_column(String(64), nullable=False)
    climate_log_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("climate_logs.id", ondelete="SET NULL"), nullable=True
    )

    window: Mapped["SpawnWindow"] = relationship("SpawnWindow", back_populates="inoculations")
    room: Mapped["Room"] = relationship("Room", back_populates="spawn_inoculations")
    climate_log: Mapped[Optional["ClimateLog"]] = relationship(
        "ClimateLog", foreign_keys=[climate_log_id]
    )
