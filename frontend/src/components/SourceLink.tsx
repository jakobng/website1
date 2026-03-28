import type { SourceReference } from '../types'

interface SourceProps {
  source: SourceReference
  onDocumentOpen?: (documentId: number, annotationId?: number | null) => void
}

export function SourceLink({ source, onDocumentOpen }: SourceProps) {
  const label = source.clause_reference
    ? `${source.description} (${source.clause_reference})`
    : source.description

  const hasPdf = source.document_ref && onDocumentOpen

  const commonClass = "inline-flex items-center gap-2 text-[9px] font-bold tracking-widest text-black hover:text-neutral-400 transition-colors uppercase border-b border-black pb-0.5"

  if (hasPdf) {
    return (
      <button
        type="button"
        onClick={() => onDocumentOpen(source.document_ref!.document_id, source.document_ref!.annotation_id)}
        className={commonClass}
      >
        [PDF]_{label}
      </button>
    )
  }

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className={commonClass}
    >
      [URL]_{label}
    </a>
  )
}

export function SourceBadge({ source, onDocumentOpen }: SourceProps) {
  const hasPdf = source.document_ref && onDocumentOpen

  const content = (
    <>
      <span className="max-w-[150px] truncate">{source.description}</span>
      {source.clause_reference && (
        <span className="ml-1 opacity-30">_{source.clause_reference}</span>
      )}
    </>
  )

  const className = "inline-flex items-center gap-2 border border-black px-2 py-0.5 text-[8px] font-bold text-black uppercase tracking-[0.2em] transition-all hover:bg-black hover:text-white"

  if (hasPdf) {
    return (
      <button
        type="button"
        onClick={() => onDocumentOpen(source.document_ref!.document_id, source.document_ref!.annotation_id)}
        className={className}
      >
        [DOC]_{content}
      </button>
    )
  }

  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
    >
      [REF]_{content}
    </a>
  )
}
