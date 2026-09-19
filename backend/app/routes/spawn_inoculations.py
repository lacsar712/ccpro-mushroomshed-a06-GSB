from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.database import SessionLocal
from app.models.climate_log import ClimateLog
from app.models.room import Room
from app.models.spawn_inoculation import SpawnInoculation
from app.models.spawn_window import SpawnWindow
from app.schemas.spawn_inoculation import (
    SpawnInoculationCreateSchema,
    SpawnInoculationOutSchema,
)
from app.services.spawn_rules import (
    INOC_CLIMATE_NOTE,
    ensure_aware,
    window_used_bags,
)
from app.utils import validation_error_response

bp = Blueprint("spawn_inoculations", __name__, url_prefix="/api/spawn-inoculations")

create_schema = SpawnInoculationCreateSchema()
out_schema = SpawnInoculationOutSchema()


@bp.get("")
@jwt_required()
def list_inoculations():
    db = SessionLocal()
    try:
        q = db.query(SpawnInoculation)
        window_id = request.args.get("windowId", type=int)
        room_id = request.args.get("roomId", type=int)
        if window_id is not None:
            q = q.filter(SpawnInoculation.window_id == window_id)
        if room_id is not None:
            q = q.filter(SpawnInoculation.room_id == room_id)
        rows = q.order_by(SpawnInoculation.inoculated_at.desc(), SpawnInoculation.id.desc()).all()
        return jsonify(out_schema.dump(rows, many=True))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_inoculation():
    db = SessionLocal()
    try:
        try:
            data = create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)

        # 行锁整扇窗：并发补接种时 cap 校验也不会被绕过
        w = (
            db.query(SpawnWindow)
            .filter(SpawnWindow.id == data["window_id"])
            .with_for_update()
            .first()
        )
        if not w:
            return jsonify({"detail": "扩培窗不存在"}), 400
        if w.status == "closed":
            return (
                jsonify(
                    {
                        "detail": "扩培窗已关闭，禁止新接种",
                        "windowId": w.id,
                        "closedAt": w.closed_at,
                    }
                ),
                409,
            )

        room = db.query(Room).filter(Room.id == data["room_id"]).first()
        if not room:
            return jsonify({"detail": "出菇室不存在"}), 400
        # 接种必须落到同棚 room——禁止无 Room 挂接、禁止跨棚
        if room.shed_id != w.shed_id:
            return (
                jsonify(
                    {
                        "detail": "出菇室不属于该扩培窗所在菇房",
                        "roomShedId": room.shed_id,
                        "windowShedId": w.shed_id,
                    }
                ),
                400,
            )

        inoculated_at = ensure_aware(data["inoculated_at"])
        opened_at = ensure_aware(w.opened_at)
        if inoculated_at < opened_at:
            return (
                jsonify(
                    {
                        "detail": "接种时间早于开窗时间，不在接种窗区间内",
                        "openedAt": w.opened_at,
                    }
                ),
                400,
            )
        if w.closed_at is not None and inoculated_at > ensure_aware(w.closed_at):
            return jsonify({"detail": "接种时间晚于关窗时间，不在接种窗区间内"}), 400

        used = window_used_bags(db, w.id)
        projected = used + data["bag_count"]
        if projected > w.cap_bags:
            # 409 并回显累计，前端据此提示
            db.rollback()
            return (
                jsonify(
                    {
                        "detail": f"累计接种 {projected} 袋超过该窗容量 {w.cap_bags} 袋",
                        "windowId": w.id,
                        "capBags": w.cap_bags,
                        "usedBags": used,
                        "requestedBags": data["bag_count"],
                        "projectedBags": projected,
                        "remainingBags": max(0, w.cap_bags - used),
                    }
                ),
                409,
            )

        inoc = SpawnInoculation(
            window_id=w.id,
            room_id=room.id,
            bag_count=data["bag_count"],
            inoculated_at=inoculated_at,
            operator_name=data["operator_name"],
        )
        db.add(inoc)
        db.flush()  # 取 inoc.id；二者仍在同一事务

        # 接种成功必须同事务写一条该 room 的环境邻域记录
        climate = ClimateLog(
            room_id=room.id,
            recorded_at=inoculated_at,  # recordedAt 等于 inoculatedAt
            temp_c=data["temp_c"],
            humidity_pct=data["humidity_pct"],
            co2_ppm=data.get("co2_ppm"),
            notes=data.get("notes") or INOC_CLIMATE_NOTE,
        )
        db.add(climate)
        db.commit()
        db.refresh(inoc)
        payload = out_schema.dump(
            {
                "id": inoc.id,
                "window_id": inoc.window_id,
                "room_id": inoc.room_id,
                "bag_count": inoc.bag_count,
                "inoculated_at": inoc.inoculated_at,
                "operator_name": inoc.operator_name,
                "climate_log_id": climate.id,
            }
        )
        return jsonify(payload), 201
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
