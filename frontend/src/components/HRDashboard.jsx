import React, { useState, useEffect, useRef } from 'react'
import { speak } from '../utils/speech'
import { API_BASE_URL, WS_BASE_URL } from '../apiConfig'

export default function HRDashboard({ user, onLogout }) {
  const [candidates, setCandidates] = useState({}) // user_id -> candidate object
  const [activeCandidateId, setActiveCandidateId] = useState(null)
  const [messages, setMessages] = useState([])
  const [notifications, setNotifications] = useState([])
  const [suggestion, setSuggestion] = useState("Awaiting candidate engagement...")
  const [highlights, setHighlights] = useState([]) // Array of { intent, timestamp, question }
  const [notes, setNotes] = useState('')
  const [flags, setFlags] = useState([])
  const [sessionTimer, setSessionTimer] = useState(0)
  const [showSummary, setShowSummary] = useState(false)
  const [activeQuestion, setActiveQuestion] = useState(1)
  const [isMuted, setIsMuted] = useState(false)
  const [isCameraOff, setIsCameraOff] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [copied, setCopied] = useState(false)
  
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const socketRef = useRef(null)
  const pcMap = useRef({}) // user_id -> RTCPeerConnection
  const [remoteStreams, setRemoteStreams] = useState({}) // user_id -> MediaStream

  // Timer
  useEffect(() => {
    const timer = setInterval(() => setSessionTimer(prev => prev + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  // Sync local video element with stream
  useEffect(() => {
    if (videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [videoRef.current, streamRef.current])

  // Camera initialization
  useEffect(() => {
    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        streamRef.current = stream
      } catch (err) { console.error("Camera error:", err) }
    }
    startCamera()
    return () => { if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop()) }
  }, [])

  // Suggestion logic updated
  useEffect(() => {
    const fetchSuggestion = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/session/${user.session_id}/suggestions?context=hr`)
        const data = await res.json()
        if (data.suggestion) {
          setSuggestion(data.suggestion)
          if (isSpeaking) speak(data.suggestion)
        }
      } catch (err) { console.error("Poll error:", err) }
    }
    fetchSuggestion()
    const interval = setInterval(fetchSuggestion, 10000)
    return () => clearInterval(interval)
  }, [user.session_id, isSpeaking])

  // WebSocket for real-time updates
  useEffect(() => {
    const socket = new WebSocket(`${WS_BASE_URL}/ws/${user.session_id}?user_id=${user.user_id}`)
    socketRef.current = socket

    const getPC = (userId) => {
      if (pcMap.current[userId]) return pcMap.current[userId]
      
      const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
      pcMap.current[userId] = pc
      
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          socket.send(JSON.stringify({ type: 'candidate', candidate: event.candidate, target: userId }))
        }
      }
      
      pc.ontrack = (event) => {
        setRemoteStreams(prev => ({ ...prev, [userId]: event.streams[0] }))
      }
      
      if (streamRef.current) {
         streamRef.current.getTracks().forEach(track => pc.addTrack(track, streamRef.current))
      }
      
      return pc
    }

    socket.onmessage = async (event) => {
      const msg = JSON.parse(event.data)
      
      // WebRTC Signaling
      if (msg.type === 'offer') {
          const pc = getPC(msg.from)
          await pc.setRemoteDescription(new RTCSessionDescription(msg.offer))
          const answer = await pc.createAnswer()
          await pc.setLocalDescription(answer)
          socket.send(JSON.stringify({ type: 'answer', answer: answer, target: msg.from }))
      } else if (msg.type === 'candidate') {
          const pc = getPC(msg.from)
          await pc.addIceCandidate(new RTCIceCandidate(msg.candidate))
      }
      
      // Other messages
      else if (msg.type === 'student_joined') {
        setCandidates(prev => ({
          ...prev,
          [msg.data.id]: { id: msg.data.id, name: msg.data.name, status: 'Active', metrics: null }
        }))
        if (!activeCandidateId) setActiveCandidateId(msg.data.id)
      } 
      else if (msg.type === 'student_update') {
        setCandidates(prev => {
          const candidate = prev[msg.data.user_id]
          if (!candidate) return prev
          
          let newStatus = msg.data.metrics.risk === 'high' ? 'Review Needed' : 'Active'
          
          if (msg.data.user_id === activeCandidateId && (!candidate.metrics || candidate.metrics.intent !== msg.data.metrics.intent)) {
            setHighlights(h => [...h, { 
              intent: msg.data.metrics.intent, 
              timestamp: new Date().toLocaleTimeString(),
              strength: msg.data.metrics.signal_strength,
              question: activeQuestion
            }].slice(-10))
          }

          if (msg.data.metrics.tech_issue && !flags.includes("Technical issue detected")) {
             setFlags(f => [...f, "Technical issue detected"])
          }

          return {
            ...prev,
            [msg.data.user_id]: { 
               ...candidate, 
               status: newStatus,
               metrics: msg.data.metrics 
            }
          }
        })
      }
    }
    return () => { socket.close(); Object.values(pcMap.current).forEach(pc => pc.close()) }
  }, [user.session_id, activeCandidateId, flags, activeQuestion])

  const toggleMute = () => {
    if (streamRef.current) {
      const audioTracks = streamRef.current.getAudioTracks()
      audioTracks.forEach(t => t.enabled = isMuted)
      setIsMuted(!isMuted)
    }
  }

  const toggleCamera = () => {
    if (streamRef.current) {
      const videoTracks = streamRef.current.getVideoTracks()
      videoTracks.forEach(t => t.enabled = isCameraOff)
      setIsCameraOff(!isCameraOff)
    }
  }

  const moderateUser = async (userId, action) => {
    try {
      await fetch(`${API_BASE_URL}/session/${user.session_id}/participants/${userId}/action`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action })
      })
    } catch (err) { console.error(err) }
  }

  const activeCandidate = candidates[activeCandidateId]
  const formatTime = (s) => `${Math.floor(s/60)}:${(s%60).toString().padStart(2,'0')}`

  const copySessionId = () => {
    navigator.clipboard.writeText(user.session_id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleEndSession = () => setShowSummary(true)

  const getSessionReliability = () => {
    if (flags.length > 0) return "Low Reliability"
    if (highlights.filter(h => h.strength === 'Low confidence').length > 3) return "Medium Reliability"
    return "High Reliability"
  }

  if (showSummary) {
    const reliability = getSessionReliability()
    return (
      <div className="flex-center" style={{ padding: '2rem' }}>
        <div className="glass-panel" style={{ maxWidth: '800px', width: '100%', padding: '3rem', animation: 'fadeIn 0.5s ease-out' }}>
          <h2 style={{ marginBottom: '1.5rem' }}>Interview Session Summary</h2>
          <div className="grid-2" style={{ gap: '2rem', marginBottom: '2rem' }}>
            <div className="glass-card">
               <h4 style={{ color: 'var(--text-secondary)' }}>Overall Patterns</h4>
               <p><strong>Session Reliability:</strong> <span style={{ color: reliability === 'High Reliability' ? 'var(--success)' : reliability === 'Medium Reliability' ? 'var(--warning)' : 'var(--danger)' }}>{reliability}</span></p>
               <p><strong>Engagement:</strong> High Average</p>
               <p><strong>Tech Continuity:</strong> {flags.length > 0 ? 'Poor' : 'Excellent'}</p>
            </div>
            <div className="glass-card">
               <h4 style={{ color: 'var(--text-secondary)' }}>Key Moments</h4>
               <div style={{ maxHeight: '150px', overflowY: 'auto', fontSize: '0.85rem' }}>
                  {highlights.map((h, i) => (
                    <div key={i} style={{ marginBottom: '0.4rem', color: 'var(--text-secondary)' }}>• {h.intent} during Question {h.question} ({h.timestamp})</div>
                  ))}
               </div>
            </div>
          </div>
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', padding: '1rem', borderRadius: '8px', marginBottom: '2rem', fontSize: '0.9rem', color: 'var(--danger)', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
             <strong>Reviewer Decision Required:</strong> Please finalize your hiring recommendation manually based on these AI-assisted patterns.
          </div>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
             <button className="btn-secondary" onClick={() => setShowSummary(false)}>Back to Dashboard</button>
             <button className="btn-primary" style={{ background: 'var(--danger)' }} onClick={onLogout}>Finalize & Logout</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="app-container animate-in" style={{ display: 'grid', gridTemplateColumns: '320px 1fr 350px', gridTemplateRows: 'auto 1fr 250px', gap: '1rem', height: '100vh', padding: '1rem' }}>
      
      {/* 1. Candidate Info Panel */}
      <div className="glass-panel" style={{ gridRow: '1 / 2', position: 'relative', padding: '1.5rem' }}>
        <h3 style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem', marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.8rem', textTransform: 'uppercase' }}>Candidate Profile</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div><label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>NAME</label><p style={{ margin: 0, fontWeight: 600, fontSize: '1.1rem' }}>{activeCandidate?.name || "No Candidate"}</p></div>
          <div style={{ display: 'flex', gap: '1rem' }}>
             <div style={{ flex: 1 }}><label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>ROLE</label><p style={{ margin: 0 }}>Senior Developer</p></div>
             <div style={{ width: '80px' }}><label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Q#</label>
               <input type="number" min="1" value={activeQuestion} onChange={e => setActiveQuestion(parseInt(e.target.value))} className="input-field" style={{ padding: '4px 8px', marginBottom: 0 }} />
             </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', alignItems: 'center' }}>
             <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>⏱ {formatTime(sessionTimer)}</span>
             <span className={`badge badge-${activeCandidate?.status === 'Active' ? 'green' : 'yellow'}`}>{activeCandidate?.status || 'Waiting'}</span>
          </div>
          {activeCandidateId && (
            <div style={{ marginTop: '1.5rem', display: 'flex', gap: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '1rem' }}>
               <button className="copy-btn" title="Mute Candidate" onClick={() => moderateUser(activeCandidateId, 'mute')}>🎙️</button>
               <button className="copy-btn" title="Toggle Candidate Camera" onClick={() => moderateUser(activeCandidateId, activeCandidate?.metrics ? 'camera_off' : 'camera_on')}>
                  {activeCandidate?.metrics ? '📹' : '🚫'}
               </button>
               <button className="copy-btn" style={{ background: 'var(--danger)' }} title="Remove Candidate" onClick={() => moderateUser(activeCandidateId, 'kick')}>🚫</button>
            </div>
          )}
        </div>
        
        {activeCandidate?.metrics?.risk === 'high' && (
          <div className="pulse-primary" style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'var(--danger)', color: 'white', padding: '4px 8px', borderRadius: '4px', fontSize: '0.65rem', fontWeight: 'bold' }}>
             ⚠️ ACTION REQUIRED
          </div>
        )}
      </div>

      {/* Header */}
      <div className="glass-panel" style={{ gridColumn: '2 / 3', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.2rem' }} className="accent-text">🤝 AI-Assisted Interview</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>ID: {user.session_id}</span>
            <button className="copy-btn" onClick={copySessionId}>
              {copied ? '✅ Copied' : '📄 Copy ID'}
            </button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
           <button className="btn-secondary">Pause</button>
           <button className="btn-primary" onClick={handleEndSession} style={{ background: 'var(--danger)' }}>End Session</button>
        </div>
      </div>

      {/* 2. Live Interview Center */}
      <div className="glass-panel" style={{ gridColumn: '2 / 3', gridRow: '2 / 3', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <div className="glass-card" style={{ width: '320px', height: '240px', padding: 0, overflow: 'hidden', position: 'relative', marginBottom: '2rem', border: '2px solid var(--accent-primary)' }}>
            {activeCandidateId && remoteStreams[activeCandidateId] ? (
              <video 
                autoPlay 
                playsInline 
                style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                ref={el => { if (el) el.srcObject = remoteStreams[activeCandidateId] }}
              />
            ) : (
              <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            )}
            
            <div style={{ position: 'absolute', bottom: 10, left: 10, display: 'flex', gap: '8px' }}>
               <button onClick={toggleMute} style={{ background: isMuted ? 'var(--danger)' : 'var(--accent-primary)', border: 'none', color: 'white', padding: '2px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.7rem' }}>
                 {isMuted ? '🔇' : '🎙️'}
               </button>
               <button onClick={toggleCamera} style={{ background: isCameraOff ? 'var(--danger)' : 'var(--accent-primary)', border: 'none', color: 'white', padding: '2px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.7rem' }}>
                 {isCameraOff ? '🚫' : '📹'}
               </button>
            </div>
            <div style={{ position: 'absolute', top: 10, right: 10, background: 'var(--accent-primary)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem' }}>AI ANALYSIS ACTIVE</div>
        </div>

        <div style={{ textAlign: 'center', maxWidth: '500px' }}>
           <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '2px' }}>Current Inference</span>
           <h1 style={{ margin: '0.5rem 0', fontSize: '3.5rem', fontWeight: 800, color: activeCandidate?.metrics?.risk === 'medium' ? 'var(--warning)' : activeCandidate?.metrics?.risk === 'high' ? 'var(--danger)' : 'white' }}>
             {activeCandidate?.metrics?.candidate_state || "Listening..."}
           </h1>
           <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
             {activeCandidate?.metrics?.signal_strength ? `${activeCandidate.metrics.signal_strength} (${Math.round(activeCandidate.metrics.confidence * 100)}%)` : 'Awaiting signals...'}
           </p>
           
           <div style={{ width: '250px', height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', margin: '1.5rem auto', overflow: 'hidden' }}>
              <div style={{ width: `${(activeCandidate?.metrics?.confidence || 0) * 100}%`, height: '100%', background: 'linear-gradient(to right, var(--accent-primary), #60a5fa)', transition: 'width 0.5s ease' }}></div>
           </div>
        </div>
      </div>

      <div className="glass-panel" style={{ gridColumn: '3 / 4', gridRow: '1 / 3', display: 'flex', flexDirection: 'column', padding: 0 }}>
        <div style={{ padding: '1.2rem', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
           <h3 style={{ margin: 0, fontSize: '1rem', color: 'var(--accent-primary)' }}>🧠 Assistive Insights</h3>
           <button 
                onClick={() => setIsSpeaking(!isSpeaking)} 
                title={isSpeaking ? "Turn off voice" : "Turn on voice"}
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', padding: 0, filter: isSpeaking ? 'none' : 'grayscale(100%)' }}
              >
                🔊
            </button>
        </div>
        <div style={{ flex: 1, padding: '1.5rem', overflowY: 'auto' }}>
           <div className="glass-card" style={{ background: 'rgba(59, 130, 246, 0.1)', borderLeft: '4px solid var(--accent-primary)', padding: '1.2rem', marginBottom: '2rem' }}>
              <p style={{ margin: 0, fontSize: '0.95rem', color: 'white', lineHeight: '1.6' }}>{suggestion}</p>
           </div>
           
           <h4 style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '1rem', letterSpacing: '1px' }}>Supportive Prompts</h4>
           <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <button className="btn-secondary" style={{ textAlign: 'left', fontSize: '0.8rem' }} onClick={() => setNotes(n => n + `\nAsked to clarify expectations on Q${activeQuestion}.`)}>Clarify question expectations</button>
              <button className="btn-secondary" style={{ textAlign: 'left', fontSize: '0.8rem' }} onClick={() => setNotes(n => n + `\nProbed deeper on Q${activeQuestion}.`)}>Probe for deeper thought process</button>
           </div>
        </div>

        <div style={{ padding: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: '0.7rem', color: 'var(--text-secondary)', fontStyle: 'italic', textAlign: 'center' }}>
           AI insights are assistive and may not fully capture human context. Final decisions remain yours.
        </div>
      </div>

      {/* 4. Timeline */}
      <div className="glass-panel" style={{ gridColumn: '1 / 2', gridRow: '2 / 4', display: 'flex', flexDirection: 'column', padding: '1.5rem' }}>
         <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>Session Timeline</h3>
         <div style={{ flex: 1, overflowY: 'auto' }}>
            {highlights.map((h, i) => (
              <div key={i} className="glass-card" style={{ padding: '0.8rem', marginBottom: '0.8rem', borderLeft: '2px solid var(--accent-primary)' }}>
                 <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>{h.intent}</div>
                 <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Q{h.question} • {h.timestamp}</div>
              </div>
            ))}
            {highlights.length === 0 && (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                <p style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>✨</p>
                <p style={{ fontSize: '0.75rem' }}>No alerts yet.</p>
              </div>
            )}
         </div>
      </div>

      {/* 5. Flags */}
      <div className="glass-panel" style={{ gridColumn: '3 / 4', gridRow: '3 / 4', padding: '1.2rem' }}>
         <h3 style={{ fontSize: '0.8rem', color: 'var(--danger)', marginBottom: '1rem', textTransform: 'uppercase' }}>Safety Flags</h3>
         <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {flags.map((f, i) => (
               <div key={i} className="badge-red" style={{ padding: '8px 12px', borderRadius: '6px', fontSize: '0.75rem' }}>⚠️ {f}</div>
            ))}
            {flags.length === 0 && (
              <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                ✅ Technical signals clean
              </div>
            )}
         </div>
      </div>

      {/* 6. Notes */}
      <div className="glass-panel" style={{ gridColumn: '2 / 3', gridRow: '3 / 4', display: 'flex', gap: '1.5rem', padding: '1.5rem' }}>
         <textarea 
           className="input-field"
           style={{ flex: 1, marginBottom: 0, resize: 'none', background: 'rgba(0,0,0,0.3)' }}
           placeholder="Interactive interview notes..."
           value={notes}
           onChange={e => setNotes(e.target.value)}
         />
         <div style={{ width: '150px', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <button className="btn-primary" style={{ flex: 1 }}>Save</button>
            <button className="btn-secondary" style={{ fontSize: '0.75rem' }} onClick={handleEndSession}>Review</button>
         </div>
      </div>

    </div>
  )
}
