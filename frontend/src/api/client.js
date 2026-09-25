import axios from 'axios'

const ACCESS_KEY = 'portal.access'
const REFRESH_KEY = 'portal.refresh'

export const tokens = {
  get access() { return localStorage.getItem(ACCESS_KEY) },
  get refresh() { return localStorage.getItem(REFRESH_KEY) },
  set({ access, refresh }) {
    if (access) localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

api.interceptors.request.use((config) => {
  if (tokens.access) config.headers.Authorization = `Bearer ${tokens.access}`
  return config
})

// On a 401, refresh the access token once and replay the request. Concurrent
// failures share a single refresh call.
let refreshing = null
let onSessionExpired = () => {}
export const setSessionExpiredHandler = (fn) => { onSessionExpired = fn }

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    const isAuthCall = original?.url?.startsWith('/auth/token')
    if (error.response?.status !== 401 || original._retried || isAuthCall || !tokens.refresh) {
      return Promise.reject(error)
    }
    original._retried = true
    try {
      refreshing ??= api
        .post('/auth/token/refresh/', { refresh: tokens.refresh })
        .then(({ data }) => tokens.set(data))
        .finally(() => { refreshing = null })
      await refreshing
      return api(original)
    } catch (refreshError) {
      tokens.clear()
      onSessionExpired()
      return Promise.reject(refreshError)
    }
  },
)

/** The first message in a (possibly nested) DRF error body, with the path to the field. */
function firstError(data, path = []) {
  if (typeof data === 'string') return { path, text: data }
  if (Array.isArray(data)) {
    for (const [i, item] of data.entries()) {
      const found = firstError(item, typeof item === 'object' && item !== null && data.length > 1 ? [...path, `#${i + 1}`] : path)
      if (found) return found
    }
    return null
  }
  if (data && typeof data === 'object') {
    for (const [key, value] of Object.entries(data)) {
      const found = firstError(value, key === 'non_field_errors' || key === 'detail' ? path : [...path, key])
      if (found) return found
    }
  }
  return null
}

/** Turn a DRF error response into one readable sentence, e.g. "offering › days: Unknown weekdays". */
export function errorMessage(error, fallback = 'Something went wrong. Please try again.') {
  const data = error?.response?.data
  if (!data) return error?.message === 'Network Error' ? 'Cannot reach the server.' : fallback
  if (typeof data === 'string') return fallback
  const found = firstError(data)
  if (!found) return fallback
  const where = found.path.map((p) => p.replaceAll('_', ' ')).join(' › ')
  return where ? `${where}: ${found.text}` : found.text
}

/** The public website's API: no credentials, no token refresh. */
export const publicApi = axios.create({ baseURL: `${import.meta.env.VITE_API_URL || '/api'}/public` })

/** Unwrap paginated or plain list responses. */
export const results = (data) => (Array.isArray(data) ? data : data?.results ?? [])

export default api

/** Download a file from an authenticated endpoint (the JWT can't ride along on a plain link). */
export async function downloadFile(url, params, fallbackName = 'download.pdf') {
  const res = await api.get(url, { params, responseType: 'blob' })
  const match = /filename="([^"]+)"/.exec(res.headers['content-disposition'] || '')
  const href = URL.createObjectURL(res.data)
  const link = document.createElement('a')
  link.href = href
  link.download = match ? match[1] : fallbackName
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

/** Blob error responses hide DRF's JSON message; unwrap it for errorMessage(). */
export async function blobErrorMessage(error) {
  const data = error?.response?.data
  if (data instanceof Blob) {
    try {
      error.response.data = JSON.parse(await data.text())
    } catch { /* not JSON */ }
  }
  return errorMessage(error)
}
