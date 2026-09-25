import { useCallback, useEffect, useState } from 'react'
import api, { errorMessage } from '../api/client'

/**
 * GET a URL, re-fetching whenever the URL or params change (pass url = null to skip).
 *
 * Each response is tagged with the request it answers, so a slow, outdated response can
 * never overwrite a newer one, and `loading` is simply "the latest request hasn't answered".
 * The previous data stays visible while a new request is in flight.
 * Pass `client` to use another Axios instance (e.g. the public website's).
 */
export default function useApi(url, params, client = api) {
  const paramsKey = JSON.stringify(params ?? {})
  const [version, setVersion] = useState(0)
  const requestKey = url ? `${url}?${paramsKey}#${version}` : null
  const [state, setState] = useState({ key: null, data: null, error: null })

  useEffect(() => {
    if (!requestKey) return undefined
    let current = true
    client.get(url, { params: JSON.parse(paramsKey) })
      .then((res) => current && setState({ key: requestKey, data: res.data, error: null }))
      .catch((err) => current && setState((s) => ({ key: requestKey, data: s.data, error: errorMessage(err) })))
    return () => { current = false }
  }, [client, url, paramsKey, requestKey])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  const setData = useCallback(
    (update) => setState((s) => ({ ...s, data: typeof update === 'function' ? update(s.data) : update })),
    [],
  )

  return {
    data: state.data,
    error: state.error,
    loading: Boolean(requestKey) && state.key !== requestKey,
    reload,
    setData,
  }
}
