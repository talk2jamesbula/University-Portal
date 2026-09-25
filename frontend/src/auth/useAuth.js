import { createContext, useContext } from 'react'

export const AuthContext = createContext(null)

/** { user, setUser, loading, login, logout(exitTo?), exitTo, reload } from the nearest <AuthProvider>. */
export const useAuth = () => useContext(AuthContext)
