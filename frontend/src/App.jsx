import { useState, useEffect } from 'react'
import './index.css'
import Landing from './components/Landing'
import Dashboard from './components/Dashboard'

function App() {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('facial_intent_user')
    return saved ? JSON.parse(saved) : null
  })

  useEffect(() => {
    if (user) {
      localStorage.setItem('facial_intent_user', JSON.stringify(user))
    } else {
      localStorage.removeItem('facial_intent_user')
    }
  }, [user])

  if (!user) {
    return <Landing onLogin={setUser} />
  }

  return <Dashboard user={user} onLogout={() => setUser(null)} />
}

export default App
