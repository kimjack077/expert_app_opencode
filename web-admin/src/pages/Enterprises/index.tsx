import { useState, useEffect } from 'react'
import { Card, Table, Button, Modal, Form, Input, Select, message, Space, Tag, Tabs, DatePicker, InputNumber, Descriptions, Row, Col } from 'antd'
import { PlusOutlined, EyeOutlined, EditOutlined, DeleteOutlined, SearchOutlined, BankOutlined, EnvironmentOutlined, PhoneOutlined, UserOutlined } from '@ant-design/icons'
import { enterpriseApi } from '@/services/api'
import dayjs from 'dayjs'

const { TextArea } = Input

interface Enterprise {
  id: string
  name: string
  credit_code: string
  org_code: string
  address: string
  legal_person: string
  contact_person: string
  contact_phone: string
  enterprise_type: string
  economic_type: string
  risk_level: string
  status: string
  district: string
  employee_count: number
  created_at: string
}

export default function Enterprises() {
  const [enterprises, setEnterprises] = useState<Enterprise[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [detailVisible, setDetailVisible] = useState(false)
  const [currentEnterprise, setCurrentEnterprise] = useState<any>(null)
  const [editingEnterprise, setEditingEnterprise] = useState<Enterprise | null>(null)
  const [form] = Form.useForm()
  const [searchParams, setSearchParams] = useState({
    name: '',
    district: '',
    risk_level: '',
    status: '',
  })

  useEffect(() => {
    fetchEnterprises()
  }, [])

  const fetchEnterprises = async () => {
    setLoading(true)
    try {
      const params: any = {}
      if (searchParams.name) params.name = searchParams.name
      if (searchParams.district) params.district = searchParams.district
      if (searchParams.risk_level) params.risk_level = searchParams.risk_level
      if (searchParams.status) params.status = searchParams.status
      const res: any = await enterpriseApi.getEnterprises(params)
      setEnterprises(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } catch (error) {
      console.error('Failed to fetch enterprises:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      if (editingEnterprise) {
        await enterpriseApi.updateEnterprise(editingEnterprise.id, values)
        message.success('企业更新成功')
      } else {
        await enterpriseApi.createEnterprise(values)
        message.success('企业创建成功')
      }
      setModalVisible(false)
      setEditingEnterprise(null)
      form.resetFields()
      fetchEnterprises()
    } catch (error) {
      message.error(editingEnterprise ? '更新失败' : '创建失败')
    }
  }

  const handleEdit = (record: Enterprise) => {
    setEditingEnterprise(record)
    form.setFieldsValue(record)
    setModalVisible(true)
  }

  const handleViewDetail = async (id: string) => {
    try {
      const res: any = await enterpriseApi.getEnterprise(id)
      setCurrentEnterprise(res.data)
      setDetailVisible(true)
    } catch (error) {
      message.error('获取详情失败')
    }
  }

  const handleDelete = async (id: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除该企业吗？此操作不可恢复。',
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await enterpriseApi.deleteEnterprise(id)
          message.success('删除成功')
          fetchEnterprises()
        } catch (error) {
          message.error('删除失败')
        }
      },
    })
  }

  const getRiskTag = (level: string) => {
    const levelMap: Record<string, { color: string; text: string }> = {
      A: { color: 'success', text: 'A级（低风险）' },
      B: { color: 'processing', text: 'B级（一般）' },
      C: { color: 'warning', text: 'C级（较高风险）' },
      D: { color: 'error', text: 'D级（高风险）' },
    }
    const item = levelMap[level] || { color: 'default', text: level }
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      active: { color: 'success', text: '正常' },
      suspended: { color: 'warning', text: '停业' },
      revoked: { color: 'error', text: '吊销' },
    }
    const item = statusMap[status] || { color: 'default', text: status }
    return <Tag color={item.color}>{item.text}</Tag>
  }

  const columns = [
    { 
      title: '企业名称', 
      dataIndex: 'name', 
      key: 'name', 
      width: 200,
      render: (name: string) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 32,
            height: 32,
            background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--accent-color) 100%)',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <BankOutlined style={{ color: 'white', fontSize: 14 }} />
          </div>
          <span style={{ fontWeight: 500 }}>{name}</span>
        </div>
      ),
    },
    { title: '统一社会信用代码', dataIndex: 'credit_code', key: 'credit_code', width: 200 },
    { title: '法定代表人', dataIndex: 'legal_person', key: 'legal_person', width: 100 },
    { title: '联系电话', dataIndex: 'contact_phone', key: 'contact_phone', width: 130 },
    { title: '所属区域', dataIndex: 'district', key: 'district', width: 100 },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      key: 'risk_level',
      width: 120,
      render: (level: string) => getRiskTag(level),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right' as const,
      render: (_: any, record: Enterprise) => (
        <Space size="small">
          <Button 
            type="text" 
            size="small" 
            icon={<EyeOutlined />} 
            onClick={() => handleViewDetail(record.id)}
            style={{ color: 'var(--info-color)' }}
          >
            详情
          </Button>
          <Button 
            type="text" 
            size="small" 
            icon={<EditOutlined />} 
            onClick={() => handleEdit(record)}
            style={{ color: 'var(--primary-color)' }}
          >
            编辑
          </Button>
          <Button 
            type="text" 
            size="small" 
            danger 
            icon={<DeleteOutlined />} 
            onClick={() => handleDelete(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">企业管理</h1>
        <Button 
          type="primary" 
          icon={<PlusOutlined />} 
          onClick={() => setModalVisible(true)}
          style={{
            background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--primary-hover) 100%)',
            border: 'none',
          }}
        >
          新增企业
        </Button>
      </div>

      <Card variant="borderless">
        <div className="search-bar">
          <Input
            placeholder="搜索企业名称"
            prefix={<SearchOutlined style={{ color: 'var(--text-light)' }} />}
            value={searchParams.name}
            onChange={(e) => setSearchParams({ ...searchParams, name: e.target.value })}
            style={{ width: 240 }}
            onPressEnter={fetchEnterprises}
            allowClear
          />
          <Select
            placeholder="风险等级"
            allowClear
            style={{ width: 160 }}
            value={searchParams.risk_level || undefined}
            onChange={(v) => setSearchParams({ ...searchParams, risk_level: v || '' })}
          >
            <Select.Option value="A">A级（低风险）</Select.Option>
            <Select.Option value="B">B级（一般）</Select.Option>
            <Select.Option value="C">C级（较高风险）</Select.Option>
            <Select.Option value="D">D级（高风险）</Select.Option>
          </Select>
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 120 }}
            value={searchParams.status || undefined}
            onChange={(v) => setSearchParams({ ...searchParams, status: v || '' })}
          >
            <Select.Option value="active">正常</Select.Option>
            <Select.Option value="suspended">停业</Select.Option>
            <Select.Option value="revoked">吊销</Select.Option>
          </Select>
          <Button type="primary" onClick={fetchEnterprises}>
            查询
          </Button>
          <Button onClick={() => {
            setSearchParams({ name: '', district: '', risk_level: '', status: '' })
            fetchEnterprises()
          }}>
            重置
          </Button>
        </div>

        <Table
          columns={columns}
          dataSource={enterprises}
          rowKey="id"
          loading={loading}
          pagination={{ 
            pageSize: 10,
            total: total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (t) => `共 ${t} 条记录`,
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      <Modal
        title={editingEnterprise ? '编辑企业' : '新增企业'}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setEditingEnterprise(null)
          form.resetFields()
        }}
        footer={null}
        width={800}
        centered
        styles={{ body: { maxHeight: '60vh', overflowY: 'auto', paddingRight: 8 } }}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f5f5f5', borderRadius: 8 }}>
            <div style={{ fontWeight: 600, color: '#1890ff', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
              <BankOutlined /> 基本信息
            </div>
          </div>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="企业名称" rules={[{ required: true, message: '请输入企业名称' }]}>
                <Input placeholder="请输入企业名称" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="credit_code" label="统一社会信用代码">
                <Input placeholder="请输入统一社会信用代码" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="org_code" label="组织机构代码">
                <Input placeholder="请输入组织机构代码" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="legal_person" label="法定代表人">
                <Input placeholder="请输入法定代表人" />
              </Form.Item>
            </Col>
          </Row>

          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f5f5f5', borderRadius: 8, marginTop: 8 }}>
            <div style={{ fontWeight: 600, color: '#52c41a', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
              <PhoneOutlined /> 联系信息
            </div>
          </div>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="contact_person" label="联系人">
                <Input placeholder="请输入联系人" prefix={<UserOutlined style={{ color: 'var(--text-light)' }} />} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="contact_phone" label="联系电话">
                <Input placeholder="请输入联系电话" prefix={<PhoneOutlined style={{ color: 'var(--text-light)' }} />} />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item name="address" label="企业地址">
                <Input placeholder="请输入企业地址" prefix={<EnvironmentOutlined style={{ color: 'var(--text-light)' }} />} />
              </Form.Item>
            </Col>
          </Row>

          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f5f5f5', borderRadius: 8, marginTop: 8 }}>
            <div style={{ fontWeight: 600, color: '#faad14', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
              <EnvironmentOutlined /> 扩展信息
            </div>
          </div>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="district" label="所属区域">
                <Input placeholder="请输入所属区域" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="street" label="街道">
                <Input placeholder="请输入街道" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="enterprise_type" label="企业类型">
                <Select allowClear placeholder="请选择企业类型">
                  <Select.Option value="生产">生产</Select.Option>
                  <Select.Option value="加工">加工</Select.Option>
                  <Select.Option value="销售">销售</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="economic_type" label="经济类型">
                <Select allowClear placeholder="请选择经济类型">
                  <Select.Option value="国有">国有</Select.Option>
                  <Select.Option value="集体">集体</Select.Option>
                  <Select.Option value="私营">私营</Select.Option>
                  <Select.Option value="外资">外资</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="risk_level" label="风险等级" initialValue="B">
                <Select placeholder="请选择风险等级">
                  <Select.Option value="A">A级（低风险）</Select.Option>
                  <Select.Option value="B">B级（一般）</Select.Option>
                  <Select.Option value="C">C级（较高风险）</Select.Option>
                  <Select.Option value="D">D级（高风险）</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="status" label="状态" initialValue="active">
                <Select placeholder="请选择状态">
                  <Select.Option value="active">正常</Select.Option>
                  <Select.Option value="suspended">停业</Select.Option>
                  <Select.Option value="revoked">吊销</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="employee_count" label="员工人数">
                <InputNumber min={0} style={{ width: '100%' }} placeholder="请输入员工人数" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="annual_output" label="年产值（万元）">
                <InputNumber min={0} style={{ width: '100%' }} placeholder="请输入年产值" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="longitude" label="经度">
                <Input placeholder="请输入经度" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="latitude" label="纬度">
                <Input placeholder="请输入纬度" />
              </Form.Item>
            </Col>
            <Col span={24}>
              <Form.Item name="remarks" label="备注">
                <TextArea rows={3} placeholder="请输入备注信息" />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item style={{ marginTop: 16, textAlign: 'right', marginBottom: 0 }}>
            <Space>
              <Button onClick={() => {
                setModalVisible(false)
                setEditingEnterprise(null)
                form.resetFields()
              }}>取消</Button>
              <Button type="primary" htmlType="submit">
                {editingEnterprise ? '更新' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 40,
              height: 40,
              background: 'linear-gradient(135deg, var(--primary-color) 0%, var(--accent-color) 100%)',
              borderRadius: 10,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              <BankOutlined style={{ color: 'white', fontSize: 18 }} />
            </div>
            <span>企业详情</span>
          </div>
        }
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={900}
        centered
      >
        {currentEnterprise && (
          <Tabs
            defaultActiveKey="basic"
            style={{ marginTop: 16 }}
            items={[
              {
                key: 'basic',
                label: '基本信息',
                children: (
                  <Descriptions bordered column={2} size="middle">
                    <Descriptions.Item label="企业名称">{currentEnterprise.name}</Descriptions.Item>
                    <Descriptions.Item label="统一社会信用代码">{currentEnterprise.credit_code}</Descriptions.Item>
                    <Descriptions.Item label="组织机构代码">{currentEnterprise.org_code}</Descriptions.Item>
                    <Descriptions.Item label="法定代表人">{currentEnterprise.legal_person}</Descriptions.Item>
                    <Descriptions.Item label="联系人">{currentEnterprise.contact_person}</Descriptions.Item>
                    <Descriptions.Item label="联系电话">{currentEnterprise.contact_phone}</Descriptions.Item>
                    <Descriptions.Item label="企业地址" span={2}>{currentEnterprise.address}</Descriptions.Item>
                    <Descriptions.Item label="所属区域">{currentEnterprise.district}</Descriptions.Item>
                    <Descriptions.Item label="街道">{currentEnterprise.street}</Descriptions.Item>
                    <Descriptions.Item label="企业类型">{currentEnterprise.enterprise_type}</Descriptions.Item>
                    <Descriptions.Item label="经济类型">{currentEnterprise.economic_type}</Descriptions.Item>
                    <Descriptions.Item label="风险等级">{getRiskTag(currentEnterprise.risk_level)}</Descriptions.Item>
                    <Descriptions.Item label="状态">{getStatusTag(currentEnterprise.status)}</Descriptions.Item>
                    <Descriptions.Item label="员工人数">{currentEnterprise.employee_count}</Descriptions.Item>
                    <Descriptions.Item label="年产值">{currentEnterprise.annual_output} 万元</Descriptions.Item>
                    <Descriptions.Item label="经度">{currentEnterprise.longitude}</Descriptions.Item>
                    <Descriptions.Item label="纬度">{currentEnterprise.latitude}</Descriptions.Item>
                    <Descriptions.Item label="备注" span={2}>{currentEnterprise.remarks}</Descriptions.Item>
                  </Descriptions>
                ),
              },
              {
                key: 'qualifications',
                label: '资质信息',
                children: (
                  <Table
                    dataSource={currentEnterprise.qualifications || []}
                    rowKey="id"
                    size="middle"
                    pagination={false}
                    locale={{ emptyText: '暂无资质信息' }}
                  >
                    <Table.Column title="资质类型" dataIndex="qual_type" />
                    <Table.Column title="证书编号" dataIndex="cert_no" />
                    <Table.Column title="产品名称" dataIndex="product_name" />
                    <Table.Column title="有效期至" dataIndex="valid_until" render={(v) => v ? dayjs(v).format('YYYY-MM-DD') : '-'} />
                    <Table.Column title="状态" dataIndex="status" render={(s) => s === 'valid' ? <Tag color="success">有效</Tag> : <Tag color="error">失效</Tag>} />
                  </Table>
                ),
              },
              {
                key: 'products',
                label: '产品信息',
                children: (
                  <Table
                    dataSource={currentEnterprise.products || []}
                    rowKey="id"
                    size="middle"
                    pagination={false}
                    locale={{ emptyText: '暂无产品信息' }}
                  >
                    <Table.Column title="产品名称" dataIndex="name" />
                    <Table.Column title="产品类别" dataIndex="category" />
                    <Table.Column title="规格型号" dataIndex="specification" />
                    <Table.Column title="年产量" dataIndex="annual_output" />
                    <Table.Column title="获证状态" dataIndex="cert_status" />
                  </Table>
                ),
              },
            ]}
          />
        )}
      </Modal>
    </div>
  )
}
