import customtkinter as ctk
from tkinter import messagebox, Canvas
from pydub import AudioSegment
from pathlib import Path
import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import time

class WaveformTimeline(Canvas):
    """Widget de timeline audio avec waveform, sélection et curseur de lecture"""
    
    def __init__(self, master, audio_segment, height=150, bg_color="#2b2b2b", wave_color="#0078D4", select_color="#4f4f4f", **kwargs):
        super().__init__(master, height=height, bg=bg_color, highlightthickness=0, **kwargs)
        self.audio = audio_segment
        self.duration_ms = len(self.audio)
        self.height = height
        
        # Couleurs
        self.wave_color = wave_color
        self.select_color = select_color
        self.handle_color = "#ffffff"
        self.playhead_color = "#ff0000"
        
        # État
        self.width = 1
        self.start_ms = 0
        self.end_ms = self.duration_ms
        self.playhead_ms = 0
        self.dragging = None  # 'start', 'end', or 'playhead'
        
        # Générer les données de la waveform
        self.samples = None
        self.generate_waveform_data()
        
        # Bindings
        self.bind("<Configure>", self.on_resize)
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        
    def generate_waveform_data(self):
        """Convertit l'audio en array numpy pour la visualisation"""
        # Convertir en mono et obtenir les samples bruts
        samples = np.array(self.audio.set_channels(1).get_array_of_samples())
        
        # Normaliser entre -1 et 1
        if samples.dtype == np.int16:
            samples = samples / 32768.0
        elif samples.dtype == np.int32:
            samples = samples / 2147483648.0
            
        self.samples = samples
        
    def ms_to_x(self, ms):
        return (ms / self.duration_ms) * self.width
        
    def x_to_ms(self, x):
        return max(0, min(self.duration_ms, int((x / self.width) * self.duration_ms)))
        
    def on_resize(self, event):
        self.width = event.width
        self.draw()
        
    def draw(self):
        self.delete("all")
        
        if self.samples is None or self.width <= 0:
            return
            
        # 1. Dessiner la waveform
        # Downsampling pour la performance: 1 point par pixel
        step = max(1, len(self.samples) // self.width)
        reduced_samples = self.samples[::step]
        
        # Centrer verticalement
        mid_y = self.height / 2
        scale_y = (self.height / 2) * 0.9  # Marge de 10%
        
        points = []
        for i, sample in enumerate(reduced_samples):
            if i >= self.width: break
            x = i
            y = mid_y - (sample * scale_y)
            # On dessine une ligne verticale pour chaque sample (plus simple et joli pour l'audio dense)
            # Ou juste les points haut/bas min/max par pixel serait plus précis mais ceci est suffisant
            self.create_line(x, mid_y, x, y, fill=self.wave_color)
            
        # 2. Dessiner la zone de sélection (grisée) en dehors de la sélection
        # Zone gauche (avant start)
        x_start = self.ms_to_x(self.start_ms)
        x_end = self.ms_to_x(self.end_ms)
        
        self.create_rectangle(0, 0, x_start, self.height, fill="#000000", stipple="gray50", outline="")
        self.create_rectangle(x_end, 0, self.width, self.height, fill="#000000", stipple="gray50", outline="")
        
        # 3. Lignes de sélection (Handles)
        self.create_line(x_start, 0, x_start, self.height, fill=self.handle_color, width=2, tags="handle_start")
        self.create_line(x_end, 0, x_end, self.height, fill=self.handle_color, width=2, tags="handle_end")
        
        # Triangles pour les handles
        self.create_polygon(x_start, 0, x_start-5, 10, x_start+5, 10, fill=self.handle_color, tags="handle_start")
        self.create_polygon(x_start, self.height, x_start-5, self.height-10, x_start+5, self.height-10, fill=self.handle_color, tags="handle_start")
        
        self.create_polygon(x_end, 0, x_end-5, 10, x_end+5, 10, fill=self.handle_color, tags="handle_end")
        self.create_polygon(x_end, self.height, x_end-5, self.height-10, x_end+5, self.height-10, fill=self.handle_color, tags="handle_end")

        # 4. Tête de lecture (Playhead)
        x_play = self.ms_to_x(self.playhead_ms)
        self.create_line(x_play, 0, x_play, self.height, fill=self.playhead_color, width=1, tags="playhead")
        
    def on_click(self, event):
        x = event.x
        ms = self.x_to_ms(x)
        
        # Détection de click proche des handles (tolérance 10px)
        x_start = self.ms_to_x(self.start_ms)
        x_end = self.ms_to_x(self.end_ms)
        
        if abs(x - x_start) < 10:
            self.dragging = 'start'
        elif abs(x - x_end) < 10:
            self.dragging = 'end'
        else:
            self.dragging = None
            self.set_playhead(ms)
            
    def on_drag(self, event):
        ms = self.x_to_ms(event.x)
        
        if self.dragging == 'start':
            if ms < self.end_ms - 100: # Min 100ms duration
                self.start_ms = ms
        elif self.dragging == 'end':
            if ms > self.start_ms + 100:
                self.end_ms = ms
        
        self.draw()
        # Notifier changement si nécessaire via event virtuel ou callback
        self.event_generate("<<SelectionChanged>>")

    def on_release(self, event):
        self.dragging = None

    def set_playhead(self, ms):
        self.playhead_ms = max(0, min(self.duration_ms, ms))
        # OPTIMISATION: Ne pas tout redessiner, juste déplacer la ligne
        x_play = self.ms_to_x(self.playhead_ms)
        
        if self.find_withtag("playhead"):
            self.coords("playhead", x_play, 0, x_play, self.height)
        else:
            self.draw() # Fallback si pas encore dessiné
        
    def get_selection(self):
        return self.start_ms, self.end_ms


class AudioTrimDialog(ctk.CTkToplevel):
    """Dialog pour trimmer (couper) un fichier audio avec visualisation"""
    
    def __init__(self, parent, audio_path, callback):
        super().__init__(parent)
        self.audio_path = Path(audio_path)
        self.callback = callback
        
        self.title("Trimmer l'audio (Avancé)")
        self.geometry("800x500")
        
        # Charger l'audio
        try:
            self.audio = AudioSegment.from_file(str(self.audio_path))
            self.duration_ms = len(self.audio)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger l'audio:\n{e}")
            self.destroy()
            return
            
        self.playing = False
        self.stop_playback = threading.Event()
        
        self.setup_ui()
    
    def setup_ui(self):
        # Titre
        title_label = ctk.CTkLabel(self, text="Éditeur Audio", font=("Arial", 18, "bold"))
        title_label.pack(pady=(10, 5))
        
        # Info
        self.info_label = ctk.CTkLabel(self, text="Sélectionnez la zone à garder (gris foncé) et positionnez le curseur rouge pour écouter.")
        self.info_label.pack(pady=5)
        
        # Timeline Widget
        self.timeline = WaveformTimeline(self, self.audio, height=200, bg_color="#1e1e1e")
        self.timeline.pack(fill="x", padx=20, pady=10, expand=True)
        self.timeline.bind("<<SelectionChanged>>", self.on_selection_change)
        
        # Contrôles de temps
        time_frame = ctk.CTkFrame(self)
        time_frame.pack(fill="x", padx=20, pady=5)
        
        self.lbl_start = ctk.CTkLabel(time_frame, text="Début: 0.00s")
        self.lbl_start.pack(side="left", padx=20)
        
        self.lbl_duration = ctk.CTkLabel(time_frame, text=f"Durée: {self.duration_ms/1000:.2f}s", font=("Arial", 12, "bold"))
        self.lbl_duration.pack(side="left", expand=True)
        
        self.lbl_end = ctk.CTkLabel(time_frame, text=f"Fin: {self.duration_ms/1000:.2f}s")
        self.lbl_end.pack(side="right", padx=20)
        
        # Boutons de lecture
        play_frame = ctk.CTkFrame(self, fg_color="transparent")
        play_frame.pack(pady=10)
        
        self.btn_play_cursor = ctk.CTkButton(play_frame, text="▶ Lire depuis curseur", command=self.play_from_cursor, width=150)
        self.btn_play_cursor.pack(side="left", padx=10)
        
        self.btn_play_selection = ctk.CTkButton(play_frame, text="🔁 Lire la sélection", command=self.play_selection, width=150, fg_color="#E0a400", hover_color="#b08000", text_color="black")
        self.btn_play_selection.pack(side="left", padx=10)
        
        self.btn_stop = ctk.CTkButton(play_frame, text="⬛ Stop", command=self.stop_audio, width=100, fg_color="red", hover_color="darkred")
        self.btn_stop.pack(side="left", padx=10)

        # Boutons d'action
        action_frame = ctk.CTkFrame(self)
        action_frame.pack(side="bottom", fill="x", padx=20, pady=20)
        
        self.btn_save = ctk.CTkButton(action_frame, text="✓ Sauvegarder et Fermer", command=self.save_trimmed, fg_color="#2b825b", hover_color="#1f5d42", height=40)
        self.btn_save.pack(side="right", padx=10)
        
        self.btn_cancel = ctk.CTkButton(action_frame, text="Annuler", command=self.destroy, fg_color="transparent", border_width=1, text_color="gray")
        self.btn_cancel.pack(side="right", padx=10)

    def on_selection_change(self, event):
        start, end = self.timeline.get_selection()
        self.lbl_start.configure(text=f"Début: {start/1000:.2f}s")
        self.lbl_end.configure(text=f"Fin: {end/1000:.2f}s")
        self.lbl_duration.configure(text=f"Durée: {(end-start)/1000:.2f}s")

    def play_audio_thread(self, start_ms, end_ms=None):
        if self.playing:
            self.stop_audio()
            time.sleep(0.1)  # Laisser le temps au thread précédent de s'arrêter
            
        self.playing = True
        self.stop_playback.clear()
        
        def run():
            try:
                # Si end_ms n'est pas spécifié, jouer jusqu'à la fin
                segment = self.audio[start_ms:end_ms] if end_ms else self.audio[start_ms:]
                
                # Exporter temp
                temp_path = self.audio_path.parent / "temp_play.wav"
                segment.export(str(temp_path), format="wav")
                
                data, fs = sf.read(str(temp_path))
                
                # On utilise sounddevice en mode bloquant par blocs pour mettre à jour le curseur ?
                # Pour simplifier: on lance la lecture et on update le curseur avec un timer
                
                start_time = time.time()
                total_duration = len(segment) / 1000.0
                
                sd.play(data, fs)
                
                while self.playing and (time.time() - start_time) < total_duration:
                    if self.stop_playback.is_set():
                        sd.stop()
                        self.playing = False
                        break
                    
                    # Update curseur
                    current_pos_ms = start_ms + (time.time() - start_time) * 1000
                    self.timeline.set_playhead(current_pos_ms)
                    time.sleep(0.05)
                
                self.playing = False
                # Remettre curseur au début de la sélection ou laisser là où il s'est arrêté?
                # On laisse là.
                temp_path.unlink(missing_ok=True)
                
            except Exception as e:
                print(f"Erreur lecture: {e}")
                self.playing = False
        
        threading.Thread(target=run, daemon=True).start()

    def play_from_cursor(self):
        self.play_audio_thread(self.timeline.playhead_ms)

    def play_selection(self):
        start, end = self.timeline.get_selection()
        # Positionner le curseur au début
        self.timeline.set_playhead(start)
        self.play_audio_thread(start, end)
        
    def stop_audio(self):
        self.stop_playback.set()
        sd.stop()
        self.playing = False

    def save_trimmed(self):
        """Sauvegarder le segment trimmé"""
        try:
            start, end = self.timeline.get_selection()
            
            # Extraire le segment
            segment = self.audio[start:end]
            
            # Sauvegarder par-dessus le fichier original
            segment.export(str(self.audio_path), format=self.audio_path.suffix[1:])
            
            messagebox.showinfo("Succès", "Le son a été édité avec succès !")
            
            if self.callback:
                self.callback(str(self.audio_path))
            
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder:\n{e}")
