import { useEffect, useRef, useState } from 'react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  intent?: string
  action?: string
  timestamp: Date
}

interface Props {
  onDashboardCreated?: (url: string) => void
}

const API_BASE = '/api/v1'

const ACTION_BADGE: Record<string, { service: string; color: string; bg: string }> = {
  search_logs:        { service: 'Elasticsearch', color: '#06c',     bg: '#eef4ff' },
  create_alert_rule:  { service: 'Prometheus',    color: '#16a34a',  bg: '#f0fdf4' },
  create_dashboard:   { service: 'Grafana',       color: '#f97316',  bg: '#fff7ed' },
}

const QUICK_ACTIONS = [
  '⚡ CPU 알림 생성',
  '🔍 에러 로그 검색',
  '📊 대시보드 생성',
  '🔔 알림 현황',
]

function formatTime(date: Date) {
  return date.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: true })
}

export default function ChatBot({ onDashboardCreated }: Props) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '0',
      role: 'assistant',
      content: '안녕하세요! Observability AI입니다.\n모니터링 설정, 로그 검색, 알림 확인을 도와드릴게요.',
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = (query?: string) => {
    const text = (query ?? input).trim()
    if (!text || isStreaming) return

    const userMsg: Message = { id: `u-${Date.now()}`, role: 'user', content: text, timestamp: new Date() }
    const asstId = `a-${Date.now() + 1}`
    const asstMsg: Message = { id: asstId, role: 'assistant', content: '', timestamp: new Date() }

    setMessages(prev => [...prev, userMsg, asstMsg])
    setInput('')
    setIsStreaming(true)

    const es = new EventSource(`${API_BASE}/chat/stream?query=${encodeURIComponent(text)}`)
    esRef.current = es

    es.onmessage = (e) => {
      if (e.data === '[DONE]') {
        es.close()
        setIsStreaming(false)
        return
      }
      try {
        const data = JSON.parse(e.data) as Record<string, unknown>
        setMessages(prev =>
          prev.map(msg => {
            if (msg.id !== asstId) return msg
            return {
              ...msg,
              content:
                data['type'] === 'text'
                  ? msg.content + (data['content'] as string)
                  : data['type'] === 'error'
                    ? `오류: ${String(data['message'] ?? '요청 처리 중 오류가 발생했습니다.')}`
                    : msg.content,
              intent: data['type'] === 'intent' ? (data['intent'] as string) : msg.intent,
              action: data['type'] === 'action' ? (data['name'] as string) : msg.action,
            }
          })
        )
        if (data['type'] === 'action_result') {
          const result = data['result'] as Record<string, unknown>
          if (result['dashboard_url']) {
            onDashboardCreated?.(result['dashboard_url'] as string)
          }
        }
      } catch {}
    }

    es.onerror = () => {
      setMessages(prev =>
        prev.map(msg => {
          if (msg.id !== asstId) return msg
          if (msg.content.trim()) return msg
          return {
            ...msg,
            content: '연결이 중간에 종료되었습니다. 백엔드 서버 상태와 API 키 설정을 확인해주세요.',
          }
        })
      )
      es.close()
      setIsStreaming(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: '100%', height: '100%', background: '#fafafa', borderRight: '1.6px solid #e8e8e8' }}>

      {/* Header */}
      <div style={{ height: 64, background: '#1a1a2e', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 20px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="7.5" stroke="rgba(255,255,255,0.8)" strokeWidth="1.4" />
            <circle cx="10" cy="10" r="2.5" fill="rgba(255,255,255,0.8)" />
            <path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2" stroke="rgba(255,255,255,0.8)" strokeWidth="1.4" strokeLinecap="round" />
          </svg>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 16, fontWeight: 600, color: '#fff', lineHeight: '24px' }}>
              Observability AI
            </span>
            <span style={{ fontFamily: "'Inter', 'Noto Sans KR', sans-serif", fontSize: 11, color: 'rgba(255,255,255,0.6)', lineHeight: '16.5px' }}>
              LLM 기반 모니터링 자동화
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', flexShrink: 0 }} />
          <span style={{ fontFamily: "'Inter', 'Noto Sans KR', sans-serif", fontSize: 11, color: '#22c55e' }}>
            연결됨
          </span>
        </div>
      </div>

      {/* QuickActionChips */}
      <div
        style={{
          background: '#1a1a2e',
          borderBottom: '1.6px solid #e8e8e8',
          padding: '12px 16px',
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
          gap: 8,
          flexShrink: 0,
        }}
      >
        {QUICK_ACTIONS.map(action => (
          <button
            key={action}
            onClick={() => sendMessage(action)}
            disabled={isStreaming}
            style={{
              width: '100%',
              height: 32,
              padding: '0 10px',
              background: '#f9fafb',
              border: '1.6px solid #e8e8e8',
              borderRadius: 999,
              fontFamily: "'Inter', 'Noto Sans KR', sans-serif",
              fontSize: 12,
              fontWeight: 500,
              color: '#374151',
              cursor: isStreaming ? 'not-allowed' : 'pointer',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {action}
          </button>
        ))}
      </div>

      {/* MessageList */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {messages.map((msg, i) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
              gap: 4,
            }}
          >
            {/* Tool action badge */}
            {msg.role === 'assistant' && msg.action && (() => {
              const badge = ACTION_BADGE[msg.action] ?? { service: msg.action, color: '#6b7280', bg: '#f3f4f6' }
              return (
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: badge.bg, borderRadius: 999, padding: '4px 10px' }}>
                  <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, color: badge.color, whiteSpace: 'nowrap' }}>{msg.action}</span>
                  <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, color: badge.color }}>→</span>
                  <span style={{ fontFamily: "'Inter', sans-serif", fontSize: 11, color: badge.color, whiteSpace: 'nowrap' }}>{badge.service}</span>
                </div>
              )
            })()}

            {/* Bubble */}
            <div
              style={{
                maxWidth: '90%',
                padding: '12px 16px',
                borderRadius: msg.role === 'user' ? '18px 4px 18px 18px' : '4px 18px 18px 18px',
                background: msg.role === 'user' ? '#06c' : '#f0f2f5',
                color: msg.role === 'user' ? '#fff' : '#1f2937',
                fontSize: 14,
                lineHeight: '22.75px',
                fontFamily: "'Inter', 'Noto Sans KR', sans-serif",
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              {msg.content || (isStreaming && i === messages.length - 1 ? '▋' : '')}
            </div>

            {/* Timestamp */}
            <span style={{ fontFamily: "'Inter', 'Noto Sans KR', sans-serif", fontSize: 11, color: '#9ca3af', whiteSpace: 'nowrap' }}>
              {formatTime(msg.timestamp)}
            </span>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {/* InputArea */}
      <div style={{ height: 72, background: '#fff', borderTop: '1.6px solid #e8e8e8', display: 'flex', alignItems: 'center', padding: '0 16px', gap: 8, flexShrink: 0 }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder="예: CPU 알림 규칙 만들어줘"
            disabled={isStreaming}
            style={{
              width: '100%',
              height: 44,
              padding: '0 40px 0 16px',
              border: '1.6px solid #06c',
              borderRadius: 999,
              fontFamily: "'Inter', 'Noto Sans KR', sans-serif",
              fontSize: 14,
              color: '#374151',
              background: isStreaming ? '#f9fafb' : '#fff',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
          <div style={{ position: 'absolute', right: 14, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="5.5" y="1" width="5" height="8" rx="2.5" stroke="#9ca3af" strokeWidth="1.2" />
              <path d="M3 7.5C3 10.2614 5.23858 12.5 8 12.5C10.7614 12.5 13 10.2614 13 7.5" stroke="#9ca3af" strokeWidth="1.2" strokeLinecap="round" />
              <line x1="8" y1="12.5" x2="8" y2="15" stroke="#9ca3af" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
          </div>
        </div>
        <button
          onClick={() => sendMessage()}
          disabled={isStreaming || !input.trim()}
          style={{
            width: 44,
            height: 44,
            borderRadius: '50%',
            background: isStreaming || !input.trim() ? '#c7d2fe' : '#06c',
            border: 'none',
            cursor: isStreaming || !input.trim() ? 'not-allowed' : 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'background 0.15s',
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M9 14V4M9 4L5 8M9 4L13 8" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>

    </div>
  )
}
