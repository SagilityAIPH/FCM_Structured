import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, FileText, PanelLeftClose, PanelLeftOpen, ZoomIn, ZoomOut, LoaderCircle } from 'lucide-react'
import { Button } from './ui/button'
import type { DocumentDetail } from '@/types'
import { getAPI } from '@/lib/bridge'
import { cn } from '@/lib/utils'

function Thumbnail({ id, page, selected, onClick }: {id: string; page: number; selected: boolean; onClick: () => void}) {
  const ref = useRef<HTMLButtonElement>(null)
  const [src, setSrc] = useState('')
  useEffect(() => {
    let active = true
    const observer = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) {
        observer.disconnect()
        void getAPI().then(api => api.render_page(id, page, .15)).then(value => { if (active) setSrc(value) }).catch(() => {})
      }
    })
    if (ref.current) observer.observe(ref.current)
    return () => { active = false; observer.disconnect() }
  }, [id, page])
  return <button ref={ref} className={cn('thumbnail', selected && 'selected')} aria-label={`Go to page ${page + 1}`} aria-current={selected ? 'page' : undefined} onClick={onClick}>
    {src ? <img src={src} alt="" /> : <div className="thumbnail-placeholder"><FileText size={18} /></div>}<span>{page + 1}</span>
  </button>
}

export default function PdfPreview({ doc }: {doc: DocumentDetail | null}) {
  const [page, setPage] = useState(0)
  const [zoom, setZoom] = useState(1)
  const [thumbnails, setThumbnails] = useState(false)
  const [image, setImage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  useEffect(() => { setPage(0); setImage(''); setZoom(1) }, [doc?.id])
  useEffect(() => {
    let active = true
    setError(''); setImage('')
    if (!doc?.is_pdf || page >= doc.pages) return
    setLoading(true)
    void getAPI().then(api => api.render_page(doc.id, page, Math.min(2.5, zoom * 1.5)))
      .then(value => { if (active) setImage(value) }).catch(err => { if (active) setError(String(err.message)) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [doc?.id, doc?.is_pdf, doc?.pages, page, zoom])
  return <section className="preview-panel" aria-label="Document preview">
    <div className="panel-heading"><span><FileText size={15} /> {doc?.name || 'No document selected'}</span><div className="flex items-center gap-1">
      <Button variant="ghost" size="icon" aria-label="Toggle thumbnails" disabled={!doc?.is_pdf} onClick={() => setThumbnails(!thumbnails)}>{thumbnails ? <PanelLeftClose /> : <PanelLeftOpen />}</Button>
    </div></div>
    <div className="preview-toolbar">
      <div className="flex items-center gap-1"><Button variant="ghost" size="icon" aria-label="Previous page" disabled={!doc?.is_pdf || page === 0} onClick={() => setPage(p => p - 1)}><ChevronLeft /></Button>
        <span className="tabular-nums">{doc?.is_pdf ? `${page + 1} / ${doc.pages}` : '—'}</span>
        <Button variant="ghost" size="icon" aria-label="Next page" disabled={!doc?.is_pdf || page + 1 >= doc.pages} onClick={() => setPage(p => p + 1)}><ChevronRight /></Button></div>
      <div className="flex items-center gap-1"><Button variant="ghost" size="icon" aria-label="Zoom out" disabled={!doc?.is_pdf || zoom <= .5} onClick={() => setZoom(z => Math.max(.5, z - .25))}><ZoomOut /></Button>
        <button className="min-w-10 text-[11px]" aria-label="Reset zoom" onClick={() => setZoom(1)}>{Math.round(zoom * 100)}%</button>
        <Button variant="ghost" size="icon" aria-label="Zoom in" disabled={!doc?.is_pdf || zoom >= 2.5} onClick={() => setZoom(z => Math.min(2.5, z + .25))}><ZoomIn /></Button></div>
    </div>
    {!doc ? <div className="empty-panel"><FileText /><strong>Your document, in view</strong><p>Import a document to preview it alongside its extracted fields.</p></div> : !doc.is_pdf ? <pre className="text-preview">{doc.text}</pre> : <div className="pdf-body">
      {thumbnails ? <aside className="thumbnails" aria-label="Page thumbnails">{Array.from({length: doc.pages}, (_, index) => <Thumbnail key={`${doc.id}-${index}`} id={doc.id} page={index} selected={page === index} onClick={() => setPage(index)} />)}</aside> : null}
      <div className="page-scroll">{loading ? <div className="preview-loading"><LoaderCircle className="animate-spin" size={18} /><span>Rendering page…</span></div> : null}
        {error ? <p role="alert" className="p-4 text-red-700">{error}</p> : image ? <img className="pdf-page" style={{width: `${zoom * 100}%`}} src={image} alt={`Page ${page + 1} of ${doc.name}`} /> : null}
      </div>
    </div>}
  </section>
}
