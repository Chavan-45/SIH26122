import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff } from 'lucide-react';

/**
 * Phase 9 Voice Input Button Component using Web Speech API (en-IN).
 * Produces editable text transcript only. Does NOT record or store audio files.
 */
export default function VoiceInputButton({ onTranscript, disabled }) {
  const [isSupported, setIsSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [errorTooltip, setErrorTooltip] = useState(null);

  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      setIsSupported(true);
      try {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'en-IN';

        recognition.onresult = (event) => {
          let currentTranscript = '';
          for (let i = event.resultIndex; i < event.results.length; i++) {
            currentTranscript += event.results[i][0].transcript;
          }
          if (currentTranscript && onTranscript) {
            onTranscript(currentTranscript.trim());
          }
        };

        recognition.onerror = (event) => {
          console.warn('Speech recognition error:', event.error);
          setIsListening(false);
          let userMsg = 'Voice recognition error occurred.';
          if (event.error === 'not-allowed' || event.error === 'permission-denied') {
            userMsg = 'Microphone permission was denied.';
          } else if (event.error === 'no-speech') {
            userMsg = 'No speech was detected. Please try speaking again.';
          } else if (event.error === 'audio-capture') {
            userMsg = 'Microphone is unavailable or not connected.';
          } else if (event.error === 'network') {
            userMsg = 'Voice recognition encountered a network error.';
          }
          setErrorTooltip(userMsg);
          setTimeout(() => setErrorTooltip(null), 4000);
        };

        recognition.onend = () => {
          setIsListening(false);
        };

        recognitionRef.current = recognition;
      } catch (err) {
        console.error('Failed to initialize SpeechRecognition:', err);
        setIsSupported(false);
      }
    } else {
      setIsSupported(false);
    }

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {}
      }
    };
  }, [onTranscript]);

  const toggleListening = () => {
    if (!isSupported || disabled || !recognitionRef.current) return;

    setErrorTooltip(null);
    if (isListening) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.error('Failed to start speech recognition:', err);
        setIsListening(false);
      }
    }
  };

  if (!isSupported) {
    return (
      <button
        type="button"
        disabled
        className="btn-voice-input"
        title="Voice input is not supported in this browser. Please type your message."
      >
        <MicOff size={16} className="ai-voice-mic-icon text-slate-400" />
      </button>
    );
  }

  return (
    <div className="relative inline-flex items-center">
      <button
        type="button"
        onClick={toggleListening}
        disabled={disabled}
        className={`btn-voice-input ${isListening ? 'listening' : ''}`}
        title={
          errorTooltip
            ? errorTooltip
            : isListening
            ? 'Listening (en-IN)... Click to stop'
            : 'Start voice input (en-IN)'
        }
      >
        {isListening ? (
          <>
            <span className="ai-voice-pulse-dot" />
            <Mic size={16} className="ai-voice-mic-icon" />
          </>
        ) : (
          <Mic size={16} className="ai-voice-mic-icon" />
        )}
      </button>

      {errorTooltip && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: '50%',
            transform: 'translateX(-50%)',
            marginBottom: '0.4rem',
            backgroundColor: '#1E293B',
            color: '#FFFFFF',
            fontSize: '0.725rem',
            padding: '0.35rem 0.65rem',
            borderRadius: '4px',
            whiteSpace: 'nowrap',
            zIndex: 30,
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            pointerEvents: 'none',
          }}
        >
          {errorTooltip}
        </div>
      )}
    </div>
  );
}
