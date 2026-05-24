import React, { useState } from 'react'
import Login from './Login'
import '../index.css'

export default function Landing({ onLogin }) {
  const [context, setContext] = useState('teacher')

  const options = [
    { id: 'teacher', icon: '👨‍🏫', title: 'Teacher', desc: 'Host a classroom' },
    { id: 'doctor', icon: '🩺', title: 'Doctor', desc: 'Host a consultation' },
    { id: 'hr', icon: '💼', title: 'HR', desc: 'Host an interview' },
    { id: 'student', icon: '🎓', title: 'Participant', desc: 'Join a session' }
  ]

  return (
    <div className="flex-center" style={{ minHeight: '100vh', padding: '2rem' }}>
      <div className="glass-panel" style={{ display: 'flex', maxWidth: '1000px', width: '100%', overflow: 'hidden', minHeight: '600px' }}>
        
        {/* Sidebar - Context Selection */}
        <div style={{ width: '40%', background: 'rgba(0,0,0,0.2)', padding: '2rem', borderRight: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column' }}>
          <h1 style={{ fontSize: '2.5rem', marginBottom: '2.5rem', fontWeight: 800 }} className="accent-text">
            Facial Intent
          </h1>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
            {options.map(opt => {
              const isActive = context === opt.id
              return (
                <div 
                  key={opt.id}
                  onClick={() => setContext(opt.id)}
                  style={{
                    padding: '1rem 1.5rem',
                    borderRadius: '12px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    background: isActive ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
                    border: `1px solid ${isActive ? 'rgba(59, 130, 246, 0.5)' : 'transparent'}`,
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    transform: isActive ? 'scale(1.02)' : 'scale(1)',
                    boxShadow: isActive ? '0 4px 12px rgba(59, 130, 246, 0.1)' : 'none'
                  }}
                  onMouseEnter={e => {
                    if(!isActive) Object.assign(e.currentTarget.style, { background: 'rgba(255,255,255,0.05)' })
                  }}
                  onMouseLeave={e => {
                    if(!isActive) Object.assign(e.currentTarget.style, { background: 'transparent' })
                  }}
                >
                  <span style={{ fontSize: '1.8rem' }}>{opt.icon}</span>
                  <div>
                    <strong style={{ display: 'block', fontSize: '1.1rem', color: isActive ? 'white' : 'var(--text-primary)' }}>{opt.title}</strong>
                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{opt.desc}</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Right Side - Login Form */}
        <div style={{ width: '60%', padding: '3rem', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
            <Login context={context} onLogin={onLogin} />
        </div>

      </div>
    </div>
  )
}
