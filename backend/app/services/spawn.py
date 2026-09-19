"""扩培接种窗业务服务。

关窗与采收拦截共用本模块的「已接种 room」判定，
任何路由都不得自行另写一套。
"""

from datetime import datetime, timezone
from typing import Dict, Optional, Set

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.climate_log import ClimateLog
from app.models.room import Room
from app.models.shed import Shed
from app.models.spawn_inoculation import SpawnInoculation
from app.models.spawn_window import SpawnWindow

# 接种同事务写入邻域记录时的默认湿度
DEFAULT_INOCULATION_HUMIDITY_PCT = 90


def _as_utc(dt: datetime) -> datetime:
    """无时区信息的时间按 UTC 处理，避免 aware/naive 比较报错。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class WindowError(Exception):
    def __init__(self, detail: str, status: int = 400, extra: Optional[Dict] = None):
        super().__init__(detail)
        self.detail = detail
        self.status = status
        self.extra = extra or {}


def inoculated_room_ids(db: Session, window_id: int) -> Set[int]:
    """某接种窗下已接种过的 room id 集合。

    这是唯一的「已接种 room」判定原语：
    关窗后锁定哪些 room、采收拦截哪些 room，全部由它派生，禁止别处另写一套。
    """
    rows = (
        db.query(SpawnInoculation.room_id)
        .filter(SpawnInoculation.window_id == window_id)
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def closed_window_blocking_harvest(db: Session, room_id: int) -> Optional[SpawnWindow]:
    """采收拦截：该 room 是否在某个已 closed 的接种窗中接种过。

    逐窗复用 inoculated_room_ids() —— 与关窗锁定完全同一判定。
    """
    closed_windows = (
        db.query(SpawnWindow)
        .filter(SpawnWindow.status == "closed")
        .order_by(SpawnWindow.closed_at.desc())
        .all()
    )
    for window in closed_windows:
        if room_id in inoculated_room_ids(db, window.id):
            return window
    return None


def window_totals(db: Session, window_id: int) -> Dict[str, int]:
    row = (
        db.query(
            func.coalesce(func.sum(SpawnInoculation.bag_count), 0),
            func.count(SpawnInoculation.id),
        )
        .filter(SpawnInoculation.window_id == window_id)
        .one()
    )
    return {"inoculated_bags": int(row[0]), "inoculation_count": int(row[1])}


def open_window(db: Session, data: Dict) -> SpawnWindow:
    """开窗：对 shed 行加锁后检查同棚是否已有 open 窗。"""
    shed = (
        db.query(Shed)
        .with_for_update()
        .filter(Shed.id == data["shed_id"])
        .first()
    )
    if not shed:
        raise WindowError("菇房不存在", 400)

    existing = (
        db.query(SpawnWindow)
        .filter(SpawnWindow.shed_id == shed.id, SpawnWindow.status == "open")
        .first()
    )
    if existing:
        raise WindowError(
            f"该菇房已有未关闭的扩培接种窗（窗 #{existing.id}），须先关窗",
            409,
            {"windowId": existing.id},
        )

    window = SpawnWindow(
        shed_id=shed.id,
        opened_at=_as_utc(data["opened_at"]),
        closed_at=None,
        status="open",
        cap_bags=data["cap_bags"],
    )
    db.add(window)
    db.flush()
    return window


def close_window(db: Session, window_id: int, closed_at: Optional[datetime]) -> SpawnWindow:
    window = db.query(SpawnWindow).filter(SpawnWindow.id == window_id).first()
    if not window:
        raise WindowError("扩培接种窗不存在", 404)
    if window.status == "closed":
        raise WindowError("该接种窗已关闭", 409, {"windowId": window.id})

    final_closed_at = _as_utc(closed_at) if closed_at else datetime.now(timezone.utc)
    if final_closed_at < _as_utc(window.opened_at):
        raise WindowError("关窗时间不能早于开窗时间", 400)
    window.status = "closed"
    window.closed_at = final_closed_at
    db.flush()
    return window


def create_inoculation(db: Session, data: Dict) -> SpawnInoculation:
    """接种：全部校验 + 同事务写邻域 ClimateLog，任一失败整体回滚。"""
    # 锁窗行，串行化同窗累计 bagCount
    window = (
        db.query(SpawnWindow)
        .with_for_update()
        .filter(SpawnWindow.id == data["window_id"])
        .first()
    )
    if not window:
        raise WindowError("扩培接种窗不存在", 404)

    room = db.query(Room).filter(Room.id == data["room_id"]).first()
    if not room:
        raise WindowError("出菇室不存在", 400)

    # 接种必须落到同棚 Room，禁止无 Room 挂接
    if room.shed_id != window.shed_id:
        raise WindowError(
            f"出菇室不属于该接种窗所在菇房（窗属菇房 #{window.shed_id}）", 400
        )

    inoculated_at = _as_utc(data["inoculated_at"])
    opened_at = _as_utc(window.opened_at)
    closed_at = _as_utc(window.closed_at) if window.closed_at is not None else None
    if inoculated_at < opened_at:
        raise WindowError("接种时间早于开窗时间，不在接种窗 open 区间内", 400)
    if closed_at is not None and inoculated_at > closed_at:
        raise WindowError("接种时间晚于关窗时间，不在接种窗 open 区间内", 400)

    # 窗已 closed 后禁止新接种
    if window.status != "open":
        raise WindowError("该接种窗已关闭，禁止新接种", 409, {"windowId": window.id})

    totals = window_totals(db, window.id)
    already = totals["inoculated_bags"]
    requested = data["bag_count"]
    if already + requested > window.cap_bags:
        raise WindowError(
            f"累计接种将超出窗容量 {window.cap_bags} 袋（已累计 {already} 袋，本次 {requested} 袋）",
            409,
            {
                "windowId": window.id,
                "capBags": window.cap_bags,
                "inoculatedBags": already,
                "requestedBags": requested,
                "remainingBags": max(window.cap_bags - already, 0),
            },
        )

    humidity = data.get("humidity_pct")
    if humidity is None:
        humidity = DEFAULT_INOCULATION_HUMIDITY_PCT

    # 接种成功：同事务写该 room 的环境邻域记录，recordedAt 等于 inoculatedAt
    climate_log = ClimateLog(
        room_id=room.id,
        recorded_at=inoculated_at,
        temp_c=data.get("temp_c"),
        humidity_pct=humidity,
        co2_ppm=data.get("co2_ppm"),
        notes=data.get("notes")
        or f"扩培接种同步邻域记录（窗 #{window.id}，{requested} 袋，操作人 {data['operator_name']}）",
    )
    db.add(climate_log)
    db.flush()

    inoculation = SpawnInoculation(
        window_id=window.id,
        room_id=room.id,
        bag_count=requested,
        inoculated_at=inoculated_at,
        operator_name=data["operator_name"],
        climate_log_id=climate_log.id,
    )
    db.add(inoculation)
    db.flush()
    return inoculation
