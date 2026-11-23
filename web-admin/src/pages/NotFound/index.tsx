import { Button, Result, Space } from 'antd'
import { useNavigate } from 'react-router-dom'

/** 未匹配路由的兜底页：此前访问不存在的地址会停在空白布局中 */
export default function NotFound() {
  const navigate = useNavigate()
  return (
    <Result
      status="404"
      title="页面不存在"
      subTitle="您访问的页面不存在或已被移动，请检查地址或返回工作台。"
      extra={
        <Space>
          <Button onClick={() => navigate(-1)}>返回上一页</Button>
          <Button type="primary" onClick={() => navigate('/dashboard')}>
            返回工作台
          </Button>
        </Space>
      }
    />
  )
}
