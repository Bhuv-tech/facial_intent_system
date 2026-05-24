import React, { useState, useEffect, useRef } from 'react'
import { API_BASE_URL, WS_BASE_URL } from '../apiConfig'
import InteractiveBreak from './InteractiveBreak'

export default function StudentDashboard({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState(user.is_break ? 'break' : 'meeting')
  const [isBreakMode, setIsBreakMode] = useState(user.is_break || false)
  const [notification, setNotification] = useState(null)
  const [chatMessages, setChatMessages] = useState([])
  const [chatInput, setChatInput] = useState('')
  const [isMuted, setIsMuted] = useState(false)
  const [isCameraOff, setIsCameraOff] = useState(false)
  const [mediaError, setMediaError] = useState(null)
  const [copied, setCopied] = useState(false)
  const [advice, setAdvice] = useState("AI Mentor: Connecting to your stream...")
  
  const [metrics, setMetrics] = useState({ focus: 0, intent: 'unknown', risk: 'low', emotion: 'neutral' })
  const [remoteStream, setRemoteStream] = useState(null)
  
  const videoRef = useRef(null)
  const remoteVideoRef = useRef(null)
  const streamRef = useRef(null)
  const socketRef = useRef(null)
  const pcRef = useRef(null)

  const addNotification = (text) => {
    setNotification(text)
    setTimeout(() => setNotification(null), 5000)
  }

  // Effect to assign video streams to elements when they mount/change
  useEffect(() => {
    if (videoRef.current && streamRef.current && !isCameraOff) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [activeTab, isBreakMode, isCameraOff])

  useEffect(() => {
    if (remoteVideoRef.current && remoteStream) {
      remoteVideoRef.current.srcObject = remoteStream
    }
  }, [activeTab, remoteStream])


  // Consistently create PC with all necessary handlers
  const createPC = (socket) => {
    if (pcRef.current) pcRef.current.close()
    
    const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
    pcRef.current = pc
    
    pc.onicecandidate = (event) => {
      if (event.candidate && socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'candidate', candidate: event.candidate, target: 'host' }))
      }
    }
    
    pc.ontrack = (event) => {
      console.log("Receiving remote track from host...")
      setRemoteStream(event.streams[0])
    }
    
    if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => pc.addTrack(track, streamRef.current))
    }
    
    return pc
  }

  // WebSocket connection
  useEffect(() => {
    console.log("Connecting to WebSocket...")
    const socket = new WebSocket(`${WS_BASE_URL}/ws/${user.session_id}?user_id=${user.user_id}`)
    socketRef.current = socket

    socket.onmessage = async (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'offer') {
        const pc = createPC(socket)
        await pc.setRemoteDescription(new RTCSessionDescription(data.offer))
        const answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        socket.send(JSON.stringify({ type: 'answer', answer: answer, target: data.from }))
      } else if (data.type === 'answer') {
        if (pcRef.current) await pcRef.current.setRemoteDescription(new RTCSessionDescription(data.answer))
      } else if (data.type === 'candidate') {
        if (pcRef.current) await pcRef.current.addIceCandidate(new RTCIceCandidate(data.candidate))
      } else if (data.type === 'chat') {
        setChatMessages(prev => [...prev, { 
            id: Date.now(), 
            user_name: data.data.user_name || "Unknown", 
            message: data.data.message || "" 
        }])
      } else if (data.type === 'break_toggle') {
        const active = data.status === 'active'
        setIsBreakMode(active)
        setActiveTab(active ? 'break' : 'meeting')
        addNotification(`Host has ${active ? 'started a break' : 'resumed the session'}.`)
      } else if (data.type === 'moderator_action' && String(data.target_user_id) === String(user.user_id)) {
        if (data.action === 'kick') {
          alert("You have been removed from the session.")
          if (typeof onLogout === 'function') onLogout()
        } else if (data.action === 'mute' || data.action === 'unmute') {
          const forceMute = data.action === 'mute'
          setIsMuted(forceMute)
          if (streamRef.current) {
            streamRef.current.getAudioTracks().forEach(track => { track.enabled = !forceMute })
          }
          addNotification(`The host has ${forceMute ? 'muted' : 'unmuted'} your microphone.`)
        } else if (data.action === 'camera_off' || data.action === 'camera_on') {
          const forceOff = data.action === 'camera_off'
          setIsCameraOff(forceOff)
          if (streamRef.current) {
            streamRef.current.getVideoTracks().forEach(track => { track.enabled = !forceOff })
          }
          addNotification(`The host has turned your camera ${forceOff ? 'off' : 'on'}.`)
        }
      } else if (data.type === 'host_ready') {
        renegotiate()
      }
    }
    return () => { socket.close(); if (pcRef.current) pcRef.current.close() }
  }, [user.session_id])

  // AI Mentor Advice for Student
  useEffect(() => {
    const fetchAdvice = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/session/${user.session_id}/student_advice?user_id=${user.user_id}`)
        const data = await res.json()
        if (data.advice) setAdvice(data.advice)
      } catch (err) { console.error("Advice error:", err) }
    }
    fetchAdvice()
    const interval = setInterval(fetchAdvice, 20000)
    return () => clearInterval(interval)
  }, [user.session_id, user.user_id])

  // Initialize Camera
  useEffect(() => {
    let captureInterval = null
    const startCamera = async () => {
      try {
        setMediaError(null)
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        streamRef.current = stream
        
        // Initial Offer
        renegotiate()

        captureInterval = setInterval(() => {
          if (!videoRef.current || !streamRef.current || isCameraOff) return
          const canvas = document.createElement('canvas')
          canvas.width = 300; canvas.height = 225
          const ctx = canvas.getContext('2d')
          ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height)
          const b64 = canvas.toDataURL('image/jpeg', 0.5)
          fetch(`${API_BASE_URL}/process_frame`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user.user_id, session_id: user.session_id, context: user.context, image_b64: b64 })
          })
          .then(res => res.json()).then(data => { 
            if (data && !data.error) {
              setMetrics(data)
              console.log("[AI] Frame processed:", data.intent, data.confidence)
            } else {
              console.warn("[AI] Process Error:", data.error)
            }
          })
          .catch(err => console.error("[AI] Network Error:", err))
        }, 1000)
      } catch (err) { 
        console.error("Camera error:", err) 
        setMediaError(err.name === 'NotReadableError' ? "Camera already in use by another tab" : "Camera access denied")
      }
    }
    startCamera()
    return () => {
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop())
      if (pcRef.current) pcRef.current.close()
      if (captureInterval) clearInterval(captureInterval)
    }
  }, [user.user_id, user.session_id])

  const toggleMute = () => {
    if (streamRef.current) {
      const audioTracks = streamRef.current.getAudioTracks()
      const newMute = !isMuted
      audioTracks.forEach(track => { track.enabled = !newMute })
      setIsMuted(newMute)
    }
  }

  const toggleCamera = () => {
    if (streamRef.current) {
      const videoTracks = streamRef.current.getVideoTracks()
      const newOff = !isCameraOff
      videoTracks.forEach(track => { track.enabled = !newOff })
      setIsCameraOff(newOff)
    }
  }

  const renegotiate = async () => {
    if (!streamRef.current || !socketRef.current) return
    
    const pc = createPC(socketRef.current)
    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    
    const sendOffer = () => {
       if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
          socketRef.current.send(JSON.stringify({ type: 'offer', offer: offer, target: 'host' }))
       } else {
          setTimeout(sendOffer, 500)
       }
    }
    sendOffer()
  }

  const copySessionId = () => {
    navigator.clipboard.writeText(user.session_id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const sendNudge = async (type) => {
    try {
      await fetch(`${API_BASE_URL}/nudge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: user.session_id, user_id: user.user_id, nudge_type: type })
      })
      addNotification(`Sent ${type} alert to host!`)
    } catch (err) { console.error("Nudge error:", err) }
  }

  const handleSendChat = (e) => {
    e.preventDefault()
    if (!chatInput.trim()) return
    fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            session_id: user.session_id, 
            user_name: user.name, 
            message: chatInput 
        })
    })
    setChatInput('')
  }

  const contextMap = {
    teacher: { title: 'Classroom', localLabel: 'Student' },
    doctor: { title: 'Consultation', localLabel: 'Patient' },
    hr: { title: 'Interview', localLabel: 'Candidate' }
  }
  const ctxConf = contextMap[user.context] || { title: 'Session', localLabel: 'Participant' }

  return (
    <div className="app-container animate-in" style={{ display: 'flex', flexDirection: 'column', height: '100vh', padding: '1rem' }}>
      
      {notification && (
        <div style={{ position: 'absolute', top: '20px', left: '50%', transform: 'translateX(-50%)', zIndex: 100, background: 'var(--accent-primary)', color: 'white', padding: '0.8rem 2rem', borderRadius: '30px', boxShadow: '0 4px 20px rgba(59, 130, 246, 0.4)', fontWeight: 'bold', animation: 'fadeIn 0.3s ease-out' }}>
          {notification}
        </div>
      )}

      <div className="glass-panel" style={{ padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', alignItems: 'center' }}>
        <div>
           <h2 style={{ margin: 0, fontSize: '1.1rem' }} className="accent-text">{ctxConf.title} Mode</h2>
           <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>ID: {user.session_id}</span>
              <button className="copy-btn" onClick={copySessionId}>{copied ? '✅' : '📄'}</button>
           </div>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn-secondary" onClick={() => setActiveTab('meeting')} style={{ border: activeTab === 'meeting' ? '1px solid var(--accent-primary)' : '' }}>Meeting Room</button>
          <button className="btn-secondary" onClick={() => setActiveTab('insights')} style={{ border: activeTab === 'insights' ? '1px solid var(--accent-primary)' : '' }}>AI Insights</button>
          {isBreakMode && <button className="btn-secondary" onClick={() => setActiveTab('break')} style={{ border: activeTab === 'break' ? '1px solid var(--warning)' : '', color: 'var(--warning)' }}>☕ Break Activities</button>}
          <button className="btn-primary" onClick={onLogout} style={{ background: 'var(--danger)' }}>Leave</button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '1rem', flex: 1, height: 'calc(100% - 90px)' }}>
        
        <div className="glass-panel" style={{ flex: 1, padding: '1.5rem', display: 'flex', flexDirection: 'column', position: 'relative' }}>
          {activeTab === 'break' ? (
              <InteractiveBreak />
          ) : activeTab === 'meeting' ? (
            <div style={{ flex: 1, background: '#000', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden' }}>
              
              {remoteStream ? (
                  <video ref={remoteVideoRef} autoPlay playsInline style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
              ) : (
                <div style={{ color: 'var(--text-secondary)', fontSize: '1.2rem', textAlign: 'center', padding: '1rem' }}>
                    <h3>{isBreakMode ? "Session is on BREAK" : "Wait for Host..."}</h3>
                    <p>{isBreakMode ? "Relax and try some activities in the Break tab!" : "AI Monitoring Active"}</p>
                </div>
              )}

              <div style={{ position: 'absolute', bottom: '20px', right: '20px', width: '280px', borderRadius: '12px', overflow: 'hidden', border: `2px solid ${isMuted || isCameraOff || mediaError ? 'var(--danger)' : 'var(--accent-primary)'}`, boxShadow: '0 8px 32px rgba(0,0,0,0.5)', background: '#000' }}>
                {!isCameraOff && !mediaError ? (
                    <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', display: 'block' }} />
                ) : (
                    <div style={{ padding: '2rem', textAlign: 'center', background: '#222', fontSize: '0.8rem' }}>
                        {mediaError || "Your Camera Off"}
                    </div>
                )}
                <div style={{ position: 'absolute', bottom: 10, left: 10, display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <div style={{ background: 'rgba(0,0,0,0.6)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem' }}>You</div>
                  <button onClick={toggleMute} style={{ background: isMuted ? 'var(--danger)' : 'rgba(0,0,0,0.6)', border: 'none', color: 'white', padding: '2px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}>
                    {isMuted ? '🔇' : '🎙️'}
                  </button>
                  <button onClick={toggleCamera} style={{ background: isCameraOff ? 'var(--danger)' : 'rgba(0,0,0,0.6)', border: 'none', color: 'white', padding: '2px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}>
                    {isCameraOff ? '🚫' : '📹'}
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ flex: 1, animation: 'fadeIn 0.5s ease-out' }}>
              <h3 style={{ marginBottom: '1.5rem' }}>Personal AI Insights</h3>
              <div className="grid-2">
                <div className="glass-card" style={{ textAlign: 'center', padding: '2.5rem' }}>
                  <h4 style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>Engagement Score</h4>
                  <div className="pulse-primary" style={{ fontSize: '4rem', fontWeight: 'bold', color: metrics.focus > 0.7 ? 'var(--success)' : 'var(--warning)', display: 'inline-block', padding: '10px 20px', borderRadius: '20px' }}>
                    {Math.round(metrics.focus * 100)}%
                  </div>
                  <p style={{ marginTop: '1.5rem', color: 'var(--text-secondary)' }}>{advice}</p>
                </div>
                <div className="glass-card" style={{ padding: '2.5rem' }}>
                   <div style={{ marginBottom: '1.5rem' }}><label style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>CURRENT EMOTION</label><p style={{ fontSize: '1.5rem', textTransform: 'capitalize' }}>{metrics.emotion}</p></div>
                   <div style={{ marginBottom: '1.5rem' }}><label style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>INFERRED INTENT</label><p style={{ fontSize: '1.5rem' }}>{(metrics.intent || 'Searching...').replace('_', ' ')}</p></div>
                   <div><label style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>SIGNAL STABILITY</label><p><span className={`badge badge-${metrics.risk === 'high' ? 'red' : metrics.risk === 'medium' ? 'yellow' : 'green'}`}>{metrics.risk}</span></p></div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div style={{ width: '380px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <h3 style={{ marginBottom: '1.2rem', fontSize: '1rem' }}>Quick Feedback</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
               <button className="glass-card" style={{ textAlign: 'center', cursor: 'pointer' }} onClick={() => sendNudge('confusion')}><span style={{ fontSize: '1.5rem', display: 'block' }}>❓</span><span style={{ fontSize: '0.7rem', fontWeight: 600 }}>Confused</span></button>
               <button className="glass-card" style={{ textAlign: 'center', cursor: 'pointer' }} onClick={() => sendNudge('hand')}><span style={{ fontSize: '1.5rem', display: 'block' }}>✋</span><span style={{ fontSize: '0.7rem', fontWeight: 600 }}>Raise Hand</span></button>
            </div>
          </div>

          <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)' }}><h3 style={{ margin: 0, fontSize: '0.9rem' }}>Chat Room</h3></div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '1rem' }}>
              {chatMessages.map(m => {
                const isMe = m.user_name === user.name
                return (
                    <div key={m.id} style={{ marginBottom: '0.8rem', background: isMe ? 'rgba(59,130,246,0.1)' : 'rgba(255,255,255,0.03)', padding: '0.6rem', borderRadius: '8px', borderLeft: isMe ? '2px solid var(--accent-primary)' : '' }}>
                    <strong style={{ display: 'block', fontSize: '0.7rem', color: m.user_name?.includes('Host') ? 'var(--warning)' : isMe ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>
                        {isMe ? "You" : m.user_name}
                    </strong>
                    <span style={{ fontSize: '0.85rem' }}>{m.message}</span>
                    </div>
                )
              })}
            </div>
            <form onSubmit={handleSendChat} style={{ padding: '0.8rem', borderTop: '1px solid rgba(255,255,255,0.1)', display: 'flex', gap: '0.5rem' }}>
              <input type="text" className="input-field" style={{ margin: 0, padding: '0.6rem' }} value={chatInput} onChange={e => setChatInput(e.target.value)} placeholder="Type a message..." />
              <button type="submit" className="btn-primary" style={{ padding: '0.6rem 1rem', fontSize: '0.8rem' }}>Send</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
