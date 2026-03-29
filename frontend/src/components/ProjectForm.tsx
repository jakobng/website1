import { useState, useEffect } from 'react'
import { API_BASE_URL } from '../config'
import type { ProjectInput, ShootLocation, CountryOption } from '../types'
import { Plus, X, ChevronDown } from 'lucide-react'

const FORMATS = [
  { value: 'feature_fiction', label: 'Feature Fiction' },
  { value: 'documentary', label: 'Documentary' },
  { value: 'series', label: 'Series' },
  { value: 'animation', label: 'Animation' },
]

const STAGES = [
  { value: 'development', label: 'Development' },
  { value: 'production', label: 'Production' },
  { value: 'post', label: 'Post-Production' },
]

interface Props {
  project: ProjectInput
  onChange: (project: ProjectInput) => void
  onAnalyze: () => void
  loading: boolean
  error: string | null
}

export function ProjectForm({ project, onChange, onAnalyze, loading, error }: Props) {
  const [countries, setCountries] = useState<CountryOption[]>([])

  useEffect(() => {
    fetch(`${API_BASE_URL}/api/countries`)
      .then((r) => r.json())
      .then(setCountries)
      .catch(() => {})
  }, [])

  const update = <K extends keyof ProjectInput>(key: K, value: ProjectInput[K]) => {
    onChange({ ...project, [key]: value })
  }

  const addShootLocation = () => {
    onChange({
      ...project,
      shoot_locations: [...project.shoot_locations, { country: '', percent: 0 }],
    })
  }

  const updateShootLocation = (index: number, loc: Partial<ShootLocation>) => {
    onChange({
      ...project,
      shoot_locations: project.shoot_locations.map((l, i) =>
        i === index ? { ...l, ...loc } : l
      ),
    })
  }

  const removeShootLocation = (index: number) => {
    onChange({
      ...project,
      shoot_locations: project.shoot_locations.filter((_, i) => i !== index),
    })
  }

  const totalShootPct = project.shoot_locations.reduce((sum, l) => sum + l.percent, 0)

  return (
    <div className="space-y-10">
      {/* Essentials */}
      <section className="space-y-5">
        <Field label="Title">
          <input
            type="text"
            value={project.title}
            onChange={(e) => update('title', e.target.value)}
            placeholder="Working project name"
            className="input"
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Format">
            <select value={project.format} onChange={(e) => update('format', e.target.value)} className="input bg-white">
              {FORMATS.map((f) => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Stage">
            <select value={project.stage} onChange={(e) => update('stage', e.target.value)} className="input bg-white">
              {STAGES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </Field>
        </div>
      </section>
{/* Finance */}
<section className="space-y-5">
  <Field label="Total Budget">
    <div className="flex gap-2">
      <div className="relative flex-1">
        <input
          type="number"
          min={1}
          value={project.budget || ''}
          onChange={(e) => update('budget', Math.max(0, parseFloat(e.target.value) || 0))}
          placeholder="0.00"
          className="input font-bold"
        />
      </div>
      <div className="w-24">
        <select
          value={project.budget_currency}
          onChange={(e) => update('budget_currency', e.target.value)}
          className="input bg-white font-bold"
        >
          <option value="EUR">EUR</option>
          <option value="USD">USD</option>
          <option value="GBP">GBP</option>
          <option value="AUD">AUD</option>
          <option value="CAD">CAD</option>
          <option value="CHF">CHF</option>
          <option value="JPY">JPY</option>
          <option value="CNY">CNY</option>
          <option value="INR">INR</option>
          <option value="BRL">BRL</option>
          <option value="MXN">MXN</option>
          <option value="ZAR">ZAR</option>
          <option value="KRW">KRW</option>
          <option value="SGD">SGD</option>
          <option value="NZD">NZD</option>
        </select>
      </div>
    </div>
  </Field>

  <BudgetBreakdown project={project} onChange={onChange} />
</section>

{/* Production */}
<section className="space-y-5">
        <div className="flex items-end justify-between">
          <span className="text-[10px] font-black uppercase tracking-widest text-neutral-400">Shooting Locations</span>
          <span className={`text-[10px] font-bold ${Math.abs(totalShootPct - 100) <= 1 ? 'text-emerald-600' : 'text-gallery-accent'}`}>
            {totalShootPct}% ALLOCATED
          </span>
        </div>

        <div className="space-y-3">
          {project.shoot_locations.map((loc, i) => (
            <div key={i} className="flex items-center gap-2 group">
              <div className="flex-1">
                <CountryInput
                  value={loc.country}
                  onChange={(v) => updateShootLocation(i, { country: v })}
                  countries={countries}
                  placeholder="Region"
                />
              </div>
              <div className="relative w-20">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={loc.percent || ''}
                  onChange={(e) => updateShootLocation(i, { percent: Math.max(0, Math.min(100, parseFloat(e.target.value) || 0)) })}
                  className="input pr-6 text-right"
                />
                <span className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-[10px] font-bold text-neutral-300">%</span>
              </div>
              <button
                type="button"
                onClick={() => removeShootLocation(i)}
                className="p-2 text-neutral-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
          <button
            type="button"
            onClick={addShootLocation}
            className="w-full py-2 border border-dashed border-neutral-200 text-[10px] font-bold tracking-widest text-neutral-400 hover:border-gallery-accent hover:text-gallery-accent transition-all flex items-center justify-center gap-2"
          >
            <Plus className="h-3.5 w-3.5" />
            ADD LOCATION
          </button>
        </div>
      </section>

      {/* Registry */}
      <section className="space-y-5">
        <Field label="Director Nationality">
          <MultiCountryInput
            values={project.director_nationalities}
            onCommit={(v) => update('director_nationalities', v)}
            countries={countries}
            placeholder="Add region"
          />
        </Field>
        <Field label="Producer Nationality">
          <MultiCountryInput
            values={project.producer_nationalities}
            onCommit={(v) => update('producer_nationalities', v)}
            countries={countries}
            placeholder="Add region"
          />
        </Field>
        <Field label="Production Company Location">
          <MultiCountryInput
            values={project.production_company_countries}
            onCommit={(v) => update('production_company_countries', v)}
            countries={countries}
            placeholder="Add region"
          />
        </Field>
      </section>

      {/* Cultural Tests */}
      <section className="space-y-5">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-widest text-neutral-400">Cultural Test Status</span>
        </div>
        <p className="text-[10px] text-neutral-400 leading-relaxed italic">
          Many incentives require passing a points-based cultural test.
          If you know your status for a specific region, mark it here.
        </p>
        <div className="space-y-4">
          <CulturalTestSection
            project={project}
            countries={countries}
            onChange={onChange}
          />
        </div>
      </section>

      {/* Logic */}
      <section className="space-y-4 pt-4 border-t border-neutral-100">
        <Toggle
          checked={project.shoot_locations_flexible}
          onChange={(v) => update('shoot_locations_flexible', v)}
          label="Flexible shooting"
        />
        <Toggle
          checked={project.post_flexible}
          onChange={(v) => update('post_flexible', v)}
          label="Flexible post-production"
        />
      </section>

      {/* CTA */}
      <div className="pt-4">
        <button
          type="button"
          onClick={onAnalyze}
          disabled={loading || !project.budget}
          className="btn-primary"
        >
          {loading ? 'PROCESSING...' : 'FIND CO-PRODUCTION OPTIONS'}
        </button>

        {error && (
          <p className="mt-4 text-xs font-bold text-red-500 text-center uppercase tracking-widest">{error}</p>  
        )}
      </div>
    </div>
  )
}

function BudgetBreakdown({ project, onChange }: {
  project: ProjectInput
  onChange: (project: ProjectInput) => void
}) {
  const [open, setOpen] = useState(false)

  const updateFrac = (key: keyof ProjectInput, val: number) => {
    onChange({ ...project, [key]: val / 100 })
  }

  const sections = [
    { label: 'Development', key: 'development_fraction' },
    { label: 'Above-the-Line', key: 'above_the_line_fraction' },
    { label: 'Production (BTL)', key: 'production_btl_fraction' },
    { label: 'Post-Production (BTL)', key: 'post_production_btl_fraction' },
    { label: 'Other (Legal/Cont.)', key: 'other_fraction' },
  ] as const

  const total = sections.reduce((sum, s) => sum + Math.round((project[s.key] as number) * 100), 0)

  return (
    <div className="space-y-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-[10px] font-bold text-neutral-400 uppercase tracking-widest hover:text-gallery-accent transition-colors"
      >
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} />
        Detailed Budget Allocation
      </button>

      {open && (
        <div className="space-y-5 p-4 bg-neutral-50 rounded-sm border border-neutral-100 animate-in slide-in-from-top-2">
          <div className="grid grid-cols-2 gap-x-4 gap-y-3">
            {sections.map((s) => (
              <Field key={s.key} label={`${s.label} %`}>
                <input
                  type="number" min={0} max={100}
                  value={Math.round((project[s.key] as number) * 100)}
                  onChange={(e) => updateFrac(s.key, parseFloat(e.target.value) || 0)}
                  className="input bg-white"
                />
              </Field>
            ))}
          </div>
          <div className="pt-2 flex justify-between items-center border-t border-neutral-200">
            <span className="text-[10px] font-bold text-neutral-400 uppercase">Total Allocation</span>
            <span className={`text-xs font-black ${total === 100 ? 'text-emerald-600' : 'text-red-500'}`}>{total}%</span>
          </div>
        </div>
      )}
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-black uppercase tracking-widest text-neutral-400">{label}</label>      
      {children}
    </div>
  )
}

function Toggle({ checked, onChange, label }: {
  checked: boolean
  onChange: (v: boolean) => void
  label: string
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex items-center gap-3 text-left group"
    >
      <div className={`h-4 w-4 rounded-sm border-2 transition-all flex items-center justify-center ${
        checked ? 'bg-gallery-accent border-gallery-accent' : 'bg-white border-neutral-200 group-hover:border-neutral-300'
      }`}>
        {checked && <div className="h-1.5 w-1.5 bg-white rounded-full" />}
      </div>
      <span className={`text-xs font-bold uppercase tracking-wide transition-colors ${checked ? 'text-gallery-text' : 'text-neutral-400 hover:text-neutral-600'}`}>{label}</span>
    </button>
  )
}

function CulturalTestSection({ project, countries, onChange }: {
  project: ProjectInput
  countries: CountryOption[]
  onChange: (p: ProjectInput) => void
}) {
  const [adding, setAdding] = useState(false)

  const remove = (code: string, type: 'passed' | 'failed') => {
    const key = type === 'passed' ? 'cultural_test_passed' : 'cultural_test_failed'
    onChange({ ...project, [key]: project[key].filter(c => c !== code) })
  }

  const add = (name: string, type: 'passed' | 'failed') => {
    const code = countries.find(c => c.name.toLowerCase() === name.toLowerCase())?.code
    if (!code) return
    const key = type === 'passed' ? 'cultural_test_passed' : 'cultural_test_failed'
    const other = type === 'passed' ? 'cultural_test_failed' : 'cultural_test_passed'

    onChange({
      ...project,
      [key]: Array.from(new Set([...project[key], code])),
      [other]: project[other].filter(c => c !== code)
    })
    setAdding(false)
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {project.cultural_test_passed.map(code => (
          <span key={code} className="flex items-center gap-1.5 bg-emerald-50 text-emerald-700 px-2 py-1 rounded-sm text-[10px] font-black border border-emerald-100">
            {countries.find(c => c.code === code)?.name || code} PASS
            <button onClick={() => remove(code, 'passed')} className="hover:text-emerald-900"><X className="h-3 w-3" /></button>
          </span>
        ))}
        {project.cultural_test_failed.map(code => (
          <span key={code} className="flex items-center gap-1.5 bg-red-50 text-red-700 px-2 py-1 rounded-sm text-[10px] font-black border border-red-100">
            {countries.find(c => c.code === code)?.name || code} FAIL
            <button onClick={() => remove(code, 'failed')} className="hover:text-red-900"><X className="h-3 w-3" /></button>
          </span>
        ))}
      </div>

      {!adding ? (
        <button
          onClick={() => setAdding(true)}
          className="text-[10px] font-bold text-gallery-accent border-b border-gallery-accent border-dotted hover:text-gallery-accent-dark"
        >
          + ADD MANUAL STATUS
        </button>
      ) : (
        <div className="flex items-center gap-2 p-3 bg-neutral-50 border border-neutral-100 rounded-sm">        
          <div className="flex-1">
            <CountryInput
              value=""
              onChange={(v) => {}}
              onSelect={(v) => {
                // We'll show a small sub-menu or just default to pass?
                // Let's do a simple prompt-like choice
                const type = window.confirm(`Mark ${v} as PASS? (Cancel for FAIL)`) ? 'passed' : 'failed'       
                add(v, type)
              }}
              countries={countries}
              placeholder="Search region..."
            />
          </div>
          <button onClick={() => setAdding(false)} className="text-xs text-neutral-400">Cancel</button>
        </div>
      )}
    </div>
  )
}

function CountryInput({
  value,
  onChange,
  onSelect,
  countries,
  placeholder,
}: {
  value: string
  onChange: (v: string) => void
  onSelect?: (v: string) => void
  countries: CountryOption[]
  placeholder?: string
}) {
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [focused, setFocused] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)

  const query = value.trim().toLowerCase()
  const suggestions = query.length >= 1
    ? countries.filter((c) =>
        c.name.toLowerCase().includes(query) || c.code.toLowerCase() === query
      )
    : []

  useEffect(() => {
    setSelectedIndex(0)
  }, [query])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((i) => {
        const nextIndex = (i + 1) % suggestions.length
        document.getElementById(`suggestion-${nextIndex}`)?.scrollIntoView({ block: 'nearest' })
        return nextIndex
      })
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((i) => {
        const nextIndex = (i - 1 + suggestions.length) % suggestions.length
        document.getElementById(`suggestion-${nextIndex}`)?.scrollIntoView({ block: 'nearest' })
        return nextIndex
      })
    } else if (e.key === 'Enter') {
      e.preventDefault()
      selectOption(suggestions[selectedIndex])
    } else if (e.key === 'Escape') {
      setShowSuggestions(false)
    }
  }

  const selectOption = (c: CountryOption) => {
    onChange(c.name)
    onSelect?.(c.name)
    setShowSuggestions(false)
  }

  const validateAndBlur = () => {
    setFocused(false)
    setTimeout(() => {
      setShowSuggestions(false)
      // Strict matching: if the typed value isn't an exact country name, clear it
      const exactMatch = countries.find(c => c.name.toLowerCase() === value.toLowerCase())
      if (!exactMatch && value !== '') {
        onChange('')
      }
    }, 200)
  }

  return (
    <div className="relative">
      <input
        type="text"
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setShowSuggestions(true)
        }}
        onKeyDown={handleKeyDown}
        onFocus={() => { setFocused(true); setShowSuggestions(true) }}
        onBlur={validateAndBlur}
        placeholder={placeholder}
        className="input uppercase font-bold"
        autoComplete="off"
      />
      {showSuggestions && focused && suggestions.length > 0 && (
        <ul className="absolute left-0 right-0 top-full z-20 mt-1 bg-white border border-neutral-100 shadow-xl rounded-sm py-1 max-h-60 overflow-y-auto">
          {suggestions.map((c, i) => (
            <li key={c.code} id={`suggestion-${i}`}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => selectOption(c)}
                className={`flex w-full items-center justify-between px-4 py-2 text-left text-xs transition-colors ${
                  i === selectedIndex ? 'bg-neutral-100' : 'hover:bg-neutral-50'
                }`}
              >
                <span className="font-bold uppercase">{c.name}</span>
                <span className="text-[10px] font-bold text-neutral-300">{c.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function MultiCountryInput({
  values,
  onCommit,
  countries,
  placeholder,
}: {
  values: string[]
  onCommit: (v: string[]) => void
  countries: CountryOption[]
  placeholder?: string
}) {
  const [draft, setDraft] = useState('')

  const handleSelect = (name: string) => {
    onCommit(Array.from(new Set([...values, name])))
    setDraft('')
  }

  const removeCountry = (index: number) => {
    onCommit(values.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {values.map((v, i) => (
          <span
            key={`${v}-${i}`}
            className="flex items-center gap-1.5 bg-neutral-100 px-2 py-1 rounded-sm text-[10px] font-black uppercase"
          >
            {v}
            <button onClick={() => removeCountry(i)} className="text-neutral-400 hover:text-red-500"><X className="h-3 w-3" /></button>
          </span>
        ))}
      </div>
      <CountryInput
        value={draft}
        onChange={setDraft}
        onSelect={handleSelect}
        countries={countries}
        placeholder={values.length === 0 ? placeholder : ""}
      />
    </div>
  )
}
