import { useCallback, useState } from 'react'

const KEY = 'xk_busy_slots_v1'

/** 本学期共 16 教学周；已占时段只按周一~周五标记 */
export const MAX_WEEK = 16

/** 一段周次区间 [起, 止]（含端点） */
export type WeekRange = [number, number]

/** 已占时段标记：星期 w(1-5) 第 p 节，weeks 为占用周次区间列表（如 [[2,2],[6,8]]） */
export interface BusySlot {
  w: number
  p: number
  weeks: WeekRange[]
}

export const FULL_WEEKS: WeekRange[] = [[1, MAX_WEEK]]

/** 区间列表归一化：钳制 1-16、排序、合并相邻/重叠段 */
export function normalizeWeeks(weeks: WeekRange[]): WeekRange[] {
  const clamped = weeks
    .map(([a, b]) => [Math.max(1, Math.min(a, b)), Math.min(MAX_WEEK, Math.max(a, b))] as WeekRange)
    .filter(([a, b]) => b >= a)
    .sort((x, y) => x[0] - y[0])
  const out: WeekRange[] = []
  for (const [a, b] of clamped) {
    const last = out[out.length - 1]
    if (last && a <= last[1] + 1) last[1] = Math.max(last[1], b)
    else out.push([a, b])
  }
  return out
}

/** 已占用周数 */
export function occupiedCount(s: BusySlot): number {
  return normalizeWeeks(s.weeks).reduce((n, [a, b]) => n + (b - a + 1), 0)
}

export const isFullWeeks = (s: BusySlot) => occupiedCount(s) >= MAX_WEEK

/** 周次集合 → 紧凑文本：[[2,2],[6,8]] → "2,6-8" */
export function weeksToText(weeks: WeekRange[]): string {
  return normalizeWeeks(weeks).map(([a, b]) => (a === b ? `${a}` : `${a}-${b}`)).join(',')
}

/** 紧凑文本 → 区间列表："2,6,8,10" / "1-8,10" / "1-16" → 归一化区间；非法返回 null */
export function parseWeeksText(text: string): WeekRange[] | null {
  const t = text.trim().replace(/周/g, '')
  if (!t) return null
  if (t === '全' || t === '全部') return FULL_WEEKS
  const ranges: WeekRange[] = []
  for (const part of t.split(/[,，、]/)) {
    const seg = part.trim()
    if (!seg) continue
    const m = seg.match(/^(\d+)\s*[-－~]\s*(\d+)$/)
    if (m) ranges.push([Number(m[1]), Number(m[2])])
    else if (/^\d+$/.test(seg)) ranges.push([Number(seg), Number(seg)])
    else return null
  }
  if (!ranges.length) return null
  return normalizeWeeks(ranges)
}

/** 兼容三种历史格式：{w,p,weeks}（当前）、{w,p,wmin,wmax}、旧数组 [w,p(,wmin,wmax)]。
 *  读写格式必须对称，否则每次保存后读回全被丢弃。周末标记丢弃，周次钳制 1-16。 */
function normalizeSlot(x: any): BusySlot | null {
  let w = NaN, p = NaN, weeks: WeekRange[] | null = null
  if (x && typeof x === 'object' && !Array.isArray(x)) {
    w = Number(x.w); p = Number(x.p)
    if (Array.isArray(x.weeks)) weeks = x.weeks
    else if (x.wmin != null || x.wmax != null) weeks = [[Number(x.wmin ?? 1), Number(x.wmax ?? MAX_WEEK)]]
    else weeks = FULL_WEEKS
  } else if (Array.isArray(x) && x.length >= 2) {
    w = Number(x[0]); p = Number(x[1])
    weeks = x.length >= 4 ? [[Number(x[2]), Number(x[3])]] : FULL_WEEKS
  }
  if (!Number.isInteger(w) || w < 1 || w > 5 || !Number.isInteger(p) || p < 1 || !weeks) return null
  const norm = normalizeWeeks(weeks)
  return norm.length ? { w, p, weeks: norm } : null
}

function load(): BusySlot[] {
  try {
    const raw = localStorage.getItem(KEY)
    const arr = raw ? JSON.parse(raw) : []
    if (!Array.isArray(arr)) return []
    const out: BusySlot[] = []
    for (const x of arr) {
      const s = normalizeSlot(x)
      if (s && !out.some(o => o.w === s.w && o.p === s.p)) out.push(s)
    }
    return out
  } catch {
    return []
  }
}

/** 已占时段：每人各自浏览器独立，存 localStorage；查询与 AI 默认避开 */
export function useBusySlots() {
  const [slots, setSlots] = useState<BusySlot[]>(load)

  const save = (next: BusySlot[]) => {
    setSlots(next)
    localStorage.setItem(KEY, JSON.stringify(next))
  }
  /** 批量标记/取消（拖动框选提交）：weeks=null 表示取消这些格子；
   *  标记为只加不改——已有标记（含其周次）不受重复涂抹影响 */
  const applyCells = useCallback((cells: { w: number; p: number }[], weeks: WeekRange[] | null) => {
    const cur: BusySlot[] = load()
    if (weeks === null) {
      save(cur.filter(s => !cells.some(c => c.w === s.w && c.p === s.p)))
      return
    }
    let added = false
    const next = [...cur]
    for (const c of cells) {
      if (!next.some(s => s.w === c.w && s.p === c.p)) {
        next.push({ w: c.w, p: c.p, weeks })
        added = true
      }
    }
    if (added) save(next)
  }, [])
  /** 设置某格子的周次集合（周次勾选小窗用） */
  const setWeeks = useCallback((w: number, p: number, weeks: WeekRange[]) => {
    const norm = normalizeWeeks(weeks)
    if (!norm.length) return
    save(load().map(s => (s.w === w && s.p === p ? { ...s, weeks: norm } : s)))
  }, [])
  const clear = useCallback(() => save([]), [])
  /** 显式保存：把当前标记写入 localStorage（弹窗"保存"按钮用） */
  const persist = useCallback(() => {
    localStorage.setItem(KEY, JSON.stringify(slots))
  }, [slots])

  return { slots, applyCells, setWeeks, clear, persist, has: slots.length > 0 }
}

/** 序列化为 /api/courses 的 busy_slots 参数："1:1;4:7:2,6,8,10"（全学期省略周次） */
export const busySlotsToParam = (slots: BusySlot[]) =>
  slots.map(s => (isFullWeeks(s) ? `${s.w}:${s.p}` : `${s.w}:${s.p}:${weeksToText(s.weeks)}`)).join(';')

/** 序列化为 /api/chat 的 busy_slots 字段：每条一个 "w:p[:周次]" 字符串 */
export const busySlotsToStrings = (slots: BusySlot[]) =>
  slots.map(s => (isFullWeeks(s) ? `${s.w}:${s.p}` : `${s.w}:${s.p}:${weeksToText(s.weeks)}`))
