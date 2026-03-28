import { useState, useEffect, useCallback } from 'react'
import { API_BASE_URL } from '../config'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import type { DocumentInfo, DocumentAnnotation } from '../types'

// Configure pdf.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

interface DocumentPanelProps {
  documentId: number
  annotationId?: number | null
  onClose: () => void
}

const LANG_LABELS: Record<string, string> = {
  en: 'ENGLISH',
  sv: 'SWEDISH',
  no: 'NORWEGIAN',
  fi: 'FINNISH',
  da: 'DANISH',
  is: 'ICELANDIC',
}

export function DocumentPanel({ documentId, annotationId, onClose }: DocumentPanelProps) {
  const [doc, setDoc] = useState<DocumentInfo | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [activeAnnotation, setActiveAnnotation] = useState<DocumentAnnotation | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Fetch document metadata
  useEffect(() => {
    fetch(`${API_BASE_URL}/api/documents/${documentId}`)
      .then(r => {
        if (!r.ok) throw new Error('Document not found')
        return r.json()
      })
      .then((data: DocumentInfo) => {
        setDoc(data)
        // Navigate to the requested annotation
        if (annotationId) {
          const ann = data.annotations.find(a => a.id === annotationId)
          if (ann) {
            setActiveAnnotation(ann)
            setCurrentPage(ann.page_number)
          }
        }
      })
      .catch(e => setError(e.message))
  }, [documentId, annotationId])

  const onDocumentLoadSuccess = useCallback(({ numPages: n }: { numPages: number }) => {
    setNumPages(n)
  }, [])

  const goToAnnotation = (ann: DocumentAnnotation) => {
    setActiveAnnotation(ann)
    setCurrentPage(ann.page_number)
  }

  // Custom text renderer for highlighting
  const customTextRenderer = useCallback(
    ({ str }: { str: string }) => {
      if (!activeAnnotation?.search_text) return str
      const searchText = activeAnnotation.search_text
      const idx = str.toLowerCase().indexOf(searchText.toLowerCase())
      if (idx === -1) return str
      const before = str.slice(0, idx)
      const match = str.slice(idx, idx + searchText.length)
      const after = str.slice(idx + searchText.length)
      // Using cinema-amber for highlighting
      return `${before}<mark style="background-color: #FFB400; color: #000; padding: 1px 0;">${match}</mark>${after}`
    },
    [activeAnnotation]
  )

  if (error) {
    return (
      <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-cinema-gray bg-cinema-black shadow-2xl font-mono">
        <div className="flex items-center justify-between border-b border-cinema-gray px-4 py-3">
          <span className="text-xs font-bold text-red-500 uppercase tracking-widest">[ERR]: {error}</span>      
          <button onClick={onClose} className="border border-cinema-gray p-1 text-cinema-gray hover:text-white">
            <CloseIcon />
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-cinema-gray bg-cinema-black shadow-2xl font-mono">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-cinema-gray bg-cinema-slate/50 px-5 py-4">
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-xs font-bold uppercase tracking-[0.2em] text-white">
            {doc?.title ?? 'LOADING_DOCUMENT...'}
          </h3>
          {doc && (
            <div className="mt-1.5 flex items-center gap-3 text-[10px] font-bold text-cinema-gray uppercase">   
              {doc.publisher && <span className="truncate max-w-[200px]">{doc.publisher}</span>}
              {doc.language !== 'en' && (
                <span className="border border-cinema-amber/40 bg-cinema-amber/5 px-1.5 py-0.5 text-cinema-amber">
                  {LANG_LABELS[doc.language] ?? doc.language}
                </span>
              )}
              <span className="border border-cinema-gray px-1.5 py-0.5">{numPages || doc.page_count} PAGES</span>
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="ml-4 border border-cinema-gray p-2 text-cinema-gray hover:border-cinema-amber hover:text-cinema-amber transition-colors"
        >
          <CloseIcon />
        </button>
      </div>

      {/* Active annotation summary */}
      {activeAnnotation && (
        <div className="border-b border-cinema-amber/30 bg-cinema-amber/5 px-5 py-4">
          <div className="flex items-start gap-3">
             <span className="text-xs font-bold text-cinema-amber mt-0.5">[!]</span>
             <div className="flex-1">
                <p className="text-[11px] font-bold text-cinema-amber uppercase tracking-tight">
                  {activeAnnotation.clause_reference && (
                    <span className="mr-2 border border-cinema-amber px-1.5 py-0.5 text-[9px] font-bold">       
                      {activeAnnotation.clause_reference}
                    </span>
                  )}
                  {activeAnnotation.english_summary}
                </p>
                {activeAnnotation.original_text && (
                  <p className="mt-2 text-[10px] italic leading-relaxed text-cinema-amber/70 border-l border-cinema-amber/30 pl-3">
                    SOURCE_TRANSCRIPT: "{activeAnnotation.original_text}"
                  </p>
                )}
             </div>
          </div>
        </div>
      )}

      {/* Annotation chips */}
      {doc && doc.annotations.length > 1 && (
        <div className="flex flex-wrap gap-2 border-b border-cinema-gray px-5 py-3 bg-cinema-black/40">
          <span className="text-[9px] font-bold text-cinema-gray uppercase mr-1 mt-1">Ref_Points:</span>        
          {doc.annotations.map(ann => (
            <button
              key={ann.id}
              onClick={() => goToAnnotation(ann)}
              className={`border px-2 py-0.5 text-[9px] font-bold uppercase transition-colors ${
                activeAnnotation?.id === ann.id
                  ? 'border-cinema-amber bg-cinema-amber text-black'
                  : 'border-cinema-gray text-cinema-gray hover:border-cinema-light hover:text-white'
              }`}
            >
              {ann.clause_reference ?? `P.${ann.page_number}`}
            </button>
          ))}
        </div>
      )}

      {/* PDF viewer */}
      <div className="flex-1 overflow-auto bg-cinema-black/80 custom-scrollbar relative">
        <Document
          file={`${API_BASE_URL}/api/documents/${documentId}/file`}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <div className="flex h-full items-center justify-center py-20">
              <div className="h-10 w-10 animate-spin border-2 border-cinema-gray border-t-cinema-amber" />      
            </div>
          }
          error={
            <div className="flex h-full items-center justify-center py-20">
              <p className="text-xs font-bold text-red-500 uppercase tracking-widest">[ERR]: PDF_LOAD_FAILED</p>
            </div>
          }
        >
          <div className="flex justify-center p-6">
            <div className="shadow-[0_0_50px_rgba(0,0,0,0.5)] border border-cinema-gray">
              <Page
                pageNumber={currentPage}
                width={560}
                customTextRenderer={customTextRenderer}
                renderAnnotationLayer={false}
              />
            </div>
          </div>
        </Document>
        {/* Decorative corner markers */}
        <div className="absolute top-4 left-4 w-4 h-4 border-t border-l border-cinema-amber/30 pointer-events-none" />
        <div className="absolute top-4 right-4 w-4 h-4 border-t border-r border-cinema-amber/30 pointer-events-none" />
        <div className="absolute bottom-4 left-4 w-4 h-4 border-b border-l border-cinema-amber/30 pointer-events-none" />
        <div className="absolute bottom-4 right-4 w-4 h-4 border-b border-r border-cinema-amber/30 pointer-events-none" />
      </div>

      {/* Page navigation */}
      {numPages > 0 && (
        <div className="flex items-center justify-between border-t border-cinema-gray bg-cinema-black px-6 py-3">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="border border-cinema-gray px-3 py-1.5 text-[10px] font-bold text-cinema-gray hover:border-cinema-amber hover:text-cinema-amber disabled:opacity-20 transition-colors uppercase"
          >
            [PREV]
          </button>
          <span className="text-[10px] font-bold text-cinema-amber uppercase tracking-widest tabular-nums">     
            PAGE {currentPage} // {numPages}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))}
            disabled={currentPage >= numPages}
            className="border border-cinema-gray px-3 py-1.5 text-[10px] font-bold text-cinema-gray hover:border-cinema-amber hover:text-cinema-amber disabled:opacity-20 transition-colors uppercase"
          >
            [NEXT]
          </button>
        </div>
      )}
    </div>
  )
}

function CloseIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}
