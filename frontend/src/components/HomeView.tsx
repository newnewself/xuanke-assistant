import { Button, Card, Typography } from 'antd'
import {
  BookOutlined, ClockCircleOutlined, MessageOutlined, PlusSquareOutlined,
} from '@ant-design/icons'
import { LlmConfig, Meta } from '../types'

interface Props {
  meta?: Meta
  hasData: boolean
  config?: LlmConfig
  busyCount: number
  sessionCount: number
  onNewChat: () => void
  onOpenQuery: () => void
  onOpenBusy: () => void
  onOpenGuide: () => void
}

export default function HomeView(p: Props) {
  const quick = [
    { icon: <MessageOutlined />, title: '开始新对话', desc: '用大白话说需求，AI 帮你查课', onClick: p.onNewChat },
    { icon: <PlusSquareOutlined />, title: '新建查询卡', desc: '手动多条件筛选课程', onClick: p.onOpenQuery },
    { icon: <ClockCircleOutlined />, title: '标记已占时段', desc: `已标 ${p.busyCount} 个，查询自动避开`, onClick: p.onOpenBusy },
    { icon: <BookOutlined />, title: '使用说明', desc: '三步上手', onClick: p.onOpenGuide },
  ]

  return (
    <div style={{ padding: '28px 26px', overflowY: 'auto', height: '100%' }}>
      <Typography.Title level={3} style={{ marginTop: 0 }}>你好，我是选课助手</Typography.Title>

      <Typography.Paragraph style={{ fontSize: 13, color: '#4b5563', lineHeight: 1.9, marginBottom: 8 }}>
        你可以用大白话和 AI 对话查课——按上课时间、学分、课程类别、余量等条件筛选，
        自动避开你标记的已占时段；也可以用「新建查询卡」手动多条件筛选。结果都会生成右侧表格，
        支持列头筛选、本表快搜、按余量/时段冲突实时重查，帮你选课前快速摸清可选课程。
      </Typography.Paragraph>
      <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 18 }}>
        ⚠️ AI 生成回复仅供参考
      </Typography.Paragraph>

      {!p.config?.configured && (
        <Card size="small" style={{ marginBottom: 18, borderColor: '#ffd591', background: '#fffbe6' }}>
          <span style={{ fontSize: 13 }}>
            🔑 尚未配置 AI：点「AI 设置」填入 OpenAI 兼容接口（智谱 glm-4-flash 免费），否则对话不可用，查询功能不受影响。
          </span>
        </Card>
      )}

      <div className="quick-grid">
        {quick.map(q => (
          <Card key={q.title} hoverable size="small" className="quick-card" onClick={q.onClick}>
            <div style={{ fontSize: 20 }}>{q.icon}</div>
            <div style={{ fontWeight: 600, margin: '6px 0 2px' }}>{q.title}</div>
            <div style={{ fontSize: 12, color: '#8a939f' }}>{q.desc}</div>
          </Card>
        ))}
      </div>

      {p.hasData && (
        <Button type="primary" size="large" icon={<MessageOutlined />} onClick={p.onNewChat}
          style={{ marginTop: 22 }}>
          开始选课对话
        </Button>
      )}
    </div>
  )
}
