import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

const CREDENTIALS = { username: 'admin', password: 'customer360' }

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => localStorage.getItem('c360_user'))

  const login = (username, password) => {
    if (username === CREDENTIALS.username && password === CREDENTIALS.password) {
      localStorage.setItem('c360_user', username)
      setUser(username)
      return true
    }
    return false
  }

  const logout = () => {
    localStorage.removeItem('c360_user')
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, login, logout }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
