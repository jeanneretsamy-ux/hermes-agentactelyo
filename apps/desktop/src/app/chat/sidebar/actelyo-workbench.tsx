import { useStore } from '@nanostores/react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'

import { Codicon } from '@/components/ui/codicon'
import { SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar'
import { $gateway } from '@/store/gateway'
import { $activeGatewayProfile } from '@/store/profile'
import { $activeSessionId } from '@/store/session'

import { ProcedureLearningDialog } from './procedure-learning-dialog'
import { ReaWorkbenchDialog } from './rea-workbench-dialog'

export function ActelyoWorkbench() {
  const navigate = useNavigate()
  const gateway = useStore($gateway)
  const profile = useStore($activeGatewayProfile)
  const session = useStore($activeSessionId)

  const [learning, setLearning] = useState<{
    mode: 'learn' | 'rea'
    gateway: typeof gateway
    profile: typeof profile
    session: typeof session
  } | null>(null)

  const current =
    learning && learning.gateway === gateway && learning.profile === profile && learning.session === session

  useEffect(() => {
    if (learning && !current) {
      setLearning(null)
    }
  }, [learning, current])

  return (
    <>
      <SidebarMenuItem>
        <SidebarMenuButton onClick={() => navigate('/settings?tab=providers&pview=local')}>
          <Codicon name="server" />
          Actelyo Studio
        </SidebarMenuButton>
      </SidebarMenuItem>
      <SidebarMenuItem>
        <SidebarMenuButton onClick={() => setLearning({ mode: 'rea', gateway, profile, session })}>
          <Codicon name="code" />
          REA — créer des fonctionnalités
        </SidebarMenuButton>
      </SidebarMenuItem>
      <SidebarMenuItem>
        <SidebarMenuButton onClick={() => setLearning({ mode: 'learn', gateway, profile, session })}>
          <Codicon name="record" />
          Apprendre une procédure
        </SidebarMenuButton>
      </SidebarMenuItem>
      {current && learning.mode === 'learn' && <ProcedureLearningDialog onClose={() => setLearning(null)} />}
      {current && learning.mode === 'rea' && (
        <ReaWorkbenchDialog gateway={gateway} onClose={() => setLearning(null)} profile={profile} />
      )}
    </>
  )
}
