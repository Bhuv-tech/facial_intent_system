/**
 * Lightweight TTS utility using the Browser's native Speech Synthesis API.
 */
export const speak = (text) => {
  if (!window.speechSynthesis) {
    console.warn("Speech synthesis not supported in this browser.")
    return
  }

  // Cancel any ongoing speech
  window.speechSynthesis.cancel()

  const utterance = new SpeechSynthesisUtterance(text)
  
  // Choose a clear voice if available
  const voices = window.speechSynthesis.getVoices()
  const preferredVoice = voices.find(v => v.name.includes("Google") || v.name.includes("Natural"))
  if (preferredVoice) utterance.voice = preferredVoice

  utterance.rate = 1.0
  utterance.pitch = 1.0
  utterance.volume = 1.0

  window.speechSynthesis.speak(utterance)
}
