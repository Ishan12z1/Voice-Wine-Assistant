/*
voice.js

This file adds Step 9 voice input to the browser UI.
It uses the browser speech recognition API when available so the user can:
- click the microphone button
- speak a wine question
- see the transcript appear in the input box
- automatically run the normal query flow

Why this file exists:
- It adds speech-to-text without changing backend logic.
- It reuses the existing text submission path from app.js.
- It keeps voice handling isolated from the rest of the UI code.
*/

(function () {
  const micButton = document.getElementById("mic-button");
  const voiceSupportHint = document.getElementById("voice-support-hint");

  const ui = window.wineAssistantUI;
  if (!micButton || !ui) {
    return;
  }

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    micButton.disabled = true;
    micButton.title = "Voice input is not available in this browser";
    voiceSupportHint.textContent = "Voice input is not available in this browser.";
    return;
  }

  const recognition = new SpeechRecognition();

  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  let isListening = false;
  let finalTranscript = "";

  function setListeningUI(listening) {
    isListening = listening;

    if (listening) {
      micButton.classList.add("listening");
      micButton.setAttribute("aria-label", "Stop voice input");
      micButton.title = "Listening...";
    } else {
      micButton.classList.remove("listening");
      micButton.setAttribute("aria-label", "Start voice input");
      micButton.title = "Speak your question";
    }
  }

  function getFriendlyVoiceError(errorCode) {
    switch (errorCode) {
      case "no-speech":
        return "No speech was detected. Try again.";
      case "audio-capture":
        return "No microphone was available.";
      case "not-allowed":
        return "Microphone permission was denied.";
      case "network":
        return "Speech recognition failed because of a network issue.";
      case "aborted":
        return "Voice input was canceled.";
      default:
        return `Voice input failed: ${errorCode}`;
    }
  }

  micButton.addEventListener("click", () => {
    if (isListening) {
      recognition.stop();
      return;
    }

    finalTranscript = "";

    try {
      recognition.start();
    } catch (error) {
      ui.setStatus("Voice input could not be started.", "error");
    }
  });

  recognition.onstart = () => {
    setListeningUI(true);
    voiceSupportHint.textContent = "Listening... speak your wine question.";
    ui.setStatus("Listening... speak your wine question.", "loading");
  };

  recognition.onresult = (event) => {
    let interimTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const transcriptChunk = event.results[i][0].transcript;

      if (event.results[i].isFinal) {
        finalTranscript += `${transcriptChunk} `;
      } else {
        interimTranscript += transcriptChunk;
      }
    }

    const combinedTranscript = `${finalTranscript}${interimTranscript}`.trim();
    ui.questionInput.value = combinedTranscript;
  };

  recognition.onerror = (event) => {
    setListeningUI(false);
    voiceSupportHint.textContent = "";
    ui.setStatus(getFriendlyVoiceError(event.error), "error");
  };

  recognition.onend = async () => {
    const transcript = ui.questionInput.value.trim();

    setListeningUI(false);
    voiceSupportHint.textContent = "";

    if (!transcript) {
      ui.setStatus("No transcript was captured. Try again.", "error");
      return;
    }

    await ui.submitQuestion(transcript);
  };
})();