export type RoomStatus = 'fruiting' | 'idle' | 'sanitize'
export type HarvestGrade = 'A' | 'B' | 'C'

export interface Shed {
  id: number
  name: string
  location: string
  notes?: string | null
}

export interface Room {
  id: number
  shedId: number
  roomCode: string
  species: string
  capacityBags: number
  status: RoomStatus
}

export interface ClimateLog {
  id: number
  roomId: number
  recordedAt: string
  tempC: number
  humidityPct: number
  co2Ppm?: number | null
  notes?: string | null
}

export interface FlushHarvest {
  id: number
  roomId: number
  harvestedAt: string
  flushNo: number
  weightKg: number
  grade: HarvestGrade
  operatorName: string
}

export type SpawnWindowStatus = 'open' | 'closed'

export interface SpawnWindow {
  id: number
  shedId: number
  openedAt: string
  closedAt?: string | null
  status: SpawnWindowStatus
  capBags: number
  inoculatedBags: number
  inoculationCount: number
  /** 该窗已接种过的 room；关窗后这些 room 禁止新建采收 */
  inoculatedRoomIds?: number[]
}

export interface SpawnInoculation {
  id: number
  windowId: number
  roomId: number
  bagCount: number
  inoculatedAt: string
  operatorName: string
  climateLogId?: number | null
}

/** 409 响应（超 cap / 关窗拦截）时后端回显的累计信息 */
export interface SpawnConflictDetail {
  capBags?: number
  inoculatedBags?: number
  requestedBags?: number
  remainingBags?: number
  windowId?: number
  windowStatus?: SpawnWindowStatus
  roomId?: number
}

export interface DashboardStats {
  shedTotal: number
  fruitingRoomCount: number
  climateLast24h: number
  harvestKgLast7d: number
}
