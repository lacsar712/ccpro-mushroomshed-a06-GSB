from datetime import timezone
from typing import Iterable, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.spawn_inoculation import SpawnInoculation
from app.models.spawn_window import SpawnWindow

# 接种成功后同事务写入的环境邻域默认值（README 有说明）。
DEFAULT_INOC_TEMP_C = 20.0
DEFAULT_INOC_HUMIDITY_PCT = 90
INOC_CLIMATE_NOTE = "扩培接种自动写入环境邻域"


def ensure_aware(dt):
    """MySQL DATETIME 读回为 naive，统一按 UTC 处理以便与入参比较。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def inoculated_room_ids(db: Session, window_ids: Iterable[int]) -> Set[int]:
    """给定若干窗，返回其中已接种过的 room id 集合。

    关窗锁定与 FlushHarvest 拦截共用此判定，避免两处各写一套逻辑。
    """
    ids = list(window_ids)
    if not ids:
        return set()
    rows = (
        db.query(SpawnInoculation.room_id)
        .filter(SpawnInoculation.window_id.in_(ids))
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def window_used_bags(db: Session, window_id: int) -> int:
    """该窗下所有接种累计袋数。"""
    rows = (
        db.query(SpawnInoculation.bag_count)
        .filter(SpawnInoculation.window_id == window_id)
        .all()
    )
    return sum(bag for (bag,) in rows)


def closed_windows_for_shed(db: Session, shed_id: int) -> List[SpawnWindow]:
    return (
        db.query(SpawnWindow)
        .filter(
            SpawnWindow.shed_id == shed_id,
            SpawnWindow.status == "closed",
        )
        .all()
    )


def closed_window_blocking_harvest(
    db: Session, room: Room
) -> Optional[SpawnWindow]:
    """若该 room 在某扇已关闭的窗中接种过，返回该窗，否则 None。

    「已关窗 + 已接种」即锁定 room，禁止再新建采收——与关窗接口共用
    inoculated_room_ids 这一份判定。
    """
    closed_windows = closed_windows_for_shed(db, room.shed_id)
    if not closed_windows:
        return None
    locked = inoculated_room_ids(db, [w.id for w in closed_windows])
    if room.id not in locked:
        return None
    hit = (
        db.query(SpawnInoculation.window_id)
        .filter(
            SpawnInoculation.room_id == room.id,
            SpawnInoculation.window_id.in_([w.id for w in closed_windows]),
        )
        .first()
    )
    blocking_id = hit[0]
    return next(w for w in closed_windows if w.id == blocking_id)
