import { useState } from 'react'
import { Alert, Modal, Spin, Upload, message } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import type { UploadProps } from 'antd'

interface Props {
  open: boolean
  onClose: () => void
  onImported: () => void
}

export default function ImportModal({ open, onClose, onImported }: Props) {
  const [loading, setLoading] = useState(false)
  const [lastStats, setLastStats] = useState<string>('')

  const doImport = async (file: File) => {
    setLoading(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch('/api/admin/import', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '导入失败')
      const s = data.stats
      setLastStats(`已导入 ${s.class_count} 个教学班（${s.year}学年 第${s.term}学期）`)
      message.success('导入成功')
      onImported()
      onClose()
    } catch (e: any) {
      message.error(String(e.message || e))
    } finally {
      setLoading(false)
    }
  }

  const props: UploadProps = {
    accept: '.xlsx,.xls',
    showUploadList: false,
    customRequest: options => doImport(options.file as File),
  }

  return (
    <Modal title="导入课程表" open={open} onCancel={onClose} footer={null} width={520}>
      <Spin spinning={loading} tip="正在解析并重建课程库…">
        <Upload.Dragger {...props} disabled={loading}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖入《按条件查询课程.xlsx》</p>
          <p className="ant-upload-hint">
            教务系统 → 学生选课 → 按条件查询课程 导出的文件。<br />
            导入会整体替换旧数据；教师联系电话列会被自动丢弃，不会入库。
          </p>
        </Upload.Dragger>
        {lastStats && <Alert style={{ marginTop: 12 }} type="success" showIcon message={lastStats} />}
      </Spin>
    </Modal>
  )
}
