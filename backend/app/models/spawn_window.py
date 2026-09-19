from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SpawnWindow(Base):
    """扩培接种窗：挂在某个 Shed 下，接种必须落到同棚的 Room。"""

    __tablename__ = "spawn_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shed_id: Mapped[int] = mapped_column(ForeignKey("sheds.id"), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    cap_bags: Mapped[int] = mapped_column(Integer, nullable=False)

    shed: Mapped["Shed"] = relationship("Shed")
    inoculations: Mapped[List["SpawnInoculation"]] = relationship(
        "SpawnInoculation",
        back_populates="window",
        cascade="all, delete-orphan",
    )
