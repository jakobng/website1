import { useState } from 'react'
import type { EligibleIncentive } from '../types'

interface ReportIssueModalProps {
  incentive: EligibleIncentive
  isOpen: boolean
  onClose: () => void
  onSubmit: (proposal: any) => Promise<void>
}

export function ReportIssueModal({ incentive, isOpen, onClose, onSubmit }: ReportIssueModalProps) {
  const [step, setStep] = useState<'issue' | 'details' | 'success'>('issue')
  const [issueType, setIssueType] = useState<'stale' | 'incorrect'>('stale')
  const [fieldName, setFieldName] = useState('')
  const [newValue, setNewValue] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [sourceDesc, setSourceDesc] = useState('')
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSubmit = async () => {
    if (!fieldName || !newValue || !sourceUrl || !email) {
      setError('Please fill in all required fields')
      return
    }

    setLoading(true)
    setError(null)
    try {
      await onSubmit({
        incentive_id: incentive.id || 0,
        field_name: fieldName,
        new_value: newValue,
        proposed_source_url: sourceUrl,
        proposed_source_description: sourceDesc,
        proposer_email: email,
      })
      setStep('success')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit proposal')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setStep('issue')
    setIssueType('stale')
    setFieldName('')
    setNewValue('')
    setSourceUrl('')
    setSourceDesc('')
    setEmail('')
    setError(null)
    onClose()
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/20" onClick={handleClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="w-full max-w-md rounded-lg bg-white shadow-xl">
          {/* Header */}
          <div className="border-b border-slate-200 px-6 py-4">
            <h2 className="text-lg font-semibold text-slate-900">
              {step === 'success' ? 'Thank you!' : `Report issue: ${incentive.name}`}
            </h2>
          </div>

          {/* Body */}
          <div className="px-6 py-4 space-y-4">
            {step === 'issue' && (
              <>
                <p className="text-sm text-slate-600">
                  Found a problem with this incentive data?
                </p>
                <div className="space-y-2">
                  <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    issueType === 'stale'
                      ? 'border-indigo-300 bg-indigo-50'
                      : 'border-slate-200 hover:border-slate-300'
                  }`}>
                    <input
                      type="radio"
                      value="stale"
                      checked={issueType === 'stale'}
                      onChange={(e) => setIssueType(e.target.value as 'stale' | 'incorrect')}
                      className="w-4 h-4"
                    />
                    <div>
                      <p className="font-medium text-slate-900">Data is outdated</p>
                      <p className="text-xs text-slate-500">Rate, thresholds, or rules have changed</p>
                    </div>
                  </label>
                  <label className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    issueType === 'incorrect'
                      ? 'border-indigo-300 bg-indigo-50'
                      : 'border-slate-200 hover:border-slate-300'
                  }`}>
                    <input
                      type="radio"
                      value="incorrect"
                      checked={issueType === 'incorrect'}
                      onChange={(e) => setIssueType(e.target.value as 'stale' | 'incorrect')}
                      className="w-4 h-4"
                    />
                    <div>
                      <p className="font-medium text-slate-900">Data is wrong</p>
                      <p className="text-xs text-slate-500">The information was never correct</p>
                    </div>
                  </label>
                </div>
              </>
            )}

            {step === 'details' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Which field is wrong?
                  </label>
                  <select
                    value={fieldName}
                    onChange={(e) => setFieldName(e.target.value)}
                    className="w-full px-3 py-2 rounded-md border border-slate-300 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="">Select a field...</option>
                    <option value="rebate_percent">Rebate percentage</option>
                    <option value="min_qualifying_spend">Minimum qualifying spend</option>
                    <option value="min_total_budget">Minimum total budget</option>
                    <option value="max_cap_amount">Maximum cap amount</option>
                    <option value="local_crew_min_percent">Minimum local crew %</option>
                    <option value="notes">Notes / description</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    What is the correct value? *
                  </label>
                  <input
                    type="text"
                    value={newValue}
                    onChange={(e) => setNewValue(e.target.value)}
                    placeholder="e.g., 35% or €500,000"
                    className="w-full px-3 py-2 rounded-md border border-slate-300 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Official source URL *
                  </label>
                  <input
                    type="url"
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                    placeholder="https://example.com/..."
                    className="w-full px-3 py-2 rounded-md border border-slate-300 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Source description (optional)
                  </label>
                  <input
                    type="text"
                    value={sourceDesc}
                    onChange={(e) => setSourceDesc(e.target.value)}
                    placeholder="e.g., Official guidelines, March 2026"
                    className="w-full px-3 py-2 rounded-md border border-slate-300 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Your email *
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="your@email.com"
                    className="w-full px-3 py-2 rounded-md border border-slate-300 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                {error && (
                  <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">
                    {error}
                  </div>
                )}
              </>
            )}

            {step === 'success' && (
              <div className="text-center py-4">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-emerald-100 mb-3">
                  <svg className="w-6 h-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <p className="text-sm text-slate-600 mb-2">
                  Thank you for the report!
                </p>
                <p className="text-xs text-slate-500">
                  We've received your proposal and will review it shortly. You'll hear back at {email}.
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-slate-200 px-6 py-4 flex gap-2 justify-end">
            {step !== 'success' && (
              <>
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-4 py-2 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors"
                >
                  Cancel
                </button>
                {step === 'issue' && (
                  <button
                    type="button"
                    onClick={() => setStep('details')}
                    className="px-4 py-2 rounded-md bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
                  >
                    Next
                  </button>
                )}
                {step === 'details' && (
                  <>
                    <button
                      type="button"
                      onClick={() => setStep('issue')}
                      className="px-4 py-2 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-100 transition-colors"
                    >
                      Back
                    </button>
                    <button
                      type="button"
                      onClick={handleSubmit}
                      disabled={loading}
                      className="px-4 py-2 rounded-md bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50"
                    >
                      {loading ? 'Submitting...' : 'Submit report'}
                    </button>
                  </>
                )}
              </>
            )}
            {step === 'success' && (
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 rounded-md bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors"
              >
                Done
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
