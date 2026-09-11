import { useState, useEffect } from 'react'
import { Card, Form, Input, Select, DatePicker, InputNumber, Button, message, Space, Spin, Tooltip } from 'antd'
import { QuestionCircleOutlined } from '@ant-design/icons'
import { useNavigate, useParams } from 'react-router-dom'
import { auditProjectApi } from '@/services/auditProjectApi'
import { enterpriseApi } from '@/services/api'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker
const { TextArea } = Input

export default function CreateAuditProject() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [fetchLoading, setFetchLoading] = useState(false)
  const [enterprises, setEnterprises] = useState<any[]>([])
  const isEdit = !!id

  useEffect(() => {
    fetchEnterprises()
    if (isEdit) {
      fetchProject()
    }
  }, [id])

  const fetchEnterprises = async () => {
    try {
      const response: any = await enterpriseApi.getEnterprises({ limit: 100 })
      setEnterprises(response.data?.items || [])
    } catch (error) {
      console.error('获取企业列表失败:', error)
    }
  }

  const fetchProject = async () => {
    setFetchLoading(true)
    try {
      const response = await auditProjectApi.get(id!)
      const project = response.data
      form.setFieldsValue({
        title: project.title,
        enterprise_id: project.enterprise_id,
        audit_type: project.audit_type,
        certification_systems: project.certification_systems,
        audit_criteria: project.audit_criteria,
        schedule: project.scheduled_start && project.scheduled_end
          ? [dayjs(project.scheduled_start), dayjs(project.scheduled_end)]
          : undefined,
        audit_days: project.audit_days,
        remarks: project.remarks,
      })
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取项目详情失败')
    } finally {
      setFetchLoading(false)
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

      if (isEdit) {
        await auditProjectApi.update(id!, data)
        message.success('更新审核项目成功')
        navigate(`/audit-projects/${id}`)
      } else {
        const response = await auditProjectApi.create(data)
        const projectId = response?.data?.id
        message.success('项目已创建，请继续配置审核组、计划和项目资料')
        navigate(projectId ? `/audit-projects/${projectId}` : '/audit-projects')
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || (isEdit ? '更新失败' : '创建失败'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '24px' }}>
      <Spin spinning={fetchLoading}>
        <Card title={isEdit ? '编辑审核项目' : '创建审核项目'}>
          <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
            initialValues={isEdit ? undefined : {
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
                      if (!isEdit && value[0].isBefore(dayjs(), 'day')) {
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
              label={
                <Space size={4}>
                  <span>审核工作量（人天）</span>
                  <Tooltip title="指全体审核员现场工作天数之和（例如：2 名审核员现场工作 3 天即为 6 人天）">
                    <QuestionCircleOutlined style={{ color: '#8c8c8c', cursor: 'pointer' }} />
                  </Tooltip>
                </Space>
              }
              name="audit_days"
              rules={[
                { required: true, message: '请输入审核工作量（人天）' },
                { type: 'number', min: 0.5, message: '审核工作量至少为0.5人天' },
                { type: 'number', max: 100, message: '审核工作量不能超过100人天' },
              ]}
            >
              <InputNumber
                min={0.5}
                max={100}
                step={0.5}
                precision={1}
                style={{ width: '100%' }}
                placeholder="如：3.0"
                addonAfter="人天"
              />
            </Form.Item>

            <Form.Item label="备注" name="remarks">
              <TextArea rows={4} placeholder="请输入备注信息" />
            </Form.Item>

            <Form.Item>
              <Space>
                <Button type="primary" htmlType="submit" loading={loading}>
                  {isEdit ? '保存修改' : '创建并继续配置'}
                </Button>
                <Button onClick={() => navigate('/audit-projects')}>取消</Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </Spin>
    </div>
  )
}
