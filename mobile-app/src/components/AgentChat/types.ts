export interface ToolCallStatus {
  name: string
  status: 'calling' | 'done'
}

export type ActionProposalType = 'judgment' | 'final_verdict' | 'operation'
export type ActionProposalStatus = 'pending' | 'confirmed' | 'cancelled' | 'failed'

export interface ActionProposalState {
  type: ActionProposalType
  title: string
  status: ActionProposalStatus
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
