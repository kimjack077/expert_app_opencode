import PlanEditor from './PlanEditor'

interface Props {
  projectId: string
}

export default function PlanManagement({ projectId }: Props) {
  return <PlanEditor projectId={projectId} />
}
