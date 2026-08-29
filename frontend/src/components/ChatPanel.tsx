import { memo, useCallback, useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Input, Popconfirm, Tag, Tooltip, message } from 'antd'
import { ClearOutlined, SendOutlined, StopOutlined } from '@ant-design/icons'
import Markdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { ChatMsg, PanelData, ToolTrace } from '../types'
import { deleteSession, getHistory, getPanel, streamChat } from '../api'
import { SUGGESTIONS } from '../constants'
import { BusySlot, busySlotsToStrings } from '../hooks/useBusySlots'

const TOOL_ICON: Record<string, string> = {
  search_courses: '🔍',
  get_course_detail: '📄',
  present_table: '📋',
}
const TOOL_NAME: Record<string, string> = {
  search_courses: '查询课程库',
  get_course_detail: '课程详情',
  present_table: '推送表格',
}

// token 合并刷新间隔：流式输出时无需逐字 setState，80ms 足够流畅且大幅减少重渲染
const TOKEN_FLUSH_MS = 80

const mdComponents = {
  a: ({ node: _n, ...props }: any) => <a {...props} target="_blank" rel="noopener noreferrer" />,
}

interface BubbleProps {
  m: ChatMsg
  onOpenPanel: (id: number) => void
}

/** 思考计时器：显示已用时长直到首个字输出；自带秒级 interval，不随消息流式刷新重渲染 */
const ThinkTimer = memo(function ThinkTimer() {
  const [sec, setSec] = useState(0)
  useEffect(() => {
    const t = window.setInterval(() => setSec(s => s + 1), 1000)
    return () => window.clearInterval(t)
  }, [])
  const label = sec < 60 ? `正在思考 ${sec} 秒` : `正在思考 ${Math.floor(sec / 60)} 分 ${sec % 60} 秒`
  return (
    <span className="thinking">
      {label}<span className="thinking-dots">···</span>
      {sec >= 30 && <span>（等待较久，可点右下角「停止」后重发）</span>}
    </span>
  )
})

/** 单条消息气泡：memo 后只有内容变化（通常是正在生成的那条）才会重新解析 Markdown */
const MsgBubble = memo(function MsgBubble({ m, onOpenPanel }: BubbleProps) {
  return (
    <div className={`msg-row ${m.role}`}>
      <div className={`bubble${m.error ? ' error' : ''}`}>
        {m.role === 'assistant' && (m.tools?.length || m.meta?.tools?.length) ? (
          <div className="tool-chips">
            {((m.tools?.length ? m.tools : (m.meta?.tools || [])) as { name: string; summary?: string; pending?: boolean }[]).map((t, j) => (
              <Tag key={j} bordered={false} color={t.pending ? 'processing' : 'default'}>
                {TOOL_ICON[t.name] || '🔧'} {TOOL_NAME[t.name] || t.name}
                {t.summary ? `：${t.summary}` : t.pending ? '…' : ''}
              </Tag>
            ))}
          </div>
        ) : null}
        {m.role === 'assistant' && m.streaming && !m.content ? (
          <ThinkTimer />
        ) : m.role === 'assistant' && !m.error ? (
          <>
            <Markdown remarkPlugins={[remarkBreaks, remarkGfm]} components={mdComponents}>{m.content}</Markdown>
            {m.streaming && <span>▍</span>}
          </>
        ) : (
          <>
            {m.content}
            {m.streaming && <span>▍</span>}
          </>
        )}
        {m.role === 'assistant' && !!m.meta?.panel_ids?.length && (
          <div className="panel-btns">
            {m.meta.panel_ids.map(id => (
              <Tooltip key={id} title="在右侧结果区打开这张表">
                <Button size="small" onClick={() => onOpenPanel(id)}>📋 在右侧查看</Button>
              </Tooltip>
            ))}
          </div>
        )}
      </div>
    </div>
  )
})

interface Props {
  sessionId: string
  busySlots: BusySlot[]
  onPanel: (p: PanelData) => void
  onNeedSettings: () => void
  onSessionCreated: (sid: string) => void
  onSessionDeleted: () => void
}

export default function ChatPanel({
  sessionId, busySlots, onPanel, onNeedSettings, onSessionCreated, onSessionDeleted,
}: Props) {
  // 每个会话一份本地消息缓冲：流式输出只写"发起那次对话"的缓冲，
  // 切换会话时立即显示目标会话，正在进行的流不会串到界面上
  const msgsMapRef = useRef<Map<string, ChatMsg[]>>(new Map())
  const [msgs, setMsgs] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [limitNoticeClosed, setLimitNoticeClosed] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const sessionIdRef = useRef(sessionId)
  const streamSidRef = useRef('')            // 当前进行中的流所属会话
  const pendingDeltaRef = useRef('')         // 待刷新的增量文本
  const flushTimerRef = useRef<number | null>(null)
  const doneAtRef = useRef(0)                // 流结束时间，用于只认结束后的服务端历史
  const abortRef = useRef<AbortController | null>(null)  // 进行中流的停止控制器
  const qc = useQueryClient()

  const { data: history, dataUpdatedAt: historyUpdatedAt } = useQuery({
    queryKey: ['history', sessionId],
    queryFn: () => getHistory(sessionId),
    enabled: !!sessionId,
  })

  // 切换会话：立即显示该会话的本地缓冲（无则空），服务端历史由下方效果回灌
  useEffect(() => {
    sessionIdRef.current = sessionId
    setLimitNoticeClosed(false)
    setMsgs(msgsMapRef.current.get(sessionId) ?? [])
  }, [sessionId])

  useEffect(() => {
    if (!sessionId || !history) return
    // 数据形状异常（如后端未重启、新旧版本不匹配）时跳过回灌，避免整页白屏
    const list = history.messages
    if (!Array.isArray(list)) return
    // 正在直播的会话不回灌（避免覆盖本地流式内容）
    if (sessionId === streamSidRef.current && streaming) return
    // 刚结束的会话：服务端历史还是旧缓存时先不回灌，等 invalidate 后的新数据
    if (sessionId === streamSidRef.current && historyUpdatedAt <= doneAtRef.current) return
    msgsMapRef.current.set(sessionId, list)
    setMsgs(list)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [history, sessionId, streaming, historyUpdatedAt])

  useEffect(() => () => {
    if (flushTimerRef.current != null) clearTimeout(flushTimerRef.current)
  }, [])

  // 自动滚动：仅在用户本来就在底部附近时跟随，且用瞬时定位避免平滑动画堆积
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    if (el.scrollHeight - el.scrollTop - el.clientHeight < 120) {
      el.scrollTo({ top: el.scrollHeight })
    }
  }, [msgs])

  /** 修改"进行中流"所属会话的缓冲；若该会话正显示中则同步到界面 */
  const mutateStream = (fn: (arr: ChatMsg[]) => ChatMsg[]) => {
    const sid = streamSidRef.current
    const next = fn(msgsMapRef.current.get(sid) ?? [])
    msgsMapRef.current.set(sid, next)
    if (sid === sessionIdRef.current) setMsgs(next)
  }

  const updateLast = (fn: (m: ChatMsg) => ChatMsg) =>
    mutateStream(arr => {
      const copy = [...arr]
      const last = copy[copy.length - 1]
      if (last && last.role === 'assistant') copy[copy.length - 1] = fn(last)
      return copy
    })

  const flushTokens = () => {
    if (flushTimerRef.current != null) {
      clearTimeout(flushTimerRef.current)
      flushTimerRef.current = null
    }
    const delta = pendingDeltaRef.current
    pendingDeltaRef.current = ''
    if (delta) updateLast(m => ({ ...m, content: m.content + delta }))
  }

  const replacePending = (tools: { name: string; summary?: string; pending?: boolean }[], t: ToolTrace) => {
    const idx = tools.findIndex(x => x.pending)
    if (idx >= 0) {
      const copy = [...tools]
      copy[idx] = { name: t.name, summary: t.summary }
      return copy
    }
    return [...tools, { name: t.name, summary: t.summary }]
  }

  const send = async (text?: string) => {
    const content = (text ?? input).trim()
    if (!content || streaming) return
    setInput('')
    setStreaming(true)
    const ctrl = new AbortController()
    abortRef.current = ctrl
    streamSidRef.current = sessionIdRef.current
    mutateStream(arr => [...arr,
      { role: 'user', content },
      { role: 'assistant', content: '', tools: [], streaming: true }])
    await streamChat({ content, busy_slots: busySlotsToStrings(busySlots), session_id: sessionId }, {
      onSession: sid => {
        // 新对话首条消息：把空会话键下的缓冲搬到正式 sid 下，避免残留
        if (!sessionIdRef.current) {
          const buf = msgsMapRef.current.get('')
          if (buf) { msgsMapRef.current.set(sid, buf); msgsMapRef.current.delete('') }
        }
        streamSidRef.current = sid  // 流归属会话确定后立即同步，否则停止/完成时改不到正确缓冲
        onSessionCreated(sid)
      },
      onToken: d => {
        // 增量先缓冲，按固定节奏合并刷新，避免高频 setState 卡住界面
        pendingDeltaRef.current += d
        if (flushTimerRef.current == null) {
          flushTimerRef.current = window.setTimeout(() => {
            flushTimerRef.current = null
            flushTokens()
          }, TOKEN_FLUSH_MS)
        }
      },
      onToolStart: name => updateLast(m => ({ ...m, tools: [...(m.tools || []), { name, pending: true }] })),
      onToolEnd: t => updateLast(m => ({ ...m, tools: replacePending(m.tools || [], t) })),
      onPanel: p => onPanel(p),
      onError: (code, msg) => {
        updateLast(m => ({ ...m, error: true, content: m.content ? `${m.content}\n\n⚠️ ${msg}` : `⚠️ ${msg}` }))
        if (code === 'no_config') onNeedSettings()
      },
      onDone: () => {
        flushTokens()
        mutateStream(arr => {
          const copy = [...arr]
          const last = copy[copy.length - 1]
          if (last && last.role === 'assistant') {
            const m = { ...last, streaming: false }
            // 空回复（如用户主动停止且无任何输出）：移除占位气泡
            if (!m.content && !m.tools?.length && !m.error) copy.pop()
            else copy[copy.length - 1] = m
          }
          return copy
        })
        setStreaming(false)
        doneAtRef.current = Date.now()
        qc.invalidateQueries({ queryKey: ['history', sessionIdRef.current] })
        qc.invalidateQueries({ queryKey: ['sessions'] })
      },
    }, ctrl.signal)
    abortRef.current = null
    setStreaming(false)
  }

  const onStop = () => abortRef.current?.abort()

  const openPanel = useCallback((id: number) => {
    getPanel(id).then(p => {
      onPanel(p)
      message.success('已在右侧打开表格')
    }).catch(e => message.error(String(e.message || e)))
  }, [onPanel])

  const doClear = async () => {
    if (!sessionId) return
    await deleteSession(sessionId)
    message.success('会话已删除')
    onSessionDeleted()
  }

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', borderBottom: '1px solid #f0f0f0' }}>
        <b style={{ flex: 1 }}>💬 AI 对话</b>
        <Popconfirm title="删除这段对话及其历史？" onConfirm={doClear}
          disabled={!sessionId || streaming} okText="删除" cancelText="取消">
          <Button size="small" type="text" icon={<ClearOutlined />} disabled={!sessionId || streaming}>删除会话</Button>
        </Popconfirm>
      </div>
      {history?.truncated && !limitNoticeClosed && (
        <Alert type="warning" showIcon closable style={{ margin: '8px 14px 0' }}
          message={`本会话已有 ${history.limit} 条消息，更早的内容已不传给 AI，继续聊可能"忘事"。建议点左侧「新建对话」开始新会话。`}
          onClose={() => setLimitNoticeClosed(false)} />
      )}
      <div className="chat-scroll" ref={scrollRef}>
        {msgs.length === 0 && (
          <div style={{ color: '#8a939f', fontSize: 13, padding: '8px 2px' }}>
            说说你的选课需求，我来查课程库。例如：
            <div className="suggests">
              {SUGGESTIONS.map(s => (
                <Button key={s} size="small" style={{ textAlign: 'left', height: 'auto', padding: '4px 10px', whiteSpace: 'normal' }}
                  onClick={() => send(s)}>{s}</Button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <MsgBubble key={i} m={m} onOpenPanel={openPanel} />
        ))}
      </div>
      <div className="chat-input-area">
        <Input.TextArea
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={streaming ? 'AI 正在思考…' : '描述你的选课需求，Enter 发送，Shift+Enter 换行'}
          autoSize={{ minRows: 1, maxRows: 5 }}
          disabled={streaming}
          onPressEnter={e => {
            if (!e.shiftKey) { e.preventDefault(); send() }
          }}
        />
        {streaming ? (
          <Tooltip title="中断本次 AI 响应，之后可重新发送">
            <Button icon={<StopOutlined />} onClick={onStop}>停止</Button>
          </Tooltip>
        ) : (
          <Button type="primary" icon={<SendOutlined />} onClick={() => send()} />
        )}
      </div>
    </>
  )
}
