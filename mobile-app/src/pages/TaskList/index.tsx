import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  NavBar,
  List,
  PullToRefresh,
  Empty,
  Tag,
  Badge,
  Toast,
  SpinLoading,
} from 'antd-mobile'
import {
  RightOutline,
  ClockCircleOutline,
  CheckCircleOutline,
} from 'antd-mobile-icons'
import { taskApi } from '../../services/api'
import './style.css'

interface Task {
  id: string
  task_no: string
  title: string
  company_name: string
  address: string
  status: string
  progress: number
  total_items: number
  completed_items: number
}

const TaskList: React.FC = () => {
  const navigate = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(false)

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const res: any = await taskApi.getMyTasks()
      if (res.code === 200) {
        setTasks(res.data || [])
      }
    } catch (error) {
      Toast.show({
        icon: 'fail',
        content: '获取任务失败',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTasks()
  }, [])

  const getStatusTag = (status: string) => {
    switch (status) {
      case 'pending':
        return <Tag color="warning">待开始</Tag>
      case 'in_progress':
        return <Tag color="primary">进行中</Tag>
      case 'completed':
        return <Tag color="success">已完成</Tag>
      default:
        return <Tag>未知</Tag>
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <ClockCircleOutline className="status-icon pending" />
      case 'in_progress':
        return <Badge content="进行中" className="status-badge" />
      case 'completed':
        return <CheckCircleOutline className="status-icon completed" />
      default:
        return null
    }
  }

  const handleTaskClick = (task: Task) => {
    navigate(`/inspection/${task.id}`)
  }

  return (
    <div className="task-list-page">
      <NavBar back={null} className="task-nav">
        我的检查任务
      </NavBar>

      <div className="task-content">
        <PullToRefresh onRefresh={fetchTasks}>
          {loading && tasks.length === 0 ? (
            <div className="loading-container">
              <SpinLoading color="primary" />
            </div>
          ) : tasks.length === 0 ? (
            <Empty
              description="暂无检查任务"
              imageStyle={{ width: 120 }}
            />
          ) : (
            <List className="task-list">
              {tasks.map((task) => (
                <List.Item
                  key={task.id}
                  className="task-item"
                  onClick={() => handleTaskClick(task)}
                  arrow={<RightOutline />}
                  prefix={getStatusIcon(task.status)}
                >
                  <div className="task-info">
                    <div className="task-header">
                      <span className="task-title">{task.title}</span>
                      {getStatusTag(task.status)}
                    </div>
                    <div className="task-company">{task.company_name}</div>
                    <div className="task-address">{task.address}</div>
                    <div className="task-progress">
                      <div className="progress-bar">
                        <div
                          className="progress-fill"
                          style={{
                            width: `${task.total_items > 0
                              ? (task.completed_items / task.total_items) * 100
                              : 0}%`,
                          }}
                        />
                      </div>
                      <span className="progress-text">
                        {task.completed_items}/{task.total_items} 项
                      </span>
                    </div>
                  </div>
                </List.Item>
              ))}
            </List>
          )}
        </PullToRefresh>
      </div>
    </div>
  )
}

export default TaskList
