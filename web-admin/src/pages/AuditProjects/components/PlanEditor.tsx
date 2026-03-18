import { useState, useEffect } from 'react'
import { Card, Button, Space, Modal, Form, Input, DatePicker, TimePicker, Select, message, Table, Tag } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, CalendarOutlined } from '@ant-design/icons'
import { auditPlanApi, auditTeamApi } from '@/services/auditProjectApi'
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
  activity_type: string
  status: string
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
  const [loading, setLoading] = useState(false)
  const [planItems, setPlanItems] = useState<PlanItem[]>([])
  const [modalVisible, setModalVisible] = useState(false)
  const [editingItem, setEditingItem] = useState<PlanItem | null>(null)
  const [teamMembers, setTeamMembers] = useState<any[]>([])
  const [viewMode, setViewMode] = useState<'table' | 'calendar'>('table')
  const [form] = Form.useForm()

  useEffect(() => {
    fetchPlanItems()
    fetchTeamMembers()
  }, [projectId])

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

  const handleAdd = () => {
    setEditingItem(null)
    form.resetFields()
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
      width: 150,
      render: (_, record) => `${record.time_start} - ${record.time_end}`,
    },
    {
      title: '工作组',
      dataIndex: 'group_no',
      key: 'group_no',
      width: 100,
    },
    {
      title: '区域',
      dataIndex: 'area_name',
      key: 'area_name',
      ellipsis: true,
    },
    {
      title: '活动类型',
      dataIndex: 'activity_type',
      key: 'activity_type',
      width: 120,
      render: (type: string) => activityTypeMap[type] || type,
    },
    {
      title: '认证体系',
      dataIndex: 'certification_systems',
      key: 'certification_systems',
      width: 150,
      render: (systems: string[]) => (
        <Space size={4}>
          {systems?.map((sys) => (
            <Tag key={sys} size="small">{sys}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={statusColorMap[status]}>{status}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 150,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
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

  // 按日期分组显示
  const groupedByDate = planItems.reduce((acc, item) => {
    if (!acc[item.plan_date]) {
      acc[item.plan_date] = []
    }
    acc[item.plan_date].push(item)
    return acc
  }, {} as Record<string, PlanItem[]>)

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
                            <Tag key={sys} size="small">{sys}</Tag>
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
          initialValues={{
            activity_type: 'normal',
            certification_systems: ['Q', 'E', 'S'],
          }}
        >
          <Form.Item
            label="审核日期"
            name="plan_date"
            rules={[{ required: true, message: '请选择审核日期' }]}
          >
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>

          <Space style={{ width: '100%' }} size="large">
            <Form.Item
              label="开始时间"
              name="time_start"
              rules={[{ required: true, message: '请选择开始时间' }]}
            >
              <TimePicker format="HH:mm" />
            </Form.Item>

            <Form.Item
              label="结束时间"
              name="time_end"
              rules={[{ required: true, message: '请选择结束时间' }]}
            >
              <TimePicker format="HH:mm" />
            </Form.Item>
          </Space>

          <Form.Item
            label="工作组编号"
            name="group_no"
            rules={[{ required: true, message: '请输入工作组编号' }]}
          >
            <Input placeholder="如：A、B、C、ABCDE" />
          </Form.Item>

          <Form.Item
            label="审核区域"
            name="area_name"
            rules={[{ required: true, message: '请输入审核区域' }]}
          >
            <Input placeholder="如：煤焦车间、高层领导" />
          </Form.Item>

          <Form.Item label="区域类型" name="area_type">
            <Select>
              <Select.Option value="department">职能部门</Select.Option>
              <Select.Option value="workshop">车间</Select.Option>
              <Select.Option value="office">办公室</Select.Option>
              <Select.Option value="site">现场</Select.Option>
              <Select.Option value="leadership">高层领导</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            label="分配的审核员"
            name="assigned_member_ids"
            rules={[{ required: true, message: '请选择审核员' }]}
          >
            <Select mode="multiple" placeholder="请选择审核员">
              {teamMembers.map((member) => (
                <Select.Option key={member.id} value={member.member_id}>
                  {member.member_id}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            label="认证体系"
            name="certification_systems"
            rules={[{ required: true, message: '请选择认证体系' }]}
          >
            <Select mode="multiple">
              <Select.Option value="Q">Q - 质量</Select.Option>
              <Select.Option value="E">E - 环境</Select.Option>
              <Select.Option value="S">S - 职业健康安全</Select.Option>
              <Select.Option value="En">En - 能源</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="审核条款" name="clauses">
            <Select mode="tags" placeholder="请输入条款号，如 8.5.1">
              <Select.Option value="4-5.3">4-5.3</Select.Option>
              <Select.Option value="6.1">6.1</Select.Option>
              <Select.Option value="7.1">7.1</Select.Option>
              <Select.Option value="8.5.1">8.5.1</Select.Option>
              <Select.Option value="9.1">9.1</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item label="活动类型" name="activity_type">
            <Select>
              <Select.Option value="normal">正常审核</Select.Option>
              <Select.Option value="opening_meeting">首次会议</Select.Option>
              <Select.Option value="closing_meeting">末次会议</Select.Option>
              <Select.Option value="night_inspection">夜间巡视</Select.Option>
              <Select.Option value="internal_meeting">内部沟通</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
