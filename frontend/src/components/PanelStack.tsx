import { useEffect, useRef, useState } from 'react'
import { Tabs } from 'antd'
import { PanelData } from '../types'
import { BusySlot } from '../hooks/useBusySlots'
import { FavoritesApi } from '../hooks/useFavorites'
import CourseTableCard from './CourseTableCard'

interface Props {
  panels: PanelData[]
  onClose: (index: number) => void
  busySlots: BusySlot[]
  customCategories?: string[]
  favorites?: FavoritesApi
  onOpenFavorites?: (ids?: string[]) => void
}

const keyOf = (p: PanelData) => p.localKey ?? (p.id != null ? `db-${p.id}` : `lk-${p.title}`)

/** 右侧结果表格区：多张表格以标签页形式并存，类似浏览器标签 */
export default function PanelStack({ panels, onClose, busySlots, customCategories, favorites, onOpenFavorites }: Props) {
  const [active, setActive] = useState<string>()
  const prevKeysRef = useRef<string[]>([])
  const keys = panels.map(keyOf)

  // 新表头插进来自动切到新标签；当前标签被关掉时切到第一张
  useEffect(() => {
    const prev = prevKeysRef.current
    const newest = keys[0]
    if (!panels.length) setActive(undefined)
    else if (!active || !keys.includes(active) || (newest && !prev.includes(newest))) setActive(newest)
    prevKeysRef.current = keys
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keys.join('|')])

  return (
    <div className="panel-tabs">
      <Tabs
        type="editable-card"
        hideAdd
        activeKey={active}
        onChange={setActive}
        onEdit={(e, action) => {
          if (action === 'remove') onClose(panels.findIndex(p => keyOf(p) === String(e)))
        }}
        items={panels.map((p, i) => ({
          key: keys[i],
          label: <span className="panel-tab-label" title={p.title}>{p.title}</span>,
          children: <CourseTableCard panel={p} busySlots={busySlots}
            customCategories={customCategories} favorites={favorites} onOpenFavorites={onOpenFavorites} />,
        }))}
      />
    </div>
  )
}
