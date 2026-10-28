"""
British Voice - speak normally, your Zoom/Teams call hears you in a British accent.

Pipeline (100% free, runs offline on your laptop):
  your microphone -> Whisper (speech-to-text) -> Kokoro (British text-to-speech)
  -> VB-Cable virtual microphone -> selected as the microphone in Zoom/Teams

Each team member picks a different profile in team.json, so everyone gets
their own distinct British voice.
"""

import json
import os
import queue
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

import numpy as np
import sounddevice as sd
import tkinter as tk
from tkinter import ttk, messagebox

# Program files are read-only once installed from the Store, so anything the app
# writes (voices, settings, error log) lives in the user's own AppData folder.
APP_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BritishVoice"
DATA_DIR.mkdir(parents=True, exist_ok=True)
VOICES_DIR = DATA_DIR / "voices"
# a team.json copied into DATA_DIR overrides the built-in voice list
TEAM_FILE = DATA_DIR / "team.json"
if not TEAM_FILE.exists():
    TEAM_FILE = APP_DIR / "team.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
ERROR_LOG = DATA_DIR / "error_log.txt"
VBCABLE_URL = "https://vb-audio.com/Cable/"
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("voices-v1.0.bin", "kokoro-v1.0.onnx")

WHISPER_RATE = 16000      # Whisper expects 16 kHz mono
FRAME_MS = 30
DEFAULTS = {"pause_ms": 600, "sensitivity": 3.0}

# Whisper sometimes "hears" these in silence or noise; never speak them.
# (Real short replies like "Thank you." are kept: no_speech_prob filters noise.)
HALLUCINATIONS = {"", ".", "you", "thanks for watching!", "thank you for watching.",
                  "subtitles by the amara.org community"}


# --------------------------------------------------------------------------- #
# Audio helpers
# --------------------------------------------------------------------------- #
def ensure_voices(log) -> tuple[Path, Path]:
    """Download the Kokoro voice model (about 350 MB) the first time it is used."""
    VOICES_DIR.mkdir(exist_ok=True)
    paths = []
    for name in KOKORO_FILES:
        target = VOICES_DIR / name
        if not target.exists():
            log(f"Downloading British voices: {name} (first time only, please wait)...")
            tmp = target.with_suffix(target.suffix + ".part")
            urllib.request.urlretrieve(KOKORO_URL + name, tmp)
            tmp.replace(target)
        paths.append(target)
    voices, model = paths
    return model, voices


def resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst or len(audio) == 0:
        return audio.astype(np.float32)
    n = int(round(len(audio) * dst / src))
    x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def default_rate(device, kind: str) -> int:
    return int(sd.query_devices(device, kind)["default_samplerate"])


def play(audio: np.ndarray, rate: int, device):
    """Play on one device. Uses its own stream so two devices can play at once."""
    out_rate = default_rate(device, "output")
    data = resample(audio, rate, out_rate).reshape(-1, 1)
    with sd.OutputStream(device=device, samplerate=out_rate, channels=1,
                         dtype="float32") as stream:
        stream.write(data)


def list_devices():
    """Devices of the default host API only (Windows otherwise lists each one 3-4 times)."""
    api = sd.query_hostapis(sd.default.hostapi)
    inputs, outputs = [], []
    for i in api["devices"]:
        d = sd.query_devices(i)
        label = f"{i}: {d['name']}"
        if d["max_input_channels"] > 0:
            inputs.append(label)
        if d["max_output_channels"] > 0:
            outputs.append(label)
    return inputs, outputs, api["default_input_device"], api["default_output_device"]


# --------------------------------------------------------------------------- #
# Engine
# --------------------------------------------------------------------------- #
class Engine:
    def __init__(self, log, on_text):
        self.log = log
        self.on_text = on_text
        self.whisper = None
        self.whisper_size = None
        self.tts = None
        self.stop_event = threading.Event()
        self.stop_event.set()
        self.playing = threading.Event()

    @property
    def running(self):
        return not self.stop_event.is_set()

    # ---- model loading -------------------------------------------------- #
    def load_whisper(self, size: str):
        if self.whisper is not None and self.whisper_size == size:
            return
        from faster_whisper import WhisperModel
        self.log(f"Loading speech recogniser ({size}). First time downloads it, please wait...")
        self.whisper = WhisperModel(size, device="cpu", compute_type="int8")
        self.whisper_size = size
        self.log("Speech recogniser ready.")

    def load_voices(self):
        if self.tts is not None:
            return
        from kokoro_onnx import Kokoro
        model, voices = ensure_voices(self.log)
        self.tts = Kokoro(str(model), str(voices))
        self.log("British voices ready.")

    def synthesize(self, text: str, profile: dict) -> tuple[np.ndarray, int]:
        voice = profile["voice"]
        if isinstance(voice, list):
            # a mix of two or more voices gives a new, distinct voice
            voice = np.mean([self.tts.get_voice_style(v) for v in voice], axis=0)
        audio, rate = self.tts.create(text, voice=voice, speed=profile.get("speed", 1.0),
                                      lang="en-gb")
        return audio.astype(np.float32), rate

    # ---- live loop ------------------------------------------------------ #
    def start(self, profile, mic, out, monitor, settings):
        # fresh queues + stop flag per session, so old threads can never mix in
        stop = threading.Event()
        self.stop_event = stop
        frames, utterances = queue.Queue(), queue.Queue()
        rate = default_rate(mic, "input")
        args = dict(stop=stop, frames=frames, utterances=utterances, rate=rate)
        threading.Thread(target=self._capture, kwargs=dict(args, mic=mic), daemon=True).start()
        threading.Thread(target=self._segment, kwargs=dict(args, settings=settings,
                                                           monitor=monitor), daemon=True).start()
        threading.Thread(target=self._convert, kwargs=dict(args, profile=profile, out=out,
                                                           monitor=monitor), daemon=True).start()

    def stop(self):
        self.stop_event.set()

    def _capture(self, stop, frames, utterances, rate, mic):
        def cb(indata, n, t, status):
            frames.put(indata[:, 0].copy())
        try:
            with sd.InputStream(device=mic, channels=1, samplerate=rate,
                                blocksize=rate * FRAME_MS // 1000, dtype="float32",
                                callback=cb):
                self.log("Listening... speak normally.")
                stop.wait()
        except Exception as e:
            self.log(f"Microphone error: {e}\nCheck Windows Settings > Privacy & security > "
                     "Microphone: turn on 'Let desktop apps access your microphone'.")
            stop.set()

    def _segment(self, stop, frames, utterances, rate, settings, monitor):
        """Simple voice-activity detection: cut speech into phrases at pauses."""
        noise = 0.003
        speech, silent_ms, speaking = [], 0, False
        while not stop.is_set():
            try:
                f = frames.get(timeout=0.2)
            except queue.Empty:
                continue
            # with "hear my voice" on, ignore the mic while the voice plays (no echo loop)
            if monitor and self.playing.is_set():
                continue
            rms = float(np.sqrt(np.mean(f * f)))
            threshold = max(noise * settings["sensitivity"], 0.006)
            if rms > threshold:
                speaking, silent_ms = True, 0
                speech.append(f)
            elif speaking:
                speech.append(f)
                silent_ms += FRAME_MS
                if silent_ms >= settings["pause_ms"]:
                    audio = np.concatenate(speech)
                    if len(audio) > rate * 0.4:
                        utterances.put(audio)
                    speech, silent_ms, speaking = [], 0, False
            else:
                noise = 0.95 * noise + 0.05 * rms   # learn background noise
            # hard cap so very long monologues still flow
            if speaking and len(speech) * FRAME_MS > 12000:
                utterances.put(np.concatenate(speech))
                speech, silent_ms, speaking = [], 0, False

    def _convert(self, stop, frames, utterances, rate, profile, out, monitor):
        while not stop.is_set():
            try:
                audio = utterances.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                t0 = time.time()
                segs, _ = self.whisper.transcribe(
                    resample(audio, rate, WHISPER_RATE), language="en", beam_size=1,
                    vad_filter=True, condition_on_previous_text=False)
                text = " ".join(s.text.strip() for s in segs
                                if s.no_speech_prob < 0.6).strip()
                if text.lower() in HALLUCINATIONS:
                    continue
                voice_audio, vrate = self.synthesize(text, profile)
                self.on_text(text, time.time() - t0)
                self.playing.set()
                try:
                    if monitor:
                        threading.Thread(target=play, daemon=True,
                                         args=(voice_audio, vrate, None)).start()
                    play(voice_audio, vrate, out)
                finally:
                    self.playing.clear()
            except Exception as e:
                self.log(f"Error: {e}")


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


class App:
    def __init__(self, root):
        self.root = root
        root.title("British Voice")
        root.geometry("660x560")
        self.team = load_json(TEAM_FILE, {"profiles": []})["profiles"]
        self.saved = {**DEFAULTS, **load_json(SETTINGS_FILE, {})}
        self.engine = Engine(self.log, self.on_text)
        self.starting = False

        inputs, outputs, def_in, _ = list_devices()

        pad = {"padx": 8, "pady": 4, "sticky": "we"}
        frm = ttk.Frame(root, padding=10)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        ttk.Label(frm, text="Your voice").grid(row=0, column=0, **pad)
        self.profile = ttk.Combobox(frm, state="readonly",
                                    values=[p["name"] for p in self.team])
        self.profile.grid(row=0, column=1, **pad)

        ttk.Label(frm, text="Your microphone").grid(row=1, column=0, **pad)
        self.mic = ttk.Combobox(frm, state="readonly", values=inputs)
        self.mic.grid(row=1, column=1, **pad)

        ttk.Label(frm, text="Send voice to").grid(row=2, column=0, **pad)
        self.out = ttk.Combobox(frm, state="readonly", values=outputs)
        self.out.grid(row=2, column=1, **pad)
        ttk.Label(frm, text="Pick 'CABLE Input' here. In Zoom/Teams pick microphone 'CABLE Output'.",
                  foreground="gray", wraplength=460).grid(row=3, column=1, sticky="w", padx=8)

        ttk.Label(frm, text="Accuracy").grid(row=4, column=0, **pad)
        self.model = ttk.Combobox(frm, state="readonly",
                                  values=["tiny.en", "base.en", "small.en"])
        self.model.grid(row=4, column=1, **pad)
        ttk.Label(frm, text="tiny = fastest, small = most accurate",
                  foreground="gray").grid(row=5, column=1, sticky="w", padx=8)

        self.monitor = tk.BooleanVar(value=self.saved.get("monitor", False))
        ttk.Checkbutton(frm, text="Also let me hear my British voice",
                        variable=self.monitor).grid(row=6, column=0, columnspan=2, **pad)

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=2, pady=8)
        ttk.Button(btns, text="Preview voice", command=self.preview).pack(side="left", padx=4)
        self.go = ttk.Button(btns, text="Start", command=self.toggle)
        self.go.pack(side="left", padx=4)
        ttk.Button(btns, text="Credits", command=lambda: webbrowser.open(
            (APP_DIR / "CREDITS.md").as_uri())).pack(side="left", padx=4)
        self.has_cable = any("cable input" in o.lower() for o in outputs)
        if not self.has_cable:
            ttk.Button(btns, text="Get virtual microphone (free)",
                       command=lambda: webbrowser.open(VBCABLE_URL)).pack(side="left", padx=4)

        self.text = tk.Text(frm, height=12, wrap="word", state="disabled")
        self.text.grid(row=8, column=0, columnspan=2, sticky="nsew", padx=8)
        frm.rowconfigure(8, weight=1)

        self._restore(self.profile, "profile", first=True)
        self._restore(self.mic, "mic", prefix=f"{def_in}:")
        self._restore(self.out, "out", prefer="CABLE Input")
        self._restore(self.model, "model", value="base.en")
        root.protocol("WM_DELETE_WINDOW", self.quit)
        if not self.has_cable:
            self.log("⚠ One-time setup: click 'Get virtual microphone (free)', download VB-Cable,"
                     " unzip it, right-click VBCABLE_Setup_x64 > Run as administrator >"
                     " Install Driver, then restart your PC.")
        self._sync_button()

    def _restore(self, box, key, first=False, prefix=None, prefer=None, value=None):
        vals = list(box["values"])
        picks = [self.saved.get(key), value]
        picks += [v for v in vals if prefer and prefer.lower() in v.lower()]
        picks += [v for v in vals if prefix and v.startswith(prefix)]
        for p in picks:
            if p in vals:
                box.set(p)
                return
        if vals:
            box.current(0)

    # ---- helpers -------------------------------------------------------- #
    def log(self, msg):
        self.root.after(0, self._append, msg)

    def on_text(self, text, secs):
        self.log(f"🇬🇧 {text}   ({secs:.1f}s)")

    def _append(self, msg):
        self.text.configure(state="normal")
        self.text.insert("end", msg + "\n")
        self.text.see("end")
        self.text.configure(state="disabled")

    def _sync_button(self):
        if not self.starting:
            self.go.configure(text="Stop" if self.engine.running else "Start", state="normal")
        self.root.after(500, self._sync_button)

    def current_profile(self):
        return next(p for p in self.team if p["name"] == self.profile.get())

    @staticmethod
    def dev(box):
        return int(box.get().split(":")[0]) if box.get() else None

    def save(self):
        self.saved.update({"profile": self.profile.get(), "mic": self.mic.get(),
                           "out": self.out.get(), "model": self.model.get(),
                           "monitor": self.monitor.get()})
        SETTINGS_FILE.write_text(json.dumps(self.saved, indent=2), encoding="utf-8")

    def background(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    # ---- actions -------------------------------------------------------- #
    def preview(self):
        prof = self.current_profile()

        def run():
            try:
                self.engine.load_voices()
                audio, rate = self.engine.synthesize(
                    "Hello, lovely to meet you all. Shall we get started?", prof)
                play(audio, rate, None)
            except Exception as e:
                self.log(f"Preview error: {e}")
        self.background(run)

    def toggle(self):
        if self.starting:
            return
        if self.engine.running:
            self.engine.stop()
            self.log("Stopped.")
            return
        if not self.out.get():
            messagebox.showerror("British Voice", "Choose where to send the voice.")
            return
        self.save()
        prof = self.current_profile()
        self.starting = True
        self.go.configure(text="Starting...", state="disabled")

        def run():
            try:
                self.engine.load_whisper(self.model.get())
                self.engine.load_voices()
                self.engine.start(prof, self.dev(self.mic), self.dev(self.out),
                                  self.monitor.get(), self.saved)
            except Exception as e:
                self.log(f"Start error: {e}")
            finally:
                self.starting = False
        self.background(run)

    def quit(self):
        self.engine.stop()
        try:
            self.save()
        except Exception:
            pass
        self.root.destroy()


def main():
    if "--list-devices" in sys.argv:
        print(sd.query_devices())
        return
    if "--self-test" in sys.argv:
        # used by the build: proves the packaged app has everything it needs
        # (errors go to the log, never a popup, so an unattended build can't hang)
        try:
            from kokoro_onnx import Kokoro  # noqa: F401
            from kokoro_onnx.tokenizer import Tokenizer
            from faster_whisper.vad import get_speech_timestamps
            import ctranslate2, onnxruntime  # noqa: F401
            assert Tokenizer().phonemize("Hello there.", "en-gb")
            if all((VOICES_DIR / f).exists() for f in KOKORO_FILES):
                eng = Engine(lambda m: None, None)
                eng.load_voices()
                audio, _ = eng.synthesize("Hello there.", {"voice": ["bm_george", "bf_emma"]})
                assert len(audio) > 0
            get_speech_timestamps(np.zeros(WHISPER_RATE, np.float32))
            tk.Tcl()  # Tcl/Tk files present (no window needed)
            (DATA_DIR / "self_test_ok.txt").write_text("ok", encoding="utf-8")
        except Exception:
            ERROR_LOG.write_text(traceback.format_exc(), encoding="utf-8")
            sys.exit(1)
        return
    try:
        root = tk.Tk()
        App(root)
        root.mainloop()
    except Exception:
        # the desktop shortcut has no console window, so keep the error visible
        ERROR_LOG.write_text(traceback.format_exc(), encoding="utf-8")
        messagebox.showerror("British Voice", f"Something went wrong. Details saved to:\n{ERROR_LOG}")


if __name__ == "__main__":
    main()
