from marshmallow import Schema, fields, validate


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
    # 接种邻域环境，可选；湿度默认 90
    temp_c = fields.Float(
        required=False, data_key="tempC", allow_none=True, validate=validate.Range(min=-50, max=100)
    )
    humidity_pct = fields.Int(
        required=False,
        data_key="humidityPct",
        allow_none=True,
        validate=validate.Range(min=1, max=100, error="humidityPct 须在 1–100 之间"),
    )
    co2_ppm = fields.Float(required=False, data_key="co2Ppm", allow_none=True)
    notes = fields.Str(required=False, allow_none=True)


class SpawnInoculationOutSchema(Schema):
    id = fields.Int(dump_only=True)
    window_id = fields.Int(data_key="windowId")
    room_id = fields.Int(data_key="roomId")
    bag_count = fields.Int(data_key="bagCount")
    inoculated_at = fields.DateTime(data_key="inoculatedAt")
    operator_name = fields.Str(data_key="operatorName")
    climate_log_id = fields.Int(allow_none=True, data_key="climateLogId")
