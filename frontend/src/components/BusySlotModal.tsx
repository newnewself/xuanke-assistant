import { useEffect, useMemo, useState } from 'react'
import { Button, Modal, Radio, Typography, message } from 'antd'
import { ClearOutlined, CloseOutlined, SaveOutlined } from '@ant-design/icons'
import { MAX_PERIOD, WEEKDAY_NAMES } from '../constants'
import {
  BusySlot, FULL_WEEKS, isFullWeeks, MAX_WEEK, normalizeWeeks, occupiedCount,
  WeekRange, weeksToText,
} from '../hooks/useBusySlots'

interface Props {
  open: boolean
  onClose: () => void
  slots: BusySlot[]
  applyCells: (cells: { w: number; p: number }[], weeks: WeekRange[] | null) => void
  setWeeks: (w: number, p: number, weeks: WeekRange[]) => void
  clear: () => void
  persist: () => void
}

/** 网格只排周一~周五 */
const WEEKDAYS = WEEKDAY_NAMES.slice(0, 5)

type DragState = { a: [number, number]; c: [number, number]; unmark: boolean }

/** 格子空闲度：剩余空闲周数（1-16 学期内未被标记覆盖的周）与占用周次描述 */
function cellStat(s?: BusySlot) {
  if (!s) return { marked: false, free: MAX_WEEK, occ: '' }
  return { marked: true, free: MAX_WEEK - occupiedCount(s), occ: weeksToText(s.weeks) }
}

/** 空闲越多越绿，全占满（free=0）为红 */
const lvClass = (free: number) =>
  free <= 0 ? 'busy-lv0' : free <= 3 ? 'busy-lv1' : free <= 7 ? 'busy-lv2' : free <= 11 ? 'busy-lv3' : 'busy-lv4'

/** 标记“已有课/不可用”：拖选格子=标记为全学期；单击格子=选中后右侧配周次；查询与 AI 默认避开 */
export default function BusySlotModal({ open, onClose, slots, applyCells, setWeeks, clear, persist }: Props) {
  const [mode, setMode] = useState<'paint' | 'erase'>('paint')
  const [sel, setSel] = useState<{ w: number; p: number }[]>([])

  // 拖动框选：松开提交。标记模式=仅选中这些格子（周次在右侧配置）；擦除模式=取消标记
  const [drag, setDrag] = useState<DragState | null>(null)
  useEffect(() => {
    if (!drag) return
    const onUp = () => {
      const w1 = Math.min(drag.a[0], drag.c[0]), w2 = Math.max(drag.a[0], drag.c[0])
      const p1 = Math.min(drag.a[1], drag.c[1]), p2 = Math.max(drag.a[1], drag.c[1])
      const cells = []
      for (let w = w1; w <= w2; w++) for (let p = p1; p <= p2; p++) cells.push({ w, p })
      if (drag.unmark) {
        applyCells(cells, null)
        setSel([])
      } else {
        setSel(cells)
      }
      setDrag(null)
    }
    window.addEventListener('mouseup', onUp)
    return () => window.removeEventListener('mouseup', onUp)
  }, [drag, applyCells])

  const previewClass = (w: number, p: number) => {
    if (!drag) return ''
    const inRect = w >= Math.min(drag.a[0], drag.c[0]) && w <= Math.max(drag.a[0], drag.c[0])
      && p >= Math.min(drag.a[1], drag.c[1]) && p <= Math.max(drag.a[1], drag.c[1])
    return inRect ? (drag.unmark ? ' drag-off' : ' drag') : ''
  }

  // 右侧周次面板：编辑当前选中的格子（可多个）
  const selKeys = useMemo(() => new Set(sel.map(s => `${s.w}-${s.p}`)), [sel])
  const selSlots = useMemo(
    () => sel.map(({ w, p }) => slots.find(s => s.w === w && s.p === p)).filter(Boolean) as BusySlot[],
    [sel, slots])
  const uniform = useMemo(() => {
    if (!selSlots.length) return false
    const texts = selSlots.map(s => weeksToText(s.weeks))
    return texts.every(t => t === texts[0])
  }, [selSlots])
  const checked = useMemo(() => {
    const set = new Set<number>()
    if (selSlots.length && uniform)
      for (const [a, b] of selSlots[0].weeks) for (let w = a; w <= b; w++) set.add(w)
    return set
  }, [selSlots, uniform])

  const selDesc = sel.length === 0 ? '未选择时段'
    : sel.length === 1 ? `${WEEKDAY_NAMES[sel[0].w - 1]}第${sel[0].p}节`
    : (() => {
        const days = [...new Set(sel.map(s => s.w))]
        const ps = sel.map(s => s.p).sort((a, b) => a - b)
        const dayTxt = days.length === 1 ? WEEKDAY_NAMES[days[0] - 1] : `${days.length} 天`
        return `${dayTxt} 第${ps.length > 1 ? `${ps[0]}-${ps[ps.length - 1]}` : ps[0]}节`
      })()

  /** 把周次集合应用到所有选中格子：无标记的创建，已有标记的覆盖；空集合=删除标记 */
  const applyWeeks = (weeks: WeekRange[]) => {
    if (!sel.length) return
    if (!weeks.length) { applyCells(sel, null); return }
    for (const { w, p } of sel) {
      if (slots.some(s => s.w === w && s.p === p)) setWeeks(w, p, weeks)
      else applyCells([{ w, p }], weeks)
    }
  }

  const onToggleWeek = (wk: number) => {
    const next = new Set(checked)
    if (next.has(wk)) next.delete(wk); else next.add(wk)
    applyWeeks(normalizeWeeks([...next].map(w => [w, w] as WeekRange)))
  }

  return (
    <Modal title="我的已占时段" open={open} onCancel={onClose} width={740} centered className="busy-modal"
      footer={[
        <Button key="clear" icon={<ClearOutlined />} onClick={clear}>清空</Button>,
        <Button key="save" icon={<SaveOutlined />} onClick={() => { persist(); message.success('已保存') }}>保存</Button>,
        <Button key="ok" type="primary" onClick={onClose}>完成</Button>,
      ]}>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12.5, marginBottom: 8 }}>
        <strong>单击或拖选</strong>左侧格子选中时段（可跨格多选），然后在右侧勾选适用周次：默认一周不选，点
        <strong>「全学期」</strong>全选，也可只勾第 2、6、8、10 周这类散周——所选周次对整组选中的格子生效；全部取消即删除标记。
        「擦除」模式点击/拖选取消标记。之后手动查询和 AI 对话都会默认避开：课程周次与标记不重叠的不会被剔除。
      </Typography.Paragraph>
      <div style={{ display: 'flex', gap: 14 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: 12.5 }}>
            <span style={{ color: '#5a626b' }}>操作：</span>
            <Radio.Group size="small" value={mode} onChange={e => setMode(e.target.value)}>
              <Radio.Button value="paint">标记</Radio.Button>
              <Radio.Button value="erase">擦除</Radio.Button>
            </Radio.Group>
          </div>
          <div className="busy-grid">
            <div className="busy-head">节次 \ 星期</div>
            {WEEKDAYS.map(d => <div key={d} className="busy-head">{d}</div>)}
            {Array.from({ length: MAX_PERIOD }, (_, i) => i + 1).map(p => (
              <div style={{ display: 'contents' }} key={p}>
                <div className="busy-rowlabel">第{p}节</div>
                {WEEKDAYS.map((_, wi) => {
                  const w = wi + 1
                  const slot = slots.find(s => s.w === w && s.p === p)
                  const st = cellStat(slot)
                  return (
                    <div key={wi}
                      title={`${WEEKDAY_NAMES[wi]} 第${p}节` +
                        (st.marked ? ` · 占 ${st.occ} 周 · 剩余空闲 ${st.free} 周（单击选中改周次）` : ' · 未标记，单击选中后右侧配周次')}
                      className={`busy-cell${st.marked ? ' ' + lvClass(st.free) : ''}${previewClass(w, p)}${selKeys.has(`${w}-${p}`) ? ' sel' : ''}`}
                      onMouseDown={e => {
                        e.preventDefault()
                        setDrag({ a: [w, p], c: [w, p], unmark: mode === 'erase' })
                      }}
                      onMouseEnter={() => drag && setDrag({ ...drag, c: [w, p] })} />
                  )
                })}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 11.5, color: '#8a939f', flexWrap: 'wrap' }}>
            <span>颜色 = 剩余空闲周数：</span>
            {([['busy-lv0', '0（全占满）'], ['busy-lv1', '1-3'], ['busy-lv2', '4-7'],
              ['busy-lv3', '8-11'], ['busy-lv4', '12-15'], ['', '16（全空闲）']] as const).map(([c, t]) => (
              <span key={t} style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                <i className={`busy-legend ${c}`} style={c === '' ? { background: '#fff' } : undefined} />{t}
              </span>
            ))}
          </div>
        </div>
        <div style={{ width: 208, flexShrink: 0, borderLeft: '1px solid #eef0f2', paddingLeft: 14 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 4 }}>周次设置</div>
          <div style={{ fontSize: 12, color: '#5a626b', marginBottom: 8, minHeight: 18 }}>{selDesc}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Button size="small" disabled={!sel.length || mode === 'erase'}
              onClick={() => applyWeeks(FULL_WEEKS)}>全学期</Button>
            <span style={{ fontSize: 12, color: '#8a939f' }}>
              {checked.size ? `已选 ${checked.size} 周` : '未选周次'}
            </span>
          </div>
          <div className="wk-grid"
            style={{ pointerEvents: mode === 'erase' ? 'none' : 'auto', opacity: mode === 'erase' ? 0.45 : 1 }}>
            {Array.from({ length: MAX_WEEK }, (_, i) => i + 1).map(wk => (
              <div key={wk} title={`第${wk}周`}
                className={`wk-chip${checked.has(wk) ? ' on' : ''}`}
                onMouseDown={e => { e.preventDefault(); if (sel.length) onToggleWeek(wk) }}>
                {wk}
              </div>
            ))}
          </div>
          <div style={{ marginTop: 8, fontSize: 11.5, color: '#8a939f' }}>
            {mode === 'erase' ? '擦除模式下不可编辑周次'
              : sel.length === 0 ? '先单击或拖选左侧格子'
              : uniform ? '勾选 = 该时段第几周有课；全部取消即删除标记'
              : '所选时段周次不一致，勾选将统一覆盖'}
          </div>
          <div style={{ marginTop: 12, fontSize: 11.5, color: '#8a939f' }}>
            已标记 <b>{slots.length}</b> 个时段，× 可删除单条
          </div>
          {slots.length > 0 && (
            <div style={{ maxHeight: 140, overflowY: 'auto', marginTop: 4 }}>
              {slots.map(s => {
                const key = `${s.w}-${s.p}`
                const free = cellStat(s).free
                return (
                  <div key={key} title="点击选中，在上方编辑周次"
                    style={{
                      display: 'flex', alignItems: 'center', gap: 8, padding: '2px 4px', fontSize: 12,
                      borderRadius: 4, cursor: 'pointer',
                      background: selKeys.has(key) ? '#f0f5ff' : undefined,
                    }}
                    onClick={() => setSel([{ w: s.w, p: s.p }])}>
                    <i className={`busy-legend ${lvClass(free)}`} style={{ flexShrink: 0 }} />
                    <span style={{ width: 70 }}>{WEEKDAY_NAMES[s.w - 1]}第{s.p}节</span>
                    <span style={{ flex: 1, fontFamily: 'monospace' }}>{isFullWeeks(s) ? '全学期' : `${weeksToText(s.weeks)}`}</span>
                    <Button type="text" size="small" title="删除这条标记" icon={<CloseOutlined />}
                      style={{ color: '#8a939f', flexShrink: 0 }}
                      onClick={e => { e.stopPropagation(); applyCells([{ w: s.w, p: s.p }], null) }} />
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </Modal>
  )
}
