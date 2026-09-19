from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.database import SessionLocal
from app.models.flush_harvest import FlushHarvest
from app.models.room import Room
from app.schemas.flush_harvest import FlushHarvestCreateSchema, FlushHarvestOutSchema
from app.services import spawn as spawn_service
from app.utils import validation_error_response

bp = Blueprint("flush_harvests", __name__, url_prefix="/api/flush-harvests")

create_schema = FlushHarvestCreateSchema()
out_schema = FlushHarvestOutSchema()
out_many = FlushHarvestOutSchema(many=True)


@bp.get("")
@jwt_required()
def list_flush_harvests():
    db = SessionLocal()
    try:
        room_id = request.args.get("roomId", type=int)
        q = db.query(FlushHarvest)
        if room_id is not None:
            q = q.filter(FlushHarvest.room_id == room_id)
        rows = q.order_by(FlushHarvest.harvested_at.desc()).all()
        return jsonify(out_many.dump(rows))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_flush_harvest():
    db = SessionLocal()
    try:
        try:
            data = create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)
        room = db.query(Room).filter(Room.id == data["room_id"]).first()
        if not room:
            return jsonify({"detail": "出菇室不存在"}), 400

        # 与关窗共用同一套已接种 room 判定：
        # room 在某已 closed 的接种窗中接种过 → 禁止新建采收
        blocked_window = spawn_service.closed_window_blocking_harvest(db, data["room_id"])
        if blocked_window:
            return (
                jsonify(
                    {
                        "detail": (
                            f"该出菇室已在关闭的扩培接种窗 #{blocked_window.id} 中接种，"
                            "禁止新建采收记录"
                        ),
                        "windowId": blocked_window.id,
                        "windowStatus": blocked_window.status,
                        "roomId": data["room_id"],
                    }
                ),
                409,
            )

        item = FlushHarvest(
            room_id=data["room_id"],
            harvested_at=data["harvested_at"],
            flush_no=data["flush_no"],
            weight_kg=data["weight_kg"],
            grade=data["grade"],
            operator_name=data["operator_name"],
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return jsonify(out_schema.dump(item)), 201
    finally:
        db.close()


@bp.delete("/<int:harvest_id>")
@jwt_required()
def delete_flush_harvest(harvest_id: int):
    db = SessionLocal()
    try:
        item = db.query(FlushHarvest).filter(FlushHarvest.id == harvest_id).first()
        if not item:
            return jsonify({"detail": "采收记录不存在"}), 404
        db.delete(item)
        db.commit()
        return "", 204
    finally:
        db.close()
