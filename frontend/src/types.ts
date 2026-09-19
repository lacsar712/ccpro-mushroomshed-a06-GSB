export type RoomStatus = 'fruiting' | 'idle' | 'sanitize'
export type HarvestGrade = 'A' | 'B' | 'C'
export type SpawnWindowStatus = 'open' | 'closed'

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

export interface SpawnWindow {
  id: number
  shedId: number
  openedAt: string
  closedAt?: string | null
  status: SpawnWindowStatus
  capBags: number
  usedBags: number
  lockedRoomIds: number[]
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

export interface DashboardStats {
  shedTotal: number
  fruitingRoomCount: number
  climateLast24h: number
  harvestKgLast7d: number
}
