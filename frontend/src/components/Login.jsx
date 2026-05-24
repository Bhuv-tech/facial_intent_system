import React, { useState } from 'react'
import { API_BASE_URL } from '../apiConfig'

export default function Login({ context, onLogin }) {
  const isProfessional = context !== 'student'
  
  const [authMode, setAuthMode] = useState('login') // 'login' or 'signup'
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  
  // Professional Session Options
  const [sessionOption, setSessionOption] = useState('new') // 'new' or 'join'
  const [sessionId, setSessionId] = useState('')
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    // Validation for Session ID if joining
    if ((!isProfessional || sessionOption === 'join') && sessionId.length !== 6) {
        setError("Session ID must be exactly 6 characters (e.g. T00001)")
        setLoading(false)
        return
    }

    try {
      const res = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: authMode === 'signup' ? name : (email.split('@')[0]),
          email: email,
          password: password,
          is_signup: authMode === 'signup',
          role: context === 'student' ? 'Participant' : context.charAt(0).toUpperCase() + context.slice(1),
          user_type: context === 'student' ? 'student' : 'professional',
          context: context,
          session_id: (isProfessional && sessionOption === 'new') ? null : sessionId.toUpperCase()
        })
      })
      
      const data = await res.json()
      if (!res.ok) {
        let msg = data.detail || 'Authentication failed'
        if (res.status === 401) msg = "Invalid email or password. Please check your credentials."
        if (res.status === 404) msg = "Session ID not found. Please verify the code with your host."
        if (res.status === 400) msg = "Could not join session: " + (data.detail || "Invalid request")
        throw new Error(msg)
      }
      
      onLogin(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="animate-in" style={{ width: '100%', maxWidth: '420px' }}>
      
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <h2 style={{ fontSize: '2.4rem', marginBottom: '0.5rem' }} className="accent-text">
          {authMode === 'login' ? 'Welcome Back' : 'Create Account'}
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
          {isProfessional 
            ? `Manage your ${context} session with ease` 
            : 'Enter your 6-digit session code to join'
          }
        </p>
      </div>

      {/* Auth Mode Toggle */}
      <div style={{ 
        display: 'flex', 
        background: 'rgba(0,0,0,0.3)', 
        padding: '4px', 
        borderRadius: '14px', 
        marginBottom: '2rem',
        border: '1px solid rgba(255,255,255,0.05)'
      }}>
        <button 
          onClick={() => setAuthMode('login')}
          style={{ 
            flex: 1, padding: '0.8rem', borderRadius: '11px', border: 'none',
            background: authMode === 'login' ? 'rgba(255,255,255,0.1)' : 'transparent',
            color: authMode === 'login' ? 'white' : 'var(--text-secondary)',
            fontWeight: '600', cursor: 'pointer', transition: 'all 0.3s'
          }}
        >
          Login
        </button>
        <button 
          onClick={() => setAuthMode('signup')}
          style={{ 
            flex: 1, padding: '0.8rem', borderRadius: '11px', border: 'none',
            background: authMode === 'signup' ? 'rgba(255,255,255,0.1)' : 'transparent',
            color: authMode === 'signup' ? 'white' : 'var(--text-secondary)',
            fontWeight: '600', cursor: 'pointer', transition: 'all 0.3s'
          }}
        >
          Sign Up
        </button>
      </div>

      {error && (
        <div style={{ 
          background: 'rgba(239, 68, 68, 0.1)', color: '#f87171', 
          border: '1px solid rgba(239, 68, 68, 0.2)', padding: '1rem', 
          borderRadius: '12px', marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'center' 
        }}>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        
        {authMode === 'signup' && (
          <div className="glass-card" style={{ padding: '0.6rem 1.2rem' }}>
            <label style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>Full Name</label>
            <input 
              type="text" required className="input-field" 
              style={{ border: 'none', background: 'transparent', padding: 0, marginBottom: 0 }} 
              value={name} onChange={e => setName(e.target.value)} placeholder="Enter your name" 
            />
          </div>
        )}

        <div className="glass-card" style={{ padding: '0.6rem 1.2rem' }}>
          <label style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>Email Address</label>
          <input 
            type="email" required className="input-field" 
            style={{ border: 'none', background: 'transparent', padding: 0, marginBottom: 0 }} 
            value={email} onChange={e => setEmail(e.target.value)} placeholder="Email address" 
          />
        </div>

        <div className="glass-card" style={{ padding: '0.6rem 1.2rem' }}>
          <label style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>Password</label>
          <input 
            type="password" required className="input-field" 
            style={{ border: 'none', background: 'transparent', padding: 0, marginBottom: 0 }} 
            value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" 
          />
        </div>

        {/* Professional Selection: Create vs Join */}
        {isProfessional && (
            <div style={{ marginTop: '0.5rem', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', gap: '1rem' }}>
                    <div 
                        onClick={() => setSessionOption('new')}
                        style={{ 
                            flex: 1, cursor: 'pointer', padding: '1rem', borderRadius: '12px',
                            background: sessionOption === 'new' ? 'rgba(79, 70, 229, 0.1)' : 'rgba(255,255,255,0.03)',
                            border: `1px solid ${sessionOption === 'new' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)'}`,
                            textAlign: 'center', transition: 'all 0.3s'
                        }}
                    >
                        <div style={{ fontSize: '1.2rem', marginBottom: '4px' }}>➕</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>New Meet</div>
                    </div>
                    <div 
                        onClick={() => setSessionOption('join')}
                        style={{ 
                            flex: 1, cursor: 'pointer', padding: '1rem', borderRadius: '12px',
                            background: sessionOption === 'join' ? 'rgba(79, 70, 229, 0.1)' : 'rgba(255,255,255,0.03)',
                            border: `1px solid ${sessionOption === 'join' ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)'}`,
                            textAlign: 'center', transition: 'all 0.3s'
                        }}
                    >
                        <div style={{ fontSize: '1.2rem', marginBottom: '4px' }}>🔗</div>
                        <div style={{ fontSize: '0.8rem', fontWeight: 600 }}>Resume Meet</div>
                    </div>
                </div>
            </div>
        )}

        {/* Session ID input for Joiners or resuming Professionals */}
        {(!isProfessional || (isProfessional && sessionOption === 'join')) && (
          <div className="glass-card" style={{ padding: '0.6rem 1.2rem', border: '1px solid var(--accent-primary)' }}>
            <label style={{ display: 'block', fontSize: '0.7rem', color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px' }}>Session ID</label>
            <input 
              type="text" required maxLength={6}
              className="input-field" style={{ border: 'none', background: 'transparent', padding: 0, marginBottom: 0, fontSize: '1.2rem', letterSpacing: '2px' }} 
              value={sessionId} onChange={e => setSessionId(e.target.value.toUpperCase())} placeholder="X00000" 
            />
          </div>
        )}

        <button 
          type="submit" disabled={loading} className="btn-primary pulse-primary" 
          style={{ width: '100%', marginTop: '1rem', padding: '1.2rem', fontSize: '1.1rem' }}
        >
          {loading ? 'Processing...' : (
            authMode === 'login' 
              ? (isProfessional ? (sessionOption === 'new' ? 'Start Session' : 'Resume Session') : 'Join Meeting')
              : 'Create Account'
          )}
        </button>
      </form>

      <div style={{ marginTop: '2rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
        <p>Facial Intent System &bull; Enterprise Edition</p>
      </div>

    </div>
  )
}
