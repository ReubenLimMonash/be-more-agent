# =========================================================================
#  Be More Agent 🤖
#  A Local, Offline-First AI Agent for Raspberry Pi
#
#  Copyright (c) 2026 brenpoly
#  Licensed under the MIT License
#  Source: https://github.com/brenpoly/be-more-agent
#
#  DISCLAIMER:
#  This software is provided "as is", without warranty of any kind.
#  This project is a generic framework and includes no copyrighted assets.
# =========================================================================

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading
import time
import json
import os
import subprocess
import random
import re
import sys
import select
import traceback
import atexit
import warnings
import wave
import numpy as np
import scipy.signal
import sounddevice as sd

# Suppress warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="duckduckgo_search")

# Wake word
import openwakeword
from openwakeword.model import Model

# BMO Agent & Config
from config import (
    CONFIG_FILE, MEMORY_FILE, BMO_IMAGE_FILE, WAKE_WORD_MODEL, WAKE_WORD_THRESHOLD,
    BotStates, SOUND_DIRS, CURRENT_CONFIG, TEXT_MODEL, VISION_MODEL,
    INPUT_DEVICE_NAME, choose_input_samplerate, BMO_SYSTEM_PROMPT
)
from bridge import AgentBridge 

# All configuration now imported from config.py

# =========================================================================
# 2. GUI CLASS
# =========================================================================

class BotGUI:
    BG_WIDTH, BG_HEIGHT = 800, 480 
    OVERLAY_WIDTH, OVERLAY_HEIGHT = 400, 300 

    def __init__(self, master):
        self.master = master
        master.title("BMO")
        master.attributes('-fullscreen', True) 
        master.bind('<Escape>', self.exit_fullscreen)
        
        # Inputs
        master.bind('<Return>', self.handle_ptt_toggle)
        master.bind('<space>', self.handle_speaking_interrupt)
        master.bind('<Tab>', self.toggle_chatbox)
        atexit.register(self.safe_exit)
        
        # --- PYDANTIC AI AGENT INITIALIZATION ---
        self.agent_bridge = AgentBridge(
            on_thinking=self._on_agent_thinking,
            on_response=self._on_agent_response
        )
        
        # State
        self.current_state = BotStates.WARMUP
        self.current_volume = 0 
        self.animations = {}
        self.current_frame_index = 0
        self.current_overlay_image = None
        
        self.permanent_memory = self.load_chat_history()
        self.session_memory = []
        self.thinking_sound_active = threading.Event()
        
        self.last_ptt_time = 0 
        self.ptt_event = threading.Event()       
        self.recording_active = threading.Event() 
        self.interrupted = threading.Event() 
        self.chat_mode = threading.Event()
        
        self.tts_queue = []          
        self.tts_queue_lock = threading.Lock() 
        self.tts_thread = None       
        self.tts_active = threading.Event()
        self.current_audio_process = None 
        self.exiting = False
        
        # --- WAKE WORD INITIALIZATION ---
        print("[INIT] Loading Wake Word...", flush=True)
        self.oww_model = None
        if os.path.exists(WAKE_WORD_MODEL):
            try:
                self.oww_model = Model(wakeword_model_paths=[WAKE_WORD_MODEL])
                print("[INIT] Wake Word Loaded.", flush=True)
            except TypeError:
                try:
                    self.oww_model = Model(wakeword_models=[WAKE_WORD_MODEL])
                    print("[INIT] Wake Word Loaded (New API).", flush=True)
                except Exception as e:
                    print(f"[CRITICAL] Failed to load model: {e}")
            except Exception as e:
                print(f"[CRITICAL] Failed to load model: {e}")
        else:
            print(f"[CRITICAL] Model not found: {WAKE_WORD_MODEL}")

        # GUI Setup
        self.background_label = tk.Label(master)
        self.background_label.place(x=0, y=0, width=self.BG_WIDTH, height=self.BG_HEIGHT)
        self.background_label.bind('<Button-1>', self.toggle_hud_visibility) 
        
        self.overlay_label = tk.Label(master, bg='black')
        self.overlay_label.bind('<Button-1>', self.toggle_hud_visibility)
        
        # Chatbox overlay (Tab-toggled): conversation log + typed input, bottom half of screen
        self.chat_frame = tk.Frame(master, bg="#000000")
        self.response_text = tk.Text(self.chat_frame, height=6, width=60, wrap=tk.WORD, 
                                     state=tk.DISABLED, bg="#ffffff", fg="#000000", font=('Arial', 12)) 
        self.response_text.pack(fill=tk.BOTH, expand=True)
        self.chat_entry = tk.Entry(self.chat_frame, font=('Arial', 12))
        self.chat_entry.pack(fill=tk.X)
        self.chat_entry.bind('<Return>', self.handle_chat_submit)
        
        self.status_var = tk.StringVar(value="Initializing...")
        self.status_label = ttk.Label(master, textvariable=self.status_var, background="#2e2e2e", foreground="white")
        
        self.exit_button = ttk.Button(master, text="Exit & Save", command=self.safe_exit)

        self.load_animations()
        self.update_animation() 
        
        threading.Thread(target=self.safe_main_execution, daemon=True).start()

    # --- HELPERS ---

    def extract_json_from_text(self, text):
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return None
        except: return None

    def _on_agent_thinking(self):
        """Callback when agent starts thinking."""
        self.set_state(BotStates.THINKING, "Thinking...")
        self.thinking_sound_active.set()
        threading.Thread(target=self._run_thinking_sound_loop, daemon=True).start()
    
    def _on_agent_response(self, text: str, tool_name: str = None):
        """Callback when agent has response."""
        self.thinking_sound_active.clear()
        if tool_name:
            self.append_to_text(f"BOT: (using {tool_name}) {text}")
        else:
            self.append_to_text(f"BOT: {text}")
        # Queue for TTS
        with self.tts_queue_lock:
            self.tts_queue.append(text)

    def safe_exit(self):
        if self.exiting:
            return
        self.exiting = True
        print("\n--- SHUTDOWN SEQUENCE ---", flush=True)
        
        # Shutdown agent bridge
        if hasattr(self, 'agent_bridge'):
            self.agent_bridge.shutdown()
        
        if self.current_audio_process:
            try:
                self.current_audio_process.terminate()
                self.current_audio_process.wait(timeout=1)
            except: pass

        self.recording_active.clear()
        self.thinking_sound_active.clear()
        self.tts_active.clear() 
        
        self.save_chat_history()
        
        try:
            # No need to call ollama.generate for keep_alive with Pydantic AI
            pass
        except: pass
        try:
            sd.stop()
        except: pass

        try:
            self.master.quit()
        except Exception:
            pass
        
    def exit_fullscreen(self, event=None):
        self.master.attributes('-fullscreen', False)
        self.safe_exit()

    def toggle_hud_visibility(self, event=None):
        try:
            if self.status_label.winfo_ismapped():
                self.status_label.place_forget()
                self.exit_button.place_forget()
            else:
                self.status_label.place(relx=0.5, rely=1.0, anchor=tk.S, relwidth=1)
                self.exit_button.place(x=10, y=10)
        except tk.TclError: pass

    def handle_ptt_toggle(self, event=None):
        if self.chat_mode.is_set():
            return
        current_time = time.time()
        if current_time - self.last_ptt_time < 0.5: 
            return 
        self.last_ptt_time = current_time

        if self.recording_active.is_set():
            print("[PTT] Toggle OFF", flush=True)
            self.recording_active.clear() 
        else:
            if self.current_state == BotStates.IDLE or "Wait" in self.status_var.get():
                print("[PTT] Toggle ON", flush=True)
                self.recording_active.set() 
                self.ptt_event.set()

    def handle_speaking_interrupt(self, event=None):
        if self.master.focus_get() == self.chat_entry:
            return
        if self.current_state == BotStates.SPEAKING or self.current_state == BotStates.THINKING:
            self.interrupted.set()
            self.thinking_sound_active.clear()
            with self.tts_queue_lock:
                self.tts_queue.clear()
            if self.current_audio_process:
                try: self.current_audio_process.terminate()
                except: pass
            self.set_state(BotStates.IDLE, "Interrupted.")

    def toggle_chatbox(self, event=None):
        if self.chat_frame.winfo_ismapped():
            self.chat_frame.place_forget()
            self.chat_mode.clear()
            self.master.focus_set()
        else:
            self.chat_frame.place(relx=0, rely=0.5, relwidth=1, relheight=0.5)
            self.chat_mode.set()
            self.chat_entry.focus_set()
        return "break"

    def handle_chat_submit(self, event=None):
        text = self.chat_entry.get().strip()
        if not text or self.current_state in (BotStates.THINKING, BotStates.SPEAKING):
            return "break"
        self.chat_entry.delete(0, tk.END)
        self.append_to_text(f"YOU: {text}")
        self.chat_entry.config(state=tk.DISABLED)
        threading.Thread(target=self._process_chat_message, args=(text,), daemon=True).start()
        return "break"

    def _process_chat_message(self, text):
        self.chat_and_respond(text)
        self.master.after(0, lambda: self.chat_entry.config(state=tk.NORMAL))

    def load_animations(self):
        base_path = "faces"
        states = ["idle", "listening", "thinking", "speaking", "error", "capturing", "warmup"] 
        for state in states:
            folder = os.path.join(base_path, state)
            self.animations[state] = []
            if os.path.exists(folder):
                files = sorted([f for f in os.listdir(folder) if f.lower().endswith('.png')])
                for f in files:
                    img = Image.open(os.path.join(folder, f)).resize((self.BG_WIDTH, self.BG_HEIGHT))
                    self.animations[state].append(ImageTk.PhotoImage(img))
            if not self.animations[state]:
                if state in self.animations.get("idle", []):
                     self.animations[state] = self.animations["idle"]
                else:
                    # Blue screen fallback
                    blank = Image.new('RGB', (self.BG_WIDTH, self.BG_HEIGHT), color='#0000FF')
                    self.animations[state].append(ImageTk.PhotoImage(blank))

    def update_animation(self):
        frames = self.animations.get(self.current_state, []) or self.animations.get(BotStates.IDLE, [])
        if not frames:
            self.master.after(500, self.update_animation)
            return

        if self.current_state == BotStates.SPEAKING:
            if len(frames) > 1:
                self.current_frame_index = random.randint(1, len(frames) - 1)
            else:
                self.current_frame_index = 0 
        else:
            self.current_frame_index = (self.current_frame_index + 1) % len(frames)

        self.background_label.config(image=frames[self.current_frame_index])
        
        speed = 50 if self.current_state == BotStates.SPEAKING else 500
        self.master.after(speed, self.update_animation)

    def set_state(self, state, msg="", cam_path=None):
        def _update():
            if msg: print(f"[STATE] {state.upper()}: {msg}", flush=True)
            if self.current_state != state:
                self.current_state = state
                self.current_frame_index = 0
            if msg: self.status_var.set(msg)
            if cam_path and os.path.exists(cam_path) and state in [BotStates.THINKING, BotStates.SPEAKING]:
                try:
                    img = Image.open(cam_path).resize((self.OVERLAY_WIDTH, self.OVERLAY_HEIGHT))
                    self.current_overlay_image = ImageTk.PhotoImage(img)
                    self.overlay_label.config(image=self.current_overlay_image)
                    self.overlay_label.place(x=200, y=90)
                except: pass
            else:
                self.overlay_label.place_forget()
        self.master.after(0, _update)

    def append_to_text(self, text, newline=True):
        def _update():
            self.response_text.config(state=tk.NORMAL)
            if newline: 
                self.response_text.insert(tk.END, text + "\n")
            else: 
                self.response_text.insert(tk.END, text)
            
            self.response_text.see(tk.END)
            self.response_text.config(state=tk.DISABLED)
            
        self.master.after(0, _update)

    def _stream_to_text(self, chunk):
        def update_text_stream():
            self.response_text.config(state=tk.NORMAL)
            self.response_text.insert(tk.END, chunk)
            self.response_text.see(tk.END) 
            self.response_text.config(state=tk.DISABLED)
        self.master.after(0, update_text_stream)

    # =========================================================================
    # 3. CORE LOGIC - Agent-based (Pydantic AI)
    # =========================================================================

    def safe_main_execution(self):
        try:
            self.warm_up_logic()
            self.tts_active.set()
            self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
            self.tts_thread.start()
            
            while True:
                trigger_source = self.detect_wake_word_or_ptt()
                if trigger_source == "PAUSED":
                    while self.chat_mode.is_set():
                        time.sleep(0.1)
                    continue
                if self.interrupted.is_set():
                    self.interrupted.clear()
                    self.set_state(BotStates.IDLE, "Resetting...")
                    continue

                self.set_state(BotStates.LISTENING, "I'm listening!")
                
                audio_file = None
                if trigger_source == "PTT":
                    audio_file = self.record_voice_ptt()
                else:
                    audio_file = self.record_voice_adaptive()
                
                if not audio_file: 
                    self.set_state(BotStates.IDLE, "Heard nothing.")
                    continue
                
                user_text = self.transcribe_audio(audio_file)
                if not user_text:
                    self.set_state(BotStates.IDLE, "Transcription empty.")
                    continue
                
                self.append_to_text(f"YOU: {user_text}")
                self.interrupted.clear()
                self.chat_and_respond(user_text, img_path=None)
                    
        except Exception as e:
            traceback.print_exc()
            self.set_state(BotStates.ERROR, f"Fatal Error: {str(e)[:40]}")

    def warm_up_logic(self):
        self.set_state(BotStates.WARMUP, "Warming up brains...")
        try:
            # Agent will load models on first use
            pass
        except Exception as e:
            print(f"Failed to initialize: {e}", flush=True)
        self.play_sound(self.get_random_sound(SOUND_DIRS["greeting"]))
        print("Ready to serve!", flush=True)

    def detect_wake_word_or_ptt(self):
        self.set_state(BotStates.IDLE, "Waiting...")
        self.ptt_event.clear()
        
        if self.oww_model: self.oww_model.reset()

        if self.oww_model is None:
            self.ptt_event.wait()
            self.ptt_event.clear()
            return "PTT"

        CHUNK_SIZE = 1280
        OWW_SAMPLE_RATE = 16000

        input_rate = choose_input_samplerate(INPUT_DEVICE_NAME, CURRENT_CONFIG.get("input_sample_rate"))
        use_resampling = (input_rate != OWW_SAMPLE_RATE)
        input_chunk_size = int(CHUNK_SIZE * (input_rate / OWW_SAMPLE_RATE)) if use_resampling else CHUNK_SIZE

        stream_args = {
            "samplerate": input_rate, 
            "channels": 1, 
            "dtype": 'int16', 
            "blocksize": input_chunk_size, 
            "device": INPUT_DEVICE_NAME
        }

        # Try to find a compatible block size and sample rate
        try:
            # First attempt: standard settings
            self._listen_loop(stream_args, input_chunk_size, CHUNK_SIZE, use_resampling)
        except StopIteration as si:
            return str(si)
        except Exception as e:
            print(f"[AUDIO] Stream failed with defaults: {e}. Retrying with loose settings...", flush=True)
            try:
                # Second attempt: Let PortAudio decide blocksize (0) and latency
                stream_args["blocksize"] = 0 
                stream_args["latency"] = "high"
                # If blocksize is variable, we must read specific amounts manually or handle buffering.
                # Simplest fallback: Just attempt small fixed block
                stream_args["blocksize"] = 1024
                use_resampling = True
                
                self._listen_loop(stream_args, 1024, CHUNK_SIZE, use_resampling)
            except StopIteration as si:
                return str(si)
            except Exception as e2:
                print(f"[CRITICAL] Wake Word Stream Error: {e2}")
                self.ptt_event.wait()
                return "PTT"
        
        return "WAKE"

    def _listen_loop(self, stream_args, input_chunk_size, target_chunk_size, use_resampling):
        # Force software backend (no mmap) via environment variable if possible, 
        # but here we can try to hint loop settings.
        # However, the most effective fix for ALSA mmap issues is often just asking for 'blocksize=0' 
        # and letting portaudio manage the buffering, OR very small chunks.
        
        # Let's try to be less aggressive with reads.
        
         with sd.InputStream(**stream_args) as stream:
                print(f"[AUDIO] Listening with rate {stream_args['samplerate']} and block {stream_args['blocksize']}", flush=True)
                
                # Pre-allocate buffer for speed
                # If blocksize is 0, we read what is available.
                
                while True:
                    if self.chat_mode.is_set():
                        raise StopIteration("PAUSED")
                    if self.ptt_event.is_set():
                        self.ptt_event.clear()
                        raise StopIteration("PTT")

                    rlist, _, _ = select.select([sys.stdin], [], [], 0.001)
                    if rlist: 
                        sys.stdin.readline()
                        raise StopIteration("CLI")

                    # If fallback mode (blocksize 0), read fixed amount
                    read_size = input_chunk_size
                    if stream_args.get('blocksize') == 0:
                        read_size = 1024 # Safe small read
                    
                    try:
                        data, overflow = stream.read(read_size)
                        if overflow:
                            print("!", end="", flush=True) 
                            # If we overflow excessively, raise error to trigger fallback to SAFE MODE (PulseAudio/Software)
                            # We can use a simple counter attached to the function or object, but here raising immediately 
                            # after a few in a row is safest.
                            raise RuntimeError("Audio Buffer Overflow - Triggering Safe Mode")
                    except Exception as e:
                        # Convert uncatchable PaErrorCode wrapper to standard Exception if needed
                        # But honestly, `raise e` should work... unless it's a SystemExit?
                        # Let's wrap it in a new exception to be sure it bubbles up
                        raise RuntimeError(f"Audio read failed: {e}")

                    audio_data = np.frombuffer(data, dtype=np.int16)

                    # Ensure flattening for openwakeword compatibility
                    if audio_data.ndim > 1:
                        audio_data = audio_data.flatten()

                    if use_resampling:
                        # FAST RESAMPLING: Nearest-neighbor slicing instead of scipy.signal.resample
                        # This avoids the CPU bottleneck that causes overflow (!!!!!!!) on Raspberry Pi
                        step = len(audio_data) / target_chunk_size
                        indices = np.arange(0, len(audio_data), step)[:target_chunk_size].astype(int)
                        audio_data = audio_data[indices]
                    
                    # Convert to float for model prediction without needing heavy resampling logic
                    # The wake word model needs 16000, which we just faked above.
                    
                    # Debug volume occasionally
                    current_max = np.max(np.abs(audio_data))
                    
                    # Only predict if volume is significant to save CPU
                    if current_max > 200: 
                        prediction = self.oww_model.predict(audio_data)
                        for mdl in self.oww_model.prediction_buffer.keys():
                            score = list(self.oww_model.prediction_buffer[mdl])[-1]
                            if score > 0.1: # Show potential triggers
                                print(f"\r[Oww] Score: {score:.3f} | Vol: {current_max}   ", end="", flush=True)

                            if score > WAKE_WORD_THRESHOLD:
                                print(f"\n[WAKE] Triggered on '{mdl}' with score: {score:.2f}", flush=True)
                                self.oww_model.reset() 
                                return # Success


    def record_voice_adaptive(self, filename="input.wav"):
        print("Recording (Adaptive)...", flush=True)
        time.sleep(0.5) 
        samplerate = choose_input_samplerate(INPUT_DEVICE_NAME, CURRENT_CONFIG.get("input_sample_rate"))

        silence_threshold = 0.006
        silence_duration = 1.5
        max_record_time = 30.0
        buffer = []
        silent_chunks = 0
        chunk_duration = 0.05 
        chunk_size = int(samplerate * chunk_duration)
        
        num_silent_chunks = int(silence_duration / chunk_duration)
        max_chunks = int(max_record_time / chunk_duration)
        recorded_chunks = 0
        silence_started = False

        def callback(indata, frames, time_info, status):
            nonlocal silent_chunks, recorded_chunks, silence_started
            volume_norm = np.linalg.norm(indata) / np.sqrt(len(indata))
            buffer.append(indata.copy())  
            recorded_chunks += 1
            if recorded_chunks < 5: return 
            if volume_norm < silence_threshold:
                silent_chunks += 1
                if silent_chunks >= num_silent_chunks: silence_started = True
            else: silent_chunks = 0

        try:
            # Explicitly close stream if it exists to free hardware
            sd.stop()
            time.sleep(0.2)
            
            with sd.InputStream(samplerate=samplerate, channels=1, callback=callback, 
                                device=INPUT_DEVICE_NAME, blocksize=chunk_size): 
                while not silence_started and recorded_chunks < max_chunks:
                    sd.sleep(int(chunk_duration * 1000))
        except Exception as e: 
            print(f"[AUDIO ERROR] Adaptive Recording Failed: {e}", flush=True)
            return None 
        
        return self.save_audio_buffer(buffer, filename, samplerate)

    def record_voice_ptt(self, filename="input.wav"):
        print("Recording (PTT)...", flush=True)
        time.sleep(0.5)
        samplerate = choose_input_samplerate(INPUT_DEVICE_NAME, CURRENT_CONFIG.get("input_sample_rate"))

        buffer = []
        def callback(indata, frames, time_info, status): buffer.append(indata.copy())
        
        try:
            # Explicitly close stream if it exists to free hardware
            # This is critical on Pi 5 where hardware contention causes freezes
            sd.stop() 
            time.sleep(0.2)
            
            with sd.InputStream(samplerate=samplerate, channels=1, callback=callback, device=INPUT_DEVICE_NAME):
                while self.recording_active.is_set(): 
                    sd.sleep(50)
        except Exception as e: 
            print(f"[AUDIO ERROR] PTT Recording Failed: {e}", flush=True)
            return None
            
        return self.save_audio_buffer(buffer, filename, samplerate)

    def save_audio_buffer(self, buffer, filename, samplerate=16000):
        if not buffer: return None
        audio_data = np.concatenate(buffer, axis=0).flatten()
        audio_data = np.nan_to_num(audio_data, nan=0.0, posinf=0.0, neginf=0.0)
        audio_data = (audio_data * 32767).astype(np.int16)
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(samplerate)
            wf.writeframes(audio_data.tobytes())
        self.play_sound(self.get_random_sound(SOUND_DIRS["ack_sounds"]))
        return filename

    def transcribe_audio(self, filename):
        print("Transcribing...", flush=True)
        try:
            result = subprocess.run(
                ["./whisper.cpp/build/bin/whisper-cli", "-m", "./whisper.cpp/models/ggml-base.en.bin", "-l", "en", "-t", "4", "-f", filename],
                capture_output=True, text=True
            )
            transcription_lines = result.stdout.strip().split('\n')
            if transcription_lines and transcription_lines[-1].strip():
                last_line = transcription_lines[-1].strip()
                if ']' in last_line: transcription = last_line.split("]")[1].strip()
                else: transcription = last_line
            else: transcription = ""
            print(f"Heard: '{transcription}'", flush=True)
            return transcription.strip()
        except Exception as e:
            print(f"Transcription Error: {e}")
            return ""

    def capture_image(self):
        self.set_state(BotStates.CAPTURING, "Watching...")
        try:
            subprocess.run(["rpicam-still", "-t", "500", "-n", "--width", "640", "--height", "480", "-o", BMO_IMAGE_FILE], check=True)
            rotation = CURRENT_CONFIG.get("camera_rotation", 0)
            if rotation != 0:
                img = Image.open(BMO_IMAGE_FILE)
                img = img.rotate(rotation, expand=True) 
                img.save(BMO_IMAGE_FILE)
            return BMO_IMAGE_FILE
        except Exception as e:
            print(f"Camera Error: {e}")
            return None

    # =========================================================================
    # 5. CHAT & RESPOND (via Pydantic AI Agent)
    # =========================================================================

    def chat_and_respond(self, text, img_path=None):
        if "forget everything" in text.lower() or "reset memory" in text.lower():
            self.session_memory = []
            self.permanent_memory = [{"role": "system", "content": BMO_SYSTEM_PROMPT}]
            self.save_chat_history()
            with self.tts_queue_lock:
                self.tts_queue.append("Okay. Memory wiped.")
            self.set_state(BotStates.IDLE, "Memory Wiped")
            return

        # Use Pydantic AI agent via bridge
        response = self.agent_bridge.run_agent(text)
        
        # Add to memory
        if response.success:
            self.session_memory.append({"role": "user", "content": text})
            self.session_memory.append({"role": "assistant", "content": response.text})
        
        self.wait_for_tts()
        self.set_state(BotStates.IDLE, "Ready")

    def wait_for_tts(self):
        while self.tts_queue or self.tts_active.is_set():
            if self.interrupted.is_set(): break
            time.sleep(0.1)

    def _tts_worker(self):
        while True:
            text = None
            with self.tts_queue_lock:
                if self.tts_queue: 
                    text = self.tts_queue.pop(0)
                    self.tts_active.set() 
            if text: 
                self.speak(text)
                self.tts_active.clear() 
            else: time.sleep(0.05)

    def speak(self, text):
        clean = re.sub(r"[^\w\s,.!?:-]", "", text)
        if not clean.strip(): return
        
        print(f"[PIPER SPEAKING] '{clean}'", flush=True)
        voice_model = CURRENT_CONFIG.get("voice_model", "piper/en_GB-semaine-medium.onnx")
        
        try:
            self.current_audio_process = subprocess.Popen(
                ["./piper/piper", "--model", voice_model, "--output-raw"], 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            self.current_audio_process.stdin.write(clean.encode() + b'\n')
            self.current_audio_process.stdin.close() 

            try:
                device_info = sd.query_devices(kind='output')
                native_rate = int(device_info['default_samplerate'])
            except:
                native_rate = 48000 

            PIPER_RATE = 22050
            use_native_rate = False
            
            try:
                sd.check_output_settings(device=None, samplerate=PIPER_RATE)
            except:
                use_native_rate = True

            with sd.RawOutputStream(samplerate=native_rate if use_native_rate else PIPER_RATE, 
                                    channels=1, dtype='int16', 
                                    device=None, latency='low', blocksize=2048) as stream:
                while True:
                    if self.interrupted.is_set(): break
                    data = self.current_audio_process.stdout.read(4096)
                    if not data: break 
                    
                    audio_chunk = np.frombuffer(data, dtype=np.int16)
                    if len(audio_chunk) > 0:
                        self.current_volume = np.max(np.abs(audio_chunk))
                        if use_native_rate:
                            num_samples = int(len(audio_chunk) * (native_rate / PIPER_RATE))
                            audio_chunk = scipy.signal.resample(audio_chunk, num_samples).astype(np.int16)
                        stream.write(audio_chunk.tobytes())
                    else:
                        self.current_volume = 0
                time.sleep(0.5) 
                    
        except Exception as e:
            print(f"Audio Error: {e}")
        finally:
            self.current_volume = 0 
            if self.current_audio_process:
                if self.current_audio_process.stdout: self.current_audio_process.stdout.close()
                if self.current_audio_process.poll() is None: self.current_audio_process.terminate()
                self.current_audio_process = None

    def _run_thinking_sound_loop(self):
        time.sleep(0.5)
        while self.thinking_sound_active.is_set():
            sound = self.get_random_sound(SOUND_DIRS["thinking"])
            if sound: self.play_sound(sound)
            for _ in range(50):
                if not self.thinking_sound_active.is_set(): return
                time.sleep(0.1)

    def get_random_sound(self, directory):
        if os.path.exists(directory):
            files = [f for f in os.listdir(directory) if f.endswith(".wav")]
            return os.path.join(directory, random.choice(files)) if files else None
        return None

    def play_sound(self, file_path):
        if not file_path or not os.path.exists(file_path): return
        try:
            with wave.open(file_path, 'rb') as wf:
                file_sr = wf.getframerate()
                data = wf.readframes(wf.getnframes())
                audio = np.frombuffer(data, dtype=np.int16)

            try:
                device_info = sd.query_devices(kind='output')
                native_rate = int(device_info['default_samplerate'])
            except:
                native_rate = 48000 

            playback_rate = file_sr
            try:
                sd.check_output_settings(device=None, samplerate=file_sr)
            except:
                playback_rate = native_rate
                num_samples = int(len(audio) * (native_rate / file_sr))
                audio = scipy.signal.resample(audio, num_samples).astype(np.int16)

            sd.play(audio, playback_rate)
            sd.wait() 
        except: pass

    def load_chat_history(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f: return json.load(f)
            except: pass
        return [{"role": "system", "content": BMO_SYSTEM_PROMPT}]

    def save_chat_history(self):
        full = self.permanent_memory + self.session_memory
        conv = full[1:]
        if len(conv) > 10: conv = conv[-10:]
        with open(MEMORY_FILE, "w") as f: 
            json.dump([full[0]] + conv, f, indent=4)

if __name__ == "__main__":
    print("--- SYSTEM STARTING ---", flush=True)
    root = tk.Tk()
    app = BotGUI(root)
    root.mainloop()
