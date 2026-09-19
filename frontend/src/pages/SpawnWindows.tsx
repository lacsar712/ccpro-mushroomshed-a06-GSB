import { A, useSearchParams } from '@solidjs/router'
import { createMemo, createSignal, For, onMount, Show } from 'solid-js'
import { api } from '../api/client'
import type { Room, Shed, SpawnInoculation, SpawnWindow } from '../types'

function toLocalInput(d = new Date()) {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const winEmpty = { shedId: '', openedAt: toLocalInput(), capBags: '' }
const inocEmpty = {
  windowId: '',
  roomId: '',
  bagCount: '',
  inoculatedAt: toLocalInput(),
  operatorName: '',
  tempC: '20',
  humidityPct: '90',
}

export default function SpawnWindows() {
  const [windows, setWindows] = createSignal<SpawnWindow[]>([])
  const [inoculations, setInoculations] = createSignal<SpawnInoculation[]>([])
  const [sheds, setSheds] = createSignal<Shed[]>([])
  const [rooms, setRooms] = createSignal<Room[]>([])
  const [params] = useSearchParams<{ shedId?: string }>()
  const shedFilter = () => (params.shedId ? Number(params.shedId) : null)
  const [winForm, setWinForm] = createSignal({
    ...winEmpty,
    shedId: params.shedId ?? '',
  })
  const [inocForm, setInocForm] = createSignal({ ...inocEmpty })
  const [winError, setWinError] = createSignal('')
  const [inocError, setInocError] = createSignal('')
  const [notice, setNotice] = createSignal('')

  async function load() {
    const [w, ins, s, r] = await Promise.all([
      api<SpawnWindow[]>('/api/spawn-windows'),
      api<SpawnInoculation[]>('/api/spawn-inoculations'),
      api<Shed[]>('/api/sheds'),
      api<Room[]>('/api/rooms'),
    ])
    setWindows(w)
    setInoculations(ins)
    setSheds(s)
    setRooms(r)
  }

  // 进入页面先拉全量；room 下拉随后按所选窗所属 shed 收敛
  onMount(() => {
    load().catch((e) => setWinError(e.message))
  })

  const visibleWindows = () => {
    const sid = shedFilter()
    return sid ? windows().filter((w) => w.shedId === sid) : windows()
  }

  const shedMap = createMemo(() => new Map(sheds().map((s) => [s.id, s])))
  const roomMap = createMemo(() => new Map(rooms().map((r) => [r.id, r])))

  const openWindows = createMemo(() => {
    const sid = shedFilter()
    return windows().filter(
      (w) => w.status === 'open' && (sid === null || w.shedId === sid),
    )
  })

  // 选窗后可选 room 被强制收敛到该窗所属 shed —— 跨棚 room 不出现在列表里
  const eligibleRooms = createMemo(() => {
    const wid = Number(inocForm().windowId)
    const w = windows().find((x) => x.id === wid)
    if (!w) return []
    return rooms().filter((r) => r.shedId === w.shedId)
  })

  function inoculationsOf(windowId: number) {
    return inoculations().filter((i) => i.windowId === windowId)
  }

  async function onWindowSubmit(e: Event) {
    e.preventDefault()
    setWinError('')
    setNotice('')
    try {
      await api('/api/spawn-windows', {
        method: 'POST',
        body: JSON.stringify({
          shedId: Number(winForm().shedId),
          openedAt: new Date(winForm().openedAt).toISOString(),
          capBags: Number(winForm().capBags),
        }),
      })
      setWinForm({ ...winEmpty, openedAt: toLocalInput() })
      await load()
    } catch (err) {
      setWinError(err instanceof Error ? err.message : '开窗失败')
    }
  }

  async function closeWindow(w: SpawnWindow) {
    if (!confirm(`确认关闭菇房「${shedMap().get(w.shedId)?.name ?? w.shedId}」的扩培窗 #${w.id}？关窗后已接种的出菇室将禁止新采收。`))
      return
    setInocError('')
    setNotice('')
    try {
      const res = await api<SpawnWindow>(`/api/spawn-windows/${w.id}/close`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      setNotice(
        `窗 #${w.id} 已关闭，锁定已接种出菇室 ${res.lockedRoomIds.length} 间：${
          res.lockedRoomIds
            .map((rid) => roomMap().get(rid)?.roomCode ?? `#${rid}`)
            .join('、') || '无'
        }`,
      )
      await load()
    } catch (err) {
      setInocError(err instanceof Error ? err.message : '关窗失败')
    }
  }

  async function onInocSubmit(e: Event) {
    e.preventDefault()
    setInocError('')
    setNotice('')
    try {
      await api('/api/spawn-inoculations', {
        method: 'POST',
        body: JSON.stringify({
          windowId: Number(inocForm().windowId),
          roomId: Number(inocForm().roomId),
          bagCount: Number(inocForm().bagCount),
          inoculatedAt: new Date(inocForm().inoculatedAt).toISOString(),
          operatorName: inocForm().operatorName,
          tempC: Number(inocForm().tempC),
          humidityPct: Number(inocForm().humidityPct),
        }),
      })
      setInocForm({ ...inocEmpty, inoculatedAt: toLocalInput() })
      await load()
    } catch (err) {
      // 409：超 cap 回显累计 / 已关窗禁止接种，均在 detail 中
      setInocError(err instanceof Error ? err.message : '接种失败')
    }
  }

  return (
    <div>
      <header class="page-header">
        <h1>扩培接种窗</h1>
        <p class="muted">
          接种必须落在同棚出菇室；接种成功会同事务写入该室环境邻域（默认湿度 90%、温度 20°C）
        </p>
      </header>

      <Show when={winError()}><div class="error">{winError()}</div></Show>
      <Show when={inocError()}><div class="error">{inocError()}</div></Show>
      <Show when={notice()}><div class="panel" style={{ color: 'var(--forest-mid)' }}>{notice()}</div></Show>

      <Show when={shedFilter()}>
        <div class="panel" style={{ display: 'flex', 'align-items': 'center', gap: '12px' }}>
          <span>
            仅显示菇房 <strong>{sheds().find((s) => s.id === shedFilter())?.name}</strong> 的扩培窗
          </span>
          <a class="btn ghost" href="/spawn-windows">清除筛选</a>
        </div>
      </Show>

      <form class="panel form-grid" onSubmit={onWindowSubmit}>
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
          容量 (袋)
          <input
            type="number"
            min="1"
            value={winForm().capBags}
            onInput={(e) => setWinForm({ ...winForm(), capBags: e.currentTarget.value })}
            required
          />
        </label>
        <button type="submit" class="btn primary">新开扩培窗</button>
      </form>

      <Show
        when={openWindows().length > 0}
        fallback={<p class="muted">当前没有开启中的扩培窗。</p>}
      >
        <form class="panel form-grid" onSubmit={onInocSubmit}>
          <h3 class="span-2" style={{ margin: 0 }}>窗内接种登记</h3>
          <label>
            扩培窗（仅开启中）
            <select
              value={inocForm().windowId}
              onChange={(e) => setInocForm({ ...inocForm(), windowId: e.currentTarget.value, roomId: '' })}
              required
            >
              <option value="">选择扩培窗</option>
              <For each={openWindows()}>
                {(w) => (
                  <option value={String(w.id)}>
                    #{w.id} · {shedMap().get(w.shedId)?.name} · 已种 {w.usedBags}/{w.capBags}
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
              <For each={eligibleRooms()}>
                {(r) => (
                  <option value={String(r.id)}>
                    {r.roomCode} · {r.species}
                  </option>
                )}
              </For>
            </select>
          </label>
          <label>
            袋数
            <input
              type="number"
              min="1"
              value={inocForm().bagCount}
              onInput={(e) => setInocForm({ ...inocForm(), bagCount: e.currentTarget.value })}
              required
            />
          </label>
          <label>
            接种时间（需在开窗区间内）
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
            邻域温度 °C（默认 20）
            <input
              type="number"
              step="0.1"
              value={inocForm().tempC}
              onInput={(e) => setInocForm({ ...inocForm(), tempC: e.currentTarget.value })}
            />
          </label>
          <label>
            邻域湿度 %（默认 90）
            <input
              type="number"
              min="1"
              max="100"
              value={inocForm().humidityPct}
              onInput={(e) => setInocForm({ ...inocForm(), humidityPct: e.currentTarget.value })}
            />
          </label>
          <button type="submit" class="btn primary">登记接种</button>
        </form>
      </Show>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>窗 ID</th>
              <th>菇房</th>
              <th>开窗</th>
              <th>关窗</th>
              <th>状态</th>
              <th>累计 / 容量</th>
              <th>已接种出菇室</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <For each={visibleWindows()}>
              {(w) => (
                <>
                  <tr>
                    <td>{w.id}</td>
                    <td>
                      <A class="nav-link" href={`/rooms?shedId=${w.shedId}`}>
                        {shedMap().get(w.shedId)?.name ?? `菇房 #${w.shedId}`}
                      </A>
                    </td>
                    <td>{new Date(w.openedAt).toLocaleString()}</td>
                    <td>{w.closedAt ? new Date(w.closedAt).toLocaleString() : '—'}</td>
                    <td><span class={`badge ${w.status}`}>{w.status}</span></td>
                    <td>
                      {w.usedBags} / {w.capBags}
                      <div class="cap-bar"><div class="cap-fill" style={{ width: `${Math.min(100, (w.usedBags / w.capBags) * 100)}%` }} /></div>
                    </td>
                    <td>
                      <For each={inoculationsOf(w.id)}>
                        {(i) => (
                          <A class="nav-link" href={`/climate-logs?roomId=${i.roomId}`} style={{ display: 'inline-block', margin: '2px 6px 2px 0' }}>
                            {roomMap().get(i.roomId)?.roomCode ?? `室#${i.roomId}`}·{i.bagCount}
                          </A>
                        )}
                      </For>
                    </td>
                    <td>
                      <Show when={w.status === 'open'}>
                        <button type="button" class="btn ghost" onClick={() => closeWindow(w)}>关窗</button>
                      </Show>
                    </td>
                  </tr>
                </>
              )}
            </For>
          </tbody>
        </table>
      </div>
    </div>
  )
}
