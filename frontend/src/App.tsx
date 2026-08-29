import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Badge, Button, Empty, Menu, message, Space, Tooltip, Typography } from 'antd'
import {
  BookOutlined, BorderOutlined, ClockCircleOutlined, CommentOutlined, FileExcelOutlined,
  HomeOutlined, MessageOutlined, PlusOutlined, SettingOutlined, StarOutlined, SwitcherOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { PanelData } from './types'
import { APP_VERSION, FEEDBACK_URL } from './constants'
import { filterByIds, getConfig, getMeta, getSessions } from './api'
import { useBusySlots } from './hooks/useBusySlots'
import { useFavorites } from './hooks/useFavorites'
import ChatPanel from './components/ChatPanel'
import HomeView from './components/HomeView'
import PanelStack from './components/PanelStack'
import BusySlotModal from './components/BusySlotModal'
import SettingsModal from './components/SettingsModal'
import GuideModal from './components/GuideModal'
import ImportModal from './components/ImportModal'
import QueryModal from './components/QueryModal'
import SourceCard from './components/SourceCard'

export default function App() {
  const qc = useQueryClient()
  const { data: meta } = useQuery({ queryKey: ['meta'], queryFn: getMeta })
  const { data: config } = useQuery({ queryKey: ['config'], queryFn: getConfig })
  const { data: sessions } = useQuery({ queryKey: ['sessions'], queryFn: getSessions })
  const busy = useBusySlots()
  const favorites = useFavorites()

  const [view, setView] = useState<'home' | 'chat' | 'source'>('home')
  const [currentSession, setCurrentSession] = useState('')
  const [panels, setPanels] = useState<PanelData[]>([])
  const [busyOpen, setBusyOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const [queryOpen, setQueryOpen] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  const panelScrollRef = useRef<HTMLDivElement>(null)

  const hasData = !!meta && Number(meta.class_count) > 0

  const pushPanel = useCallback((p: PanelData) => {
    const withKey: PanelData = {
      ...p,
      localKey: p.localKey ?? (p.id != null ? `db-${p.id}` : `lk-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`),
    }
    setPanels(prev => [
      withKey,
      ...prev.filter(x => (x.id != null ? x.id !== withKey.id : x.localKey !== withKey.localKey)),
    ])
    requestAnimationFrame(() => panelScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' }))
  }, [])

  const closePanel = useCallback((index: number) => {
    setPanels(prev => prev.filter((_, i) => i !== index))
  }, [])

  /** 打开/刷新「我的收藏」标签页：按收藏顺序取回最新数据（余量随导入刷新）；
   *  旧收藏页整体替换（新 localKey），保证在别的标签页时也能自动切过去 */
  const openFavorites = useCallback(async (idsOverride?: string[]) => {
    const ids = idsOverride ?? favorites.ids
    if (!ids.length) {
      if (idsOverride) setPanels(prev => prev.filter(p => p.kind !== 'favorites'))
      message.info(idsOverride ? '收藏列表已清空' : '还没有收藏：在右侧表格勾选课程行，点工具栏「收藏」加入')
      return
    }
    try {
      const res = await filterByIds({ xk_ids: ids })
      const missing = ids.length - res.rows.length
      if (missing > 0) message.warning(`${missing} 门收藏未在当前课程数据中找到，已跳过（课程表可能已更新）`)
      setPanels(prev => [
        { localKey: `fav-${Date.now()}`, kind: 'favorites' as const,
          title: `⭐ 我的收藏（${res.rows.length} 门）`, rows: res.rows, total: res.rows.length },
        ...prev.filter(p => p.kind !== 'favorites'),
      ])
      requestAnimationFrame(() => panelScrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' }))
    } catch (e: any) {
      message.error(String(e.message || e))
    }
  }, [favorites.ids])

  const onImported = () => qc.invalidateQueries({ queryKey: ['meta'] })
  const newChat = () => { setCurrentSession(''); setView('chat') }
  const onSessionCreated = (sid: string) => {
    setCurrentSession(sid)
    qc.invalidateQueries({ queryKey: ['sessions'] })
  }
  const onSessionDeleted = () => {
    qc.invalidateQueries({ queryKey: ['sessions'] })
    setView('home')
  }

  const onMenuClick = (key: string) => {
    if (key === 'home') setView('home')
    else if (key === 'new') newChat()
    else if (key.startsWith('s:')) { setCurrentSession(key.slice(2)); setView('chat') }
    else if (key === 'guide') setGuideOpen(true)
    else if (key === 'busy') setBusyOpen(true)
    else if (key === 'favorites') openFavorites()
    else if (key === 'import') setImportOpen(true)
    else if (key === 'query') setQueryOpen(true)
    else if (key === 'source') setView('source')
    else if (key === 'config') setSettingsOpen(true)
    else if (key === 'feedback') window.open(FEEDBACK_URL, '_blank', 'noopener,noreferrer')
  }

  // 全屏表格区时 Esc 退出
  useEffect(() => {
    if (!fullscreen) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setFullscreen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [fullscreen])

  const menuItems = [
    { key: 'home', icon: <HomeOutlined />, label: '首页' },
    {
      key: 'history', icon: <MessageOutlined />, label: '对话历史',
      children: [
        { key: 'new', icon: <PlusOutlined />, label: '新建对话' },
        ...(sessions || []).map(s => ({
          key: 's:' + s.session_id,
          label: (s.title || '未命名对话'),
        })),
      ],
    },
    { key: 'guide', icon: <BookOutlined />, label: '使用说明' },
    { key: 'busy', icon: <ClockCircleOutlined />, label: '已占时段' },
    { key: 'favorites', icon: <StarOutlined />, label: `我的收藏${favorites.ids.length ? `（${favorites.ids.length}）` : ''}` },
    { key: 'source', icon: <FileExcelOutlined />, label: '资料来源' },
    { key: 'feedback', icon: <CommentOutlined />, label: '意见反馈' },
    { key: 'config', icon: <SettingOutlined />, label: 'AI 设置' },
  ]

  const selectedKeys = view === 'home' ? ['home']
    : view === 'source' ? ['source']
    : (currentSession ? ['s:' + currentSession] : ['new'])

  return (
    <div className={`app-shell${fullscreen ? ' fullscreen' : ''}`}>
      <aside className="sidebar">
        <div className="sidebar-title">🎓 选课助手 <span className="ver">{APP_VERSION}</span></div>
        <div className="sidebar-sub">
          {hasData ? `${meta!.year}学年 第${meta!.term}学期` : '未导入课程数据'}
        </div>
        <div className="sidebar-note">适用于第二轮选课开始前做相关准备</div>
        <div className="sidebar-disclaimer">个人开发 仅供参考</div>
        <Menu mode="inline" items={menuItems} onClick={e => onMenuClick(e.key as string)}
          selectedKeys={selectedKeys} defaultOpenKeys={['history']} />
        <div className="sidebar-foot">
          <Badge dot={!config?.configured} size="small">
            <span style={{ fontSize: 12, color: '#8a939f' }}>
              {config?.configured ? 'AI' : 'AI 未配置'}
            </span>
          </Badge>
        </div>
      </aside>

      {view === 'source' ? (
        <div className="source-page">
          <SourceCard />
        </div>
      ) : (
        <>
          <div className="chat-side">
        {view === 'home' ? (
          <HomeView
            meta={meta} hasData={hasData} config={config} busyCount={busy.slots.length}
            sessionCount={sessions?.length || 0}
            onNewChat={newChat}
            onOpenQuery={() => setQueryOpen(true)}
            onOpenBusy={() => setBusyOpen(true)}
            onOpenGuide={() => setGuideOpen(true)}
          />
        ) : (
          <ChatPanel
            sessionId={currentSession}
            busySlots={busy.slots}
            onPanel={pushPanel}
            onNeedSettings={() => setSettingsOpen(true)}
            onSessionCreated={onSessionCreated}
            onSessionDeleted={onSessionDeleted}
          />
        )}
      </div>

      <div className="panel-side">
        <div className="panel-toolbar">
          <b>📋 结果表格</b>
          <span className="app-sub">{panels.length ? `${panels.length} 张表格` : ''}</span>
          <Space style={{ marginLeft: 'auto' }} size={6}>
            <Tooltip title={fullscreen ? '退出全屏（Esc）' : '放大表格区（隐藏侧栏和对话栏，Esc 退出）'}>
              <Button size="small" icon={fullscreen ? <SwitcherOutlined /> : <BorderOutlined />}
                onClick={() => setFullscreen(f => !f)}>
                {fullscreen ? '退出全屏' : ''}
              </Button>
            </Tooltip>
            <Button size="small" icon={<PlusOutlined />} disabled={!hasData}
              onClick={() => setQueryOpen(true)}>新建查询卡</Button>          </Space>
        </div>
        <div className="panel-scroll" ref={panelScrollRef}>
          {!hasData && (
            <div style={{ paddingTop: 70, paddingRight: 14 }}>
              <Empty description={
                <Typography.Text type="secondary">
                  还没有课程数据。<br />导入教务系统导出的《按条件查询课程.xlsx》即可开始。
                </Typography.Text>
              }>
                <Button type="primary" icon={<UploadOutlined />} onClick={() => setImportOpen(true)}>导入课程表</Button>
              </Empty>
            </div>
          )}
          {hasData && panels.length === 0 && (
            <div style={{ paddingTop: 70, paddingRight: 14 }}>
              <Empty description={
                <Typography.Text type="secondary">
                  还没有结果表格。<br />对 AI 说出你的选课需求，或点「新建查询卡」手动筛选。
                </Typography.Text>
              } />
            </div>
          )}
          {hasData && panels.length > 0 && (
            <PanelStack panels={panels} onClose={closePanel} busySlots={busy.slots}
              customCategories={meta?.custom_categories ?? []} favorites={favorites}
              onOpenFavorites={openFavorites} />
          )}
        </div>
      </div>
        </>
      )}

      <BusySlotModal open={busyOpen} onClose={() => setBusyOpen(false)}
        slots={busy.slots} applyCells={busy.applyCells} setWeeks={busy.setWeeks}
        clear={busy.clear} persist={busy.persist} />
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <GuideModal open={guideOpen} onClose={() => setGuideOpen(false)} />
      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} onImported={onImported} />
      <QueryModal open={queryOpen} onClose={() => setQueryOpen(false)} meta={meta} onPush={pushPanel}
        busySlots={busy.slots} />
    </div>
  )
}
