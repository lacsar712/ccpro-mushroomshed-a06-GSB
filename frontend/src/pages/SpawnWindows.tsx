import { A } from '@solidjs/router'
import { createMemo, createSignal, For, onMount, Show } from 'solid-js'
import { ApiError, api } from '../api/client'
import type {
  Room,
  Shed,
  SpawnInoculation,
  SpawnWindow,
} from '../types'

function toLocalInput(d = new Date()) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const emptyWindow = { shedId: '', openedAt: toLocalInput(), capBags: '' }
const emptyInoc = {
  windowId: '',
  roomId: '',
  bagCount: '',
  inoculatedAt: toLocalInput(),
  operatorName: '',
  tempC: '',
  humidityPct: '',
  co2Ppm: '',
  notes: '',
}

export default function SpawnWindows() {
  const [windows, setWindows] = createSignal<SpawnWindow[]>([])
  const [inoculations, setInoculations] = createSignal<SpawnInoculation[]>([])
  const [sheds, setSheds] = createSignal<Shed[]>([])
  const [rooms, setRooms] = createSignal<Room[]>([])
  const [winForm, setWinForm] = createSignal({ ...emptyWindow })
  const [inocForm, setInocForm] = createSignal({ ...emptyInoc })
  const [error, setError] = createSignal('')
  const [conflict, setConflict] = createSignal('')
  const [inocFilter, setInocFilter] = createSignal('')

  async function load() {
    const [windowList, inocList, shedList, roomList] = await Promise.all([
      api<SpawnWindow[]>('/api/spawn-windows'),
      api<SpawnInoculation[]>('/api/spawn-inoculations'),
      api<Shed[]>('/api/sheds'),
      api<Room[]>('/api/rooms'),
    ])
    setWindows(windowList)
    setInoculations(inocList)
    setSheds(shedList)
    setRooms(roomList)
  }

  // 网络失败或页面过期时兜底加载
  onMount(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : '加载失败'))
  })

  const shedMap = createMemo(() => new Map(sheds().map((s) => [s.id, s])))
  const roomMap = createMemo(() => new Map(rooms().map((r) => [r.id, r])))

  const openWindows = createMemo(() => windows().filter((w) => w.status === 'open'))

  // 接种房只允许选当前 open 窗所在菇房的 Room（联锁以后端 400/409 为准，前端仅收敛选项）
  const inocRoomChoices = createMemo(() => {
    const w = windows().find((x) => x.id === Number(inocForm().windowId))
    if (!w) return []
    return rooms().filter((r) => r.shedId === w.shedId)
  })

  const visibleInoculations = createMemo(() => {
    const id = Number(inocFilter())
    const list = inoculations()
    return id ? list.filter((i) => i.windowId === id) : list
  })

  async function onOpenWindow(e: Event) {
    e.preventDefault()
    setError('')
    setConflict('')
    try {
      await api('/api/spawn-windows', {
        method: 'POST',
        body: JSON.stringify({
          shedId: Number(winForm().shedId),
          openedAt: new Date(winForm().openedAt).toISOString(),
          capBags: Number(winForm().capBags),
        }),
      })
      setWinForm({ ...emptyWindow, openedAt: toLocalInput() })
      await load()
    } catch (err) {
      reportError(err, '开窗失败')
    }
  }

  async function onClose(id: number) {
    if (!confirm(`确认关闭扩培接种窗 #${id}？关窗后该窗禁止新接种，且已接种室禁止新建采收。`)) return
    setError('')
    setConflict('')
    try {
      await api(`/api/spawn-windows/${id}/close`, { method: 'POST', body: '{}' })
      await load()
    } catch (err) {
      reportError(err, '关窗失败')
    }
  }

  async function onInoculate(e: Event) {
    e.preventDefault()
    setError('')
    setConflict('')
    const humidity = inocForm().humidityPct
    try {
      await api('/api/spawn-inoculations', {
        method: 'POST',
        body: JSON.stringify({
          windowId: Number(inocForm().windowId),
          roomId: Number(inocForm().roomId),
          bagCount: Number(inocForm().bagCount),
          inoculatedAt: new Date(inocForm().inoculatedAt).toISOString(),
          operatorName: inocForm().operatorName,
          tempC: inocForm().tempC ? Number(inocForm().tempC) : null,
          // 留空则后端默认 90
          humidityPct: humidity ? Number(humidity) : null,
          co2Ppm: inocForm().co2Ppm ? Number(inocForm().co2Ppm) : null,
          notes: inocForm().notes || null,
        }),
      })
      setInocForm({ ...emptyInoc, inoculatedAt: toLocalInput() })
      await load()
    } catch (err) {
      reportError(err, '接种失败')
    }
  }

  function reportError(err: unknown, fallback: string) {
    if (err instanceof ApiError) {
      if (err.status === 409) {
        const d = err.data || {}
        const parts = [err.message]
        if (d.inoculatedBags !== undefined && d.capBags !== undefined) {
          parts.push(
            `累计 ${String(d.inoculatedBags)}/${String(d.capBags)} 袋，剩余 ${String(
              d.remainingBags ?? Number(d.capBags) - Number(d.inoculatedBags),
            )} 袋（本次 ${String(d.requestedBags ?? '?')} 袋）`,
          )
        }
        setConflict(parts.join('；'))
        load().catch(() => undefined)
        return
      }
      setError(err.message || fallback)
      return
    }
    setError(err instanceof Error ? err.message : fallback)
  }

  function shedName(id: number) {
    return shedMap().get(id)?.name ?? `菇房 #${id}`
  }

  function roomLabel(id: number) {
    const r = roomMap().get(id)
    return r ? `${r.roomCode} · ${r.species}` : `出菇室 #${id}`
  }

  return (
    <div>
      <header class="page-header">
        <h1>扩培接种窗</h1>
        <p class="muted">
          接种窗挂在菇房上，接种必须落到同棚出菇室；接种成功会同事务写入该室环境邻域记录（湿度默认
          90%）。每棚同时仅一条 open 窗。
        </p>
      </header>

      <Show when={error()}>
        <div class="error">{error()}</div>
      </Show>
      <Show when={conflict()}>
        <div class="error conflict">409 冲突：{conflict()}</div>
      </Show>

      <form class="panel form-grid" onSubmit={onOpenWindow}>
        <label>
          菇房
          <select
            value={winForm().shedId}
            onChange={(e) => setWinForm({ ...winForm(), shedId: e.currentTarget.value })}
            required
          >
            <option value="">选择菇房</option>
            <For each={sheds()}>
              {(s) => <option value={String(s.id)}>{s.name}</option>}
            </For>
          </select>
        </label>
        <label>
          开窗时间
          <input
            type="datetime-local"
            value={winForm().openedAt}
            onInput={(e) => setWinForm({ ...winForm(), openedAt: e.currentTarget.value })}
            required
          />
        </label>
        <label>
          容量 capBags（袋，正整数）
          <input
            type="number"
            min="1"
            step="1"
            value={winForm().capBags}
            onInput={(e) => setWinForm({ ...winForm(), capBags: e.currentTarget.value })}
            required
          />
        </label>
        <button type="submit" class="btn primary">
          开窗
        </button>
      </form>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>窗 ID</th>
              <th>菇房</th>
              <th>开窗时间</th>
              <th>关窗时间</th>
              <th>状态</th>
              <th>累计 / 容量</th>
              <th>接种次数</th>
              <th>已接种室（关窗后锁采收）</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <For each={windows()}>
              {(w) => (
                <tr>
                  <td>{w.id}</td>
                  <td>
                    <A class="inline-link" href="/sheds">
                      {shedName(w.shedId)}
                    </A>
                  </td>
                  <td>{new Date(w.openedAt).toLocaleString()}</td>
                  <td>{w.closedAt ? new Date(w.closedAt).toLocaleString() : '—'}</td>
                  <td>
                    <span class={`badge window-${w.status}`}>{w.status}</span>
                  </td>
                  <td>
                    {w.inoculatedBags} / {w.capBags}
                    <span class={w.inoculatedBags > w.capBags ? 'over-cap' : 'muted'}>
                      {' '}
                      （余 {Math.max(w.capBags - w.inoculatedBags, 0)}）
                    </span>
                  </td>
                  <td>{w.inoculationCount}</td>
                  <td>
                    <Show when={w.inoculatedRoomIds?.length} fallback="—">
                      <For each={w.inoculatedRoomIds}>
                        {(rid, idx) => (
                          <>
                            {idx() > 0 ? '、' : ''}
                            <A class="inline-link" href="/rooms">
                              {roomLabel(rid)}
                            </A>
                          </>
                        )}
                      </For>
                      <Show when={w.status === 'closed'}>
                        <div class="muted">已锁定，禁止新采收</div>
                      </Show>
                    </Show>
                  </td>
                  <td>
                    <Show when={w.status === 'open'}>
                      <button type="button" class="btn ghost" onClick={() => onClose(w.id)}>
                        关窗
                      </button>
                    </Show>
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>

      <h2 class="section-title">登记接种</h2>
      <form class="panel form-grid" onSubmit={onInoculate}>
        <label>
          接种窗（仅 open）
          <select
            value={inocForm().windowId}
            onChange={(e) =>
              setInocForm({ ...inocForm(), windowId: e.currentTarget.value, roomId: '' })
            }
            required
          >
            <option value="">选择接种窗</option>
            <For each={openWindows()}>
              {(w) => (
                <option value={String(w.id)}>
                  窗 #{w.id} · {shedName(w.shedId)}（余 {w.capBags - w.inoculatedBags} 袋）
                </option>
              )}
            </For>
          </select>
        </label>
        <label>
          出菇室（同棚）
          <select
            value={inocForm().roomId}
            onChange={(e) => setInocForm({ ...inocForm(), roomId: e.currentTarget.value })}
            required
          >
            <option value="">选择出菇室</option>
            <For each={inocRoomChoices()}>
              {(r) => (
                <option value={String(r.id)}>
                  {r.roomCode} · {r.species}
                </option>
              )}
            </For>
          </select>
        </label>
        <label>
          袋数 bagCount（正整数）
          <input
            type="number"
            min="1"
            step="1"
            value={inocForm().bagCount}
            onInput={(e) => setInocForm({ ...inocForm(), bagCount: e.currentTarget.value })}
            required
          />
        </label>
        <label>
          接种时间（须落在 open 区间）
          <input
            type="datetime-local"
            value={inocForm().inoculatedAt}
            onInput={(e) => setInocForm({ ...inocForm(), inoculatedAt: e.currentTarget.value })}
            required
          />
        </label>
        <label>
          操作人
          <input
            value={inocForm().operatorName}
            onInput={(e) => setInocForm({ ...inocForm(), operatorName: e.currentTarget.value })}
            required
          />
        </label>
        <label>
          邻域温度 °C（可空）
          <input
            type="number"
            step="0.1"
            value={inocForm().tempC}
            onInput={(e) => setInocForm({ ...inocForm(), tempC: e.currentTarget.value })}
          />
        </label>
        <label>
          邻域湿度 %（留空默认 90）
          <input
            type="number"
            min="1"
            max="100"
            placeholder="90"
            value={inocForm().humidityPct}
            onInput={(e) => setInocForm({ ...inocForm(), humidityPct: e.currentTarget.value })}
          />
        </label>
        <label>
          CO₂ ppm（可空）
          <input
            type="number"
            step="1"
            value={inocForm().co2Ppm}
            onInput={(e) => setInocForm({ ...inocForm(), co2Ppm: e.currentTarget.value })}
          />
        </label>
        <label class="span-2">
          邻域备注（可空，留空自动生成）
          <input
            value={inocForm().notes}
            onInput={(e) => setInocForm({ ...inocForm(), notes: e.currentTarget.value })}
          />
        </label>
        <button type="submit" class="btn primary">
          登记接种
        </button>
      </form>

      <h2 class="section-title">
        接种记录
        <select
          class="title-filter"
          value={inocFilter()}
          onChange={(e) => setInocFilter(e.currentTarget.value)}
        >
          <option value="">全部窗</option>
          <For each={windows()}>
            {(w) => <option value={String(w.id)}>窗 #{w.id}</option>}
          </For>
        </select>
      </h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>窗 ID</th>
              <th>出菇室</th>
              <th>袋数</th>
              <th>接种时间</th>
              <th>操作人</th>
              <th>邻域环境记录</th>
            </tr>
          </thead>
          <tbody>
            <For each={visibleInoculations()}>
              {(i) => (
                <tr>
                  <td>{i.id}</td>
                  <td>{i.windowId}</td>
                  <td>
                    <A class="inline-link" href="/rooms">
                      {roomLabel(i.roomId)}
                    </A>
                  </td>
                  <td>{i.bagCount}</td>
                  <td>{new Date(i.inoculatedAt).toLocaleString()}</td>
                  <td>{i.operatorName}</td>
                  <td>
                    <Show when={i.climateLogId} fallback="—">
                      <A class="inline-link" href="/climate-logs">
                        环境记录 #{i.climateLogId}
                      </A>
                    </Show>
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </div>
    </div>
  )
}
