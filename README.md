# MushroomShed-01 · 菇房出菇台账

食用菌菇房「出菇室环境记录与采收台账」种子项目（非库存 / 电商 / 医院 / 考勤）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11 · Flask · SQLAlchemy 2 · Marshmallow · Flask-JWT-Extended · passlib(bcrypt) · gunicorn |
| 前端 | SolidJS · Vite · TypeScript · @solidjs/router |
| 数据库 | MySQL 8（协议兼容原 MariaDB 设计） |
| 部署 | docker-compose · 前端 Nginx 反代 `/api` |

## 端口与账号

| 服务 | 端口 |
| --- | --- |
| 前端 | **3800** |
| 后端 API | **8800** |
| MySQL | **3310** |

| 用户名 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `123456` | admin（场长） |
| `fruiter` | `123456` | fruiter（出菇员） |

数据库：`mushroomshed` / `mushroomshed`，库名 `mushroomshed`。JWT 密钥环境变量 **`JWT_SECRET`**。

## 一键启动

```bash
cd MushroomShed-01
docker compose up --build
```

启动后访问：

- 前端：http://localhost:3800
- 后端健康检查：http://localhost:8800/api/health

后端 entrypoint 流程：等待 MySQL 就绪 → `create_all` 建表 → seed 初始数据 → 启动 gunicorn。

## 功能模块

1. **Auth**：JWT 登录（OAuth2 表单或 JSON），`/api/auth/login`、`/api/auth/me`，`Authorization: Bearer`
2. **Shed 菇房**：`name`、`location`、`notes`
3. **Room 出菇室**：`shedId`、`roomCode`、`species`、`capacityBags`、`status(fruiting|idle|sanitize)`；同菇房 `roomCode` 唯一
4. **ClimateLog 环境记录**：`roomId`、`recordedAt`、`tempC`、`humidityPct`、`co2Ppm`、`notes`；`humidityPct ∈ [1,100]`，否则 **400**
5. **FlushHarvest 采收**：`roomId`、`harvestedAt`、`flushNo(≥1)`、`weightKg`、`grade(A|B|C)`、`operatorName`；`weightKg > 0`，否则 **400**
6. **SpawnWindow 扩培接种窗**（挂在 Shed 上，非通用日历）：`shedId`、`openedAt`、`closedAt(可空)`、`status(open|closed)`、`capBags(正整数)`；每个 Shed 同时只许一条 `open`，重复开窗 **409**（回显 `openWindowId`）
7. **SpawnInoculation 窗内接种**：`windowId`、`roomId`、`bagCount(正整数)`、`inoculatedAt`、`operatorName`；规则：
   - `room` 必须属于该窗所在 Shed，且接种不允许无 Room 挂接（跨棚 / 缺 Room → **400**）
   - `inoculatedAt` 必须落在开窗区间内（≥ `openedAt`，已关窗时 ≤ `closedAt`），否则 **400**
   - 窗已 `closed` 后禁止新接种 → **409**
   - 该窗累计 `bagCount` 超过 `capBags` → **409**，响应回显 `usedBags / capBags / requestedBags / projectedBags / remainingBags`
   - **接种成功在同一事务内写入一条该 room 的 ClimateLog**：`recordedAt` 等于 `inoculatedAt`，`humidityPct` 默认 **90**、`tempC` 默认 **20**（均可在接种请求中覆写，`humidityPct` 仍受 1–100 校验），备注为「扩培接种自动写入环境邻域」；任一写入失败整体回滚
8. **关窗锁定与采收拦截共用同一套「已接种 room」判定**（`app/services/spawn_rules.py`）：关窗后该窗已接种过的 room 即锁定，`POST /api/flush-harvests` 对这些 room 返回 **409**（回显 `windowId`）；只改接种或只改采收都无法绕过
9. **Dashboard**：`shedTotal`、`fruitingRoomCount`、`climateLast24h`、`harvestKgLast7d`

各实体 API：`GET/POST` 列表与创建、`DELETE` 按 ID 删除。扩培窗另设：

| 方法与路径 | 说明 |
| --- | --- |
| `GET /api/spawn-windows?shedId=` | 窗列表（响应含 `usedBags` 与关窗后的 `lockedRoomIds`） |
| `POST /api/spawn-windows` | 开窗 |
| `POST /api/spawn-windows/{id}/close` | 关窗（body 可空；可传 `closedAt`，缺省取服务端当前时间），响应回显 `lockedRoomIds` |
| `GET /api/spawn-inoculations?windowId=&roomId=` | 接种记录 |
| `POST /api/spawn-inoculations` | 登记接种（同事务写 ClimateLog，响应含 `climateLogId`） |

## 前端页面

Login · Dashboard · Sheds · Rooms · ClimateLogs · FlushHarvests · **SpawnWindows 扩培窗**（侧边栏布局）

扩培窗页：开窗 / 窗内接种 / 关窗；选择扩培窗后，出菇室下拉只出现**同棚** Room（服务端同样强制，非前端假联锁）；超 cap、关窗后接种、关窗后采收的 409 信息原样展示，含累计袋数回显。Shed 名可跳入 `Rooms?shedId=`，已接种 Room 可跳入 `ClimateLogs?roomId=` 查看自动写入的环境邻域。

## Seed 内置的两条失败路径

种子数据（`app/seed.py`）除正常台账外，预置：

1. **超 cap 失败**：溪兰恒温菇房有一扇开启中的窗 `capBags=1000`，V-02 已接种 700 袋。再接种 400 袋 → **409**，回显 `usedBags=700, projectedBags=1100, remainingBags=300`。
2. **关窗后采收失败**：松木岭一号菇房有一扇已关闭的窗（800 袋），R-02 在其中接种 600 袋。对 R-02 新建 FlushHarvest → **409**。

复现（先登录取 token）：

```bash
# 超 cap：窗 id=2 / room V-02 id=4，700+400 > 1000
curl -s -X POST localhost:8800/api/spawn-inoculations -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"windowId":2,"roomId":4,"bagCount":400,"inoculatedAt":"2026-09-19T08:00:00Z","operatorName":"t"}'
# 409 {"capBags":1000,"usedBags":700,"projectedBags":1100,"remainingBags":300,...}

# 关窗后采收：room R-02 id=2 在已关闭窗 id=1 中接种过
curl -s -X POST localhost:8800/api/flush-harvests -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"roomId":2,"harvestedAt":"2026-09-19T10:00:00Z","flushNo":1,"weightKg":10,"grade":"A","operatorName":"t"}'
# 409 {"roomId":2,"windowId":1,"windowStatus":"closed",...}
```

## 本地开发（可选）

```bash
# 数据库（或用 compose 只起 db）
docker compose up -d db

# 后端
cd backend
pip install -r requirements.txt
set DATABASE_URL=mysql+pymysql://mushroomshed:mushroomshed@localhost:3310/mushroomshed
set JWT_SECRET=local-dev-secret
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)"
python -c "from app.seed import seed; seed()"
gunicorn wsgi:app --bind 0.0.0.0:8800 --reload

# 前端
cd frontend
npm install
npm run dev
```

## 目录结构

```
MushroomShed-01/
├── docker-compose.yml
├── README.md
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── wsgi.py
│   └── app/
│       ├── __init__.py
│       ├── config.py
│       ├── database.py
│       ├── auth.py
│       ├── seed.py
│       ├── utils.py
│       ├── models/          # shed / room / climate_log / flush_harvest / spawn_window / spawn_inoculation
│       ├── schemas/
│       ├── services/        # spawn_rules.py：关窗与采收共用的「已接种 room」判定
│       └── routes/
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── pages/
        ├── components/
        └── api/
```
