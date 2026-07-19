import { useState, useEffect } from 'react'
import { Card, Button, Space, Modal, Form, Input, DatePicker, TimePicker, Select, message, Table, Tag } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, CalendarOutlined, EyeOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { auditPlanApi, auditTeamApi, auditProjectApi } from '@/services/auditProjectApi'
import { templateApi } from '@/services/api'
import dayjs from 'dayjs'
import type { ColumnsType } from 'antd/es/table'

interface Props {
  projectId: string
}

interface PlanItem {
  id: string
  plan_date: string
  time_start: string
  time_end: string
  group_no: string
  area_name: string
  area_type: string
  assigned_member_ids: string[]
  certification_systems: string[]
  clauses: string[]
  template_id: string
  activity_type: string
  status: string
  inspection_task_id: string | null
}

interface ProjectDetail {
  id: string
  scheduled_start: string
  scheduled_end: string
  certification_systems: string[]
}

const activityTypeMap: Record<string, string> = {
  normal: '正常审核',
  opening_meeting: '首次会议',
  closing_meeting: '末次会议',
  night_inspection: '夜间巡视',
  internal_meeting: '内部沟通',
}

const statusColorMap: Record<string, string> = {
  pending: 'default',
  in_progress: 'processing',
  completed: 'success',
}

export default function PlanEditor({ projectId }: Props) {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [planItems, setPlanItems] = useState<PlanItem[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editingItem, setEditingItem] = useState<PlanItem | null>(null)
  const [teamMembers, setTeamMembers] = useState<any[]>([])
  const [templates, setTemplates] = useState<any[]>([])
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [viewMode, setViewMode] = useState<'table' | 'calendar'>('table')
  const [form] = Form.useForm()

  useEffect(() => {
    fetchProject()
    fetchPlanItems()
    fetchTeamMembers()
    fetchTemplates()
  }, [projectId])

  const fetchProject = async () => {
    try {
      const response = await auditProjectApi.get(projectId)
      setProject(response.data)
    } catch (error) {
      console.error('获取项目详情失败:', error)
    }
  }

  const fetchPlanItems = async () => {
    setLoading(true)
    try {
      const response = await auditPlanApi.list(projectId)
      setPlanItems(response.data || [])
    } catch (error: any) {
      message.error(error.response?.data?.message || '获取审核计划失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchTeamMembers = async () => {
    try {
      const response = await auditTeamApi.list(projectId)
      setTeamMembers(response.data || [])
    } catch (error) {
      console.error('获取审核组成员失败:', error)
    }
  }

  const fetchTemplates = async () => {
    try {
      const response: any = await templateApi.getTemplates({ limit: 100 })
      setTemplates(response.data?.items || response.data || [])
    } catch (error) {
      console.error('获取模板列表失败:', error)
    }
  }

  const getMemberName = (memberId: string) => {
    const member = teamMembers.find((m) => m.member_id === memberId)
    if (member?.member_name || member?.member_username) {
      return member.member_name || member.member_username
    }
    return memberId
  }

  const getTemplateName = (templateId: string) => {
    const template = templates.find((t) => t.id === templateId)
    return template ? template.name : templateId
  }

  const handleAdd = async () => {
    await Promise.all([fetchTeamMembers(), fetchTemplates()])
    setEditingItem(null)
    const defaultDate = project?.scheduled_start ? dayjs(project.scheduled_start) : dayjs()
    form.resetFields()
    form.setFieldsValue({
      plan_date: defaultDate,
      time_start: dayjs('09:00', 'HH:mm'),
      time_end: dayjs('17:00', 'HH:mm'),
      group_no: 'A',
      activity_type: 'normal',
      certification_systems: project?.certification_systems || ['Q', 'E', 'S'],
    })
    setModalVisible(true)
  }

  const handleEdit = (item: PlanItem) => {
    setEditingItem(item)
    form.setFieldsValue({
      ...item,
      plan_date: dayjs(item.plan_date),
      time_start: dayjs(item.time_start, 'HH:mm'),
      time_end: dayjs(item.time_end, 'HH:mm'),
    })
    setModalVisible(true)
  }

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个审核计划项吗？',
      okText: '确定',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        try {
          await auditPlanApi.delete(id)
          message.success('删除成功')
          fetchPlanItems()
        } catch (error: any) {
          message.error(error.response?.data?.message || '删除失败')
        }
      },
    })
  }

  const handleSubmit = async (values: any) => {
    try {
      const data = {
        ...values,
        plan_date: values.plan_date.format('YYYY-MM-DD'),
        time_start: values.time_start.format('HH:mm'),
        time_end: values.time_end.format('HH:mm'),
        project_id: projectId,
      }

      if (editingItem) {
        await auditPlanApi.update(editingItem.id, data)
        message.success('更新成功')
      } else {
        await auditPlanApi.create(projectId, data)
        message.success('创建成功')
      }

      setModalVisible(false)
      form.resetFields()
      fetchPlanItems()
    } catch (error: any) {
      message.error(error.response?.data?.message || '操作失败')
    }
  }

  const columns: ColumnsType<PlanItem> = [
    {
      title: '日期',
      dataIndex: 'plan_date',
      key: 'plan_date',
      width: 120,
      sorter: (a, b) => a.plan_date.localeCompare(b.plan_date),
    },
    {
      title: '时间',
      key: 'time',
      width: 130,
      render: (_, record) => `${record.time_start} - ${record.time_end}`,
    },
    {
      title: '工作组',
      dataIndex: 'group_no',
      key: 'group_no',
      width: 80,
    },
    {
      title: '区域',
      dataIndex: 'area_name',
      key: 'area_name',
      ellipsis: true,
    },
    {
      title: '检查模板',
      dataIndex: 'template_id',
      key: 'template_id',
      width: 150,
      ellipsis: true,
      render: (templateId: string) => getTemplateName(templateId),
    },
    {
      title: '活动类型',
      dataIndex: 'activity_type',
      key: 'activity_type',
      width: 100,
      render: (type: string) => activityTypeMap[type] || type,
    },
    {
      title: '认证体系',
      dataIndex: 'certification_systems',
      key: 'certification_systems',
      width: 120,
      render: (systems: string[]) => (
        <Space size={4}>
          {systems?.map((sys) => (
            <Tag key={sys}>{sys}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => {
        const statusTextMap: Record<string, string> = {
          pending: '待开始',
          in_progress: '进行中',
          completed: '已完成',
        }
        return (
          <Tag color={statusColorMap[status]}>{statusTextMap[status] || status}</Tag>
        )
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          {record.inspection_task_id && (
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => navigate(`/inspection/${record.inspection_task_id}`)}
            >
              {record.status === 'completed' ? '查看/修改检查' : '执行检查'}
            </Button>
          )}
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            danger
            size="small"
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  const groupedByDate = planItems.reduce((acc, item) => {
    if (!acc[item.plan_date]) {
      acc[item.plan_date] = []
    }
    acc[item.plan_date].push(item)
    return acc
  }, {} as Record<string, PlanItem[]>)

  const disabledDate = (current: dayjs.Dayjs) => {
    if (!project) return false
    const start = project.scheduled_start ? dayjs(project.scheduled_start).startOf('day') : null
    const end = project.scheduled_end ? dayjs(project.scheduled_end).endOf('day') : null
    if (start && current < start) return true
    if (end && current > end) return true
    return false
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加计划项
        </Button>
        <Button
          icon={<CalendarOutlined />}
          onClick={() => setViewMode(viewMode === 'table' ? 'calendar' : 'table')}
        >
          {viewMode === 'table' ? '日历视图' : '表格视图'}
        </Button>
      </Space>

      {viewMode === 'table' ? (
        <Table
          columns={columns}
          dataSource={planItems}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 1200 }}
        />
      ) : (
        <div className="calendar-view">
          {Object.keys(groupedByDate).sort().map((date) => (
            <Card
              key={date}
              title={date}
              size="small"
              style={{ marginBottom: 16 }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                {groupedByDate[date].map((item) => (
                  <Card
                    key={item.id}
                    size="small"
                    hoverable
                    onClick={() => handleEdit(item)}
                    style={{ cursor: 'pointer' }}
                  >
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <div>
                        <Tag color="blue">{item.group_no}</Tag>
                        <Tag>{item.time_start} - {item.time_end}</Tag>
                        <Tag color={statusColorMap[item.status]}>{item.status}</Tag>
                      </div>
                      <div style={{ fontWeight: 'bold' }}>{item.area_name}</div>
                      <div>
                        <Space size={4}>
                          {item.certification_systems?.map((sys) => (
                            <Tag key={sys}>{sys}</Tag>
                          ))}
                        </Space>
                      </div>
                    </Space>
                  </Card>
                ))}
              </Space>
            </Card>
          ))}
        </div>
      )}

      <Modal
        title={editingItem ? '编辑审核计划项' : '添加审核计划项'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          form.resetFields()
        }}
        onOk={() => form.submit()}
        width={700}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Space style={{ width: '100%' }} size="large">
            <Form.Item
              label="审核日期"
              name="plan_date"
              rules={[{ required: true, message: '请选择审核日期' }]}
            >
              <DatePicker 
                style={{ width: 200 }} 
                disabledDate={disabledDate}
                placeholder={project ? `${project.scheduled_start || ''} ~ ${project.scheduled_end || ''}` : '选择日期'}
              />
            </Form.Item>

            <Form.Item
              label="开始时间"
              name="time_start"
              rules={[{ required: true, message: '请选择开始时间' }]}
            >
              <TimePicker format="HH:mm" style={{ width: 120 }} />
            </Form.Item>

            <Form.Item
              label="结束时间"
              name="time_end"
              rules={[{ required: true, message: '请选择结束时间' }]}
            >
              <TimePicker format="HH:mm" style={{ width: 120 }} />
            </Form.Item>
          </Space>

          <Space style={{ width: '100%' }} size="large">
            <Form.Item
              label="工作组编号"
              name="group_no"
              rules={[{ required: true, message: '请输入工作组编号' }]}
            >
              <Input placeholder="如：A、B、C" style={{ width: 120 }} />
            </Form.Item>

            <Form.Item label="活动类型" name="activity_type" style={{ flex: 1 }}>
              <Select style={{ width: 150 }}>
                <Select.Option value="normal">正常审核</Select.Option>
                <Select.Option value="opening_meeting">首次会议</Select.Option>
                <Select.Option value="closing_meeting">末次会议</Select.Option>
                <Select.Option value="night_inspection">夜间巡视</Select.Option>
                <Select.Option value="internal_meeting">内部沟通</Select.Option>
              </Select>
            </Form.Item>
          </Space>

          <Form.Item
            label="审核区域"
            name="area_name"
            rules={[{ required: true, message: '请输入审核区域' }]}
          >
            <Input placeholder="如：煤焦车间、高层领导" />
          </Form.Item>

          <Form.Item label="区域类型" name="area_type">
            <Select placeholder="选择区域类型" allowClear>
              <Select.Option value="department">职能部门</Select.Option>
              <Select.Option value="workshop">车间</Select.Option>
              <Select.Option value="office">办公室</Select.Option>
              <Select.Option value="site">现场</Select.Option>
              <Select.Option value="leadership">高层领导</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="检查模板"
            name="template_id"
            rules={[{ required: true, message: '请选择检查模板' }]}
            extra="选择检查模板后，模板中的检查项将作为本次审核的检查条款"
          >
            <Select 
              placeholder="请选择检查模板" 
              showSearch
              optionFilterProp="children"
              filterOption={(input, option) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
              }
              options={templates.map((t) => ({
                label: t.name,
                value: t.id,
              }))}
            />
          </Form.Item>

          <Form.Item
            label="分配的审核员"
            name="assigned_member_ids"
            rules={[{ required: true, message: '请选择审核员' }]}
          >
            <Select mode="multiple" placeholder="请选择审核员">
              {teamMembers.map((member) => (
                <Select.Option key={member.id} value={member.member_id}>
                  {getMemberName(member.member_id)}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="认证体系"
            name="certification_systems"
            rules={[{ required: true, message: '请选择认证体系' }]}
          >
            <Select mode="multiple" placeholder="请选择认证体系">
              <Select.Option value="Q">Q - 质量</Select.Option>
              <Select.Option value="E">E - 环境</Select.Option>
              <Select.Option value="S">S - 职业健康安全</Select.Option>
              <Select.Option value="En">En - 能源</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
