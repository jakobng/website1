import { useState, useRef, useEffect } from 'react'
import { API_BASE_URL } from '../config'
import type { Scenario, ProjectInput } from '../types'
import { CheckCircle2, AlertCircle, MessageSquare, RotateCcw } from 'lucide-react'

interface CulturalTestCountry {
  country_code: string
  country_name: string
  incentive_name: string
  score_info: string
}

interface ReviewMessage {
  role: 'assistant' | 'user'
  text: string
  score?: { current: number | null; required: number | null; total: number | null }
}

interface Props {
  scenarios: Scenario[]
  project: ProjectInput
  sessionId: string | null
  onProjectUpdate: (project: ProjectInput) => void
  onReanalyze: () => void
}

function extractCulturalTestCountries(scenarios: Scenario[]): CulturalTestCountry[] {
  const seen = new Set<string>()
  const result: CulturalTestCountry[] = []

  for (const scenario of scenarios.slice(0, 5)) {
    for (const partner of scenario.partners) {
      for (const inc of partner.eligible_incentives) {
        const hasReq = inc.requirements.some(r => r.category === 'cultural')
        if (hasReq && !seen.has(partner.country_code)) {
          seen.add(partner.country_code)
          const req = inc.requirements.find(r => r.category === 'cultural')!
          const scoreMatch = req.description.match(/(\d+)\/(\d+) points/)
          const scoreInfo = scoreMatch ? `${scoreMatch[1]}/${scoreMatch[2]} PT_REQ` : 'Pass Required'
          result.push({
            country_code: partner.country_code,
            country_name: partner.country_name,
            incentive_name: inc.name,
            score_info: scoreInfo,
          })
        }
      }
    }
  }

  return result
}

export function CulturalTestPanel({ scenarios, project, sessionId, onProjectUpdate, onReanalyze }: Props) {     
  const countries = extractCulturalTestCountries(scenarios)

  if (countries.length === 0) return null

  return (
    <div className="card p-8 border-gallery-accent/20 bg-gallery-accent/5">
      <div className="flex items-center gap-3 mb-8 border-b border-gallery-accent/10 pb-4">
        <AlertCircle className="h-5 w-5 text-gallery-accent" />
        <h3 className="text-xs font-black tracking-[0.2em] uppercase">Compliance Verification</h3>
      </div>
      <div className="space-y-10">
        {countries.map((c) => (
          <CulturalTestRow
            key={c.country_code}
            country={c}
            project={project}
            sessionId={sessionId}
            onProjectUpdate={onProjectUpdate}
            onReanalyze={onReanalyze}
          />
        ))}
      </div>
    </div>
  )
}

function CulturalTestRow({
  country,
  project,
  sessionId,
  onProjectUpdate,
  onReanalyze,
}: {
  country: CulturalTestCountry
  project: ProjectInput
  sessionId: string | null
  onProjectUpdate: (p: ProjectInput) => void
  onReanalyze: () => void
}) {
  const passed = project.cultural_test_passed?.includes(country.country_code)
  const failed = project.cultural_test_failed?.includes(country.country_code)
  const status = passed ? 'pass' : failed ? 'fail' : 'unknown'

  const [reviewing, setReviewing] = useState(false)
  const [messages, setMessages] = useState<ReviewMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [verdict, setVerdict] = useState<'pass' | 'fail' | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const callEndpoint = async (endpoint: string, body: object) => {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }

  const markStatus = async (action: 'pass' | 'fail') => {
    if (!sessionId) return
    setLoading(true)
    try {
      const data = await callEndpoint('/api/intake/cultural-test', {
        session_id: sessionId,
        country_code: country.country_code,
        country_name: country.country_name,
        action,
        incentive_name: country.incentive_name,
        score_info: country.score_info,
      })
      onProjectUpdate({
        ...project,
        cultural_test_passed: data.project_draft.cultural_test_passed || [],
        cultural_test_failed: data.project_draft.cultural_test_failed || [],
      })
      onReanalyze()
    } finally {
      setLoading(false)
    }
  }

  const startReview = async () => {
    if (!sessionId) return
    setLoading(true)
    setReviewing(true)
    try {
      const data = await callEndpoint('/api/intake/cultural-test', {
        session_id: sessionId,
        country_code: country.country_code,
        country_name: country.country_name,
        action: 'start_review',
        incentive_name: country.incentive_name,
        score_info: country.score_info,
      })
      setMessages([{
        role: 'assistant',
        text: data.reply,
        score: { current: data.current_score, required: data.required_score, total: data.total_possible },      
      }])
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async () => {
    if (!input.trim() || !sessionId || loading) return
    const text = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text }])
    setLoading(true)
    try {
      const data = await callEndpoint('/api/intake/cultural-test-message', {
        session_id: sessionId,
        country_code: country.country_code,
        message: text,
      })
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: data.reply,
        score: { current: data.current_score, required: data.required_score, total: data.total_possible },      
      }])
      if (data.is_complete && data.verdict) {
        setVerdict(data.verdict)
        onProjectUpdate({
          ...project,
          cultural_test_passed: data.project_draft.cultural_test_passed || [],
          cultural_test_failed: data.project_draft.cultural_test_failed || [],
        })
        onReanalyze()
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-8">
        <div className="space-y-1.5">
          <h4 className="text-lg font-bold font-serif tracking-tight">{country.country_name}</h4>
          <div className="flex items-center gap-3">
            <span className="text-[10px] font-black uppercase tracking-widest text-gallery-accent">{country.incentive_name}</span>
            <span className="text-[10px] font-bold text-neutral-300 uppercase tracking-widest">/ {country.score_info}</span>
          </div>
        </div>

        {status === 'unknown' && !reviewing && (
          <div className="flex items-center gap-4">
            <button
              onClick={() => markStatus('pass')}
              className="text-[10px] font-black tracking-widest px-3 py-1.5 border border-neutral-200 hover:border-emerald-500 hover:text-emerald-600 transition-all uppercase"
            >
              [Pass]
            </button>
            <button
              onClick={() => markStatus('fail')}
              className="text-[10px] font-black tracking-widest px-3 py-1.5 border border-neutral-200 hover:border-red-500 hover:text-red-600 transition-all uppercase"
            >
              [Fail]
            </button>
            <button
              onClick={startReview}
              className="text-[10px] font-black tracking-widest px-4 py-1.5 bg-gallery-text text-white hover:bg-gallery-accent transition-all uppercase flex items-center gap-2"
            >
              <MessageSquare className="h-3 w-3" />
              Start Review
            </button>
          </div>
        )}

        {(status === 'pass' || status === 'fail') && (
          <div className="flex items-center gap-6">
            <div className={`flex items-center gap-2 px-3 py-1 border font-black text-[9px] uppercase tracking-widest ${
              status === 'pass' ? 'border-emerald-500 text-emerald-600 bg-emerald-50' : 'border-red-500 text-red-600 bg-red-50'
            }`}>
              {status === 'pass' ? <CheckCircle2 className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}  
              {status === 'pass' ? 'Validated' : 'Rejected'}
            </div>
            <button
              onClick={() => {
                onProjectUpdate({
                  ...project,
                  cultural_test_passed: (project.cultural_test_passed || []).filter(c => c !== country.country_code),
                  cultural_test_failed: (project.cultural_test_failed || []).filter(c => c !== country.country_code),
                })
                onReanalyze()
              }}
              className="text-neutral-300 hover:text-gallery-accent transition-colors"
              title="Reset"
            >
              <RotateCcw className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {reviewing && !verdict && (
        <div className="pl-8 border-l-2 border-neutral-100 space-y-8 animate-in slide-in-from-left-2 duration-500">
          <div className="space-y-8">
            {messages.map((msg, i) => (
              <div key={i} className="space-y-3">
                <span className="text-[9px] font-black uppercase tracking-widest text-neutral-300">
                  {msg.role === 'user' ? 'Producer Response' : 'Compliance Query'}
                </span>
                <p className="text-sm normal-case leading-relaxed max-w-xl text-neutral-600">
                  {msg.text}
                </p>
                {msg.role === 'assistant' && msg.score?.current !== undefined && (
                  <div className="inline-block px-2 py-1 bg-neutral-100 text-[9px] font-black uppercase tracking-widest">
                    Current Valuation: {msg.score.current} / {msg.score.required} required
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-4">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMessage()}
              placeholder="Provide evidence..."
              className="flex-1 border-b-2 border-neutral-100 focus:border-gallery-accent py-2 text-sm focus:outline-none transition-colors"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="text-[10px] font-black tracking-widest uppercase hover:text-gallery-accent transition-colors"
            >
              Submit Response
            </button>
          </div>
        </div>
      )}

      {verdict && (
        <div className={`mt-6 p-4 border flex items-center gap-3 text-xs font-black uppercase tracking-widest animate-in zoom-in-95 ${
          verdict === 'pass' ? 'border-emerald-500 text-emerald-600 bg-emerald-50' : 'border-red-500 text-red-600 bg-red-50'
        }`}>
          {verdict === 'pass' ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}     
          Verdict: {country.country_name} test {verdict === 'pass' ? 'Passed' : 'Failed'}
        </div>
      )}
    </div>
  )
}
