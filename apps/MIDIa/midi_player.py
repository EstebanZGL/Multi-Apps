import time
import mido
import threading

class MidiPlayer:
    def __init__(self):
        self.port = None
        self.thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set() # Unpaused initially
        self._is_playing = False
        self._current_time = 0.0
        self._total_time = 0.0
        self.playback_messages = []

    def play(self, midi_path, on_progress_callback=None):
        self.stop()
        self.stop_event.clear()
        self.pause_event.set()
        self._is_playing = True
        self._current_time = 0.0
        
        try:
            mid = mido.MidiFile(midi_path)
            
            # Pre-calculate playback messages to know the exact total time instantly
            tempo = 500000
            ticks_per_beat = mid.ticks_per_beat
            messages = list(mido.merge_tracks(mid.tracks))
            
            self.playback_messages = []
            current_sec = 0.0
            for msg in messages:
                if msg.is_meta and msg.type == 'set_tempo':
                    tempo = msg.tempo
                delta_sec = mido.tick2second(msg.time, ticks_per_beat, tempo)
                current_sec += delta_sec
                self.playback_messages.append((current_sec, msg))
                
            self._total_time = current_sec
        except Exception as e:
            self._is_playing = False
            raise e

        def run():
            try:
                # Microsoft GS Wavetable Synth opens by default on Windows when open_output() has no port name
                self.port = mido.open_output()
                
                start_playback_time = time.time()
                accumulated_pause_duration = 0.0
                
                i = 0
                while i < len(self.playback_messages) and not self.stop_event.is_set():
                    # Support Pause
                    if not self.pause_event.is_set():
                        pause_start = time.time()
                        if self.port:
                            self.port.panic() # Stop hanging notes
                        self.pause_event.wait()
                        accumulated_pause_duration += (time.time() - pause_start)
                    
                    target_time, msg = self.playback_messages[i]
                    
                    while not self.stop_event.is_set():
                        # Wait for pause if triggered during sleep
                        if not self.pause_event.is_set():
                            break
                            
                        elapsed = time.time() - start_playback_time - accumulated_pause_duration
                        if elapsed >= target_time:
                            break
                        # High resolution sleep step
                        time.sleep(0.005)
                    
                    if not self.pause_event.is_set():
                        # Loop again to handle the pause block
                        continue
                        
                    if self.stop_event.is_set():
                        break
                        
                    if self.port and not msg.is_meta:
                        self.port.send(msg)
                        
                    self._current_time = target_time
                    if on_progress_callback:
                        on_progress_callback(self._current_time, self._total_time)
                        
                    i += 1
            except Exception as e:
                print("Error in MidiPlayer thread:", e)
            finally:
                self._is_playing = False
                if self.port:
                    try:
                        self.port.panic()
                        self.port.close()
                    except Exception:
                        pass
                    self.port = None
                if on_progress_callback:
                    on_progress_callback(0.0, self._total_time)

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def pause(self):
        if self._is_playing:
            self.pause_event.clear()

    def resume(self):
        if self._is_playing:
            self.pause_event.set()

    def stop(self):
        self.stop_event.set()
        self.pause_event.set() # Release wait if paused
        if self.thread:
            self.thread.join(timeout=1.0)
            self.thread = None
        self._is_playing = False
        self._current_time = 0.0

    def is_playing(self):
        return self._is_playing

    def is_paused(self):
        return not self.pause_event.is_set()

    def get_progress(self):
        return self._current_time, self._total_time
