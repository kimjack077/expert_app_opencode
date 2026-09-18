import { useState, useEffect } from 'react'
import { Card, Form, Input, Select, Button, DatePicker, Space, message, Row, Col, Divider } from 'antd'
import { ArrowLeftOutlined, FileTextOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { templateApi, enterpriseApi, recordApi } from '@/services/api'
import dayjs from 'dayjs'

const { TextArea } = Input

export default function NewInspection() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [templates, setTemplates] = useState<any[]>([])
  const [enterprises, setEnterprises] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedEnterprise, setSelectedEnterprise] = useState<string | null>(null)

  useEffect(() => {
    fetchTemplates()
    fetchEnterprises()
  }, [])

  const fetchTemplates = async () => {
    try {
      const res: any = await templateApi.getTemplates({ is_published: true })
      setTemplates(res.data || [])
    } catch (error) {
      console.error('Failed to fetch templates:', error)
    }
  }

  const fetchEnterprises = async () => {
    try {
      const res: any = await enterpriseApi.getEnterprises({ limit: 100 })
      setEnterprises(res.data?.items || [])
    } catch (error) {
      console.error('Failed to fetch enterprises:', error)
    }
  }

  const handleEnterpriseChange = (value: string) => {
    setSelectedEnterprise(value)
    const enterprise = enterprises.find(e => e.id === value)
    if (enterprise) {
      form.setFieldsValue({
        enterprise_name: enterprise.name,
        enterprise_address: enterprise.address,
        contact_person: enterprise.contact_person,
        contact_phone: enterprise.contact_phone,
      })
    }
  }

  const handleSubmit = async (values: any) => {
    setLoading(true)
    try {
      const data = {
        ...values,
        enterprise_id: values.enterprise_id || undefined,
        inspection_date: values.inspection_date?.toISOString(),
      }
      const res: any = await recordApi.createRecord(data)
      message.success('检查记录创建成功')
      navigate(`/record/${res.data.id}`)
    } catch (error: any) {
      console.error('Failed to create record:', error)
      message.error(error?.response?.data?.message || '创建失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Button
            type="link"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/records')}
          >
            返回
          </Button>
          <h1 className="page-title" style={{ margin: 0 }}>新建检查</h1>
        </div>
      </div>

      <Card style={{ maxWidth: 800, margin: '24px auto' }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            inspection_date: dayjs(),
          }}
        >
          <Divider orientation="left" orientationMargin="0">检查信息</Divider>
          
          <Form.Item
            name="template_id"
            label="检查模板"
            rules={[{ required: true, message: '请选择检查模板' }]}
          >
            <Select
              placeholder="选择检查模板"
              options={templates.map(t => ({ value: t.id, label: t.name }))}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
            />
          </Form.Item>

          <Form.Item
            name="inspection_date"
            label="检查时间"
            rules={[{ required: true, message: '请选择检查时间' }]}
          >
            {/* 检查时间精确到分钟，不显示秒列 */}
            <DatePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: '100%' }} />
          </Form.Item>

          <Divider orientation="left" orientationMargin="0">企业信息</Divider>

          <Form.Item
            name="enterprise_id"
            label="选择企业（可选）"
          >
            <Select
              placeholder="选择已有企业，或不选手动输入"
              options={enterprises.map(e => ({ value: e.id, label: e.name }))}
              showSearch
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              onChange={handleEnterpriseChange}
              allowClear
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="enterprise_name"
                label="企业名称"
                rules={[{ required: true, message: '请输入企业名称' }]}
              >
                <Input placeholder="输入企业名称" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="contact_phone"
                label="联系电话"
              >
                <Input placeholder="输入联系电话" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="enterprise_address"
            label="企业地址"
          >
            <TextArea rows={2} placeholder="输入企业地址" />
          </Form.Item>

          <Form.Item
            name="contact_person"
            label="联系人"
          >
            <Input placeholder="输入联系人姓名" />
          </Form.Item>

          <Form.Item
            name="remarks"
            label="检查备注"
          >
            <TextArea rows={3} placeholder="输入检查备注信息（可选）" />
          </Form.Item>

          <Form.Item style={{ marginTop: 32 }}>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                icon={<FileTextOutlined />}
                size="large"
              >
                开始检查
              </Button>
              <Button onClick={() => navigate('/records')} size="large">
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
