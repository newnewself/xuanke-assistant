import { useMemo, useState } from 'react'
import { Checkbox, Form, Input, Modal, Select, Switch, Button, Space, message } from 'antd'
import { Meta, PanelData } from '../types'
import { MAX_PERIOD, WEEKDAY_NAMES } from '../constants'
import { searchCourses } from '../api'
import { BusySlot, busySlotsToParam } from '../hooks/useBusySlots'

interface Props {
  open: boolean
  onClose: () => void
  meta?: Meta
  onPush: (p: PanelData) => void
  busySlots: BusySlot[]
}

interface FormValues {
  course_name?: string; course_no?: string; course_category?: string; course_attribution?: string
  weekdays?: number[]; periods?: number[]
  only_available?: boolean; avoid_busy?: boolean
}

export default function QueryModal({ open, onClose, meta, onPush, busySlots }: Props) {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)

  // 课程类别候选：教务类别 ∪ 自定义类别（自定义类别可能尚未关联任何课程，也保持可见）
  const categoryOptions = useMemo(() => {
    const set = new Set([...(meta?.course_categories || []), ...(meta?.custom_categories || [])])
    return Array.from(set).sort().map(c => ({ value: c }))
  }, [meta])
  const attributionOptions = useMemo(
    () => (meta?.course_attributions || []).map(c => ({ value: c })), [meta])

  const onRun = async () => {
    const v: FormValues = await form.validateFields()
    setLoading(true)
    try {
      // 多选的周几/节次转成逗号串传给后端；query 里存同样的串，表格工具栏重查时原样带回
      const query = {
        ...v,
        weekdays: v.weekdays?.length ? v.weekdays.join(',') : undefined,
        periods: v.periods?.length ? v.periods.join(',') : undefined,
      }
      const res = await searchCourses({
        limit: 0, ...query,
        // avoid_busy 之前只传了开关没传时段数据，后端无从剔除；这里补齐（含周次限制）
        ...(v.avoid_busy && busySlots.length ? { busy_slots: busySlotsToParam(busySlots) } : {}),
      })
      const parts: string[] = []
      if (v.course_name) parts.push(`“${v.course_name}”`)
      if (v.course_no) parts.push(v.course_no)
      if (v.course_category) parts.push(v.course_category)
      if (v.course_attribution) parts.push(v.course_attribution)
      if (v.weekdays?.length) parts.push(v.weekdays.map(d => WEEKDAY_NAMES[d - 1] ?? `周${d}`).join('/'))
      if (v.periods?.length) parts.push(`${v.periods.join(',')}节`)
      if (v.only_available) parts.push('有余量')
      const title = `${parts.join(' · ') || '全部课程'}（${res.total} 门）`
      // 带上查询参数与避开开关初始态：表格工具栏可切换"避开已占时段"重查
      onPush({ title: title.length > 60 ? title.slice(0, 57) + '…' : title,
        rows: res.rows, total: res.total, query, avoid_busy: !!v.avoid_busy })
      onClose()
    } catch (e: any) {
      message.error(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal title="新建查询卡" open={open} onCancel={onClose} width={520}
      footer={[
        <Button key="reset" onClick={() => form.resetFields()}>重置</Button>,
        <Button key="run" type="primary" loading={loading} onClick={onRun}>查询并生成表格</Button>,
      ]}>
      <Form form={form} layout="vertical"
        initialValues={{ only_available: true, avoid_busy: true }}>
        <Space wrap size={12} style={{ display: 'flex' }}>
          <Form.Item name="course_name" label="课程名称" style={{ width: 220 }}>
            <Input placeholder="课程名称，支持模糊" allowClear />
          </Form.Item>
          <Form.Item name="course_no" label="课程号" style={{ width: 160 }}>
            <Input placeholder="课程号，支持模糊" allowClear />
          </Form.Item>
          <Form.Item name="course_category" label="课程类别" style={{ width: 160 }}>
            <Select options={categoryOptions} allowClear showSearch placeholder="不限" />
          </Form.Item>
          <Form.Item name="course_attribution" label="课程归属" style={{ width: 160 }}>
            <Select options={attributionOptions} allowClear showSearch placeholder="不限" />
          </Form.Item>
        </Space>
        <Form.Item name="weekdays" label="周几（可多选；不勾=不限）" style={{ marginBottom: 10 }}>
          <Checkbox.Group options={WEEKDAY_NAMES.map((label, i) => ({ label, value: i + 1 }))} />
        </Form.Item>
        <Form.Item name="periods" label={`上课节数（可多选；每天共 ${MAX_PERIOD} 节，不勾=不限）`}
          style={{ marginBottom: 16 }}>
          <Checkbox.Group options={Array.from({ length: MAX_PERIOD }, (_, i) => ({ label: `${i + 1}节`, value: i + 1 }))} />
        </Form.Item>
        <Space size={24}>
          <Form.Item name="only_available" label="仅看有余量" valuePropName="checked" style={{ marginBottom: 0 }}>
            <Switch />
          </Form.Item>
          <Form.Item name="avoid_busy" label={`避开我标记的已占时段${busySlots.length ? `（${busySlots.length} 个）` : ''}`} valuePropName="checked" style={{ marginBottom: 0 }}>
            <Switch />
          </Form.Item>
        </Space>
      </Form>
    </Modal>
  )
}
