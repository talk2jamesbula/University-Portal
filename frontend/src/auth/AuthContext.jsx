import { useCallback, useEffect, useMemo, useState } from 'react'
import api, { setSessionExpiredHandler, tokens } from '../api/client'
import { AuthContext } from './useAuth'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // Only show the start-up spinner when there is a saved session to restore.
  const [loading, setLoading] = useState(Boolean(tokens.access))
  // Where to send someone who signed out on purpose (an expired session goes to sign-in instead).
  const [exitTo, setExitTo] = useState(null)

  const logout = useCallback((destination = null) => {
    tokens.clear()
    setExitTo(destination)
    setUser(null)
  }, [])

  const loadUser = useCallback(async () => {
    const { data } = await api.get('/auth/me/')
    setUser(data)
    return data
  }, [])

  useEffect(() => {
    setSessionExpiredHandler(() => setUser(null))
    if (!tokens.access) return
    api.get('/auth/me/')
      .then(({ data }) => setUser(data))
      .catch(() => tokens.clear())
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async (username, password) => {
    const { data } = await api.post('/auth/token/', { username, password })
    tokens.set(data)
    setExitTo(null)
    return loadUser()
  }, [loadUser])

  const value = useMemo(
    () => ({ user, setUser, loading, login, logout, exitTo, reload: loadUser }),
    [user, loading, login, logout, exitTo, loadUser],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
