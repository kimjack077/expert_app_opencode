import React from 'react'
import { MessageOutline } from 'antd-mobile-icons'
import './AgentFab.css'

interface AgentFabProps {
  onClick: () => void
}

const AgentFab: React.FC<AgentFabProps> = ({ onClick }) => {
  return (
    <div className="agent-fab" onClick={onClick}>
      <MessageOutline fontSize={24} color="#fff" />
    </div>
  )
}

export default AgentFab
