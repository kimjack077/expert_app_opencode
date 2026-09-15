import PlanEditor from './PlanEditor'

interface Props {
  projectId: string
  /** 跳转到「审核组」页签，供审核组为空时的引导按钮使用 */
  onGoToTeam?: () => void
}

export default function PlanManagement({ projectId, onGoToTeam }: Props) {
  return <PlanEditor projectId={projectId} onGoToTeam={onGoToTeam} />
}
