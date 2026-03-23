import { useState, useEffect } from 'react'
import { Table, Tag, message, Empty } from 'antd'
import { nonconformityApi } from '@/services/auditProjectApi'

interface Props {
  projectId: string
}

export default function NonconformitiesList({ projectId }: Props) {
  const [loading, setLoading] = useState(false)
  const [nonconformities, setNonconformities] = useState<any[]>([])

  useEffect(() => {
    fetchNonconformities()
  }, [projectId])

  const fetchNonconformities = async () => {
    setLoading(true)
    try {
      const response = await nonconformityApi.list(projectId)
      setNonconformities(response.data || [])
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取不符合项失败')
    } finally {
      setLoading(false)
    }
  }

  const columns = [
    { title: '编号', dataIndex: 'nc_no', key: 'nc_no', width: 150 },
    { 
      title: '严重程度', 
      dataIndex: 'severity', 
      key: 'severity', 
      width: 100,
      render: (severity: string) => {
        const colorMap: Record<string, string> = {
          major: 'error',
          minor: 'warning',
          observation: 'default',
        }
        const textMap: Record<string, string> = {
          major: '严重不符合',
          minor: '一般不符合',
          observation: '观察项',
        }
        return <Tag color={colorMap[severity]}>{textMap[severity] || severity}</Tag>
      }
    },
    { title: '条款号', dataIndex: 'clause_no', key: 'clause_no', width: 100 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status', 
      width: 100,
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          open: 'error',
          pending_verification: 'warning',
          closed: 'success',
        }
        const textMap: Record<string, string> = {
          open: '待整改',
          pending_verification: '待验证',
          closed: '已关闭',
        }
        return <Tag color={colorMap[status]}>{textMap[status] || status}</Tag>
      }
    },
    { title: '发现来源', dataIndex: 'source', key: 'source', width: 120 },
  ]

  if (nonconformities.length === 0 && !loading) {
    return (
      <Empty
        description="暂无不符合项"
        style={{ padding: '40px 0' }}
      >
        <span style={{ color: '#999', fontSize: 13 }}>
          不符合项由审核员在现场检查时发现并记录，无需手动创建
        </span>
      </Empty>
    )
  }

  return (
    <Table columns={columns} dataSource={nonconformities} rowKey="id" loading={loading} />
  )
}
