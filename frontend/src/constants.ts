import { CourseRow } from './types'

export const APP_VERSION = 'v1.0'

// 意见反馈表单（腾讯文档），侧栏入口直接新开此链接
export const FEEDBACK_URL = 'https://docs.qq.com/form/page/DSkd2SHJIUG1iZUp0'

export interface FieldDef {
  key: keyof CourseRow
  title: string
  main?: boolean
  width?: number
  render?: 'remaining' | 'credit' | 'nature'
  filter?: boolean
  /** 筛选下拉里带搜索框（课程名称/教师这类值多的列） */
  filterSearch?: boolean
}

/** 列定义：main 为默认展示列，其余在“全部字段”或“列设置”中打开；数组顺序即列顺序 */
export const FIELD_DEFS: FieldDef[] = [
  { key: 'course_no', title: '课程号', main: true, width: 100, filter: true, filterSearch: true },
  { key: 'course_name', title: '课程名称', main: true, width: 170, filter: true, filterSearch: true },
  { key: 'teachers', title: '教师', main: true, width: 110, filter: true, filterSearch: true },
  { key: 'sessions_brief', title: '上课时间', main: true, width: 200 },
  { key: 'credit', title: '学分', main: true, width: 70, render: 'credit', filter: true },
  { key: 'nature', title: '性质', main: true, width: 80, render: 'nature' },
  { key: 'course_category', title: '课程类别', main: true, width: 110, filter: true },
  { key: 'course_attribution', title: '课程归属', main: true, width: 130, filter: true },
  { key: 'remaining', title: '余量', main: true, width: 76, render: 'remaining', filter: true },
  { key: 'plan_size', title: '教学班人数', main: true, width: 100 },
  { key: 'enrolled', title: '选课人数', main: true, width: 90 },
  { key: 'rooms', title: '地点', main: true, width: 120 },
  { key: 'campus', title: '校区', main: true, width: 80, filter: true },
  { key: 'seats', title: '座位数', width: 80 },
  { key: 'college', title: '开课学院', width: 160 },
  { key: 'xk_id', title: '选课课号', width: 190 },
  { key: 'staff_no', title: '教工号', width: 130 },
  { key: 'gender', title: '性别', width: 70 },
  { key: 'room_type', title: '场地类别', width: 110 },
  { key: 'room_weeks', title: '场地上课起始周', width: 150 },
  { key: 'room_periods', title: '场地上课节次', width: 140 },
  { key: 'building', title: '教学楼', width: 120 },
  { key: 'floor', title: '楼层号', width: 80 },
  { key: 'week_hours', title: '周学时', width: 76 },
  { key: 'total_hours', title: '总学时', width: 76 },
  { key: 'teacher_titles', title: '教师职称', width: 140 },
  { key: 'teacher_edu', title: '教师学历', width: 110 },
  { key: 'teacher_college', title: '教师所属学院', width: 160 },
  { key: 'teacher_segments', title: '教师分段', width: 200 },
  { key: 'major_group', title: '专业组成', width: 180 },
  { key: 'class_group', title: '教学班组成', width: 180 },
  { key: 'year', title: '学年', width: 100 },
  { key: 'term', title: '学期', width: 70 },
]

export const WEEKDAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
export const MAX_PERIOD = 12

export const SUGGESTIONS = [
  '帮我找周四6-8节的通识课，要有余量的',
  '列出余量最多的20节通识课，和我的课表不冲突的',
  '音乐与社会、中华诗词之美、恋爱心理学还有余量吗',
]
