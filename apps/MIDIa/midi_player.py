import ctypes
import os
import time
import mido
import threading

def send_mci(cmd):
    buf = ctypes.create_unicode_buffer(256)
    res = ctypes.windll.winmm.mciSendStringW(cmd, buf, 256, 0)
    if res != 0:
        # Avoid console spam when device is closed/closing (errors like 263, 296, 305)
        if res not in [263, 296, 305]:
            err_buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.winmm.mciGetErrorStringW(res, err_buf, 256)
            print(f"MCI Error for '{cmd}': {err_buf.value}")
        return None
    return buf.value.strip()

class MidiPlayer:
    def __init__(self):
        self._is_playing = False
        self._is_paused = False
        self._total_time = 0.0
        self._current_time = 0.0
        self.notes_intervals = []
        self.active_notes = set()
        self.midi_path = None
        self.monitor_thread = None
        self.stop_monitor = threading.Event()

    def play(self, midi_path, on_progress_callback=None):
        self.stop()
        
        self.midi_path = os.path.abspath(midi_path)
        
        # Parse MIDI file for note intervals and total duration
        try:
            mid = mido.MidiFile(midi_path)
            ticks_per_beat = mid.ticks_per_beat
            tempo = 500000 # default 120 BPM
            merged = mido.merge_tracks(mid.tracks)
            
            notes_on = {}
            self.notes_intervals = []
            current_sec = 0.0
            
            for msg in merged:
                if msg.is_meta and msg.type == 'set_tempo':
                    tempo = msg.tempo
                delta_sec = mido.tick2second(msg.time, ticks_per_beat, tempo)
                current_sec += delta_sec
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    notes_on[msg.note] = current_sec
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    if msg.note in notes_on:
                        start_time = notes_on.pop(msg.note)
                        self.notes_intervals.append((start_time, current_sec, msg.note))
            
            # Close any notes that weren't explicitly turned off
            for note, start_time in notes_on.items():
                self.notes_intervals.append((start_time, current_sec, note))
                
            self._total_time = current_sec
        except Exception as e:
            print("Error parsing MIDI file in MidiPlayer:", e)
            self._total_time = 0.0
            self.notes_intervals = []
            
        # Clean close any existing MCI my_midi alias
        send_mci("close my_midi")
        
        # Open MIDI file using sequencer
        res = send_mci(f'open "{self.midi_path}" type sequencer alias my_midi')
        if res is None:
            # If path contains weird characters, try short path
            try:
                import win32api
                short_path = win32api.GetShortPathName(self.midi_path)
                res = send_mci(f'open "{short_path}" type sequencer alias my_midi')
            except Exception:
                pass
                
        if res is None:
            # Failed to open MIDI via MCI
            self._is_playing = False
            return False
            
        # Set time format to milliseconds
        send_mci("set my_midi time format milliseconds")
        
        # Start playback
        send_mci("play my_midi")
        self._is_playing = True
        self._is_paused = False
        self.stop_monitor.clear()
        
        # Start polling thread
        def monitor():
            while not self.stop_monitor.is_set():
                pos_str = send_mci("status my_midi position")
                if pos_str:
                    try:
                        pos_ms = int(pos_str)
                        self._current_time = pos_ms / 1000.0
                    except ValueError:
                        pass
                
                # Check status mode
                mode = send_mci("status my_midi mode")
                if mode == "stopped" or mode is None:
                    # Check if close to end
                    if self._current_time >= self._total_time - 0.5:
                        self._is_playing = False
                        self._current_time = 0.0
                        self.active_notes.clear()
                        if on_progress_callback:
                            on_progress_callback(0.0, self._total_time)
                        break
                
                # Determine active notes
                curr = self._current_time
                self.active_notes = {note for start, end, note in self.notes_intervals if start <= curr <= end}
                
                if on_progress_callback:
                    on_progress_callback(self._current_time, self._total_time)
                    
                time.sleep(0.03) # poll every 30ms
                
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
        return True

    def pause(self):
        if self._is_playing and not self._is_paused:
            send_mci("pause my_midi")
            self._is_paused = True

    def resume(self):
        if self._is_playing and self._is_paused:
            send_mci("play my_midi")
            self._is_paused = False

    def stop(self):
        self.stop_monitor.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=0.5)
            self.monitor_thread = None
        send_mci("stop my_midi")
        send_mci("close my_midi")
        self._is_playing = False
        self._is_paused = False
        self._current_time = 0.0
        self.active_notes.clear()

    def is_playing(self):
        return self._is_playing

    def is_paused(self):
        return self._is_paused

    def get_progress(self):
        return self._current_time, self._total_time

    def get_active_notes(self):
        return self.active_notes
