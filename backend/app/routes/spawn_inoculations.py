from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.database import SessionLocal
from app.models.spawn_inoculation import SpawnInoculation
from app.schemas.spawn_inoculation import (
    SpawnInoculationCreateSchema,
    SpawnInoculationOutSchema,
)
from app.services import spawn as spawn_service
from app.utils import validation_error_response

bp = Blueprint("spawn_inoculations", __name__, url_prefix="/api/spawn-inoculations")

create_schema = SpawnInoculationCreateSchema()
out_schema = SpawnInoculationOutSchema()
out_many = SpawnInoculationOutSchema(many=True)


@bp.get("")
@jwt_required()
def list_inoculations():
    db = SessionLocal()
    try:
        window_id = request.args.get("windowId", type=int)
        room_id = request.args.get("roomId", type=int)
        q = db.query(SpawnInoculation)
        if window_id is not None:
            q = q.filter(SpawnInoculation.window_id == window_id)
        if room_id is not None:
            q = q.filter(SpawnInoculation.room_id == room_id)
        rows = q.order_by(SpawnInoculation.inoculated_at.desc()).all()
        return jsonify(out_many.dump(rows))
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
        try:
            # 校验 + 邻域 ClimateLog 同事务写入，任一失败整体回滚
            item = spawn_service.create_inoculation(db, data)
            db.commit()
        except spawn_service.WindowError as exc:
            db.rollback()
            return jsonify({"detail": exc.detail, **exc.extra}), exc.status
        db.refresh(item)
        return jsonify(out_schema.dump(item)), 201
    finally:
        db.close()
