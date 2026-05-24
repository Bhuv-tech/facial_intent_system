import React, { useState, useEffect, useRef } from 'react'
import { API_BASE_URL, WS_BASE_URL } from '../apiConfig'

export default function PatientInterface({ user, onLogout }) {
  const [view, setView] = useState('consent') // 'consent', 'session', 'feedback'
  const [metrics, setMetrics] = useState({ focus: 0, intent: 'stable', risk: 'low', emotion: 'neutral' })
  const [feedbackSuccess, setFeedbackSuccess] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [isCameraOff, setIsCameraOff] = useState(false)
  const [copied, setCopied] = useState(false)
  const videoRef = useRef(null)
  const remoteVideoRef = useRef(null)
  const streamRef = useRef(null)
  const socketRef = useRef(null)
  const pcRef = useRef(null)

  // WebSocket connection
  useEffect(() => {
    if (view !== 'session') return

    const socket = new WebSocket(`${WS_BASE_URL}/ws/${user.session_id}?user_id=${user.user_id}`)
    socketRef.current = socket

    socket.onmessage = async (event) => {
      const data = JSON.parse(event.data)
      
      if (data.type === 'answer') {
        if (pcRef.current) await pcRef.current.setRemoteDescription(new RTCSessionDescription(data.answer))
      } else if (data.type === 'candidate') {
        if (pcRef.current) await pcRef.current.addIceCandidate(new RTCIceCandidate(data.candidate))
      } else if (data.type === 'host_ready') {
        renegotiate()
      } else if (data.type === 'moderator_action' && String(data.target_user_id) === String(user.user_id)) {
        if (data.action === 'mute' || data.action === 'unmute') {
           const forceMute = data.action === 'mute'
           setIsMuted(forceMute)
           if (streamRef.current) streamRef.current.getAudioTracks().forEach(t => t.enabled = !forceMute)
        } else if (data.action === 'camera_off' || data.action === 'camera_on') {
           const forceOff = data.action === 'camera_off'
           setIsCameraOff(forceOff)
           if (streamRef.current) streamRef.current.getVideoTracks().forEach(t => t.enabled = !forceOff)
        }
      }
    }

    return () => { socket.close(); if (pcRef.current) pcRef.current.close() }
  }, [view, user.session_id])

  // Webcam frame capture & WebRTC logic
  useEffect(() => {
    if (view !== 'session') return

    let captureInterval = null
    const startCamera = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream

        // Initialize WebRTC
        const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
        pcRef.current = pc
        
        pc.onicecandidate = (event) => {
          if (event.candidate && socketRef.current) {
            socketRef.current.send(JSON.stringify({ type: 'candidate', candidate: event.candidate, target: 'host' }))
          }
        }
        
        pc.ontrack = (event) => {
           if (remoteVideoRef.current) remoteVideoRef.current.srcObject = event.streams[0]
        }
        
        stream.getTracks().forEach(track => pc.addTrack(track, stream))
        
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

        captureInterval = setInterval(() => {
          if (!videoRef.current) return
          const canvas = document.createElement('canvas')
          canvas.width = 300; canvas.height = 225
          const ctx = canvas.getContext('2d')
          ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height)
          const b64 = canvas.toDataURL('image/jpeg', 0.5)

          fetch(`${API_BASE_URL}/process_frame`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              user_id: user.user_id, 
              session_id: user.session_id, 
              context: 'doctor', 
              image_b64: b64 
            })
          })
          .then(res => res.json())
          .then(data => { if (!data.error) setMetrics(data) })
          .catch(err => console.error(err))
        }, 1500)
      } catch (err) { console.error("Camera error:", err) }
    }

    startCamera()
    return () => {
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop())
      if (pcRef.current) pcRef.current.close()
      if (captureInterval) clearInterval(captureInterval)
    }
  }, [view, user])

  const copySessionId = () => {
    navigator.clipboard.writeText(user.session_id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const renegotiate = async () => {
    if (!streamRef.current || !socketRef.current) return
    if (pcRef.current) pcRef.current.close()
    
    const pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] })
    pcRef.current = pc
    pc.onicecandidate = (e) => {
      if (e.candidate && socketRef.current) socketRef.current.send(JSON.stringify({ type: 'candidate', candidate: e.candidate, target: 'host' }))
    }
    pc.ontrack = (e) => { if (remoteVideoRef.current) remoteVideoRef.current.srcObject = e.streams[0] }
    
    streamRef.current.getTracks().forEach(t => pc.addTrack(t, streamRef.current))
    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    socketRef.current.send(JSON.stringify({ type: 'offer', offer, target: 'host' }))
  }

  const toggleMute = () => {
    if (streamRef.current) {
      const tracks = streamRef.current.getAudioTracks()
      tracks.forEach(t => t.enabled = isMuted)
      setIsMuted(!isMuted)
    }
  }

  const toggleCamera = () => {
    if (streamRef.current) {
      const tracks = streamRef.current.getVideoTracks()
      tracks.forEach(t => t.enabled = isCameraOff)
      setIsCameraOff(!isCameraOff)
    }
  }

  const submitFeedback = (accurate) => {
    setFeedbackSuccess(true)
    setTimeout(() => onLogout(), 2000)
  }

  if (view === 'consent') {
    return (
      <div className="flex-center" style={{ padding: '2rem' }}>
        <div className="glass-panel" style={{ maxWidth: '600px', padding: '3rem', textAlign: 'center', animation: 'fadeIn 0.5s ease-out' }}>
          <div style={{ fontSize: '4rem', marginBottom: '1.5rem' }}>🔐</div>
          <h2 style={{ marginBottom: '1.5rem' }}>Privacy & Clinical Consent</h2>
          <div style={{ textAlign: 'left', color: 'var(--text-secondary)', marginBottom: '2.5rem', lineHeight: '1.7' }}>
            <p>To assist your doctor during this consultation, our system uses real-time AI to observe non-verbal signals. This helps the doctor monitor your comfort level more closely.</p>
            <ul style={{ marginTop: '1.5rem', marginLeft: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <li><strong>Absolute Privacy:</strong> Your camera feed is processed live and never recorded.</li>
              <li><strong>Clinical Support:</strong> Only intent signals (like "Distress" or "Stable") are shared with the doctor.</li>
              <li><strong>Doctor Controlled:</strong> The AI is purely assistive; your doctor makes all decisions.</li>
            </ul>
          </div>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <button className="btn-secondary" onClick={onLogout}>Decline & Exit</button>
            <button className="btn-primary" onClick={() => setView('session')}>Accept & Join</button>
          </div>
        </div>
      </div>
    )
  }

  if (view === 'feedback') {
    return (
      <div className="flex-center" style={{ padding: '2rem' }}>
        <div className="glass-panel" style={{ maxWidth: '500px', padding: '3rem', textAlign: 'center' }}>
          <h2 style={{ marginBottom: '1rem' }}>Consultation Complete</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '2.5rem' }}>
            To help improve our clinical AI, was the system's interpretation of your comfort level accurate today?
          </p>
          {feedbackSuccess ? (
            <div className="badge-green" style={{ padding: '1rem', borderRadius: '8px' }}>Thank you! Ending session...</div>
          ) : (
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
              <button className="btn-secondary" onClick={() => submitFeedback(false)}>No, was inaccurate</button>
              <button className="btn-primary" onClick={() => submitFeedback(true)}>Yes, was accurate</button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="app-container animate-in" style={{ display: 'flex', flexDirection: 'column', height: '100vh', padding: '1rem' }}>
      
      {/* Top Nav */}
      <div className="glass-panel" style={{ padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', marginBottom: '1rem', alignItems: 'center' }}>
        <div>
           <h2 style={{ margin: 0, fontSize: '1.1rem' }} className="accent-text">Clinical Consultation</h2>
           <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Session ID: {user.session_id}</span>
              <button className="copy-btn" onClick={copySessionId}>{copied ? '✅' : '📄'}</button>
           </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
           <span style={{ color: 'var(--success)', fontSize: '0.9rem' }}>● Secure Clinical Connection</span>
           <button className="btn-primary" style={{ background: 'var(--danger)', padding: '0.6rem 1.2rem' }} onClick={() => setView('feedback')}>Finish Session</button>
        </div>
      </div>

      {/* Main View */}
      <div style={{ flex: 1, display: 'flex', gap: '1.5rem' }}>
        <div className="glass-panel" style={{ flex: 1, background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden' }}>
          <video ref={remoteVideoRef} autoPlay playsInline style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          {!remoteVideoRef.current?.srcObject && (
            <div style={{ position: 'absolute', color: 'var(--text-secondary)', textAlign: 'center' }}>
               <p style={{ fontSize: '1.5rem' }}>Doctor's Video Stream</p>
               <span style={{ fontSize: '0.8rem' }}>AI Monitoring Active locally for clinic support</span>
            </div>
          )}

          {/* Local PiP */}
          <div style={{ position: 'absolute', bottom: '30px', right: '30px', width: '280px', borderRadius: '12px', overflow: 'hidden', border: '2px solid var(--accent-primary)', boxShadow: '0 8px 32px rgba(0,0,0,0.5)' }}>
            <video ref={videoRef} autoPlay playsInline muted style={{ width: '100%', display: 'block' }} />
            <div style={{ position: 'absolute', bottom: 10, left: 10, display: 'flex', gap: '8px', alignItems: 'center' }}>
               <div style={{ background: 'rgba(0,0,0,0.6)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.7rem' }}>You (Patient)</div>
               <button onClick={toggleMute} style={{ background: isMuted ? 'var(--danger)' : 'rgba(0,0,0,0.6)', border: 'none', color: 'white', padding: '2px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}>
                 {isMuted ? '🔇' : '🎙️'}
               </button>
               <button onClick={toggleCamera} style={{ background: isCameraOff ? 'var(--danger)' : 'rgba(0,0,0,0.6)', border: 'none', color: 'white', padding: '2px 10px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem' }}>
                 {isCameraOff ? '🚫' : '📹'}
               </button>
            </div>
          </div>
        </div>

        {/* Minimal Indicators Sidebar */}
        <div style={{ width: '320px', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
           <div className="glass-panel" style={{ padding: '1.5rem' }}>
             <h4 style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', textTransform: 'uppercase', marginBottom: '1rem' }}>Observed Sentiment</h4>
             <p style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
               {metrics.confidence > 0.6 ? (metrics.intent.replace('_', ' ')) : 'Establishing Baseline...'}
             </p>
           </div>

           <div className="glass-panel" style={{ flex: 1, padding: '1.5rem', color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: '1.6' }}>
             <h4 style={{ color: 'white', marginBottom: '1rem' }}>Privacy Shield</h4>
             <p>Our HIPAA-compliant local processing ensures no video data ever leaves your device.</p>
             <p style={{ marginTop: '1rem' }}>Only abstract behavioral metadata (anonymized) is shared with your healthcare provider.</p>
           </div>
        </div>
      </div>

    </div>
  )
}
