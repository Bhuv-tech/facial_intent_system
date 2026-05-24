import React, { useState, useEffect, useRef } from 'react'
import { speak } from '../utils/speech'
import { API_BASE_URL, WS_BASE_URL } from '../apiConfig'

export default function TeacherDashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState('main') // 'main', 'grid', 'list'
  const [students, setStudents] = useState({}) // user_id -> metric object
  const [messages, setMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [notifications, setNotifications] = useState([])
  const [isBreak, setIsBreak] = useState(user.is_break || false)
  const [breakTimer, setBreakTimer] = useState(0)
  const [suggestion, setSuggestion] = useState("AI is analyzing the session...")
  const [isMuted, setIsMuted] = useState(false)
  const [isCameraOff, setIsCameraOff] = useState(false)
  const [mediaError, setMediaError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [remoteStreams, setRemoteStreams] = useState({}) // user_id -> MediaStream
  const [classMetrics, setClassMetrics] = useState({ engagement_pct: 0, confusion_pct: 0, avg_focus_score: 0 })
  const [priorityStudents, setPriorityStudents] = useState([])
  const [isSpeaking, setIsSpeaking] = useState(false)

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const socketRef = useRef(null)
  const pcMap = useRef({}) // user_id -> RTCPeerConnection

  // Break Timer
  useEffect(() => {
    let interval = null
    if (isBreak) interval = setInterval(() => setBreakTimer(t => t + 1), 1000)
    else setBreakTimer(0)
    return () => clearInterval(interval)
  }, [isBreak])

  // LLM Suggestion
  useEffect(() => {
    const fetchSuggestion = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/session/${user.session_id}/suggestions?context=${user.context}`)
        const data = await res.json()
        if (data.suggestion) {
          setSuggestion(data.suggestion)
          if (isSpeaking) speak(data.suggestion)
        }
        if (data.metrics) setClassMetrics(data.metrics)
        if (data.priority_students) setPriorityStudents(data.priority_students)
      } catch (err) { console.error("Poll error:", err) }
    }
    fetchSuggestion()
    const interval = setInterval(fetchSuggestion, 15000)
    return () => clearInterval(interval)
  }, [user.session_id, user.context, isSpeaking])

  const formatTime = (secs) => `${Math.floor(secs/60)}:${(secs%60).toString().padStart(2,'0')}`

  const addNotification = (text, duration=5000) => {
    const id = Date.now()
    setNotifications(prev => [...prev, { id, text }])
    setTimeout(() => setNotifications(prev => prev.filter(n => n.id !== id)), duration)
  }

  const copySessionId = () => {
    try {
      const sid = user?.session_id || localStorage.getItem('facial_intent_user') ? JSON.parse(localStorage.getItem('facial_intent_user')).session_id : ''
      if (sid) {
        navigator.clipboard.writeText(sid)
        setCopied(true)
        addNotification("Session ID copied to clipboard!")
        setTimeout(() => setCopied(false), 2000)
      } else {
        addNotification("Could not find Session ID")
      }
    } catch (err) {
      console.error("Copy error:", err)
      addNotification("Copy failed. Please manually select the ID.")
    }
  }

  // WebSocket
  useEffect(() => {
    console.log(`[WS] Connecting to ${WS_BASE_URL}/ws/${user.session_id}?user_id=${user.user_id}`)
    const socket = new WebSocket(`${WS_BASE_URL}/ws/${user.session_id}?user_id=${user.user_id}`)
    socketRef.current = socket

    socket.onopen = () => console.log("[WS] Connected successfully")
    socket.onerror = (err) => console.error("[WS] Error:", err)
    socket.onclose = (e) => console.warn("[WS] Closed:", e.code, e.reason)

    const getPC = (studentId) => {
      if (pcMap.current[studentId]) return pcMap.current[studentId]
      
      const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
      pcMap.current[studentId] = pc
      
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          socket.send(JSON.stringify({ type: 'candidate', candidate: event.candidate, target: studentId }))
        }
      }
      
      pc.ontrack = (event) => {
        setRemoteStreams(prev => ({ ...prev, [studentId]: event.streams[0] }))
      }
      
      // Also add OUR tracks to the connection so the student can see us
      if (streamRef.current) {
         streamRef.current.getTracks().forEach(track => pc.addTrack(track, streamRef.current))
      }
      
      return pc
    }

    socket.onmessage = async (event) => {
      const msg = JSON.parse(event.data)
      console.log("[WS] Received:", msg.type, msg.data)
      
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
      else if (msg.type === 'chat') {
        console.log("Teacher received chat:", msg.data)
        setMessages(prev => [...prev, msg.data])
      } else if (msg.type === 'student_joined') {
        const { user_id, user_name, role } = msg.data
        addNotification(`👋 ${user_name} joined!`)
        setStudents(prev => ({ ...prev, [user_id]: { id: user_id, name: user_name, role: role, metrics: null } }))
      } else if (msg.type === 'nudge') {
        const studentId = msg.data.user_id
        const studentName = msg.data.user_name || students[studentId]?.name || `Student #${studentId}`
        addNotification(`${msg.data.nudge_type === 'confusion' ? '❓' : '✋'} ${studentName} (${msg.data.nudge_type})!`)
      } else if (msg.type === 'student_update') {
        setStudents(prev => ({ ...prev, [msg.data.user_id]: { ...prev[msg.data.user_id], metrics: msg.data.metrics } }))
      }
    }
    
    fetch(`${API_BASE_URL}/session/${user.session_id}/participants`).then(res => res.json()).then(data => {
      const parts = {}; data.forEach(p => { parts[p.id] = { id: p.id, name: p.name, role: p.role, metrics: null } }); setStudents(parts)
    })
    
    return () => {
       socket.close()
       Object.values(pcMap.current).forEach(pc => pc.close())
    }
  }, [user.session_id])

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
        
        // If we already have peer connections (students joined before our cam started), add tracks now
        Object.values(pcMap.current).forEach(pc => {
          stream.getTracks().forEach(track => pc.addTrack(track, stream))
        })
      } catch (err) { console.error("Camera error:", err) }
    }
    startCamera()
    return () => { if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop()) }
  }, [])

  const toggleMute = () => {
    if (streamRef.current) {
      const audioTracks = streamRef.current.getAudioTracks()
      const newMute = !isMuted
      audioTracks.forEach(t => t.enabled = !newMute)
      setIsMuted(newMute)
      // Also update any existing PCs
      Object.values(pcMap.current).forEach(pc => {
        pc.getSenders().forEach(sender => {
          if (sender.track && sender.track.kind === 'audio') sender.track.enabled = !newMute
        })
      })
    }
  }

  const toggleCamera = () => {
    if (streamRef.current) {
      const videoTracks = streamRef.current.getVideoTracks()
      const newOff = !isCameraOff
      videoTracks.forEach(t => t.enabled = !newOff)
      setIsCameraOff(newOff)
      // Also update any existing PCs
      Object.values(pcMap.current).forEach(pc => {
        pc.getSenders().forEach(sender => {
          if (sender.track && sender.track.kind === 'video') sender.track.enabled = !newOff
        })
      })
    }
  }

  const handleToggleBreak = async () => {
     const newStatus = isBreak ? 'ended' : 'active'
     try {
        await fetch(`${API_BASE_URL}/session/${user.session_id}/break`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        })
        setIsBreak(!isBreak)
        addNotification(`Session ${newStatus === 'active' ? 'Break Started' : 'Resumed'}`)
     } catch (err) { console.error(err) }
  }

  const moderateUser = async (userId, action) => {
    try {
      await fetch(`${API_BASE_URL}/session/${user.session_id}/participants/${userId}/action`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action })
      })
      // Update local state to reflect toggle instantly for host
      setStudents(prev => {
        const student = prev[userId]
        if (!student) return prev
        if (action === 'mute') return { ...prev, [userId]: { ...student, is_muted: true } }
        if (action === 'unmute') return { ...prev, [userId]: { ...student, is_muted: false } }
        if (action === 'camera_off') return { ...prev, [userId]: { ...student, is_camera_off: true } }
        if (action === 'camera_on') return { ...prev, [userId]: { ...student, is_camera_off: false } }
        return prev
      })
      addNotification(`${action.toUpperCase()} action sent.`)
    } catch (err) { console.error(err) }
  }

  const sendChat = (e) => {
    e.preventDefault(); if (!chatInput.trim()) return
    console.log("Teacher sending chat:", chatInput)
    fetch(`${API_BASE_URL}/chat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: user.session_id, user_name: user.name + " (Host)", message: chatInput })
    })
    setChatInput('')
  }

  return (
    <div className="app-container animate-in" style={{ display: 'flex', flexDirection: 'column', height: '100vh', padding: '1rem' }}>
      
      {/* Floating Notifications */}
      <div style={{ position: 'absolute', top: '90px', left: '50%', transform: 'translateX(-50%)', zIndex: 100, display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {notifications.map(n => (
          <div key={n.id} style={{ background: 'var(--accent-primary)', color: 'white', padding: '0.8rem 1.5rem', borderRadius: '30px', boxShadow: '0 4px 15px rgba(0,0,0,0.3)', fontWeight: 'bold', animation: 'fadeIn 0.3s ease-out' }}>
            {n.text}
          </div>
        ))}
      </div>

      {/* Top Nav */}
      <div className="glass-panel" style={{ padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', alignItems: 'center' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.2rem' }} className="accent-text">🎓 Classroom Management</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>ID: {user.session_id}</span>
            <button className="copy-btn" onClick={copySessionId}>{copied ? '✅' : '📄'}</button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn-secondary" onClick={handleToggleBreak} style={{ border: isBreak ? '1px solid var(--warning)' : '' }}>
            ☕ {isBreak ? `Resume (${formatTime(breakTimer)})` : 'Break'}
          </button>
          <button className="btn-secondary" onClick={() => setActiveTab('main')} style={{ background: activeTab === 'main' ? 'rgba(255,255,255,0.1)' : '' }}>Dashboard</button>
          <button className="btn-secondary" onClick={() => setActiveTab('grid')} style={{ background: activeTab === 'grid' ? 'rgba(255,255,255,0.1)' : '' }}>Grid</button>
          <button className="btn-primary" onClick={onLogout} style={{ background: 'var(--danger)' }}>End</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '1rem', flex: 1, minHeight: 0 }}>
        
        {/* Main Workspace */}
        <div className="glass-panel" style={{ flex: 1, padding: '1.5rem', display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
          
          {/* Session Health Header */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
             <div className="glass-card" style={{ padding: '0.8rem', textAlign: 'center' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>ENGAGEMENT</span>
                <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', margin: '5px 0' }}>
                   <div style={{ height: '100%', width: `${classMetrics.engagement_pct}%`, background: 'var(--success)', borderRadius: '3px', transition: 'width 0.5s ease' }} />
                </div>
                <strong style={{ fontSize: '0.9rem' }}>{classMetrics.engagement_pct}%</strong>
             </div>
             <div className="glass-card" style={{ padding: '0.8rem', textAlign: 'center' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>CONFUSION</span>
                <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '3px', margin: '5px 0' }}>
                   <div style={{ height: '100%', width: `${classMetrics.confusion_pct}%`, background: 'var(--warning)', borderRadius: '3px', transition: 'width 0.5s ease' }} />
                </div>
                <strong style={{ fontSize: '0.9rem' }}>{classMetrics.confusion_pct}%</strong>
             </div>
             <div className="glass-card" style={{ padding: '0.8rem', textAlign: 'center' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>SESSION STATE</span>
                <div style={{ fontSize: '0.9rem', marginTop: '5px', fontWeight: 'bold' }}>{classMetrics.engagement_pct > 70 ? '🟢 Stable' : '🟡 Review Suggested'}</div>
             </div>
          </div>

          {activeTab === 'main' ? (
            <>
              <div style={{ width: '100%', height: '350px', background: '#000', borderRadius: '12px', overflow: 'hidden', position: 'relative', marginBottom: '1.5rem' }}>
                {!isCameraOff && !mediaError ? (
                    <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-secondary)', padding: '2rem', textAlign: 'center' }}>
                        {mediaError || "Camera Off"}
                    </div>
                )}
                <div style={{ position: 'absolute', bottom: 15, left: 15, display: 'flex', gap: '10px' }}>
                   <div style={{ background: 'rgba(0,0,0,0.6)', padding: '5px 12px', borderRadius: '6px', fontSize: '0.8rem' }}>Host Camera</div>
                   <div style={{ display: 'flex', gap: '8px' }}>
                     <button onClick={toggleMute} style={{ background: isMuted ? 'var(--danger)' : 'var(--accent-primary)', border: 'none', color: 'white', padding: '5px 15px', borderRadius: '6px', cursor: 'pointer' }}>
                       {isMuted ? '🔇' : '🎙️'}
                     </button>
                     <button onClick={toggleCamera} style={{ background: isCameraOff ? 'var(--danger)' : 'var(--accent-primary)', border: 'none', color: 'white', padding: '5px 15px', borderRadius: '6px', cursor: 'pointer' }}>
                       {isCameraOff ? '🚫' : '📹'}
                     </button>
                   </div>
                </div>
              </div>
              
              <h3>Participant Sentiment Grid</h3>
              <div className="grid-3" style={{ marginTop: '1rem' }}>
                {Object.entries(students).map(([id, s]) => (
                  <div key={id} className="glass-card" style={{ padding: '1rem', display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <div style={{ width: '120px', height: '90px', background: '#000', borderRadius: '8px', overflow: 'hidden', flexShrink: 0, position: 'relative' }}>
                       {remoteStreams[id] ? (
                         <video 
                           autoPlay 
                           playsInline 
                           style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                           ref={el => { if (el) el.srcObject = remoteStreams[id] }} 
                         />
                       ) : (
                         <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: '0.6rem', color: '#444' }}>OFFLINE</div>
                       )}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>{s.name}</div>
                      {s.metrics ? (
                        <div style={{ fontSize: '0.8rem' }}>
                          <p>Focus: <span style={{ color: s.metrics.focus > 0.7 ? 'var(--success)' : 'var(--warning)' }}>{Math.round(s.metrics.focus * 100)}%</span></p>
                          <p>Intent: <span style={{ textTransform: 'capitalize' }}>{s.metrics.intent.replace('_', ' ')}</span></p>
                          <div style={{ marginTop: '5px' }} className={`badge badge-${s.metrics.risk === 'high' ? 'red' : 'green'}`}>{s.metrics.risk} risk</div>
                        </div>
                      ) : <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Awaiting telemetry...</p>}
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="grid-3">
              {Object.entries(students).map(([id, s]) => (
                <div key={id} style={{ background: '#111', height: '180px', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', border: '1px solid rgba(255,255,255,0.05)', overflow: 'hidden' }}>
                  {remoteStreams[id] ? (
                    <video 
                      autoPlay 
                      playsInline 
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
                      ref={el => { if (el) el.srcObject = remoteStreams[id] }}
                    />
                  ) : <span style={{ color: '#444' }}>AWAITING FEED...</span>}
                  
                  <div style={{ position: 'absolute', bottom: 10, left: 10, background: 'rgba(0,0,0,0.6)', padding: '3px 10px', borderRadius: '4px', fontSize: '0.75rem' }}>{s.name}</div>
                  <div style={{ position: 'absolute', top: 10, right: 10, display: 'flex', gap: '5px' }}>
                     <button 
                        className="copy-btn" style={{ padding: '6px', fontSize: '0.8rem', background: s.is_muted ? 'var(--danger)' : 'var(--accent-primary)' }} 
                        onClick={() => moderateUser(id, s.is_muted ? 'unmute' : 'mute')}
                        title={s.is_muted ? "Unmute Student" : "Mute Student"}
                     >
                        {s.is_muted ? '🔈' : '🎙️'}
                     </button>
                     <button 
                        className="copy-btn" style={{ padding: '6px', fontSize: '0.8rem', background: s.is_camera_off ? 'var(--danger)' : 'var(--accent-primary)' }} 
                        onClick={() => moderateUser(id, s.is_camera_off ? 'camera_on' : 'camera_off')}
                        title={s.is_camera_off ? "Turn On Camera" : "Turn Off Camera"}
                     >
                        {s.is_camera_off ? '📹' : '🚫'}
                     </button>
                     <button className="copy-btn" style={{ padding: '6px', fontSize: '0.8rem', background: 'var(--danger)' }} onClick={() => moderateUser(id, 'kick')} title="Remove Student">KICK</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Side Panel */}
        <div style={{ width: '380px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          
          <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)', background: 'rgba(59, 130, 246, 0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '1rem' }}>🤖 AI Co-Pilot</h3>
              <button 
                onClick={() => setIsSpeaking(!isSpeaking)} 
                title={isSpeaking ? "Turn off voice" : "Turn on voice"}
                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', padding: 0, filter: isSpeaking ? 'none' : 'grayscale(100%)' }}
              >
                🔊
              </button>
            </div>
            <div style={{ padding: '1.2rem', flex: 1, overflowY: 'auto' }}>
              <div className="glass-card" style={{ borderLeft: '4px solid var(--accent-primary)', padding: '1.2rem', marginBottom: '1rem' }}>
                <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: '1.6' }}>{suggestion}</p>
              </div>

              {priorityStudents.length > 0 && (
                <div style={{ marginTop: '1.5rem' }}>
                   <h4 style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '0.8rem' }}>Watchlist ({priorityStudents.length})</h4>
                   <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {priorityStudents.map((ps, idx) => (
                        <div key={idx} className="glass-card" style={{ padding: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderLeft: '4px solid var(--warning)' }}>
                           <span style={{ fontSize: '0.8rem', fontWeight: 'bold' }}>{ps.name}</span>
                           <span style={{ fontSize: '0.7rem' }} className="badge badge-yellow">{ps.issue}</span>
                        </div>
                      ))}
                   </div>
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
              <h3 style={{ margin: 0, fontSize: '1rem' }}>Group Chat</h3>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
              {messages.map((m, i) => {
                const isMe = m.user_name === user.name + " (Host)"
                return (
                    <div key={i} style={{ marginBottom: '0.8rem', background: isMe ? 'rgba(59,130,246,0.1)' : 'rgba(255,255,255,0.03)', padding: '0.6rem', borderRadius: '8px', borderLeft: isMe ? '2px solid var(--accent-primary)' : '' }}>
                    <strong style={{ display: 'block', fontSize: '0.7rem', color: m.user_name.includes('Host') ? 'var(--warning)' : 'var(--accent-primary)' }}>{isMe ? "You (Host)" : m.user_name}</strong>
                    <span style={{ fontSize: '0.85rem' }}>{m.message}</span>
                    </div>
                )
              })}
            </div>
            <div style={{ padding: '1rem', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
              <form onSubmit={sendChat} style={{ display: 'flex', gap: '0.5rem' }}>
                <input type="text" className="input-field" style={{ margin: 0 }} value={chatInput} onChange={e => setChatInput(e.target.value)} placeholder="Message group..." />
                <button type="submit" className="btn-primary" style={{ padding: '0.7rem' }}>Send</button>
              </form>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
