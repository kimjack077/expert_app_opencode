export interface ToolCallStatus {
  name: string
  status: 'calling' | 'done'
}

export type ActionProposalType = 'judgment' | 'final_verdict' | 'operation'
export type ActionProposalStatus = 'pending' | 'confirmed' | 'cancelled' | 'failed'

export interface ActionProposalState {
  type: ActionProposalType
  /** 服务端动作名（apply_check_result / apply_final_verdict / ...），用于比对动作注册表。 */
  action: string
  title: string
  status: ActionProposalStatus
  /**
   * 服务端持久化提案的坐标。确认时只回传这两个值，
   * 执行内容完全由服务端决定。
   */
  messageId?: string
  actionIndex: number
  data: {
    recordId?: string
    itemId?: string
    checkItem?: string
    result?: string
    problemDescription?: string
    rectificationSuggestion?: string
    verdict?: string
    comment?: string
    [key: string]: unknown
  }
}

export interface ChatMessageState {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  toolCalls?: ToolCallStatus[]
  actionProposal?: ActionProposalState
}

export interface AgentChatContext {
  recordId?: string
  currentItemId?: string
  currentItemTitle?: string
  enterpriseId?: string
  mediaFileId?: string
}
