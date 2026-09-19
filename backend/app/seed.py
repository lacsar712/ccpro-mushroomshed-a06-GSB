from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.database import SessionLocal
from app.models.climate_log import ClimateLog
from app.models.flush_harvest import FlushHarvest
from app.models.room import Room
from app.models.shed import Shed
from app.models.spawn_inoculation import SpawnInoculation
from app.models.spawn_window import SpawnWindow
from app.models.user import User
from app.services.spawn_rules import (
    DEFAULT_INOC_HUMIDITY_PCT,
    DEFAULT_INOC_TEMP_C,
    INOC_CLIMATE_NOTE,
)


def seed() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            db.add_all(
                [
                    User(
                        username="admin",
                        hashed_password=hash_password("123456"),
                        role="admin",
                        display_name="场长",
                    ),
                    User(
                        username="fruiter",
                        hashed_password=hash_password("123456"),
                        role="fruiter",
                        display_name="出菇员",
                    ),
                ]
            )
            db.commit()

        if db.query(Shed).count() == 0:
            s1 = Shed(
                name="松木岭一号菇房",
                location="闽北高海拔林区 A 区",
                notes="主产香菇与平菇",
            )
            s2 = Shed(
                name="溪谷恒温菇房",
                location="山谷侧翼 B 区",
                notes="杏鲍菇与秀珍菇轮作",
            )
            db.add_all([s1, s2])
            db.flush()

            r1 = Room(
                shed_id=s1.id,
                room_code="R-01",
                species="香菇",
                capacity_bags=1200,
                status="fruiting",
            )
            r2 = Room(
                shed_id=s1.id,
                room_code="R-02",
                species="平菇",
                capacity_bags=800,
                status="idle",
            )
            r3 = Room(
                shed_id=s2.id,
                room_code="V-01",
                species="杏鲍菇",
                capacity_bags=600,
                status="fruiting",
            )
            r4 = Room(
                shed_id=s2.id,
                room_code="V-02",
                species="秀珍菇",
                capacity_bags=500,
                status="sanitize",
            )
            db.add_all([r1, r2, r3, r4])
            db.flush()

            now = datetime.now(timezone.utc)
            db.add_all(
                [
                    ClimateLog(
                        room_id=r1.id,
                        recorded_at=now - timedelta(hours=2),
                        temp_c=18.5,
                        humidity_pct=88,
                        co2_ppm=950.0,
                        notes="晨检正常",
                    ),
                    ClimateLog(
                        room_id=r1.id,
                        recorded_at=now - timedelta(hours=8),
                        temp_c=17.8,
                        humidity_pct=90,
                        co2_ppm=880.0,
                        notes=None,
                    ),
                    ClimateLog(
                        room_id=r3.id,
                        recorded_at=now - timedelta(hours=4),
                        temp_c=16.2,
                        humidity_pct=85,
                        co2_ppm=720.0,
                        notes="CO2 略偏高",
                    ),
                    ClimateLog(
                        room_id=r3.id,
                        recorded_at=now - timedelta(hours=12),
                        temp_c=15.9,
                        humidity_pct=87,
                        co2_ppm=690.0,
                        notes=None,
                    ),
                    FlushHarvest(
                        room_id=r1.id,
                        harvested_at=now - timedelta(hours=6),
                        flush_no=2,
                        weight_kg=42.5,
                        grade="A",
                        operator_name="出菇员",
                    ),
                    FlushHarvest(
                        room_id=r1.id,
                        harvested_at=now - timedelta(days=1),
                        flush_no=1,
                        weight_kg=38.0,
                        grade="B",
                        operator_name="场长",
                    ),
                    FlushHarvest(
                        room_id=r3.id,
                        harvested_at=now - timedelta(days=3),
                        flush_no=1,
                        weight_kg=55.2,
                        grade="A",
                        operator_name="出菇员",
                    ),
                ]
            )

            # --- 扩培接种窗：含两条立即可复现的失败路径 ---
            # 1) s1 一扇已关闭的窗，R-02 在其中接种 600/800 → 对 R-02 新建采收必 409
            w_closed = SpawnWindow(
                shed_id=s1.id,
                opened_at=now - timedelta(days=10),
                closed_at=now - timedelta(days=7),
                status="closed",
                cap_bags=800,
            )
            # 2) s2 一扇开启中的窗，V-02 已累计 700/1000 → 再接种 400 袋必 409（剩 300）
            w_open = SpawnWindow(
                shed_id=s2.id,
                opened_at=now - timedelta(days=5),
                closed_at=None,
                status="open",
                cap_bags=1000,
            )
            db.add_all([w_closed, w_open])
            db.flush()

            inoc_closed = SpawnInoculation(
                window_id=w_closed.id,
                room_id=r2.id,
                bag_count=600,
                inoculated_at=now - timedelta(days=9),
                operator_name="场长",
            )
            inoc_open = SpawnInoculation(
                window_id=w_open.id,
                room_id=r4.id,
                bag_count=700,
                inoculated_at=now - timedelta(days=3),
                operator_name="出菇员",
            )
            db.add_all([inoc_closed, inoc_open])
            db.flush()

            # 每次接种同事务落一条该 room 的环境邻域（默认湿度 90% / 温度 20°C）
            db.add_all(
                [
                    ClimateLog(
                        room_id=r2.id,
                        recorded_at=now - timedelta(days=9),
                        temp_c=DEFAULT_INOC_TEMP_C,
                        humidity_pct=DEFAULT_INOC_HUMIDITY_PCT,
                        co2_ppm=None,
                        notes=INOC_CLIMATE_NOTE,
                    ),
                    ClimateLog(
                        room_id=r4.id,
                        recorded_at=now - timedelta(days=3),
                        temp_c=DEFAULT_INOC_TEMP_C,
                        humidity_pct=DEFAULT_INOC_HUMIDITY_PCT,
                        co2_ppm=None,
                        notes=INOC_CLIMATE_NOTE,
                    ),
                ]
            )
            db.commit()
            print("Seed data inserted.")
        else:
            print("Seed skipped (data exists).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
