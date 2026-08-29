import { useQuery } from '@tanstack/react-query'
import { Button, Tag } from 'antd'
import { DownloadOutlined, FileExcelOutlined } from '@ant-design/icons'
import { getSource } from '../api'

const FILE_NAME = '资料来源_按条件查询上课情况.xlsx'

function fmtSize(n?: number) {
  if (!n) return ''
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}

/** 「资料来源」独立页面：展示课程表格文件本身，查看需下载到本地用 Excel/WPS 打开。 */
export default function SourceCard() {
  const { data, isLoading } = useQuery({ queryKey: ['source'], queryFn: getSource })

  return (
    <div className="panel-card source-card">
      <div className="panel-card-head">
        <h4>📄 资料来源</h4>
        {!!data?.rows && <Tag>{data.rows} 行</Tag>}
      </div>
      {isLoading ? (
        <div className="panel-card-body" style={{ color: '#8a939f', fontSize: 13 }}>加载中…</div>
      ) : !data?.available ? (
        <div className="panel-card-body" style={{ color: '#8a939f', fontSize: 13 }}>
          尚未生成资料来源表。项目维护者可运行：<code>python -X utf8 -m app.source_gen &lt;教务导出的xlsx&gt;</code>
        </div>
      ) : (
        <div className="panel-card-body">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
            border: '1px solid #e8e8e8', borderRadius: 8, background: '#fafafa' }}>
            <FileExcelOutlined style={{ fontSize: 34, color: '#217346' }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13.5, fontWeight: 600, color: '#1f2733' }}>{FILE_NAME}</div>
              <div style={{ fontSize: 12, color: '#8a939f', marginTop: 2 }}>
                xlsx · {data.rows} 行 × {data.cols} 列{fmtSize(data.size_bytes) && ` · ${fmtSize(data.size_bytes)}`}
              </div>
            </div>
            <a href="/api/source/download">
              <Button type="primary" icon={<DownloadOutlined />}>下载 Excel</Button>
            </a>
          </div>
          <div style={{ fontSize: 12.5, color: '#4b5563', lineHeight: 1.8, marginTop: 10 }}>
            {data.note}，更新于 {data.updated_at}。表格不在线展示，<b>下载后用 Excel / WPS 打开查看</b>。
          </div>
        </div>
      )}
    </div>
  )
}
