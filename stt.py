"""Realtime microphone speech-to-text using Google's online speech service."""

import speech_recognition as sr


class SpeechToText:
    """Manages a background microphone listener and reports recognized text."""

    def __init__(self, device_index: int | None = None):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300  
        self.recognizer.dynamic_energy_threshold = True
        self.device_index = device_index
        self.microphone = sr.Microphone(device_index=device_index)
        self._stop_listening = None

    def list_microphones(self) -> None:
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f"{index}: {name}")

    def calibrate(self, duration: float = 1.0) -> None:
        with self.microphone as source:
            print("Calibrating microphone for ambient noise...", flush=True)
            self.recognizer.adjust_for_ambient_noise(source, duration=duration)

    def start(self, callback) -> None:
        """Start listening in the background. `callback(text)` is called on each phrase."""
        self._stop_listening = self.recognizer.listen_in_background(
            self.microphone,
            lambda rec, audio: self._on_audio(callback, rec, audio),
            phrase_time_limit=8,
        )

    def _on_audio(self, callback, recognizer, audio) -> None:
        try:
            text = recognizer.recognize_google(audio, language="en-US")
            if text and text.strip():
                callback(text.strip())
        except sr.UnknownValueError:
            pass
        except sr.RequestError as error:
            print(f"Speech service error: {error}", flush=True)

    def stop(self) -> None:
        if self._stop_listening:
            self._stop_listening(wait_for_stop=True)