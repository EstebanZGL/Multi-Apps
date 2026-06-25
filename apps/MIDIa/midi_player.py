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

    def play(self, midi_path, on_progress_callback=None):
        self.stop()
        self.stop_event.clear()
        self.pause_event.set()
        self._is_playing = True
        self._current_time = 0.0
        
        try:
            mid = mido.MidiFile(midi_path)
            self._total_time = mid.length
        except Exception as e:
            self._is_playing = False
            raise e

        def run():
            try:
                # Microsoft GS Wavetable Synth opens by default on Windows when open_output() has no port name
                self.port = mido.open_output()
                
                start_playback_time = time.time()
                accumulated_pause_duration = 0.0
                
                # We iterate over the midi events. 
                # Since mid.play() is a blocking generator that respects delta times, we can write our own player loop
                # to easily support pause/resume and time scrubbing.
                messages = list(mid)
                
                i = 0
                while i < len(messages) and not self.stop_event.is_set():
                    # Support Pause
                    if not self.pause_event.is_set():
                        pause_start = time.time()
                        if self.port:
                            self.port.panic() # Stop hanging notes
                        self.pause_event.wait()
                        accumulated_pause_duration += (time.time() - pause_start)
                    
                    msg = messages[i]
                    # Sleep for the message's delta time
                    # We compare actual elapsed time with the message's absolute time to avoid time drift
                    target_time = msg.time
                    
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
                        
                    self._current_time = msg.time
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
