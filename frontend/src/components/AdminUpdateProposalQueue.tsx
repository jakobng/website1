import { useState, useEffect } from 'react'
import { API_BASE_URL } from '../config'

interface Proposal {
  id: number
  incentive_id: number
  incentive_name: string
  incentive_country: string
  field_name: string
  old_value: string | null
  new_value: string
  proposed_source_url: string
  proposed_source_description: string
  proposer_email: string
  status: string
  created_at: string
  reviewed_at: string | null
  reviewed_by: string | null
  notes: string | null
}

interface Props {
  initialStatus?: string  // "pending", "approved", "rejected"
}

export function AdminUpdateProposalQueue({ initialStatus = 'pending' }: Props) {
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState(initialStatus)
  const [reviewingId, setReviewingId] = useState<number | null>(null)
  const [reviewNotes, setReviewNotes] = useState('')

  useEffect(() => {
    loadProposals()
  }, [status])

  const loadProposals = async () => {
    setLoading(true)
    try {
      const url = `/api/admin/update-proposals${status ? `?status=${status}` : ''}`
      const response = await fetch(url)
      if (!response.ok) throw new Error('Failed to load proposals')
      const data = await response.json()
      setProposals(data)
    } catch (err) {
      console.error('Failed to load proposals:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleReview = async (proposalId: number, action: 'approve' | 'reject') => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/admin/update-proposals/${proposalId}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action,
          notes: reviewNotes || null,
        }),
      })
      if (!response.ok) throw new Error('Failed to review proposal')

      // Reload proposals
      setReviewingId(null)
      setReviewNotes('')
      await loadProposals()
    } catch (err) {
      console.error('Failed to review proposal:', err)
    }
  }

  return (
    <div className="space-y-4">
      {/* Status filter */}
      <div className="flex gap-2">
        {['pending', 'approved', 'rejected'].map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              status === s
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
            }`}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
            {s === 'pending' && proposals.length > 0 && (
              <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold bg-red-100 text-red-700">
                {proposals.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Proposals list */}
      {loading ? (
        <div className="text-center py-8 text-slate-500">Loading...</div>
      ) : proposals.length === 0 ? (
        <div className="text-center py-8 text-slate-500">
          No {status} proposals
        </div>
      ) : (
        <div className="space-y-2">
          {proposals.map((proposal) => (
            <div key={proposal.id} className="border border-slate-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
              {/* Header */}
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-medium text-slate-900 truncate">
                      {proposal.incentive_name}
                    </h3>
                    <span className="text-xs text-slate-500">
                      ({proposal.incentive_country})
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">
                    {proposal.field_name}: {proposal.old_value || '(not set)'} → {proposal.new_value}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-500">
                    {new Date(proposal.created_at).toLocaleDateString()}
                  </p>
                  <p className="text-[10px] text-slate-400">
                    {proposal.proposer_email}
                  </p>
                </div>
              </div>

              {/* Source */}
              <div className="mb-3 p-2.5 bg-slate-50 rounded-md">
                <p className="text-xs font-medium text-slate-700 mb-0.5">Source</p>
                <a
                  href={proposal.proposed_source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-indigo-600 hover:underline block truncate"
                  title={proposal.proposed_source_url}
                >
                  {proposal.proposed_source_description || proposal.proposed_source_url}
                </a>
              </div>

              {/* Actions or result */}
              {proposal.status === 'pending' ? (
                <div className="flex gap-2">
                  {reviewingId === proposal.id ? (
                    <div className="space-y-2 w-full">
                      <textarea
                        value={reviewNotes}
                        onChange={(e) => setReviewNotes(e.target.value)}
                        placeholder="Review notes (optional)..."
                        className="w-full px-2 py-1 text-xs rounded border border-slate-300 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500"
                        rows={2}
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleReview(proposal.id, 'approve')}
                          className="flex-1 px-2 py-1.5 bg-emerald-600 text-white text-xs font-medium rounded hover:bg-emerald-700 transition-colors"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleReview(proposal.id, 'reject')}
                          className="flex-1 px-2 py-1.5 bg-red-600 text-white text-xs font-medium rounded hover:bg-red-700 transition-colors"
                        >
                          Reject
                        </button>
                        <button
                          onClick={() => setReviewingId(null)}
                          className="flex-1 px-2 py-1.5 bg-slate-300 text-slate-700 text-xs font-medium rounded hover:bg-slate-400 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => setReviewingId(proposal.id)}
                      className="w-full px-3 py-1.5 border border-indigo-300 bg-indigo-50 text-indigo-700 text-xs font-medium rounded hover:bg-indigo-100 transition-colors"
                    >
                      Review
                    </button>
                  )}
                </div>
              ) : (
                <div className="flex items-start gap-3 p-2.5 bg-slate-50 rounded-md">
                  <div className="text-xs">
                    <p className={`font-medium ${
                      proposal.status === 'approved' ? 'text-emerald-700' : 'text-red-700'
                    }`}>
                      {proposal.status === 'approved' ? 'Approved' : 'Rejected'}
                    </p>
                    {proposal.reviewed_by && (
                      <p className="text-slate-500 mt-0.5">by {proposal.reviewed_by}</p>
                    )}
                    {proposal.notes && (
                      <p className="text-slate-600 mt-1 italic">{proposal.notes}</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
