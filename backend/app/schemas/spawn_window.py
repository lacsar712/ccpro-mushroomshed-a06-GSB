from marshmallow import Schema, fields, validate

WINDOW_STATUSES = ("open", "closed")


class SpawnWindowCreateSchema(Schema):
    shed_id = fields.Int(required=True, data_key="shedId")
    opened_at = fields.DateTime(required=True, data_key="openedAt")
    cap_bags = fields.Int(
        required=True,
        data_key="capBags",
        validate=validate.Range(min=1, error="capBags 须为正整数"),
    )


class SpawnWindowCloseSchema(Schema):
    closed_at = fields.DateTime(required=False, data_key="closedAt", allow_none=True)


class SpawnWindowOutSchema(Schema):
    id = fields.Int(dump_only=True)
    shed_id = fields.Int(data_key="shedId")
    opened_at = fields.DateTime(data_key="openedAt")
    closed_at = fields.DateTime(allow_none=True, data_key="closedAt")
    status = fields.Str()
    cap_bags = fields.Int(data_key="capBags")
    inoculated_bags = fields.Int(data_key="inoculatedBags")
    inoculation_count = fields.Int(data_key="inoculationCount")
    inoculated_room_ids = fields.List(fields.Int(), data_key="inoculatedRoomIds")
