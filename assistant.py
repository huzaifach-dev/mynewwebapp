"""Voice assistant: STT -> Z.AI -> tools -> TTS with Destroyer UI and Web Search."""

import argparse
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
import urllib.parse
import pyttsx3

from callAI import call_ai
from stt import SpeechToText
import destroyer_ui


class UIState:
    def __init__(self):
        self.current = "IDLE"
        self.mic_enabled = True
        self.mic_available = True
        self.voice_enabled = True


class UIContext:
    def __init__(self, assistant):
        self.assistant = assistant
        self.ui_q = queue.Queue()
        self.input_q = queue.Queue()
        self.speech_q = queue.Queue()
        self.state = UIState()
        self.reset_memory = threading.Event()
        self.stop = threading.Event()

    def submit(self, text: str) -> None:
        if text.strip():
            self.ui_q.put(("chat", "user", text))
            threading.Thread(
                target=self.assistant.process_text, args=(text,), daemon=True
            ).start()


class VoiceAssistant:
    def __init__(self, device_index: int | None = None):
        self.stt = SpeechToText(device_index=device_index)
        self.ctx = UIContext(self)
        self.accumulated_text: list[str] = []
        self.text_lock = threading.Lock()
        self.last_speech_time = time.time()
        self.ai_processing = False
        self._running = True

        destroyer_ui.configure(
            operator="Huzaifa Choudhary",
            model="glm-4.5-flash",
            provider_label="Z.AI",
        )

    def speak(self, text: str) -> None:
        if not self.ctx.state.voice_enabled:
            return

        try:
            self.ctx.state.current = "SPEAKING"
            self.ctx.ui_q.put(("log", time.strftime("%H:%M:%S"), "sys", f"Zayn Speaking: {text}"))
            
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            self.ctx.ui_q.put(("log", time.strftime("%H:%M:%S"), "error", f"TTS Error: {e}"))
        finally:
            self.ctx.state.current = "IDLE"

    def on_speech(self, text: str) -> None:
        if self.ai_processing or not self.ctx.state.mic_enabled:
            return

        with self.text_lock:
            self.accumulated_text.append(text)
        
        self.last_speech_time = time.time()
        self.ctx.state.current = "LISTENING"
        self.ctx.ui_q.put(("log", time.strftime("%H:%M:%S"), "info", f"Heard: {text}"))
        print(f"[You]: {text}", flush=True)

    def handle_tools(self, text: str) -> bool:
        """Check if user wants to search YouTube or Google."""
        text_lower = text.lower()
        
        if "youtube" in text_lower and ("search" in text_lower or "play" in text_lower or "kholo" in text_lower or "dikh ao" in text_lower):
            # Extract query after youtube search keywords
            query = text_lower.replace("youtube", "").replace("search", "").replace("par", "").replace("kholo", "").strip()
            if not query:
                query = text
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded_query}"
            
            self.ctx.ui_q.put(("log", time.strftime("%H:%M:%S"), "sys", f"Opening YouTube Search for: {query}"))
            webbrowser.open(url)
            self.speak(f"YouTube par search kar raha hoon, Master.")
            return True
            
        elif "google" in text_lower and ("search" in text_lower or "find" in text_lower or "karo" in text_lower):
            query = text_lower.replace("google", "").replace("search", "").replace("karo", "").strip()
            if not query:
                query = text
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded_query}"
            
            self.ctx.ui_q.put(("log", time.strftime("%H:%M:%S"), "sys", f"Opening Google Search for: {query}"))
            webbrowser.open(url)
            self.speak(f"Google par search kar diya hai.")
            return True
            
        return False

    def process_text(self, text_to_send: str) -> None:
        self.ai_processing = True
        self.ctx.state.current = "THINKING"
        self.ctx.ui_q.put(("log", time.strftime("%H:%M:%S"), "sys", "Processing command..."))

        # First check if it's a direct browser search command
        if self.handle_tools(text_to_send):
            self.ai_processing = False
            self.ctx.state.current = "IDLE"
            return

        try:
            response = call_ai(text_to_send)
            self.ctx.ui_q.put(("chat", "ai", response))
            print(f"[AI]: {response}", flush=True)
            self.speak(response)
        except Exception as e:
            self.ctx.ui_q.put(("log", time.strftime("%H:%M:%S"), "error", f"AI Error: {e}"))
        finally:
            self.ai_processing = False
            self.ctx.state.current = "IDLE"

    def _silence_watcher(self) -> None:
        while self._running:
            time.sleep(0.2)
            if self.ai_processing:
                continue

            with self.text_lock:
                text_to_send = " ".join(self.accumulated_text).strip()
                elapsed = time.time() - self.last_speech_time

            if text_to_send and elapsed >= 1.5:
                with self.text_lock:
                    self.accumulated_text.clear()

                self.ctx.ui_q.put(("chat", "user", text_to_send))
                threading.Thread(
                    target=self.process_text, args=(text_to_send,), daemon=True
                ).start()

    def run(self) -> int:
        try:
            self.stt.calibrate(duration=1.0)
        except (OSError, AttributeError) as e:
            print(f"Microphone error: {e}", file=sys.stderr)
            self.ctx.state.mic_available = False

        if self.ctx.state.mic_available:
            self.stt.start(self.on_speech)

        threading.Thread(target=self._silence_watcher, daemon=True).start()

        root = destroyer_ui.create_root()
        destroyer_ui.launch(root, self.ctx)

        self._running = False
        if self.ctx.state.mic_available:
            self.stt.stop()
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Voice assistant with Cyberpunk UI.")
    parser.add_argument("--device-index", type=int, help="Microphone index")
    parser.add_argument("--list-devices", action="store_true", help="List microphones")
    args = parser.parse_args()

    if args.list_devices:
        SpeechToText().list_microphones()
        return 0

    return VoiceAssistant(device_index=args.device_index).run()


if __name__ == "__main__":
    raise SystemExit(main())