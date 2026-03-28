import { useState, useRef, useEffect } from 'react'
import { API_BASE_URL } from '../config'
import type { ProjectInput, IntakeResponse } from '../types'
import { Send, FileUp, Sparkles } from 'lucide-react'

interface Message {
  role: 'assistant' | 'user'
  text: string
}

interface InvestigatingItem {
  incentive: string
  country: string
  gap: string
  potential_amount?: number
  potential_currency?: string
}

interface Props {
  onProjectReady: (project: ProjectInput) => void
  onAnalyze: () => void
  onSessionStart?: (sessionId: string) => void
}

export function IntakeChat({ onProjectReady, onAnalyze, onSessionStart }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [completeness, setCompleteness] = useState(0)
  const [isReady, setIsReady] = useState(false)
  const [started, setStarted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [investigating, setInvestigating] = useState<InvestigatingItem[]>([])
  const [uploading, setUploading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleResponse = (data: IntakeResponse & { investigating?: InvestigatingItem[] }) => {
    setMessages((prev) => [...prev, { role: 'assistant', text: data.reply }])
    setCompleteness(data.completeness_score)
    setIsReady(data.is_ready)
    onProjectReady(data.project_draft)
    if (data.investigating) {
      setInvestigating(data.investigating)
    }
  }

  const startIntake = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/intake/start', { method: 'POST' })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setSessionId(data.session_id)
      onSessionStart?.(data.session_id)
      setMessages([{ role: 'assistant', text: data.reply }])
      setCompleteness(data.completeness_score)
      setIsReady(data.is_ready)
      setStarted(true)
      if (data.is_ready) onProjectReady(data.project_draft)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start')
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || loading) return
    const userText = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text: userText }])
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/intake/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: userText }),
      })
      if (!res.ok) throw new Error(await res.text())
      handleResponse(await res.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !sessionId) return
    e.target.value = ''

    setUploading(true)
    setMessages((prev) => [...prev, { role: 'user', text: `Uploaded document: ${file.name}` }])
    setError(null)
    try {
      const formData = new FormData()
      formData.append('session_id', sessionId)
      formData.append('file', file)
      const res = await fetch(`${API_BASE_URL}/api/intake/upload`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error(await res.text())
      handleResponse(await res.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  if (!started) {
    return (
      <div className="flex flex-col items-center text-center py-8">
        <div className="h-16 w-16 bg-neutral-50 flex items-center justify-center rounded-full mb-6">
          <Sparkles className="h-8 w-8 text-gallery-accent" />
        </div>
        <h3 className="text-xl font-bold font-serif">Chat with us</h3>
        <p className="mt-2 text-sm text-neutral-500 leading-relaxed">
          Describe your project or upload a treatment PDF. We'll help find the best co-production pathways.     
        </p>
        <button
          onClick={startIntake}
          disabled={loading}
          className="btn-primary mt-8 px-12"
        >
          {loading ? 'STARTING...' : 'START CONVERSATION'}
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-[500px]">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-neutral-100 pb-4 mb-6">
        <div className="flex items-center gap-3">
          <div className="h-1.5 w-1.5 rounded-full bg-gallery-accent animate-pulse" />
          <span className="text-[10px] font-black uppercase tracking-widest">Live Briefing</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="h-1 w-16 bg-neutral-100 rounded-full overflow-hidden">
            <div className="h-full bg-gallery-text transition-all duration-1000" style={{ width: `${Math.round(completeness * 100)}%` }} />
          </div>
          <span className="text-[10px] font-bold text-neutral-300">{Math.round(completeness * 100)}%</span>     
        </div>
      </header>

      {/* Message Stream */}
      <div className="flex-1 overflow-y-auto space-y-6 pr-2 custom-scrollbar">
        {messages.map((msg, i) => (
          <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>        
            <span className="text-[8px] font-black uppercase tracking-[0.2em] mb-1.5 text-neutral-300">
              {msg.role === 'user' ? 'Producer' : 'Assistant'}
            </span>
            <div className={`max-w-[90%] px-4 py-3 text-xs leading-relaxed border shadow-sm ${
              msg.role === 'user'
                ? 'bg-gallery-text text-white border-gallery-text'
                : 'bg-white text-gallery-text border-neutral-100'
            }`}>
              {msg.text}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-1.5 p-2 animate-pulse">
            <div className="h-1 w-1 bg-neutral-300 rounded-full" />
            <div className="h-1 w-1 bg-neutral-300 rounded-full" style={{ animationDelay: '0.2s' }} />
            <div className="h-1 w-1 bg-neutral-300 rounded-full" style={{ animationDelay: '0.4s' }} />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <footer className="mt-6 pt-4 border-t border-neutral-100 space-y-4">
        {isReady && (
          <div className="flex items-center justify-between gap-4 p-3 bg-gallery-accent/5 border border-gallery-accent/10">
            <span className="text-[9px] font-black uppercase tracking-widest text-gallery-accent">Profile Complete</span>
            <button onClick={onAnalyze} className="text-[9px] font-black uppercase tracking-widest underline decoration-2 underline-offset-4 hover:text-gallery-accent">Run Calculation</button>
          </div>
        )}

        <div className="flex items-end gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading || uploading}
            className="p-2 text-neutral-300 hover:text-gallery-accent transition-colors"
          >
            <FileUp className="h-5 w-5" />
          </button>
          <input ref={fileInputRef} type="file" accept=".pdf" onChange={handleFileUpload} className="hidden" /> 

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Type your film's details..."
            rows={1}
            className="flex-1 resize-none py-2 text-xs focus:outline-none placeholder:text-neutral-200 border-b border-neutral-100 focus:border-gallery-accent transition-colors"
          />

          <button
            onClick={sendMessage}
            disabled={loading || uploading || !input.trim()}
            className="p-2 text-gallery-text hover:text-gallery-accent transition-all active:scale-90"
          >
            <Send className="h-5 w-5" />
          </button>
        </div>
      </footer>
    </div>
  )
}
