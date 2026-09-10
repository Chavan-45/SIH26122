import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff } from 'lucide-react';

/**
 * Phase 9 Voice Input Button Component using Web Speech API (en-IN).
 * Supports dual-mode interaction via single microphone button:
 *  - MODE A (TAP TO SPEAK): Short tap (<400ms) -> starts listening -> auto-stops when silence detected after speaking.
 *  - MODE B (HOLD TO TALK): Press & hold (>=400ms) -> listens while held -> stops immediately on pointer release.
 *
 * Produces editable text transcript into existing chat input.
 * Does NOT auto-send. Does NOT record or upload audio files.
 */
export default function VoiceInputButton({ onTranscript, disabled, currentInputText = '' }) {
  const [isSupported, setIsSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [errorTooltip, setErrorTooltip] = useState(null);

  const recognitionRef = useRef(null);
  const modeRef = useRef('IDLE'); // 'IDLE' | 'TAP' | 'HOLD'
  const isListeningRef = useRef(false);

  const baseTextRef = useRef('');
  const finalTranscriptRef = useRef('');
  const interimTranscriptRef = useRef('');

  const pressStartTimeRef = useRef(0);
  const isPointerDownRef = useRef(false);
  const silenceTimerRef = useRef(null);
  const isFatalErrorRef = useRef(false);

  const onTranscriptRef = useRef(onTranscript);
  const currentInputTextRef = useRef(currentInputText);

  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  useEffect(() => {
    currentInputTextRef.current = currentInputText;
  }, [currentInputText]);

  // Combine baseText + finalTranscript + interimTranscript cleanly
  const emitCombinedTranscript = () => {
    const base = baseTextRef.current.trim();
    const final = finalTranscriptRef.current.trim();
    const interim = interimTranscriptRef.current.trim();

    let fullText = base;
    if (final) {
      fullText = fullText ? `${fullText} ${final}` : final;
    }
    if (interim) {
      fullText = fullText ? `${fullText} ${interim}` : interim;
    }

    if (onTranscriptRef.current) {
      onTranscriptRef.current(fullText);
    }
  };

  const clearSilenceTimer = () => {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  };

  const resetSilenceTimer = (delayMs = 1400) => {
    clearSilenceTimer();
    // Only auto-stop on silence in TAP mode when pointer is not held
    silenceTimerRef.current = setTimeout(() => {
      if (modeRef.current === 'TAP' && !isPointerDownRef.current && isListeningRef.current) {
        stopRecognition();
      }
    }, delayMs);
  };

  const stopRecognition = () => {
    clearSilenceTimer();
    isListeningRef.current = false;
    setIsListening(false);
    modeRef.current = 'IDLE';

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (e) {
        // Safe catch if already stopped
      }
    }

    // Finalize any lingering interim text into final transcript
    if (interimTranscriptRef.current.trim()) {
      const currentFinal = finalTranscriptRef.current.trim();
      const newInterim = interimTranscriptRef.current.trim();
      finalTranscriptRef.current = currentFinal ? `${currentFinal} ${newInterim}` : newInterim;
      interimTranscriptRef.current = '';
    }
    emitCombinedTranscript();
  };

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      setIsSupported(true);
      try {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-IN';

        recognition.onspeechstart = () => {
          clearSilenceTimer();
        };

        recognition.onspeechend = () => {
          // Speech ended; set silence grace period for TAP mode (1000ms)
          if (modeRef.current === 'TAP' && !isPointerDownRef.current) {
            resetSilenceTimer(1000);
          }
        };

        recognition.onresult = (event) => {
          // Reset silence timer on every new result
          if (modeRef.current === 'TAP' && !isPointerDownRef.current) {
            resetSilenceTimer(1200);
          }

          let interimAcc = '';
          let newFinalAcc = '';

          for (let i = event.resultIndex; i < event.results.length; i++) {
            const resultPiece = event.results[i];
            const transcriptText = resultPiece[0].transcript;
            if (resultPiece.isFinal) {
              newFinalAcc += (newFinalAcc ? ' ' : '') + transcriptText.trim();
            } else {
              interimAcc += (interimAcc ? ' ' : '') + transcriptText.trim();
            }
          }

          if (newFinalAcc) {
            const prevFinal = finalTranscriptRef.current.trim();
            finalTranscriptRef.current = prevFinal ? `${prevFinal} ${newFinalAcc}` : newFinalAcc;
          }

          interimTranscriptRef.current = interimAcc;
          emitCombinedTranscript();
        };

        recognition.onerror = (event) => {
          console.warn('Speech recognition event:', event.error);
          let userMsg = null;

          if (event.error === 'not-allowed' || event.error === 'permission-denied') {
            userMsg = 'Microphone permission was denied.';
            isFatalErrorRef.current = true;
          } else if (event.error === 'audio-capture') {
            userMsg = 'Microphone unavailable or not connected.';
            isFatalErrorRef.current = true;
          } else if (event.error === 'network') {
            userMsg = 'Voice recognition network error.';
            isFatalErrorRef.current = true;
          } else if (event.error === 'no-speech') {
            userMsg = 'No speech detected.';
          }

          if (userMsg) {
            setErrorTooltip(userMsg);
            setTimeout(() => setErrorTooltip(null), 3500);
          }

          if (isFatalErrorRef.current || event.error === 'no-speech') {
            stopRecognition();
          }
        };

        recognition.onend = () => {
          if (isFatalErrorRef.current) {
            isListeningRef.current = false;
            setIsListening(false);
            modeRef.current = 'IDLE';
            return;
          }

          // If onend fires while TAP mode is supposed to be active
          if (modeRef.current === 'TAP' && isListeningRef.current) {
            stopRecognition();
          } else {
            isListeningRef.current = false;
            setIsListening(false);
            modeRef.current = 'IDLE';
          }
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
      clearSilenceTimer();
      isListeningRef.current = false;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch (e) {}
      }
    };
  }, []);

  const startListeningSession = (initialMode) => {
    if (!isSupported || disabled || !recognitionRef.current) return;

    setErrorTooltip(null);
    isFatalErrorRef.current = false;
    clearSilenceTimer();

    // Capture baseText ONCE from current input box text
    baseTextRef.current = currentInputTextRef.current || '';
    finalTranscriptRef.current = '';
    interimTranscriptRef.current = '';

    modeRef.current = initialMode;
    isListeningRef.current = true;
    setIsListening(true);

    try {
      recognitionRef.current.start();
    } catch (err) {
      console.warn('SpeechRecognition start error (retrying):', err);
      try {
        recognitionRef.current.stop();
        recognitionRef.current.start();
      } catch (retryErr) {
        console.error('Failed to start SpeechRecognition:', retryErr);
        isListeningRef.current = false;
        setIsListening(false);
        modeRef.current = 'IDLE';
        return;
      }
    }

    // Set initial no-speech timeout (3500ms) for TAP mode
    if (initialMode === 'TAP') {
      resetSilenceTimer(3500);
    }
  };

  const handlePointerDown = (e) => {
    if (disabled || !isSupported) return;
    if (e.button !== undefined && e.button !== 0) return; // Only main click

    e.preventDefault();
    pressStartTimeRef.current = Date.now();
    isPointerDownRef.current = true;

    // If currently listening in TAP mode, clicking again manually toggles/stops recognition
    if (isListeningRef.current) {
      stopRecognition();
      return;
    }

    startListeningSession('TAP');
  };

  const handlePointerUp = (e) => {
    if (!isPointerDownRef.current) return;
    isPointerDownRef.current = false;

    const pressDuration = Date.now() - pressStartTimeRef.current;
    const HOLD_THRESHOLD_MS = 400;

    if (pressDuration >= HOLD_THRESHOLD_MS) {
      // MODE B: HOLD TO TALK release -> stop recognition immediately
      modeRef.current = 'HOLD';
      stopRecognition();
    } else {
      // MODE A: TAP TO SPEAK -> keep recognition active and set silence timer
      modeRef.current = 'TAP';
      resetSilenceTimer(2500);
    }
  };

  const handlePointerLeaveOrCancel = (e) => {
    if (!isPointerDownRef.current) return;
    isPointerDownRef.current = false;

    const pressDuration = Date.now() - pressStartTimeRef.current;
    const HOLD_THRESHOLD_MS = 400;

    if (pressDuration >= HOLD_THRESHOLD_MS || modeRef.current === 'HOLD') {
      stopRecognition();
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
    <div className="ai-voice-container">
      <button
        type="button"
        onPointerDown={handlePointerDown}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerLeaveOrCancel}
        onPointerCancel={handlePointerLeaveOrCancel}
        disabled={disabled}
        className={`btn-voice-input ${isListening ? 'listening' : ''}`}
        style={{ userSelect: 'none', touchAction: 'none' }}
        title={
          errorTooltip
            ? errorTooltip
            : isListening
            ? 'Tap to stop or release to talk'
            : 'Tap to speak or press & hold to talk (en-IN)'
        }
      >
        <Mic size={16} className="ai-voice-mic-icon" />
      </button>

      {isListening && (
        <span className="ai-voice-listening-status">
          <span className="ai-voice-pulse-dot" />
          <span>Listening...</span>
        </span>
      )}

      {errorTooltip && (
        <div className="ai-voice-error-tooltip">
          {errorTooltip}
        </div>
      )}
    </div>
  );
}

