import { Modal, Typography } from 'antd'

interface Props { open: boolean; onClose: () => void }

export default function GuideModal({ open, onClose }: Props) {
  const { Title: T } = Typography
  return (
    <Modal title="使用说明" open={open} onCancel={onClose} footer={null} width={760}>
      <div className="guide">
        <T level={5}>🚀 快速上手（三步）</T>
        <ol style={{ fontSize: 13, color: '#4b5563', lineHeight: 2, paddingLeft: 20 }}>
          <li><b>标记已占时段</b>：左侧「已占时段」，把你已经有课/没空的时间点上色，可按周次细分。</li>
          <li><b>配置 AI</b>：左侧「AI 设置」填入 OpenAI 兼容接口的 Base URL / Key / 模型（Base URL 和模型已预填默认值，一般只需填 Key）。不配置也不影响手动查课。</li>
          <li><b>开始使用</b>：首页点「开始选课对话」，左侧「对话历史」可切换/新建会话，右侧自动出现结果表格。</li>
        </ol>

        <T level={5}>🔍 右侧表格卡</T>
        <ul style={{ fontSize: 13, color: '#4b5563', lineHeight: 2 }}>
          <li>默认只显示主要列；用「列设置」勾选查看选课课号、专业组成等全部信息，可「全选」或「恢复默认」。</li>
          <li>顶部快搜框在本表内过滤；课程名称、课程号、教师、学分、课程类别、课程归属、余量、校区等列头带漏斗图标，可勾选筛选（课程号/余量下拉里全量升序列出，支持搜索）。</li>
          <li>工具栏「有余量」「避开已占时段」两个开关会实时重查本表：避开默认开启（按你标记的时段含周次剔除），关闭后显示全部命中，看看被剔除的课有哪些。</li>
          <li>勾选课程行点「收藏」加入备选，左侧「我的收藏」随时查看；已收藏的行浅黄高亮，收藏页内可「移出收藏」。</li>
          <li>可以同时存在多张表格，以标签页并列，点标签上的 × 关闭。</li>
        </ul>

        <T level={5}>🔎 手动查课（不依赖 AI）</T>
        <ul style={{ fontSize: 13, color: '#4b5563', lineHeight: 2 }}>
          <li>点右上角「新建查询卡」：按课程名称 / 课程号 / 课程类别 / 课程归属组合筛选，支持模糊与精确下拉；可同时勾选「仅看有余量」「避开我标记的已占时段」。</li>
          <li>查询结果同样生成右侧表格卡，后续筛选、收藏操作与 AI 推送的表格完全一致。</li>
        </ul>

        <T level={5}>💬 对话技巧</T>
        <ul style={{ fontSize: 13, color: '#4b5563', lineHeight: 2 }}>
          <li>直接说人话：「周二下午没空，想找 2 学分好过的公选课」「把刚才的结果列个表」。</li>
          <li>AI 会自动查课程库、避开你标记的时段，并把结果推成右侧表格。</li>
          <li>每段对话独立保存：左侧「对话历史」可切换、新建；进入会话后可整段删除。</li>
        </ul>

        <p style={{ fontSize: 12, color: '#8a939f', margin: '12px 0 0' }}>⚠️ AI 生成回复仅供参考</p>
      </div>
    </Modal>
  )
}
