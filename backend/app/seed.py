from datetime import datetime, timedelta, timezone

from app.auth import hash_password
from app.database import SessionLocal
from app.models.climate_log import ClimateLog
from app.models.flush_harvest import FlushHarvest
from app.models.room import Room
from app.models.shed import Shed
from app.models.spawn_window import SpawnWindow
from app.models.user import User
from app.services import spawn as spawn_service


def _print_expected_failure(tag: str, exc: "spawn_service.WindowError") -> None:
    print(f"[seed:预期失败] {tag} → HTTP {exc.status} {exc.detail} | 回显: {exc.extra}")


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
                ]
            )
            db.commit()
            print("Seed base data inserted.")
        else:
            print("Seed base skipped (sheds exist).")

        # 扩培接种窗演示（幂等：已有窗则跳过）
        if db.query(SpawnWindow).count() == 0:
            now = datetime.now(timezone.utc)
            s1 = db.query(Shed).filter(Shed.name == "松木岭一号菇房").one()
            s2 = db.query(Shed).filter(Shed.name == "溪谷恒温菇房").one()
            r1 = db.query(Room).filter(Room.shed_id == s1.id, Room.room_code == "R-01").one()
            r2 = db.query(Room).filter(Room.shed_id == s1.id, Room.room_code == "R-02").one()
            r3 = db.query(Room).filter(Room.shed_id == s2.id, Room.room_code == "V-01").one()
            r4 = db.query(Room).filter(Room.shed_id == s2.id, Room.room_code == "V-02").one()

            # 窗一：仍 open，容量 1000 袋
            w1 = spawn_service.open_window(
                db,
                {"shed_id": s1.id, "opened_at": now - timedelta(days=2), "cap_bags": 1000},
            )
            db.commit()
            print(f"[seed] 开窗 #{w1.id}（菇房 #{s1.id}，cap 1000，open）")

            # 成功接种 600 袋到 R-01；不传湿度 → 同事务邻域记录 humidityPct 默认 90
            inoc1 = spawn_service.create_inoculation(
                db,
                {
                    "window_id": w1.id,
                    "room_id": r1.id,
                    "bag_count": 600,
                    "inoculated_at": now - timedelta(days=2) + timedelta(hours=2),
                    "operator_name": "出菇员",
                    "temp_c": 20.1,
                },
            )
            db.commit()
            print(
                f"[seed] 接种 #{inoc1.id}：R-01 600 袋，邻域环境记录 "
                f"#{inoc1.climate_log_id}（湿度默认 90），累计 600/1000"
            )

            # 失败路径①：再接种 500 袋到 R-02 → 累计 1100 > cap 1000 → 409 回显累计
            try:
                spawn_service.create_inoculation(
                    db,
                    {
                        "window_id": w1.id,
                        "room_id": r2.id,
                        "bag_count": 500,
                        "inoculated_at": now - timedelta(days=2) + timedelta(hours=3),
                        "operator_name": "出菇员",
                    },
                )
                db.commit()
                print("[seed:异常] 超 cap 接种本应失败却成功了")
            except spawn_service.WindowError as exc:
                db.rollback()
                _print_expected_failure("超 cap 接种 500 袋（累计将达 1100/1000）", exc)

            # 容量内补种 300 袋成功（显式湿度 92）
            inoc2 = spawn_service.create_inoculation(
                db,
                {
                    "window_id": w1.id,
                    "room_id": r2.id,
                    "bag_count": 300,
                    "inoculated_at": now - timedelta(days=2) + timedelta(hours=4),
                    "operator_name": "场长",
                    "humidity_pct": 92,
                },
            )
            db.commit()
            print(f"[seed] 接种 #{inoc2.id}：R-02 300 袋（湿度 92），累计 900/1000")

            # 窗二：接种后关窗（用于关窗拦截演示）
            w2 = spawn_service.open_window(
                db,
                {"shed_id": s2.id, "opened_at": now - timedelta(days=6), "cap_bags": 800},
            )
            db.commit()
            print(f"[seed] 开窗 #{w2.id}（菇房 #{s2.id}，cap 800）")

            inoc3 = spawn_service.create_inoculation(
                db,
                {
                    "window_id": w2.id,
                    "room_id": r3.id,
                    "bag_count": 400,
                    "inoculated_at": now - timedelta(days=5),
                    "operator_name": "出菇员",
                },
            )
            db.commit()
            print(f"[seed] 接种 #{inoc3.id}：V-01 400 袋（湿度默认 90）")

            spawn_service.close_window(db, w2.id, now - timedelta(days=4))
            db.commit()
            print(f"[seed] 关窗 #{w2.id}")

            # 失败路径②：窗已 closed，即使时间落在原 open 区间内也禁止新接种 → 409
            try:
                spawn_service.create_inoculation(
                    db,
                    {
                        "window_id": w2.id,
                        "room_id": r4.id,
                        "bag_count": 100,
                        "inoculated_at": now - timedelta(days=5) + timedelta(hours=6),
                        "operator_name": "出菇员",
                    },
                )
                db.commit()
                print("[seed:异常] 关窗后接种本应失败却成功了")
            except spawn_service.WindowError as exc:
                db.rollback()
                _print_expected_failure("关窗后向 V-02 接种 100 袋", exc)

            # 对照：open 窗接种过的 R-02 允许新建采收
            ok_harvest = FlushHarvest(
                room_id=r2.id,
                harvested_at=now - timedelta(hours=1),
                flush_no=1,
                weight_kg=12.0,
                grade="B",
                operator_name="出菇员",
            )
            db.add(ok_harvest)
            db.commit()
            print("[seed] 对照：R-02 所在窗仍 open，新建采收成功")

            # 失败路径③：对关窗窗中已接种的 V-01 新建采收 → 409
            # 与 /api/flush-harvests 路由走完全相同的共享判定
            blocked = spawn_service.closed_window_blocking_harvest(db, r3.id)
            if blocked:
                print(
                    f"[seed:预期失败] 对 V-01 新建采收 → HTTP 409 "
                    f"该出菇室已在关闭的扩培接种窗 #{blocked.id} 中接种，禁止新建采收记录 | "
                    f"回显: {{'windowId': {blocked.id}, 'windowStatus': 'closed', "
                    f"'roomId': {r3.id}}}"
                )
            else:
                print("[seed:异常] V-01 采收本应被关窗拦截却放行")

            print("Seed spawn-window demo inserted.")
        else:
            print("Seed spawn-window demo skipped (windows exist).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
