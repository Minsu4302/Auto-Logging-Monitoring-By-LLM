import { useState } from 'react'
import ChatBot from './components/ChatBot'
import GrafanaEmbed from './components/GrafanaEmbed'

export default function App() {
  const [activeDashboard, setActiveDashboard] = useState<string | null>(null)

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', fontFamily: "'Inter', 'Noto Sans KR', sans-serif" }}>
      {/* 좌측: 챗봇 패널 */}
      <div style={{ width: 420, display: 'flex', flexShrink: 0 }}>
        <ChatBot onDashboardCreated={setActiveDashboard} />
      </div>

      {/* 우측: Grafana 대시보드 */}
      <div style={{ flex: 1 }}>
        <GrafanaEmbed dashboardUrl={activeDashboard ?? undefined} />
      </div>
    </div>
  )
}
