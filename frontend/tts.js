/*
tts.js

This file adds browser speech output for the wine assistant.
It tries to pick a more natural installed English voice when available,
cleans the text before speaking, and uses calmer speaking settings.

Why this file exists:
- Browser TTS can sound robotic with bad default voices.
- Better voice selection and better pacing can improve the result.
- This keeps speech-output logic separate from the main UI logic.
*/

(function () {
  const speakButton = document.getElementById("speak-button");
  const stopSpeechButton = document.getElementById("stop-speech-button");
  const autoSpeakCheckbox = document.getElementById("auto-speak-checkbox");

  const ui = window.wineAssistantUI;

  if (!speakButton || !stopSpeechButton || !autoSpeakCheckbox || !ui) {
    return;
  }

  if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
    speakButton.disabled = true;
    stopSpeechButton.disabled = true;
    return;
  }

  let availableVoices = [];

  function loadVoices() {
    availableVoices = window.speechSynthesis.getVoices() || [];
    console.log("Available voices:", availableVoices.map(v => `${v.name} (${v.lang})`));
  }

  loadVoices();
  window.speechSynthesis.onvoiceschanged = loadVoices;

  /**
   * Prefer more natural English voices when available.
   * Voice names vary by browser and OS, so this is heuristic-based.
   */
  function pickVoice() {
    if (!availableVoices.length) {
      return null;
    }

    const preferredNameHints = [
      "Natural",
      "Neural",
      "Google US English",
      "Google UK English Female",
      "Microsoft Aria",
      "Microsoft Jenny",
      "Samantha",
      "Siri"
    ];

    // First try exact/preferred natural-sounding names.
    for (const hint of preferredNameHints) {
      const match = availableVoices.find((voice) =>
        voice.lang?.startsWith("en") && voice.name.includes(hint)
      );
      if (match) {
        return match;
      }
    }

    // Then prefer any English local voice.
    const englishLocal = availableVoices.find(
      (voice) => voice.lang?.startsWith("en") && voice.localService
    );
    if (englishLocal) {
      return englishLocal;
    }

    // Then any English voice.
    const englishAny = availableVoices.find((voice) => voice.lang?.startsWith("en"));
    if (englishAny) {
      return englishAny;
    }

    // Final fallback.
    return availableVoices[0] || null;
  }

  /**
   * Make spoken text sound a bit more natural.
   */
  function normalizeForSpeech(text) {
    if (!text) {
      return "";
    }

    return String(text)
      .replace(/\$/g, " dollars ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function stopSpeaking() {
    window.speechSynthesis.cancel();
  }

  function speakText(text) {
    const cleaned = normalizeForSpeech(text);

    if (!cleaned) {
      ui.setStatus("There is no spoken answer to read yet.", "error");
      return;
    }

    stopSpeaking();

    const utterance = new SpeechSynthesisUtterance(cleaned);
    const voice = pickVoice();

    if (voice) {
      utterance.voice = voice;
      console.log("Using TTS voice:", voice.name, voice.lang);
    }

    // Slightly slower pace usually sounds less robotic.
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    utterance.onstart = () => {
      ui.setStatus("Speaking answer...", "loading");
    };

    utterance.onend = () => {
      ui.clearStatus();
    };

    utterance.onerror = () => {
      ui.setStatus("Voice output failed.", "error");
    };

    window.speechSynthesis.speak(utterance);
  }

  function speakLatestResponse() {
    const response = ui.lastResponse;

    if (!response) {
      ui.setStatus("Ask a question first so there is something to speak.", "error");
      return;
    }

    const textToSpeak = response.spoken_summary || response.summary || "";
    speakText(textToSpeak);
  }

  speakButton.addEventListener("click", () => {
    speakLatestResponse();
  });

  stopSpeechButton.addEventListener("click", () => {
    stopSpeaking();
    ui.clearStatus();
  });

  window.addEventListener("wine-response-ready", (event) => {
    const response = event.detail?.response || event.detail;
    const shouldAutoSpeak = event.detail?.autoSpeak !== false;
    if (!response) {
      return;
    }

    if (autoSpeakCheckbox.checked && shouldAutoSpeak) {
      const textToSpeak = response.spoken_summary || response.summary || "";
      speakText(textToSpeak);
    }
  });

  window.wineAssistantSpeech = {
    speakLatestResponse,
    stopSpeaking
  };
})();
