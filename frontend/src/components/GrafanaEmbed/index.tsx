const GRAFANA_BASE = import.meta.env.VITE_GRAFANA_BASE ?? 'http://localhost:3001'

interface Props {
  dashboardUrl?: string
  title?: string
}

export default function GrafanaEmbed({ dashboardUrl, title }: Props) {
  if (!dashboardUrl) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '100%',
          height: '100%',
          background: '#fafafa',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 12,
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              background: '#f3f4f6',
              borderRadius: 10,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <rect x="3" y="12" width="4" height="9" rx="1" fill="#9ca3af" />
              <rect x="10" y="7" width="4" height="14" rx="1" fill="#9ca3af" />
              <rect x="17" y="3" width="4" height="18" rx="1" fill="#9ca3af" />
            </svg>
          </div>
          <p
            style={{
              margin: 0,
              fontFamily: "'Inter', 'Noto Sans KR', sans-serif",
              fontSize: 14,
              fontWeight: 400,
              lineHeight: '20px',
              color: '#9ca3af',
              whiteSpace: 'nowrap',
            }}
          >
            챗봇에서 대시보드를 생성하면 여기에 표시됩니다.
          </p>
        </div>
      </div>
    )
  }

  const buildEmbedUrl = (input: string) => {
    let resolved = input
    if (input.startsWith('http')) {
      try {
        const parsed = new URL(input)
        const base = new URL(GRAFANA_BASE)
        if (parsed.hostname === 'grafana') {
          resolved = `${base.origin}${parsed.pathname}`
        }
      } catch {
        resolved = input
      }
    } else {
      resolved = `${GRAFANA_BASE}${input}`
    }

    try {
      const url = new URL(resolved)
      url.searchParams.set('orgId', '1')
      url.searchParams.set('kiosk', 'tv')
      url.searchParams.set('refresh', '30s')
      return url.toString()
    } catch {
      return resolved
    }
  }

  const embedUrl = buildEmbedUrl(dashboardUrl)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {title && (
        <div
          style={{
            padding: '10px 16px',
            background: '#1a1a2e',
            color: '#fff',
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          {title}
        </div>
      )}
      <iframe
        src={embedUrl}
        style={{ flex: 1, border: 'none', width: '100%' }}
        title={title ?? 'Grafana Dashboard'}
        allowFullScreen
      />
    </div>
  )
}
