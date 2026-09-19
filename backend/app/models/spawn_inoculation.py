from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SpawnInoculation(Base):
    """窗内一次接种登记：必须挂接同棚 Room，成功即同事务写该 room 的 ClimateLog。

    同一窗内同一 room 允许分批补接种，bag_count 按窗累计受 cap_bags 约束。
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

    window: Mapped["SpawnWindow"] = relationship("SpawnWindow", back_populates="inoculations")
    room: Mapped["Room"] = relationship("Room")
