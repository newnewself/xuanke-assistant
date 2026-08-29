import { useEffect, useMemo, useState, type Key } from 'react'
import { Button, Checkbox, Col, Dropdown, Input, Row, Space, Switch, Table, Tag, Tooltip, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { SettingOutlined, StarFilled, StarOutlined } from '@ant-design/icons'
import { CourseRow, PanelData } from '../types'
import { FIELD_DEFS, WEEKDAY_NAMES } from '../constants'
import { filterByIds, searchCourses } from '../api'
import { BusySlot, busySlotsToParam } from '../hooks/useBusySlots'
import { FavoritesApi } from '../hooks/useFavorites'

interface Props {
  panel: PanelData
  busySlots: BusySlot[]
  /** 自定义课程类别（体育课/形策/大英…）：并入"课程类别"列筛选，即使本表暂无对应课程 */
  customCategories?: string[]
  /** 收藏（勾选行 → 收藏/移出；已收藏行高亮） */
  favorites?: FavoritesApi
  /** 重开/刷新「我的收藏」标签页；移出收藏后传剩余 id，避免读到旧列表 */
  onOpenFavorites?: (ids?: string[]) => void
}

const natureColor: Record<string, string> = { 公选: 'purple', 必修: 'blue', 选修: 'green' }

function RemainingTag({ v }: { v: number }) {
  const color = v <= 0 ? 'red' : v < 10 ? 'orange' : 'green'
  return <Tag color={color} style={{ marginInlineEnd: 0 }}>{v > 0 ? v : v}</Tag>
}

/** 标签页内的表格内容：工具行 + 虚拟滚动表格（无卡片外壳，开闭由外层 Tabs 管理） */
export default function CourseTableCard({ panel, busySlots, customCategories, favorites, onOpenFavorites }: Props) {
  const [custom, setCustom] = useState<string[] | null>(null)
  const [customOpen, setCustomOpen] = useState(false)
  const [quick, setQuick] = useState('')
  // 工具栏开关：有余量 / 排除冲突。带查询参数的表重查；AI 精选表按课号走服务端过滤
  const [onlyAvail, setOnlyAvail] = useState(!!panel.query?.only_available)
  const [avoid, setAvoid] = useState(!!panel.avoid_busy)
  const [live, setLive] = useState<{ rows: CourseRow[]; total: number; busyRemoved: number } | null>(null)
  const [rerunLoading, setRerunLoading] = useState(false)
  const [selKeys, setSelKeys] = useState<Key[]>([])   // 勾选行，用于收藏/移出收藏

  // 表格体高度跟随窗口（表头固定，表体虚拟滚动）
  const [tableH, setTableH] = useState(420)
  useEffect(() => {
    const onResize = () => setTableH(Math.max(260, window.innerHeight - 360))
    onResize()
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const rows = useMemo(() => {
    const base = live?.rows ?? panel.rows
    if (!quick.trim()) return base
    const k = quick.trim().toLowerCase()
    return base.filter(r =>
      [r.course_name, r.teachers, r.college, r.rooms, r.xk_id, r.course_no, r.sessions_brief]
        .some(v => String(v ?? '').toLowerCase().includes(k)))
  }, [panel.rows, live, quick])

  // 镜像 antd 表头筛选状态，用于工具栏“当前显示”计数（含表头筛选后的行数）
  const [colFilters, setColFilters] = useState<Record<string, any[] | null>>({})
  const shownCount = useMemo(() => {
    let arr = rows
    for (const [key, vals] of Object.entries(colFilters)) {
      if (!vals || !vals.length) continue
      if (key === 'sessions_brief') {
        // 上课时间筛选按“周几”包含匹配（brief 是组合文本，精确值匹配无意义）
        arr = arr.filter(r => vals.some(v => String(r.sessions_brief ?? '').includes(String(v))))
        continue
      }
      arr = arr.filter(r => vals.includes(String(r[key] ?? '')))
    }
    return arr.length
  }, [rows, colFilters])

  const rerun = async (nextOnly: boolean, nextAvoid: boolean) => {
    setSelKeys([])   // 行集合即将变化，清掉勾选避免残留已不存在的课
    if (panel.query) {
      const res = await searchCourses({
        limit: 0, ...panel.query,
        only_available: nextOnly, avoid_busy: nextAvoid,
        ...(nextAvoid && busySlots.length ? { busy_slots: busySlotsToParam(busySlots) } : {}),
      })
      setLive({ rows: res.rows, total: res.total, busyRemoved: res.busy_removed ?? 0 })
    } else {
      if (!nextOnly && !nextAvoid) {   // 双开关全关：还原 AI 推送时的原表
        setLive(null)
        return
      }
      const res = await filterByIds({
        xk_ids: panel.rows.map(r => r.xk_id),
        only_available: nextOnly,
        ...(nextAvoid && busySlots.length ? { busy_slots: busySlotsToParam(busySlots) } : {}),
      })
      setLive({ rows: res.rows, total: panel.rows.length, busyRemoved: 0 })
    }
  }

  const onOnlyChange = async (next: boolean) => {
    setOnlyAvail(next)
    setRerunLoading(true)
    try { await rerun(next, avoid) } catch (e: any) {
      message.error(String(e.message || e))
      setOnlyAvail(!next)
    } finally { setRerunLoading(false) }
  }

  const onAvoidChange = async (next: boolean) => {
    setAvoid(next)
    setRerunLoading(true)
    try { await rerun(onlyAvail, next) } catch (e: any) {
      message.error(String(e.message || e))
      setAvoid(!next)
    } finally { setRerunLoading(false) }
  }

  // 勾选列显式加宽：默认 32px 在 small 表格下会把复选框裁掉一圈
  const rowSelection = { selectedRowKeys: selKeys, onChange: (keys: Key[]) => setSelKeys(keys), columnWidth: 44 }

  const onAddFav = () => {
    if (!favorites || !selKeys.length) return
    const added = favorites.add(selKeys.map(String))
    setSelKeys([])
    message.success(added ? `已收藏 ${added} 门，可在左侧「我的收藏」查看` : '勾选的课程都已在收藏中')
  }

  const onRemoveFav = () => {
    if (!favorites || !selKeys.length) return
    const removed = selKeys.map(String)
    favorites.remove(removed)
    setSelKeys([])
    // 显式传剩余 id 重开收藏页，避免拿到移除前的旧列表
    onOpenFavorites?.(favorites.ids.filter(x => !removed.includes(x)))
  }

  const visibleDefs = useMemo(() => {
    if (custom) return FIELD_DEFS.filter(d => custom.includes(d.key as string))
    return FIELD_DEFS.filter(d => d.main)
  }, [custom])

  const columns: ColumnsType<CourseRow> = useMemo(() => visibleDefs.map(def => {
    const col: any = {
      title: def.title, dataIndex: def.key, key: def.key, width: def.width,
      ellipsis: !def.render, fixed: def.key === 'course_no' || def.key === 'course_name' ? ('left' as const) : undefined,
    }
    if (def.filter) {
      if (def.key === 'sessions_brief') {
        // 上课时间列：时间段组合太多，按“周几”包含匹配（勾选多天=任一命中）
        col.filters = WEEKDAY_NAMES.map(w => ({ text: w, value: w }))
        col.onFilter = (v: any, row: any) => String(row.sessions_brief ?? '').includes(String(v))
        return col
      }
      // 选项取自当前实际显示的行：开关重查/快搜后选项随数据收敛，不再出现筛不出的值
      const vals = Array.from(new Set(rows.map(r => String(r[def.key] ?? '')))).filter(Boolean)
      // 课程类别列：并入自定义类别名（暂未关联课程时也保持可见）
      if (def.key === 'course_category') {
        for (const c of customCategories ?? []) if (!vals.includes(c)) vals.push(c)
      }
      let options: string[]
      if (def.key === 'remaining') {
        // 余量按数值升序列出，不限 30 个（筛选时配搜索场景少，数值个数可控）
        options = vals.map(Number).filter(n => !Number.isNaN(n)).sort((a, b) => a - b).map(String)
      } else if (def.key === 'course_no') {
        // 课程号同余量不限量（同号多班次，按课筛班），升序 + 下拉可搜索便于长列表定位
        options = vals.sort((a, b) => a.localeCompare(b, 'zh', { numeric: true }))
      } else if (def.filterSearch) {
        // 课程名称/教师：值多但下拉可搜索，放宽截断到 300
        options = vals.sort((a, b) => a.localeCompare(b, 'zh')).slice(0, 300)
      } else {
        options = vals.sort((a, b) => a.localeCompare(b, 'zh')).slice(0, 30)
      }
      col.filters = options.map(v => ({ text: v, value: v }))
      col.onFilter = (v: any, row: any) => String(row[def.key] ?? '') === v
      if (def.filterSearch) col.filterSearch = true
    }
    if (def.render === 'remaining') col.render = (v: number) => <RemainingTag v={v} />
    if (def.render === 'credit') col.render = (v: number) => <b>{v}</b>
    if (def.render === 'nature') col.render = (v: string) =>
      <Tag bordered={false} color={natureColor[v] || 'default'} style={{ marginInlineEnd: 0 }}>{v}</Tag>
    return col
  }), [visibleDefs, rows, customCategories])

  return (
    <>
      <div className="panel-card-tools">
        <Input size="small" allowClear prefix="🔍" placeholder="本表内快搜" style={{ width: 170 }}
          value={quick} onChange={e => setQuick(e.target.value)} />
        <Dropdown open={customOpen} onOpenChange={setCustomOpen} trigger={['click']} dropdownRender={() => (
          <div style={{ background: '#fff', borderRadius: 8, boxShadow: '0 3px 12px rgba(0,0,0,.15)', padding: 12, width: 460 }}>
            <div style={{ marginBottom: 6, fontSize: 12, color: '#8a939f', display: 'flex', alignItems: 'center' }}>
              <span>自定义显示列</span>
              <Space size={10} style={{ marginLeft: 'auto' }}>
                <Button size="small" type="link" style={{ padding: 0, height: 'auto' }}
                  onClick={() => setCustom(FIELD_DEFS.map(d => d.key as string))}>全选</Button>
                <Button size="small" type="link" style={{ padding: 0, height: 'auto' }}
                  onClick={() => setCustom(null)}>恢复默认</Button>
              </Space>
            </div>
            <Checkbox.Group
              value={(custom ?? FIELD_DEFS.filter(d => d.main).map(d => d.key as string)) as any}
              onChange={vals => setCustom((vals as string[]).length ? vals as string[] : null)}
              style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 320, overflow: 'auto' }}
            >
              <Row gutter={[0, 4]}>
                {FIELD_DEFS.map(d => (
                  <Col key={d.key} span={8}><Checkbox value={d.key as string}>{d.title}</Checkbox></Col>
                ))}
              </Row>
            </Checkbox.Group>
          </div>
        )}>
          <Button size="small" icon={<SettingOutlined />}>列设置</Button>
        </Dropdown>
        <Tooltip title="只看余量 > 0 的教学班">
          <Space size={4}>
            <Switch size="small" checked={onlyAvail} loading={rerunLoading} onChange={onOnlyChange} />
            <span style={{ fontSize: 12, color: '#8a939f' }}>有余量</span>
          </Space>
        </Tooltip>
        <Tooltip title="剔除与已标记的已占时段（含周次限制）冲突的课；关闭则显示全部">
          <Space size={4}>
            <Switch size="small" checked={avoid} loading={rerunLoading} onChange={onAvoidChange} />
            <span style={{ fontSize: 12, color: '#8a939f' }}>避开已占时段</span>
          </Space>
        </Tooltip>
        {panel.kind === 'favorites' ? (
          <Tooltip title="把勾选的课从收藏中移除">
            <Button size="small" icon={<StarFilled style={{ color: '#faad14' }} />} disabled={!selKeys.length}
              onClick={onRemoveFav}>移出收藏{selKeys.length ? `（${selKeys.length}）` : ''}</Button>
          </Tooltip>
        ) : (
          <Tooltip title="把勾选的课加入「我的收藏」，方便跟踪备选">
            <Button size="small" icon={<StarOutlined />} disabled={!selKeys.length}
              onClick={onAddFav}>收藏{selKeys.length ? `（${selKeys.length}）` : ''}</Button>
          </Tooltip>
        )}
        <span style={{ fontSize: 12, color: '#8a939f', marginLeft: 'auto' }}>
          当前显示 {shownCount} / {live?.total ?? panel.total} 门
          {avoid && live && live.busyRemoved > 0 ? `（已剔除 ${live.busyRemoved} 门冲突）` : ''}
        </span>
      </div>
      <Table<CourseRow>
        size="small"
        rowKey="xk_id"
        virtual
        rowSelection={rowSelection}
        rowClassName={r => (favorites?.has(r.xk_id) ? 'row-fav' : '')}
        columns={columns}
        dataSource={rows}
        scroll={{ x: visibleDefs.reduce((s, d) => s + (d.width || 120), 0), y: tableH }}
        pagination={false}
        onChange={(_pg, filters) => setColFilters(filters as Record<string, any[] | null>)}
      />
    </>
  )
}
