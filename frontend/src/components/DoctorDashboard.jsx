import React, { useState, useEffect, useRef } from 'react'
import { speak } from '../utils/speech'
import { API_BASE_URL, WS_BASE_URL } from '../apiConfig'

export default function DoctorDashboard({ user, onLogout }) {
  const [patients, setPatients] = useState({}) // user_id -> patient object
  const [activePatientId, setActivePatientId] = useState(null)
  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [notifications, setNotifications] = useState([])
  const [suggestion, setSuggestion] = useState("AI is observing patient baseline...")
  const [sessionTimeline, setSessionTimeline] = useState([]) // Array of { intent, timestamp }
  const [notes, setNotes] = useState('')
  const [isMuted, setIsMuted] = useState(false)
  const [isCameraOff, setIsCameraOff] = useState(false)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [sessionMetrics, setSessionMetrics] = useState(null)
  const [priorityAlerts, setPriorityAlerts] = useState([])
  const [copied, setCopied] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const socketRef = useRef(null)
  const pcMap = useRef({}) // user_id -> RTCPeerConnection
  const [remoteStreams, setRemoteStreams] = useState({}) // user_id -> MediaStream
 
  // Suggestion polling
  useEffect(() => {
    const fetchSuggestion = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/session/${user.session_id}/suggestions?context=${user.context}`)
        const data = await res.json()
        if (data.suggestion) {
          setSuggestion(data.suggestion)
          if (isSpeaking) speak(data.suggestion)
        }
        if (data.metrics) setSessionMetrics(data.metrics)
        if (data.priority_students) setPriorityAlerts(data.priority_students)
      } catch (err) { console.error("Poll error:", err) }
    }
    fetchSuggestion()
    const interval = setInterval(fetchSuggestion, 10000)
    return () => clearInterval(interval)
  }, [user.session_id, user.context, isSpeaking])

  const copySessionId = () => {
    navigator.clipboard.writeText(user.session_id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const addNotification = (text, duration=5000) => {
    const id = Date.now()
    setNotifications(prev => [...prev, { id, text }])
    setTimeout(() => setNotifications(prev => prev.filter(n => n.id !== id)), duration)
  }

  // WebSocket
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
        setPatients(prev => ({ ...prev, [msg.data.id]: { id: msg.data.id, name: msg.data.name, status: 'Stable', metrics: null } }))
        if (!activePatientId) setActivePatientId(msg.data.id)
      } else if (msg.type === 'student_update') {
        setPatients(prev => {
          const patient = prev[msg.data.user_id]
          if (!patient) return prev
          const newStatus = msg.data.metrics.risk === 'high' ? 'Critical' : msg.data.metrics.risk === 'medium' ? 'Attention Needed' : 'Stable'
          if (msg.data.user_id === activePatientId && (!patient.metrics || patient.metrics.intent !== msg.data.metrics.intent)) {
            setSessionTimeline(t => [...t, { intent: msg.data.metrics.intent, timestamp: new Date().toLocaleTimeString() }].slice(-10))
          }
          return { ...prev, [msg.data.user_id]: { ...patient, status: newStatus, metrics: msg.data.metrics } }
        })
        if (msg.data.metrics.risk === 'high' && msg.data.metrics.confidence > 0.8) {
          addNotification(`🚨 Critical: ${msg.data.metrics.intent} detected!`, 8000)
        }
      } else if (msg.type === 'chat') {
        setMessages(prev => [...prev, msg.data])
      }
    }
    return () => { socket.close(); Object.values(pcMap.current).forEach(pc => pc.close()) }
  }, [user.session_id, activePatientId])

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
      addNotification(`${action.toUpperCase()} action sent.`)
    } catch (err) { console.error(err) }
  }

  const activePatient = patients[activePatientId]

  return (
    <div className="app-container animate-in" style={{ display: 'grid', gridTemplateColumns: 'minmax(300px, 1fr) 2fr minmax(350px, 1fr)', gridTemplateRows: 'auto 1fr 220px', gap: '1rem', height: '100vh', padding: '1rem' }}>
      
      {/* Patient Info Panel */}
      <div className="glass-panel" style={{ padding: '1.5rem', gridRow: '1 / 2' }}>
        <h3 style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem', marginBottom: '1.2rem', fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Patient Summary</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div><label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>NAME</label><p style={{ margin: 0, fontWeight: 600 }}>{activePatient?.name || "No Patient active"}</p></div>
          <div>
            <label style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>SESSION ID</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
              <span style={{ fontSize: '0.75rem' }}>{user.session_id.slice(0, 8)}...</span>
              <button className="copy-btn" onClick={copySessionId}>{copied ? '✅' : '📄'}</button>
            </div>
          </div>
          <div style={{ marginTop: '0.5rem' }}>
            <span className={`badge badge-${activePatient?.status === 'Critical' ? 'red' : activePatient?.status === 'Attention Needed' ? 'yellow' : 'green'}`}>
              Current State: {activePatient?.status || 'Waiting'}
            </span>
          </div>
          {activePatientId && (
            <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem' }}>
               <button className="copy-btn" title="Mute Patient" onClick={() => moderateUser(activePatientId, 'mute')}>🎙️</button>
               <button className="copy-btn" title="Toggle Patient Camera" onClick={() => moderateUser(activePatientId, activePatient?.metrics ? 'camera_off' : 'camera_on')}>
                  {activePatient?.metrics ? '📹' : '🚫'}
               </button>
               <button className="copy-btn" style={{ background: 'var(--danger)' }} title="End Patient Session" onClick={() => moderateUser(activePatientId, 'kick')}>🚫</button>
            </div>
          )}
        </div>
      </div>

      {/* Header */}
      <div className="glass-panel" style={{ gridColumn: '2 / 3', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0, fontSize: '1.2rem' }} className="accent-text">🩺 Clinical Consultation Dashboard</h2>
        <button className="btn-primary" onClick={onLogout} style={{ background: 'var(--danger)' }}>End Consultation</button>
      </div>

      {/* Live Inference Center */}
      <div className="glass-panel" style={{ gridColumn: '2 / 3', gridRow: '2 / 3', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
         <div style={{ position: 'relative', width: '320px', height: '240px', background: '#000', borderRadius: '16px', overflow: 'hidden', border: '2px solid var(--accent-primary)', boxShadow: '0 8px 32px rgba(0,0,0,0.5)', marginBottom: '2rem' }}>
            {activePatientId && remoteStreams[activePatientId] ? (
              <video 
                autoPlay 
                playsInline 
                style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                ref={el => { if (el) el.srcObject = remoteStreams[activePatientId] }}
              />
            ) : (
              <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            )}
            
            <div style={{ position: 'absolute', bottom: 10, left: 10, display: 'flex', gap: '8px' }}>
               <button onClick={toggleMute} style={{ background: isMuted ? 'var(--danger)' : 'var(--accent-primary)', border: 'none', color: 'white', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}>
                 {isMuted ? '🔇' : '🎙️'}
               </button>
               <button onClick={toggleCamera} style={{ background: isCameraOff ? 'var(--danger)' : 'var(--accent-primary)', border: 'none', color: 'white', padding: '4px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}>
                 {isCameraOff ? '🚫' : '📹'}
               </button>
            </div>
            <div style={{ position: 'absolute', top: 12, right: 12 }}>
               <span className="badge badge-green" style={{ fontSize: '0.65rem' }}>● LIVE INFERENCE ACTIVE</span>
            </div>
         </div>

        <div style={{ textAlign: 'center', maxWidth: '500px' }}>
           <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '2px' }}>Patient Clinical Intent</span>
           <h1 style={{ fontSize: '3rem', margin: '0.5rem 0', color: activePatient?.metrics?.risk === 'high' ? 'var(--danger)' : 'white' }}>
            {activePatient?.metrics?.intent || "Calibrating..."}
           </h1>
           <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
             Confidence: <strong style={{ color: 'var(--accent-primary)' }}>{activePatient?.metrics ? Math.round(activePatient.metrics.confidence * 100) : '--'}%</strong>
           </p>
           
           <div style={{ marginTop: '1.5rem', height: '6px', width: '200px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', margin: '1.5rem auto', overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${(activePatient?.metrics?.confidence || 0) * 100}%`, background: 'var(--accent-primary)', transition: 'width 0.5s ease' }}></div>
           </div>
        </div>
      </div>

      {/* AI Co-Pilot Panel */}
      <div className="glass-panel" style={{ gridColumn: '3 / 4', gridRow: '1 / 3', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0, fontSize: '0.9rem' }}>🤖 Clinical Assistant</h3>
          <button 
            onClick={() => setIsSpeaking(!isSpeaking)} 
            title={isSpeaking ? "Turn off voice" : "Turn on voice"}
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', padding: 0, filter: isSpeaking ? 'none' : 'grayscale(100%)' }}
          >
            🔊
          </button>
        </div>
        <div style={{ padding: '1.5rem', flex: 1, overflowY: 'auto' }}>
          <div className="glass-card" style={{ borderLeft: '4px solid var(--accent-primary)', padding: '1.2rem', marginBottom: '1.5rem' }}>
             <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: '1.6', color: 'var(--text-secondary)' }}>
               {suggestion}
             </p>
          </div>

          {priorityAlerts.length > 0 && (
            <div>
              <h4 style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '1rem' }}>Active Alerts</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                {priorityAlerts.map((alert, idx) => (
                  <div key={idx} className="glass-card" style={{ padding: '0.8rem', borderLeft: '4px solid var(--danger)' }}>
                     <div style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>{alert.patient}</div>
                     <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{alert.risk} Risk: Sustained {alert.emotion} Detected</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Activity Timeline */}
      <div className="glass-panel" style={{ gridColumn: '1 / 2', gridRow: '2 / 4', padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
        <h3 style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>Session Timeline</h3>
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {sessionTimeline.map((item, idx) => (
            <div key={idx} className="glass-card" style={{ padding: '0.8rem' }}>
              <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600 }}>{item.intent}</p>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{item.timestamp}</span>
            </div>
          ))}
          {sessionTimeline.length === 0 && <p style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', textAlign: 'center' }}>Awaiting data...</p>}
        </div>
      </div>

      {/* Notes & Actions Panel */}
      <div className="glass-panel" style={{ gridColumn: '2 / 4', gridRow: '3 / 4', padding: '1.5rem', display: 'flex', gap: '1.5rem' }}>
         <textarea 
           className="input-field" 
           style={{ flex: 1, marginBottom: 0, resize: 'none', background: 'rgba(0,0,0,0.3)' }} 
           placeholder="Clinical session notes..." 
           value={notes}
           onChange={e => setNotes(e.target.value)}
         />
         <div style={{ width: '220px', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <button className="btn-primary" style={{ width: '100%' }}>💾 Save Clinical Log</button>
            <button className="btn-secondary" style={{ width: '100%', borderColor: 'var(--warning)', color: 'var(--warning)', fontSize: '0.8rem' }}>⚠️ Override AI Baseline</button>
            <button className="btn-secondary" style={{ width: '100%', fontSize: '0.8rem' }} onClick={() => setNotifications([])}>Clear Alerts</button>
         </div>
      </div>

    </div>
  )
}
