from marshmallow import Schema, fields, validate

from app.services.spawn_rules import DEFAULT_INOC_HUMIDITY_PCT, DEFAULT_INOC_TEMP_C


class SpawnInoculationCreateSchema(Schema):
    window_id = fields.Int(required=True, data_key="windowId")
    room_id = fields.Int(required=True, data_key="roomId")
    bag_count = fields.Int(
        required=True,
        data_key="bagCount",
        validate=validate.Range(min=1, error="bagCount 须为正整数"),
    )
    inoculated_at = fields.DateTime(required=True, data_key="inoculatedAt")
    operator_name = fields.Str(
        required=True, data_key="operatorName", validate=validate.Length(min=1, max=64)
    )
    # 接种同事务落一条该 room 的 ClimateLog，环境邻域允许覆盖默认值（README 有说明）
    temp_c = fields.Float(load_default=DEFAULT_INOC_TEMP_C, data_key="tempC")
    humidity_pct = fields.Int(
        load_default=DEFAULT_INOC_HUMIDITY_PCT,
        data_key="humidityPct",
        validate=validate.Range(min=1, max=100, error="humidityPct 须在 1–100 之间"),
    )
    co2_ppm = fields.Float(allow_none=True, load_default=None, data_key="co2Ppm")
    notes = fields.Str(allow_none=True, load_default=None)


class SpawnInoculationOutSchema(Schema):
    id = fields.Int(dump_only=True)
    window_id = fields.Int(data_key="windowId")
    room_id = fields.Int(data_key="roomId")
    bag_count = fields.Int(data_key="bagCount")
    inoculated_at = fields.DateTime(data_key="inoculatedAt")
    operator_name = fields.Str(data_key="operatorName")
    climate_log_id = fields.Int(allow_none=True, dump_default=None, data_key="climateLogId")
