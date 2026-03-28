import { useState, useEffect, useCallback } from 'react'
import { API_BASE_URL } from './config'
import type { ProjectInput, AnalyzeResponse } from './types'
import { ProjectForm } from './components/ProjectForm'
import { ScenarioList } from './components/ScenarioList'
import { IntakeChat } from './components/IntakeChat'
import { CulturalTestPanel } from './components/CulturalTestPanel'
import { DocumentPanel } from './components/DocumentPanel'
import { Calculator, MessageSquare, Info, ArrowRight } from 'lucide-react'

const DEFAULT_PROJECT: ProjectInput = {
  title: '',
  format: 'feature_fiction',
  stage: 'production',
  budget: 0,
  budget_currency: 'EUR',
  budget_min: undefined,
  budget_max: undefined,
  shoot_locations_flexible: false,
  open_to_copro_countries: [],
  director_nationalities: [],
  producer_nationalities: [],
  production_company_countries: [],
  languages: [],
  development_fraction: 0.05,
  above_the_line_fraction: 0.20,
  production_btl_fraction: 0.40,
  post_production_btl_fraction: 0.25,
  other_fraction: 0.10,
  post_production_country: undefined,
  shoot_locations: [{ country: '', percent: 0 }],
  spend_allocations: [],
  stages: [],
  post_flexible: false,
  vfx_flexible: false,
  has_coproducer: [],
  willing_add_coproducer: true,
  streamer_attached: false,
  cultural_test_passed: [],
  cultural_test_failed: [],
}

type InputMode = 'form' | 'interview'

function App() {
  const [project, setProject] = useState<ProjectInput>(DEFAULT_PROJECT)
  const [response, setResponse] = useState<AnalyzeResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [stats, setStats] = useState({ countries: 0, incentives: 0, treaties: 0 })
  const [inputMode, setInputMode] = useState<InputMode>('interview')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [docViewer, setDocViewer] = useState<{ documentId: number; annotationId?: number | null } | null>(null) 

  const handleDocumentOpen = useCallback((documentId: number, annotationId?: number | null) => {
    setDocViewer({ documentId, annotationId })
  }, [])

  useEffect(() => {
    fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {})
  }, [])

  const analyze = async () => {
    if (!project.budget || project.budget <= 0) {
      setError('Please enter a budget to begin.')
      return
    }
    setLoading(true)
    setError(null)
    setResponse(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/projects/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(project),
      })
      if (!res.ok) throw new Error(await res.text())
      const data: AnalyzeResponse = await res.json()
      setResponse(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  const scenarioCount = response?.scenarios.length ?? 0

  return (
    <div className="min-h-screen bg-gallery-base text-gallery-text selection:bg-gallery-accent selection:text-white">
      {/* High-End Header */}
      <header className="border-b border-neutral-100 bg-white sticky top-0 z-50">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-12">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 bg-gallery-text flex items-center justify-center rounded-sm">
                <span className="text-white font-serif font-bold text-lg">C</span>
              </div>
              <h1 className="text-xl font-bold tracking-tight font-serif">CoPro Calculator</h1>
            </div>
          </div>

          <div className="hidden lg:flex items-center gap-4 text-[10px] font-bold text-neutral-300">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            LIVE DATA &middot; {stats.countries} REGIONS &middot; {stats.treaties} TREATIES
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-12">
        {/* Simple Introduction */}
        <section className="mb-12 pb-8 border-b border-neutral-100">
          <p className="text-lg text-neutral-600 leading-relaxed max-w-5xl">
            Input your project details to find the international film funds and tax credits you qualify for today.
            The calculator also identifies additional financing you could unlock through minor logistical changes or by adding a co-production partner.
            Every scenario is transparent: click any result to inspect the underlying math and cited treaty texts.
            Start a <strong>Chat</strong> to walk through your project details (or upload a treatment), or use <strong>Manual</strong> mode to input all your data directly.
          </p>
        </section>

        <div className="grid gap-16 lg:grid-cols-12">
          {/* Left: Project Definition */}
          <section className="lg:col-span-5 xl:col-span-4">
            <div className="lg:sticky lg:top-32 space-y-8">
              <div>
                <h2 className="text-2xl font-bold font-serif tracking-tight">Project details</h2>
                <p className="mt-2 text-sm text-neutral-500">Provide your film's basics to see available financing.</p>
              </div>

              <div className="flex p-1 bg-neutral-100 rounded-sm">
                <button
                  onClick={() => setInputMode('interview')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-[11px] font-bold transition-all ${
                    inputMode === 'interview' ? 'bg-white text-gallery-text shadow-sm' : 'text-neutral-400 hover:text-neutral-600'
                  }`}
                >
                  <MessageSquare className="h-3.5 w-3.5" />
                  CHAT
                </button>
                <button
                  onClick={() => setInputMode('form')}
                  className={`flex-1 flex items-center justify-center gap-2 py-2.5 text-[11px] font-bold transition-all ${
                    inputMode === 'form' ? 'bg-white text-gallery-text shadow-sm' : 'text-neutral-400 hover:text-neutral-600'
                  }`}
                >
                  <Calculator className="h-3.5 w-3.5" />
                  MANUAL
                </button>
              </div>

              <div className="card p-6">
                {inputMode === 'form' ? (
                  <ProjectForm
                    project={project}
                    onChange={setProject}
                    onAnalyze={analyze}
                    loading={loading}
                    error={error}
                  />
                ) : (
                  <IntakeChat
                    onProjectReady={(draft) => setProject(draft)}
                    onAnalyze={analyze}
                    onSessionStart={setSessionId}
                  />
                )}
              </div>
            </div>
          </section>

          {/* Right: Results */}
          <section className="lg:col-span-7 xl:col-span-8">
            {!response && !loading && (
              <div className="h-full flex flex-col items-center justify-center py-32 text-center border-2 border-dashed border-neutral-100 rounded-sm">
                <div className="p-4 bg-neutral-50 rounded-full mb-6">
                  <ArrowRight className="h-8 w-8 text-neutral-300" />
                </div>
                <h3 className="text-xl font-bold font-serif text-neutral-400">Ready to analyze</h3>
                <p className="mt-2 text-sm text-neutral-400 max-w-xs mx-auto">
                  Fill in the project profile on the left to see potential savings and treaty options.
                </p>
              </div>
            )}

            {loading && (
              <div className="py-32 text-center space-y-6">
                <div className="inline-block h-10 w-10 border-2 border-gallery-accent border-t-transparent animate-spin rounded-full" />
                <p className="text-[11px] font-bold tracking-[0.3em] text-neutral-400 uppercase">Calculating Scenarios...</p>
              </div>
            )}

            {response && (
              <div className="space-y-12 animate-in fade-in duration-700">
                <header className="space-y-4">
                  <div className="flex items-end justify-between border-b border-gallery-text pb-6">
                    <h2 className="text-3xl font-bold font-serif tracking-tight">Financing Scenarios</h2>       
                    <div className="text-[11px] font-black uppercase tracking-widest text-gallery-accent bg-gallery-accent/5 px-3 py-1 border border-gallery-accent/20">
                      {scenarioCount} OPTIONS FOUND
                    </div>
                  </div>
                  <p className="text-sm text-neutral-500 italic leading-relaxed">"{response.project_summary}"</p>
                </header>

                <CulturalTestPanel
                  scenarios={response.scenarios}
                  project={project}
                  sessionId={sessionId}
                  onProjectUpdate={setProject}
                  onReanalyze={analyze}
                />

                <ScenarioList
                  scenarios={response.scenarios}
                  budget={project.budget}
                  currency={project.budget_currency}
                  onDocumentOpen={handleDocumentOpen}
                />

                <footer className="mt-24 pt-8 border-t border-neutral-100 flex items-start gap-4">
                  <Info className="h-4 w-4 text-neutral-300 shrink-0 mt-0.5" />
                  <p className="text-[10px] text-neutral-400 leading-relaxed uppercase tracking-wider">
                    Disclaimer: {response.data_disclaimer}
                  </p>
                </footer>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* Document Slide-over */}
      {docViewer && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/10 backdrop-blur-[1px]"
            onClick={() => setDocViewer(null)}
          />
          <DocumentPanel
            documentId={docViewer.documentId}
            annotationId={docViewer.annotationId}
            onClose={() => setDocViewer(null)}
          />
        </>
      )}
    </div>
  )
}

export default App
