from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.database import SessionLocal
from app.models.spawn_inoculation import SpawnInoculation
from app.models.spawn_window import SpawnWindow
from app.schemas.spawn_inoculation import SpawnInoculationOutSchema
from app.schemas.spawn_window import (
    SpawnWindowCloseSchema,
    SpawnWindowCreateSchema,
    SpawnWindowOutSchema,
)
from app.services import spawn as spawn_service
from app.utils import validation_error_response

bp = Blueprint("spawn_windows", __name__, url_prefix="/api/spawn-windows")

create_schema = SpawnWindowCreateSchema()
close_schema = SpawnWindowCloseSchema()
out_schema = SpawnWindowOutSchema()
out_many = SpawnWindowOutSchema(many=True)
inoc_out_many = SpawnInoculationOutSchema(many=True)


def _dump_window(db, window: SpawnWindow) -> dict:
    totals = spawn_service.window_totals(db, window.id)
    payload = out_schema.dump(window)
    payload["inoculatedBags"] = totals["inoculated_bags"]
    payload["inoculationCount"] = totals["inoculation_count"]
    # 关窗后这些 room 禁止新建采收；与采收拦截走同一判定原语
    payload["inoculatedRoomIds"] = sorted(
        spawn_service.inoculated_room_ids(db, window.id)
    )
    return payload


@bp.get("")
@jwt_required()
def list_windows():
    db = SessionLocal()
    try:
        shed_id = request.args.get("shedId", type=int)
        q = db.query(SpawnWindow)
        if shed_id is not None:
            q = q.filter(SpawnWindow.shed_id == shed_id)
        rows = q.order_by(SpawnWindow.opened_at.desc()).all()
        return jsonify([_dump_window(db, w) for w in rows])
    finally:
        db.close()


@bp.get("/<int:window_id>")
@jwt_required()
def get_window(window_id: int):
    db = SessionLocal()
    try:
        window = db.query(SpawnWindow).filter(SpawnWindow.id == window_id).first()
        if not window:
            return jsonify({"detail": "扩培接种窗不存在"}), 404
        return jsonify(_dump_window(db, window))
    finally:
        db.close()


@bp.get("/<int:window_id>/inoculations")
@jwt_required()
def list_window_inoculations(window_id: int):
    db = SessionLocal()
    try:
        window = db.query(SpawnWindow).filter(SpawnWindow.id == window_id).first()
        if not window:
            return jsonify({"detail": "扩培接种窗不存在"}), 404
        items = (
            db.query(SpawnInoculation)
            .filter(SpawnInoculation.window_id == window_id)
            .order_by(SpawnInoculation.inoculated_at.desc())
            .all()
        )
        return jsonify(inoc_out_many.dump(items))
    finally:
        db.close()


@bp.post("")
@jwt_required()
def open_window():
    db = SessionLocal()
    try:
        try:
            data = create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return validation_error_response(err)
        try:
            window = spawn_service.open_window(db, data)
            db.commit()
        except spawn_service.WindowError as exc:
            db.rollback()
            return jsonify({"detail": exc.detail, **exc.extra}), exc.status
        db.refresh(window)
        return jsonify(_dump_window(db, window)), 201
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
        try:
            window = spawn_service.close_window(db, window_id, data.get("closed_at"))
            db.commit()
        except spawn_service.WindowError as exc:
            db.rollback()
            return jsonify({"detail": exc.detail, **exc.extra}), exc.status
        db.refresh(window)
        return jsonify(_dump_window(db, window))
    finally:
        db.close()
