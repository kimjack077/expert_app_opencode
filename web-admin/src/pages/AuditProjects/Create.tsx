import { useState, useEffect } from 'react'
import { Card, Form, Input, Select, DatePicker, InputNumber, Button, message, Space } from 'antd'
import { useNavigate } from 'react-router-dom'
import { auditProjectApi } from '@/services/auditProjectApi'
import { enterpriseApi } from '@/services/api'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker
const { TextArea } = Input

export default function CreateAuditProject() {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [enterprises, setEnterprises] = useState<any[]>([])

  useEffect(() => {
    fetchEnterprises()
  }, [])

  const fetchEnterprises = async () => {
    try {
      const response: any = await enterpriseApi.getEnterprises({ limit: 100 })
      setEnterprises(response.data?.items || [])
    } catch (error) {
      console.error('获取企业列表失败:', error)
    }
  }

  const handleSubmit = async (values: any) => {
    setLoading(true)
    try {
      const data = {
        ...values,
        scheduled_start: values.schedule?.[0]?.toISOString(),
        scheduled_end: values.schedule?.[1]?.toISOString(),
      }
      delete data.schedule

      await auditProjectApi.create(data)
      message.success('创建审核项目成功')
      navigate('/audit-projects')
    } catch (error: any) {
      message.error(error.response?.data?.message || '创建失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '24px' }}>
      <Card title="创建审核项目">
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            audit_type: 'recertification',
            certification_systems: ['Q', 'E', 'S'],
            audit_criteria: ['GB/T 19001-2016', 'GB/T 24001-2016', 'GB/T 45001-2020'],
          }}
        >
          <Form.Item
            label="项目名称"
            name="title"
            rules={[
              { required: true, message: '请输入项目名称' },
              { min: 5, message: '项目名称至少5个字符' },
              { max: 200, message: '项目名称不能超过200个字符' },
            ]}
          >
            <Input placeholder="如：山东盛发焦化有限公司再认证审核" maxLength={200} showCount />
          </Form.Item>

          <Form.Item
            label="受审核企业"
            name="enterprise_id"
            rules={[{ required: true, message: '请选择受审核企业' }]}
          >
            <Select
              placeholder="请选择企业"
              showSearch
              optionFilterProp="children"
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={enterprises.map((e) => ({
                label: e.name,
                value: e.id,
              }))}
            />
          </Form.Item>

          <Form.Item
            label="审核类型"
            name="audit_type"
            rules={[{ required: true, message: '请选择审核类型' }]}
          >
            <Select placeholder="请选择审核类型">
              <Select.Option value="initial">初审</Select.Option>
              <Select.Option value="surveillance">监督</Select.Option>
              <Select.Option value="recertification">再认证</Select.Option>
              <Select.Option value="expansion">扩项</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="认证体系"
            name="certification_systems"
            rules={[
              { required: true, message: '请选择认证体系' },
              { type: 'array', min: 1, message: '至少选择一个认证体系' },
            ]}
          >
            <Select mode="multiple" placeholder="请选择认证体系" maxTagCount={4}>
              <Select.Option value="Q">Q - 质量管理体系</Select.Option>
              <Select.Option value="E">E - 环境管理体系</Select.Option>
              <Select.Option value="S">S - 职业健康安全管理体系</Select.Option>
              <Select.Option value="En">En - 能源管理体系</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="审核准则"
            name="audit_criteria"
            rules={[
              { required: true, message: '请选择审核准则' },
              { type: 'array', min: 1, message: '至少选择一个审核准则' },
            ]}
          >
            <Select mode="tags" placeholder="请选择或输入审核准则" maxTagCount={6}>
              <Select.Option value="GB/T 19001-2016">GB/T 19001-2016</Select.Option>
              <Select.Option value="GB/T 24001-2016">GB/T 24001-2016</Select.Option>
              <Select.Option value="GB/T 45001-2020">GB/T 45001-2020</Select.Option>
              <Select.Option value="GB/T 23331-2020">GB/T 23331-2020</Select.Option>
              <Select.Option value="ISO 9001:2015">ISO 9001:2015</Select.Option>
              <Select.Option value="ISO 14001:2015">ISO 14001:2015</Select.Option>
              <Select.Option value="ISO 45001:2018">ISO 45001:2018</Select.Option>
              <Select.Option value="ISO 50001:2018">ISO 50001:2018</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="计划审核时间"
            name="schedule"
            rules={[
              { required: true, message: '请选择审核时间' },
              {
                validator: (_, value) => {
                  if (value && value[0] && value[1]) {
                    if (value[1].isBefore(value[0])) {
                      return Promise.reject('结束时间不能早于开始时间')
                    }
                    if (value[0].isBefore(dayjs(), 'day')) {
                      return Promise.reject('开始时间不能早于今天')
                    }
                  }
                  return Promise.resolve()
                },
              },
            ]}
          >
            <RangePicker showTime style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            label="审核人天数"
            name="audit_days"
            rules={[
              { required: true, message: '请输入审核人天数' },
              { type: 'number', min: 0.5, message: '审核人天数至少为0.5天' },
              { type: 'number', max: 100, message: '审核人天数不能超过100天' },
            ]}
          >
            <InputNumber
              min={0.5}
              max={100}
              step={0.5}
              precision={1}
              style={{ width: '100%' }}
              placeholder="如：3.0"
              addonAfter="天"
            />
          </Form.Item>

          <Form.Item label="备注" name="remarks">
            <TextArea rows={4} placeholder="请输入备注信息" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                创建项目
              </Button>
              <Button onClick={() => navigate('/audit-projects')}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
