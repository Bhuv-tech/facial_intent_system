import React, { useState, useEffect } from 'react'

const QUIZ_QUESTIONS = [
  { q: "What is the primary goal of the Facial Intent System?", a: ["Surveillance", "Better Communication", "Data Collection", "Entertainment"], correct: 1 },
  { q: "Which AI model helps in inferring intentions?", a: ["CNN", "RNN", "LLM", "GNN"], correct: 2 },
  { q: "Emotional intelligence is key to identifying what?", a: ["Faces", "Intentions", "Colors", "Shapes"], correct: 1 },
  { q: "The system provides suggestions using which models?", a: ["Local LLM", "Cloud API", "Fixed Rules", "Randomizer"], correct: 0 }
]

const EMOJIS = ['🧠', '🤖', '🎨', '🚀', '🌈', '💎', '🔥', '🌟']

export default function InteractiveBreak() {
  const [showGame, setShowGame] = useState(false)
  const [quizIndex, setQuizIndex] = useState(0)
  const [score, setScore] = useState(0)
  const [quizFinished, setQuizFinished] = useState(false)
  
  // Emoji Game State
  const [cards, setCards] = useState([])
  const [flipped, setFlipped] = useState([])
  const [matched, setMatched] = useState([])
  const [moves, setMoves] = useState(0)

  // Initialize Emoji Match
  useEffect(() => {
    if (showGame) {
      const pairEmojis = [...EMOJIS, ...EMOJIS]
      const shuffled = pairEmojis.sort(() => Math.random() - 0.5).map((emoji, index) => ({ id: index, emoji }))
      setCards(shuffled)
      setMatched([])
      setFlipped([])
      setMoves(0)
    }
  }, [showGame])

  const handleQuizAnswer = (idx) => {
    if (idx === QUIZ_QUESTIONS[quizIndex].correct) setScore(s => s + 1)
    if (quizIndex < QUIZ_QUESTIONS.length - 1) {
      setQuizIndex(quizIndex + 1)
    } else {
      setQuizFinished(true)
    }
  }

  const handleCardClick = (id) => {
    if (flipped.length === 2 || matched.includes(id) || flipped.includes(id)) return
    
    const newFlipped = [...flipped, id]
    setFlipped(newFlipped)
    
    if (newFlipped.length === 2) {
      setMoves(m => m + 1)
      const [first, second] = newFlipped
      if (cards[first].emoji === cards[second].emoji) {
        setMatched([...matched, first, second])
        setFlipped([])
      } else {
        setTimeout(() => setFlipped([]), 1000)
      }
    }
  }

  const resetQuiz = () => {
    setQuizIndex(0)
    setScore(0)
    setQuizFinished(false)
  }

  return (
    <div className="glass-panel animate-in" style={{ padding: '2rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="accent-text" style={{ margin: 0 }}>⏳ Session Break</h2>
        <div className="pill-toggle" style={{ display: 'flex', background: 'rgba(0,0,0,0.2)', padding: '5px', borderRadius: '12px' }}>
          <button 
            className="btn-secondary" 
            onClick={() => setShowGame(false)}
            style={{ padding: '0.5rem 1rem', background: !showGame ? 'var(--accent-primary)' : 'transparent', border: 'none' }}
          >
            Quick Quiz
          </button>
          <button 
            className="btn-secondary" 
            onClick={() => setShowGame(true)}
            style={{ padding: '0.5rem 1rem', background: showGame ? 'var(--accent-primary)' : 'transparent', border: 'none' }}
          >
            Fun Game
          </button>
        </div>
      </div>

      {!showGame ? (
        <div className="glass-card" style={{ padding: '2.5rem', textAlign: 'center', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          {!quizFinished ? (
            <>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>QUESTION {quizIndex + 1} OF {QUIZ_QUESTIONS.length}</p>
              <h3 style={{ fontSize: '1.8rem', marginBottom: '2.5rem' }}>{QUIZ_QUESTIONS[quizIndex].q}</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                {QUIZ_QUESTIONS[quizIndex].a.map((ans, i) => (
                  <button key={i} className="btn-secondary" onClick={() => handleQuizAnswer(i)} style={{ padding: '1.2rem' }}>
                    {ans}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div>
              <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>🎉</div>
              <h2>Quiz Finished!</h2>
              <p style={{ fontSize: '1.5rem', margin: '1rem 0' }}>Your score: <span style={{ color: 'var(--success)', fontWeight: 'bold' }}>{score}/{QUIZ_QUESTIONS.length}</span></p>
              <button className="btn-primary" onClick={resetQuiz}>Try Again</button>
            </div>
          )}
        </div>
      ) : (
        <div className="glass-card" style={{ padding: '2rem', flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', marginBottom: '1rem' }}>
             <span>Matched: {matched.length / 2} / {EMOJIS.length}</span>
             <span>Moves: {moves}</span>
          </div>
          <div style={{ 
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', 
            width: '100%', maxWidth: '500px', flex: 1 
          }}>
            {cards.map((card, i) => {
              const isFlipped = flipped.includes(i) || matched.includes(i)
              return (
                <div 
                  key={i} 
                  onClick={() => handleCardClick(i)}
                  style={{
                    height: '80px', background: isFlipped ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)',
                    borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '2rem', cursor: 'pointer', transition: 'all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                    transform: isFlipped ? 'rotateY(0)' : 'rotateY(180deg)',
                    border: '1px solid rgba(255,255,255,0.1)'
                  }}
                >
                  <span style={{ display: isFlipped ? 'block' : 'none' }}>{card.emoji}</span>
                </div>
              )
            })}
          </div>
          {matched.length === cards.length && matched.length > 0 && (
              <div style={{ marginTop: '2rem', textAlign: 'center' }}>
                  <h3 className="accent-text">Well Done!</h3>
                  <button className="btn-primary" onClick={() => setShowGame(false)}>Back to Quiz</button>
              </div>
          )}
        </div>
      )}

      <div style={{ textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
        <p>Break time is healthy! Stretch your eyes and relax. 🧘‍♂️</p>
      </div>
    </div>
  )
}
