import { useState } from 'react'
import type { Scenario, CoproductionPartner, EligibleIncentive, NearMiss, Requirement } from '../types'
import { SourceBadge } from './SourceLink'
import { ChevronDown, ChevronUp, CheckCircle2, AlertCircle, ArrowRight, HelpCircle } from 'lucide-react'

type DocOpenHandler = (documentId: number, annotationId?: number | null) => void

interface Props {
  scenarios: Scenario[]
  budget: number
  currency: string
  onDocumentOpen?: DocOpenHandler
}

function fmt(amount: number, currency: string) {
  return `${currency} ${amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

export function ScenarioList({ scenarios, budget, currency, onDocumentOpen }: Props) {
  if (scenarios.length === 0) return null

  return (
    <div className="space-y-8">
      {scenarios.map((scenario, idx) => (
        <ScenarioCard key={idx} scenario={scenario} index={idx} currency={currency} onDocumentOpen={onDocumentOpen} />
      ))}
    </div>
  )
}

function ScenarioCard({ scenario, index, currency, onDocumentOpen }: { scenario: Scenario; index: number; currency: string; onDocumentOpen?: DocOpenHandler }) {
  const [open, setOpen] = useState(index === 0)
  
  // Calculate total confirmed vs potential
  const confirmedTotal = scenario.estimated_total_financing_amount
  const potentialTotal = scenario.near_misses?.reduce((sum, nm) => sum + (nm.potential_benefit_amount || 0), 0) || 0
  const confirmedPct = scenario.estimated_total_financing_percent

  return (
    <div className={`border-2 transition-all ${open ? 'border-black bg-white shadow-xl' : 'border-neutral-200 bg-neutral-50 hover:border-neutral-300'}`}>
      {/* HEADER: Summary of the Deal */}
      <button 
        onClick={() => setOpen(!open)}
        className="w-full p-6 flex flex-wrap items-center justify-between gap-6 text-left"
      >
        <div className="flex items-center gap-6">
          <div className="h-12 w-12 flex items-center justify-center bg-black text-white font-bold text-xl">
            {index + 1}
          </div>
          <div>
            <h3 className="text-2xl font-bold tracking-tight">
              {scenario.partners.map(p => p.country_name).join(' + ')}
            </h3>
            <p className="text-sm text-neutral-500 font-medium">
              Estimated incentive recovery: <span className="text-black font-bold">{fmt(confirmedTotal, currency)}</span> ({confirmedPct}% of budget)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-8">
          {potentialTotal > 0 && (
            <div className="text-right px-4 border-r border-neutral-200">
              <span className="block text-[10px] font-black uppercase text-amber-600 tracking-widest">Unclaimed Potential</span>
              <span className="text-lg font-bold text-amber-600">+{fmt(potentialTotal, currency)}</span>
            </div>
          )}
          {open ? <ChevronUp /> : <ChevronDown />}
        </div>
      </button>

      {open && (
        <div className="border-t-2 border-neutral-100 p-8 space-y-12 animate-in fade-in slide-in-from-top-1">
          
          {/* Rationale */}
          <div className="bg-neutral-50 p-6 border-l-4 border-black">
            <p className="text-lg leading-relaxed font-medium">"{scenario.rationale}"</p>
          </div>

          {/* 1. ELIGIBLE SECTION */}
          <section className="space-y-6">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center">
                <CheckCircle2 size={20} />
              </div>
              <h4 className="text-xl font-bold">Eligible Incentives</h4>
              <span className="text-sm text-neutral-400 font-medium">(Confirmed based on your current project)</span>
            </div>

            <div className="grid gap-4 pl-11">
              {scenario.partners.flatMap(p => p.eligible_incentives).map((inc, i) => (
                <div key={i} className="border border-neutral-200 p-5 flex justify-between items-start">
                  <div>
                    <p className="font-bold text-lg uppercase tracking-tight">{inc.name} ({inc.country_name})</p>
                    <p className="text-neutral-500 mt-1 max-w-xl">{inc.benefit?.benefit_explanation}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {inc.benefit?.sources.map((s, idx) => (
                        <SourceBadge key={idx} source={s} onDocumentOpen={onDocumentOpen} />
                      ))}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xl font-bold text-emerald-600">+{fmt(inc.benefit?.benefit_amount || 0, inc.benefit?.benefit_currency || currency)}</span>
                    <span className="block text-xs font-bold text-neutral-400 mt-1">{inc.rebate_percent}% REBATE</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* 2. NEAR MISSES SECTION */}
          {scenario.near_misses && scenario.near_misses.length > 0 && (
            <section className="space-y-6">
              <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center">
                  <AlertCircle size={20} />
                </div>
                <h4 className="text-xl font-bold">Missing Opportunities</h4>
                <span className="text-sm text-neutral-400 font-medium">(You are close to qualifying for these)</span>
              </div>

              <div className="grid gap-4 pl-11">
                {scenario.near_misses.map((nm, i) => (
                  <div key={i} className="border-2 border-amber-100 bg-amber-50/20 p-6">
                    <div className="flex justify-between items-start mb-6">
                      <div>
                        <p className="font-bold text-lg uppercase tracking-tight text-amber-800">{nm.incentive_name}</p>
                        <p className="text-sm text-amber-700 font-medium">Gap: {nm.gap_category}</p>
                      </div>
                      <div className="text-right">
                        <span className="text-xl font-bold text-amber-600">+{fmt(nm.potential_benefit_amount || 0, nm.potential_benefit_currency || currency)}</span>
                        <span className="block text-xs font-bold text-neutral-400 mt-1">AVAILABLE IF RESOLVED</span>
                      </div>
                    </div>

                    {/* ACTION PLAN */}
                    <div className="bg-white border border-amber-200 p-4 flex items-center gap-4">
                      <div className="bg-amber-600 text-white text-[10px] font-black px-2 py-1 uppercase">Action Required</div>
                      <p className="font-bold text-neutral-800">{nm.gap_description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* 3. COMPLIANCE CHECKLIST */}
          <section className="space-y-6 pt-6 border-t border-neutral-100">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-neutral-100 text-neutral-700 flex items-center justify-center">
                <HelpCircle size={20} />
              </div>
              <h4 className="text-xl font-bold">What you need to do</h4>
              <span className="text-sm text-neutral-400 font-medium">(Administrative & creative requirements)</span>
            </div>

            <ul className="grid gap-3 pl-11">
              {scenario.requirements.map((r, i) => (
                <li key={i} className="flex items-start gap-4 p-4 border border-neutral-100 bg-neutral-50/50">
                  <ArrowRight size={16} className="mt-1 shrink-0 text-neutral-400" />
                  <span className="text-neutral-700 font-medium">{r.description}</span>
                </li>
              ))}
            </ul>
          </section>

        </div>
      )}
    </div>
  )
}
