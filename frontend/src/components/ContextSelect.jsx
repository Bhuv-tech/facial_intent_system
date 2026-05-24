import React from 'react'
import '../index.css'

export default function ContextSelect({ onSelect }) {
  const options = [
    { id: 'teacher', icon: '👨‍🏫', title: 'Teacher', desc: 'Host a classroom session' },
    { id: 'doctor', icon: '🩺', title: 'Doctor', desc: 'Host a medical consultation' },
    { id: 'hr', icon: '💼', title: 'HR Manager', desc: 'Host an interview' },
    { id: 'student', icon: '🎓', title: 'Participant', desc: 'Join a session' }
  ]

  return (
    <div className="flex-center">
      <div className="glass-panel" style={{ padding: '3rem', maxWidth: '800px', width: '100%', textAlign: 'center' }}>
        <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem', background: 'linear-gradient(to right, #60a5fa, #a78bfa)', WebkitBackgroundClip: 'text', color: 'transparent' }}>
          Welcome to Facial Intent
        </h1>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '3rem', fontSize: '1.2rem' }}>
          Select your role to begin
        </p>

        <div className="grid-2">
          {options.map((opt) => (
            <div 
              key={opt.id} 
              className="glass-card" 
              style={{ cursor: 'pointer', textAlign: 'left' }}
              onClick={() => onSelect(opt.id)}
            >
              <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>{opt.icon}</div>
              <h3 style={{ fontSize: '1.5rem', color: 'white' }}>{opt.title}</h3>
              <p style={{ color: 'var(--text-secondary)' }}>{opt.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
