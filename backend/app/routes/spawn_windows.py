from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.database import SessionLocal
from app.models.shed import Shed
from app.models.spawn_window import SpawnWindow
from app.schemas.spawn_window import (
    SpawnWindowCloseSchema,
    SpawnWindowCreateSchema,
    SpawnWindowOutSchema,
)
from app.services.spawn_rules import inoculated_room_ids, window_used_bags
from app.utils import validation_error_response

bp = Blueprint("spawn_windows", __name__, url_prefix="/api/spawn-windows")

create_schema = SpawnWindowCreateSchema()
close_schema = SpawnWindowCloseSchema()
out_schema = SpawnWindowOutSchema()


def serialize(db, w: SpawnWindow, *, include_locked: bool = False) -> dict:
    data = {
        "id": w.id,
        "shed_id": w.shed_id,
        "opened_at": w.opened_at,
        "closed_at": w.closed_at,
        "status": w.status,
        "cap_bags": w.cap_bags,
        "used_bags": window_used_bags(db, w.id),
        "locked_room_ids": [],
    }
    if include_locked or w.status == "closed":
        data["locked_room_ids"] = sorted(inoculated_room_ids(db, [w.id]))
    return out_schema.dump(data)


@bp.get("")
@jwt_required()
def list_windows():
    db = SessionLocal()
    try:
        shed_id = request.args.get("shedId", type=int)
        q = db.query(SpawnWindow)
        if shed_id is not None:
            q = q.filter(SpawnWindow.shed_id == shed_id)
        rows = q.order_by(SpawnWindow.opened_at.desc(), SpawnWindow.id.desc()).all()
        return jsonify([serialize(db, w) for w in rows])
    finally:
        db.close()


@bp.post("")
@jwt_required()
def create_window():
    db = SessionLocal()
    try:
        try:
            data = create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)

        shed = db.query(Shed).filter(Shed.id == data["shed_id"]).first()
        if not shed:
            return jsonify({"detail": "菇房不存在"}), 400

        existing = (
            db.query(SpawnWindow)
            .filter(SpawnWindow.shed_id == data["shed_id"], SpawnWindow.status == "open")
            .first()
        )
        if existing:
            return (
                jsonify(
                    {
                        "detail": "该菇房已有一扇开启中的扩培窗，须先关窗",
                        "openWindowId": existing.id,
                    }
                ),
                409,
            )

        item = SpawnWindow(
            shed_id=data["shed_id"],
            opened_at=data["opened_at"],
            closed_at=None,
            status="open",
            cap_bags=data["cap_bags"],
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return jsonify(serialize(db, item)), 201
    finally:
        db.close()


@bp.post("/<int:window_id>/close")
@jwt_required()
def close_window(window_id: int):
    db = SessionLocal()
    try:
        try:
            data = close_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)

        w = db.query(SpawnWindow).filter(SpawnWindow.id == window_id).first()
        if not w:
            return jsonify({"detail": "扩培窗不存在"}), 404
        if w.status == "closed":
            return jsonify({"detail": "该扩培窗已关闭"}), 409

        # closedAt 可空：未传则取服务端当前时刻
        w.closed_at = data.get("closed_at") or datetime.now(timezone.utc)
        w.status = "closed"
        db.commit()
        db.refresh(w)
        # 回显该窗已接种、因此被锁定的 room——锁定判定与采收拦截共用同一套逻辑
        return jsonify(serialize(db, w, include_locked=True))
    finally:
        db.close()
