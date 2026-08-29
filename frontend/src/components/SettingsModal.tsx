import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, Form, Input, Modal, message } from 'antd'
import { getConfig, saveConfig, testConfig } from '../api'

interface Props { open: boolean; onClose: () => void }

export default function SettingsModal({ open, onClose }: Props) {
  const [form] = Form.useForm()
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null)
  const qc = useQueryClient()
  const { data: cfg } = useQuery({ queryKey: ['config'], queryFn: getConfig, enabled: open })

  const onSave = async () => {
    try {
      const values = await form.validateFields()
      await saveConfig(values)
      message.success('已保存（存储在本机 config.local.json，不会上传/进仓库）')
      qc.invalidateQueries({ queryKey: ['config'] })
      setTestResult(null)
      onClose()
    } catch { /* 校验失败 */ }
  }

  const onTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const values = await form.validateFields()
      await saveConfig(values)
      qc.invalidateQueries({ queryKey: ['config'] })
      const r = await testConfig()
      setTestResult(r)
    } catch (e: any) {
      setTestResult({ ok: false, message: String(e.message || e) })
    } finally {
      setTesting(false)
    }
  }

  return (
    <Modal title="AI 接口设置" open={open} onCancel={onClose} width={560}
      footer={[
        <Button key="test" loading={testing} onClick={onTest}>保存并测试连接</Button>,
        <Button key="ok" type="primary" onClick={onSave}>保存</Button>,
      ]}
      afterOpenChange={o => {
        if (o) form.setFieldsValue({ api_key: '' })
      }}>
      <Alert type="info" showIcon style={{ marginBottom: 14 }}
        message="接口地址与模型已内置，只需填写 API Key。key 只保存在你自己的电脑上（config.local.json，已被 .gitignore 排除），对话时由本机后端直连 AI 服务。" />
      <Form form={form} layout="vertical">
        <Form.Item name="api_key"
          label={`API Key${cfg?.api_key_masked ? `（已保存：${cfg.api_key_masked}，留空则不修改）` : ''}`}
          extra="向作者获取，形如 sk-...">
          <Input.Password placeholder="sk-..." autoComplete="new-password" />
        </Form.Item>
      </Form>
      {testResult && (
        <Alert type={testResult.ok ? 'success' : 'error'} showIcon
          message={testResult.ok ? '连接成功，可以开始对话了' : testResult.message} />
      )}
    </Modal>
  )
}
