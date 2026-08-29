import { Alert, Button, Card } from 'antd'

/** 占位组件：资料来源功能由另一会话开发中，落地后整体替换本文件即可。 */
export default function SourceTableCard({ onClose }: { onClose: () => void }) {
  return (
    <Card title="📄 资料来源" extra={<Button size="small" type="text" onClick={onClose}>关闭</Button>}>
      <Alert type="info" showIcon message="资料来源功能开发中，敬请期待。" />
    </Card>
  )
}
