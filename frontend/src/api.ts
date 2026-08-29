import { ChatMsg, ChatSession, HistoryData, LlmConfig, Meta, PanelData, SearchResult, SourceData, ToolTrace } from './types'

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      detail = data.detail || data.message || detail
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json()
}

export const getMeta = () => api<Meta>('/api/meta')
export const getSessions = () => api<ChatSession[]>('/api/sessions')
export const getHistory = (sessionId: string) => api<HistoryData>(`/api/history?session_id=${encodeURIComponent(sessionId)}`)
export const deleteSession = (sessionId: string) =>
  api<{ ok: boolean }>(`/api/sessions/${encodeURIComponent(sessionId)}`, { method: 'DELETE' })
export const getConfig = () => api<LlmConfig>('/api/config')
export const saveConfig = (cfg: { api_key: string }) =>
  api<{ ok: boolean }>('/api/config', { method: 'PUT', body: JSON.stringify(cfg) })
export const testConfig = () => api<{ ok: boolean; message: string }>('/api/config/test', { method: 'POST' })
export const getPanel = (id: number) => api<PanelData>(`/api/panels/${id}`)
export const getSource = () => api<SourceData>('/api/source')
export const searchCourses = (params: Record<string, any>) =>
  api<SearchResult>(`/api/courses?${new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== '' && v !== null),
  ).toString()}`)

/** AI 精选表格（无查询参数）的工具栏过滤：按课号 + 有余量/排除冲突 */
export const filterByIds = (body: { xk_ids: string[]; only_available?: boolean; busy_slots?: string }) =>
  api<SearchResult>('/api/courses/filter', { method: 'POST', body: JSON.stringify(body) })

export interface ChatHandlers {
  onSession: (sessionId: string) => void
  onToken: (delta: string) => void
  onToolStart: (name: string, args: any) => void
  onToolEnd: (trace: ToolTrace) => void
  onPanel: (panel: PanelData) => void
  onError: (code: string, message: string) => void
  onDone: (data: { text?: string; panel_ids?: number[]; tools?: ToolTrace[] }) => void
}

/** POST /api/chat 的 SSE 客户端（EventSource 不支持 POST，手工解析流）；signal 用于用户主动停止 */
export async function streamChat(
  body: { content: string; busy_slots: string[]; session_id: string },
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e: any) {
    if (e?.name === 'AbortError') { handlers.onDone({}); return }
    handlers.onError('', '无法连接服务，请确认后端已启动')
    handlers.onDone({})
    return
  }
  if (!res.ok || !res.body) {
    let detail = `请求失败 (${res.status})`
    try {
      const data = await res.json()
      detail = data.detail || data.message || detail
    } catch { /* ignore */ }
    handlers.onError('', detail)
    handlers.onDone({})
    return
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  let finished = false
  const dispatch = (event: string, d: any) => {
      switch (event) {
        case 'session': handlers.onSession(d.session_id ?? ''); break
        case 'token': handlers.onToken(d.delta ?? ''); break
      case 'tool_start': handlers.onToolStart(d.name, d.args); break
      case 'tool_end': handlers.onToolEnd(d); break
      case 'panel': handlers.onPanel({ id: d.id, title: d.title, rows: d.rows, total: d.total,
        query: d.query, avoid_busy: d.avoid_busy }); break
      case 'error': handlers.onError(d.code ?? '', d.message ?? ''); break
      case 'done': finished = true; handlers.onDone(d ?? {}); break
    }
  }
  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const block = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        let event = 'message'
        let data = ''
        for (const line of block.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (!data) continue
        try {
          dispatch(event, JSON.parse(data))
        } catch { /* 跳过坏块 */ }
      }
    }
  } catch (e: any) {
    // 用户主动停止：静默收尾；其他读流异常也按结束处理，避免未处理 rejection
    if (e?.name !== 'AbortError') console.warn('流读取中断:', e)
  }
  if (!finished) handlers.onDone({})
}
