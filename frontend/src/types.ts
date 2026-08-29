export interface CourseRow {
  xk_id: string
  course_no: string
  course_name: string
  teachers: string
  staff_no?: string
  gender?: string
  credit: number
  nature: string
  course_category?: string
  course_attribution?: string
  time_text: string
  sessions_brief: string
  college: string
  campus: string
  rooms: string
  room_no?: string
  room_type?: string
  room_weeks?: string
  room_periods?: string
  building?: string
  floor?: string
  remaining: number
  plan_size: number
  enrolled: number
  seats: number
  week_hours?: number
  total_hours?: number
  teacher_titles?: string
  teacher_edu?: string
  teacher_college?: string
  teacher_segments?: string
  major_group?: string
  class_group?: string
  year?: string
  term?: string
  [key: string]: any
}

export interface Meta {
  class_count: string
  year: string
  term: string
  imported_at: string
  colleges: string[]
  campuses: string[]
  natures: string[]
  /** 课程类别（教务原始类别 ∪ 导入后落库的自定义类别） */
  course_categories?: string[]
  /** 课程归属 */
  course_attributions?: string[]
  /** 自定义课程类别（体育课/形策/大英…），可能尚未关联任何课程 */
  custom_categories?: string[]
}

export interface SearchResult {
  total: number
  busy_removed?: number
  rows: CourseRow[]
}

export interface PanelData {
  id?: number
  localKey?: string   // 前端标签页用的稳定 key；服务端面板优先用 db-<id>
  title: string
  rows: CourseRow[]
  total: number
  /** 生成该表的查询参数；存在时表格工具栏提供"避开已占时段"开关（重查本表） */
  query?: Record<string, any>
  /** 建表时是否已按已占时段剔除（开关初始态） */
  avoid_busy?: boolean
  /** 面板类型：favorites = 我的收藏（工具栏提供"移出收藏"） */
  kind?: 'favorites'
}

export interface ToolTrace {
  name: string
  summary: string
  args?: Record<string, any>
}

export interface ChatSession {
  session_id: string
  title: string
  count: number
  last_time: string
}

export interface ChatMsg {
  id?: number
  role: 'user' | 'assistant'
  content: string
  meta?: { tools?: ToolTrace[]; panel_ids?: number[] }
  streaming?: boolean
  error?: boolean
  tools?: { name: string; summary?: string; pending?: boolean }[]
}

export interface HistoryData {
  /** 会话消息数已达上限，更早内容不再传给模型 */
  truncated: boolean
  limit: number
  messages: ChatMsg[]
}

export interface LlmConfig {
  configured: boolean
  model: string
  api_key_masked: string
}

export interface SourceData {
  available: boolean
  note?: string
  updated_at?: string
  rows?: number
  cols?: number
  size_bytes?: number
}
