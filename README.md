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
6. **SpawnWindow 扩培接种窗**（挂在 Shed 上，非通用日历）：`shedId`、`openedAt`、`closedAt(可空)`、`status(open|closed)`、`capBags(正整数)`；每棚同时仅一条 open，重复开窗 **409**
7. **SpawnInoculation 扩培接种**：`windowId`、`roomId`、`bagCount(正整数)`、`inoculatedAt`、`operatorName`；Room 必须与窗同棚（否则 **400**），`inoculatedAt` 须落在 open 区间（否则 **400**），累计 `bagCount` 超 `capBags` 返回 **409** 并回显 `capBags / inoculatedBags / requestedBags / remainingBags`
8. **接种邻域联动**：接种成功在**同一事务**内写一条该 Room 的 ClimateLog，`recordedAt = inoculatedAt`，`humidityPct` 默认 **90**（接种请求可显式传 `humidityPct` 覆盖，范围 1–100），`tempC/co2Ppm/notes` 可空；接种回包带 `climateLogId`。接种失败整体回滚，不留孤立环境记录
9. **关窗联锁**：窗 closed 后禁止新接种（**409**）；该窗中已接种过的 Room 禁止新建 FlushHarvest（**409**，回显 `windowId/windowStatus/roomId`）。关窗与采收拦截共用 `app/services/spawn.py` 的同一套已接种 Room 判定，不存在只改一侧的旁路
10. **Dashboard**：`shedTotal`、`fruitingRoomCount`、`climateLast24h`、`harvestKgLast7d`

各实体 API：`GET/POST` 列表与创建、`DELETE` 按 ID 删除。接种窗另含 `POST /api/spawn-windows/<id>/close`、`GET /api/spawn-windows/<id>/inoculations`。

## 前端页面

Login · Dashboard · Sheds · Rooms · ClimateLogs · **扩培窗（SpawnWindows）** · FlushHarvests（侧边栏布局）

扩培窗页可开窗/关窗、向 open 窗的同棚 Room 登记接种（仅展示同棚 Room，联锁仍以后端校验为准）、查看每窗累计/容量与接种记录；菇房、出菇室、邻域环境记录均可点击跳入对应页面；409 时页面回显累计袋数与剩余容量。

## 种子数据与失败路径

`python -m app.seed`（容器启动时自动执行）除基础台账外演示两条**预期失败**路径，启动日志可见：

- 窗 cap 1000：先接种 600（成功，邻域湿度默认 90）→ 再报 500 → **409 回显累计 600/1000、剩余 400**（该次接种与邻域记录整体回滚）→ 改报 300 成功（累计 900）
- 另一窗接种 400 后关窗：关窗后再接种 → **409**；对该窗已接种的 V-01 新建采收 → **409**（回显 windowId=2）；open 窗接种过的 Room 采收成功作对照

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
│       ├── models/
│       ├── schemas/
│       ├── services/   # spawn.py：开窗/接种事务与已接种 Room 共享判定
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
