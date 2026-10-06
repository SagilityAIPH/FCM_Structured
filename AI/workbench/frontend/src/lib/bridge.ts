import type { API } from '@/types'

type Reply = {ok: boolean; value?: unknown; error?: string}
declare global { interface Window { pywebview?: {api: Record<string, (...args: unknown[]) => Promise<Reply>>} } }
export const previewMode = new URLSearchParams(location.search).get('preview') === '1'
const bridgeReady = previewMode ? Promise.resolve(null) : new Promise<NonNullable<Window['pywebview']>>((resolve, reject) => {
  if (window.pywebview?.api?.get_state) { resolve(window.pywebview); return }
  const ready = () => { if (window.pywebview) { clearTimeout(timeout); resolve(window.pywebview) } }
  const timeout = setTimeout(() => { window.removeEventListener('pywebviewready', ready); reject(new Error('Desktop bridge unavailable. Launch with Python, or add ?preview=1 for the synthetic browser preview.')) }, 10000)
  window.addEventListener('pywebviewready', ready, { once: true })
})
const apiPromise: Promise<API> = previewMode ? import('./preview').then(module => module.previewAPI) : bridgeReady.then(bridge => new Proxy({} as API, {
  get: (_, method: string) => method === 'then' ? undefined : async (...args: unknown[]) => {
    const reply = await bridge!.api[method](...args)
    if (!reply.ok) throw new Error(reply.error || 'Operation failed')
    return reply.value
  },
}))
export async function getAPI() { return apiPromise }
