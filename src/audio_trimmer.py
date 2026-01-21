import customtkinter as ctk
from tkinter import messagebox
from pydub import AudioSegment
from pathlib import Path
import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import time

import uuid

# Essayer d'importer depuis le même dossier ou via src
try:
    from utils import center_window
except ImportError:
    from src.utils import center_window

class WaveformTimeline(ctk.CTkCanvas):
    """Widget de timeline audio avec waveform, sélection, règle et curseur de lecture"""
    
    def __init__(self, master, audio_segment, height=200, bg_color="#2b2b2b", wave_color="#0078D4", select_color="#4f4f4f", **kwargs):
        super().__init__(master, height=height, bg=bg_color, highlightthickness=0, borderwidth=0, **kwargs)
        # Forcer la configuration pour être sûr
        self.configure(highlightthickness=0, borderwidth=0)
        
        self.audio = audio_segment
        self.duration_ms = len(self.audio)
        self.height = height
        
        # Couleurs et Styles
        self.wave_color = wave_color
        self.select_color = select_color
        self.handle_color = "#ffffff"
        self.handle_hover_color = "#cccccc"
        self.playhead_color = "#ff4444"
        self.ruler_color = "#888888"
        self.ruler_text_color = "#aaaaaa"
        self.overlay_color = "#000000"
        self.overlay_stipple = "gray50" # Trame pour l'assombrissement
        
        # État
        self.width = 1
        self.start_ms = 0
        self.end_ms = self.duration_ms
        self.playhead_ms = 0
        self.dragging = None  # 'start', 'end', or 'playhead'
        self.hovering = None
        
        # Marge pour la règle (en haut)
        self.ruler_height = 25
        
        # Samples pour la waveform
        self.samples = None
        self.generate_waveform_data()
        
        # Bindings
        self.bind("<Configure>", self.on_resize)
        self.bind("<Button-1>", self.on_click)
        self.bind("<B1-Motion>", self.on_drag)
        self.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Motion>", self.on_mouse_move)

        
    def generate_waveform_data(self):
        """Convertit l'audio en array numpy pour la visualisation"""
        # Convertir en mono
        samples = np.array(self.audio.set_channels(1).get_array_of_samples())
        
        # Normaliser
        if samples.dtype == np.int16:
            samples = samples / 32768.0
        elif samples.dtype == np.int32:
            samples = samples / 2147483648.0
            
        self.samples = samples
        
    def ms_to_x(self, ms):
        """Convertit millisecondes en pixels"""
        return (ms / self.duration_ms) * self.width
        
    def x_to_ms(self, x):
        """Convertit pixels en millisecondes"""
        return max(0, min(self.duration_ms, int((x / self.width) * self.duration_ms)))
        
    def on_resize(self, event):
        self.width = event.width
        self.draw()
        
    def draw(self):
        self.delete("all")
        
        if self.samples is None or self.width <= 0:
            return
            
        # 1. Dessiner la Waveform
        self.draw_waveform()
            
        # 2. Dessiner la Règle temporelle
        self.draw_ruler()

        # 3. Dessiner l'Overlay (zones non sélectionnées assombries)
        self.draw_overlay()
        
        # 4. Dessiner les Handles (Poignées)
        self.draw_handles()

        # 5. Dessiner la Tête de lecture
        self.draw_playhead()
        
    def draw_waveform(self):
        # Hauteur disponible pour la waveform (sous la règle)
        wave_h = self.height - self.ruler_height
        mid_y = self.ruler_height + (wave_h / 2)
        scale_y = (wave_h / 2) * 0.95
        
        # Downsampling AMÉLIORÉ : min/max par pixel pour garder les pics
        samples_per_pixel = len(self.samples) / max(1, self.width)
        
        for pixel_x in range(int(self.width)):
            # Calculer la plage de samples pour ce pixel
            start_idx = int(pixel_x * samples_per_pixel)
            end_idx = int((pixel_x + 1) * samples_per_pixel)
            end_idx = min(end_idx, len(self.samples))
            
            if start_idx >= len(self.samples):
                break
                
            # Prendre le min et max dans cette plage pour garder l'enveloppe
            chunk = self.samples[start_idx:end_idx]
            if len(chunk) == 0:
                continue
                
            min_val = np.min(chunk)
            max_val = np.max(chunk)
            
            # Dessiner une ligne du min au max
            y_min = mid_y - (min_val * scale_y)
            y_max = mid_y - (max_val * scale_y)
            
            # Inverser si nécessaire pour que la ligne soit toujours de haut en bas
            if y_min > y_max:
                y_min, y_max = y_max, y_min
                
            self.create_line(pixel_x, y_min, pixel_x, y_max, fill=self.wave_color)

    def draw_ruler(self):
        # Fond de la règle
        self.create_rectangle(0, 0, self.width, self.ruler_height, fill="#222222", outline="")
        
        # Déterminer l'intervalle des graduations (optimisé selon la durée)
        duration_sec = self.duration_ms / 1000
        
        if duration_sec < 5: interval = 0.5
        elif duration_sec < 10: interval = 1
        elif duration_sec < 30: interval = 2
        elif duration_sec < 60: interval = 5
        else: interval = 10
        
        t = 0
        while t <= duration_sec:
            x = self.ms_to_x(t * 1000)
            
            # Grande graduation avec texte
            self.create_line(x, 0, x, self.ruler_height, fill=self.ruler_color)
            self.create_text(x + 2, self.ruler_height / 2, text=f"{t}s", anchor="w", fill=self.ruler_text_color, font=("Arial", 8))
            
            # Petites graduations intermédiaires
            if t + (interval/2) <= duration_sec:
                x_mid = self.ms_to_x((t + interval/2) * 1000)
                self.create_line(x_mid, self.ruler_height/2, x_mid, self.ruler_height, fill=self.ruler_color)
            
            t += interval
            
        self.create_line(0, self.ruler_height, self.width, self.ruler_height, fill=self.ruler_color)

    def draw_overlay(self):
        x_start = self.ms_to_x(self.start_ms)
        x_end = self.ms_to_x(self.end_ms)
        
        # Toujours créer les zones (même si largeur 0) pour pouvoir les mettre à jour
        self.create_rectangle(0, self.ruler_height, x_start, self.height, fill=self.overlay_color, stipple=self.overlay_stipple, outline="", tags="overlay_left")
        self.create_rectangle(x_end, self.ruler_height, self.width, self.height, fill=self.overlay_color, stipple=self.overlay_stipple, outline="", tags="overlay_right")

    def draw_handles(self):
        x_start = self.ms_to_x(self.start_ms)
        x_end = self.ms_to_x(self.end_ms)
        
        # Lignes verticales
        self.create_line(x_start, self.ruler_height, x_start, self.height, fill=self.handle_color, width=2, tags=("handle_line_start"))
        self.create_line(x_end, self.ruler_height, x_end, self.height, fill=self.handle_color, width=2, tags=("handle_line_end"))
        
        # Grips (Poignées triangles)
        grip_size = 10
        # Start grip (en haut)
        self.create_polygon(x_start, self.ruler_height, x_start, self.ruler_height + grip_size, x_start + grip_size, self.ruler_height,
                            fill=self.handle_color, tags=("handle_grip_start"))
        # End grip (en haut)
        self.create_polygon(x_end, self.ruler_height, x_end, self.ruler_height + grip_size, x_end - grip_size, self.ruler_height,
                            fill=self.handle_color, tags=("handle_grip_end"))

    def update_visuals(self):
        """Met à jour les positions des handles et overlay sans tout redessiner"""
        x_start = self.ms_to_x(self.start_ms)
        x_end = self.ms_to_x(self.end_ms)
        
        # Update Overlay
        self.coords("overlay_left", 0, self.ruler_height, x_start, self.height)
        self.coords("overlay_right", x_end, self.ruler_height, self.width, self.height)
        
        # Update Handles Lines
        self.coords("handle_line_start", x_start, self.ruler_height, x_start, self.height)
        self.coords("handle_line_end", x_end, self.ruler_height, x_end, self.height)
        
        # Update Handles Grips
        grip_size = 10
        self.coords("handle_grip_start", x_start, self.ruler_height, x_start, self.ruler_height + grip_size, x_start + grip_size, self.ruler_height)
        self.coords("handle_grip_end", x_end, self.ruler_height, x_end, self.ruler_height + grip_size, x_end - grip_size, self.ruler_height)

    def draw_playhead(self):
        x_play = self.ms_to_x(self.playhead_ms)
        self.create_line(x_play, 0, x_play, self.height, fill=self.playhead_color, width=1, tags="playhead")
        
        # Petit triangle indicateur en haut
        self.create_polygon(x_play - 4, 0, x_play + 4, 0, x_play, 8, fill=self.playhead_color, tags="playhead_cap")

    def set_playhead(self, ms):
        self.playhead_ms = max(0, min(self.duration_ms, ms))
        
        # Optimisation: déplacer les éléments existants
        x = self.ms_to_x(self.playhead_ms)
        if self.find_withtag("playhead"):
            self.coords("playhead", x, 0, x, self.height)
            self.coords("playhead_cap", x - 4, 0, x + 4, 0, x, 8)
        else:
            self.draw_playhead()

    def on_mouse_move(self, event):
        x = event.x
        ms = self.x_to_ms(x)
        
        # Hit detection pour changer le curseur et update hover line
        x_start = self.ms_to_x(self.start_ms)
        x_end = self.ms_to_x(self.end_ms)
        tolerance = 8
        
        # Dessiner la ligne de survol
        # Optimisation: Update coordonnées au lieu de supprimer/recréer
        
        if abs(x - x_start) < tolerance or abs(x - x_end) < tolerance:
            self.config(cursor="sb_h_double_arrow")
            self.hovering = "handle"
        else:
            self.config(cursor="crosshair") # Plus précis que xterm et permet de voir l'alignement
            self.hovering = None


    def on_click(self, event):
        x = event.x
        ms = self.x_to_ms(x)
        
        # Hit detection
        x_start = self.ms_to_x(self.start_ms)
        x_end = self.ms_to_x(self.end_ms)
        tolerance = 10
        
        if abs(x - x_start) < tolerance:
            self.dragging = 'start'
        elif abs(x - x_end) < tolerance:
            self.dragging = 'end'
        else:
            self.dragging = None
            # Si on clique, on déplace le playhead
            self.set_playhead(ms)

    def on_drag(self, event):
        ms = self.x_to_ms(event.x)
        
        if self.dragging == 'start':
            if ms < self.end_ms - 100:
                self.start_ms = ms
        elif self.dragging == 'end':
            if ms > self.start_ms + 100:
                self.end_ms = ms
        elif self.dragging == 'playhead':
            self.set_playhead(ms)
            
        if self.dragging in ['start', 'end']:
            # Optimisation: Déplacer les éléments existants au lieu de delete/recreate
            x_start = self.ms_to_x(self.start_ms)
            x_end = self.ms_to_x(self.end_ms)
            
            # Mettre à jour les overlays avec coords
            self.coords("overlay_left", 0, self.ruler_height, x_start, self.height)
            self.coords("overlay_right", x_end, self.ruler_height, self.width, self.height)
            
            # Mettre à jour les handles
            self.coords("handle_line_start", x_start, self.ruler_height, x_start, self.height)
            self.coords("handle_line_end", x_end, self.ruler_height, x_end, self.height)
            
            # Mettre à jour les grips (triangles)
            grip_size = 10
            self.coords("handle_grip_start", x_start, self.ruler_height, x_start, self.ruler_height + grip_size, x_start + grip_size, self.ruler_height)
            self.coords("handle_grip_end", x_end, self.ruler_height, x_end, self.ruler_height + grip_size, x_end - grip_size, self.ruler_height)
            
            self.event_generate("<<SelectionChanged>>")

    def on_release(self, event):
        self.dragging = None
        

        
    def get_selection(self):
        return self.start_ms, self.end_ms


class AudioTrimDialog(ctk.CTkToplevel):
    """Dialog pour trimmer (couper) un fichier audio - Version Avancée"""
    
    def __init__(self, parent, audio_path, callback):
        super().__init__(parent)
        self.audio_path = Path(audio_path)
        self.callback = callback
        
        self.title(f"Éditeur Audio - {self.audio_path.name}")
        center_window(self, 900, 550, parent)
        
        self.playing = False
        self.stop_playback = threading.Event()
        self.playback_start_ms = 0
        
        # UI de chargement
        self.loading_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.loading_frame.pack(expand=True, fill="both")
        
        self.lbl_loading = ctk.CTkLabel(self.loading_frame, text="Chargement de l'audio...", font=("Segoe UI", 16))
        self.lbl_loading.pack(expand=True)
        
        self.progress = ctk.CTkProgressBar(self.loading_frame, width=200, mode="indeterminate")
        self.progress.pack(pady=10)
        self.progress.start()
        
        # Charger en background
        threading.Thread(target=self._load_audio_thread, daemon=True).start()
        
        # Bindings Clavier
        self.bind("<space>", self.toggle_playback)
        self.focus_set()
        
    def _load_audio_thread(self):
        try:
            self.audio = AudioSegment.from_file(str(self.audio_path))
            self.duration_ms = len(self.audio)
            
            # Revenir sur le thread principal pour l'UI
            self.after(0, self._on_load_complete)
            
        except Exception as e:
            self.after(0, lambda: self._on_load_error(e))
            
    def _on_load_error(self, error):
        messagebox.showerror("Erreur", f"Impossible de charger l'audio:\n{error}")
        self.destroy()
        
    def _on_load_complete(self):
        self.loading_frame.destroy()
        self.setup_ui()
    
    def setup_ui(self):
        # Container principal avec padding
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Titre et Infos
        top_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0, 10))
        
        title = ctk.CTkLabel(top_frame, text="Éditeur de Waveform", font=("Segoe UI", 20, "bold"))
        title.pack(side="left")
        
        help_text = ctk.CTkLabel(top_frame, text="[Espace] pour Lire/Pause  |  Glissez les barres blanches pour couper", text_color="gray")
        help_text.pack(side="right")
        
        # Timeline
        self.timeline = WaveformTimeline(main_frame, self.audio, height=250, bg_color="#1a1a1a", wave_color="#2b825b")
        self.timeline.pack(fill="x", pady=10, expand=True)
        self.timeline.bind("<<SelectionChanged>>", self.on_selection_change)
        
        # Dashboard (Temps)
        dash_frame = ctk.CTkFrame(main_frame)
        dash_frame.pack(fill="x", pady=10)
        
        self.lbl_start = ctk.CTkLabel(dash_frame, text="Début: 0.00s", font=("Consolas", 14))
        self.lbl_start.pack(side="left", padx=20, pady=10)
        
        self.lbl_duration = ctk.CTkLabel(dash_frame, text=f"Sélection: {self.duration_ms/1000:.2f}s", font=("Consolas", 14, "bold"), text_color="#2b825b")
        self.lbl_duration.pack(side="left", expand=True)
        
        self.lbl_end = ctk.CTkLabel(dash_frame, text=f"Fin: {self.duration_ms/1000:.2f}s", font=("Consolas", 14))
        self.lbl_end.pack(side="right", padx=20, pady=10)
        
        # Contrôles de lecture
        controls_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        controls_frame.pack(pady=10)
        
        self.btn_play = ctk.CTkButton(controls_frame, text="▶ Lire / Stop", command=self.toggle_playback, width=160, height=40, font=("Segoe UI", 13, "bold"))
        self.btn_play.pack(padx=5)

        # Actions Finales
        action_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_frame.pack(side="bottom", fill="x", pady=(20, 0))
        
        self.btn_save = ctk.CTkButton(action_frame, text="✓ SAUVEGARDER", command=self.save_trimmed, fg_color="#2b825b", hover_color="#1f5d42", height=45, width=150, font=("Segoe UI", 13, "bold"))
        self.btn_save.pack(side="right", padx=0)
        
        self.btn_cancel = ctk.CTkButton(action_frame, text="Annuler", command=self.destroy, fg_color="transparent", border_width=1, text_color="gray", height=45)
        self.btn_cancel.pack(side="right", padx=10)

    def on_selection_change(self, event):
        start, end = self.timeline.get_selection()
        self.lbl_start.configure(text=f"Début: {start/1000:.2f}s")
        self.lbl_end.configure(text=f"Fin: {end/1000:.2f}s")
        self.lbl_duration.configure(text=f"Sélection: {(end-start)/1000:.2f}s")

    def toggle_playback(self, event=None):
        if self.playing:
            self.stop_audio()
        else:
            self.play_from_cursor()

    def play_audio_thread(self, start_ms, end_ms=None):
        if self.playing:
            self.stop_audio()
            time.sleep(0.1)
            
        self.playing = True
        self.stop_playback.clear()
        self.playback_start_ms = start_ms  # Sauvegarder la position de départ
        self.btn_play.configure(text="⬛  Stop (Espace)", fg_color="#d13438", hover_color="#a02a2e")
        
        def run():
            try:
                segment = self.audio[start_ms:end_ms] if end_ms else self.audio[start_ms:]
                
                # Exporter temp avec nom unique pour éviter conflits
                temp_path = self.audio_path.parent / f"temp_play_{uuid.uuid4().hex[:8]}.wav"
                segment.export(str(temp_path), format="wav")
                
                data, fs = sf.read(str(temp_path))
                
                start_time = time.time()
                total_duration = len(segment) / 1000.0
                
                sd.play(data, fs)
                
                while self.playing and (time.time() - start_time) < total_duration:
                    if self.stop_playback.is_set():
                        sd.stop()
                        self.playing = False
                        break
                    
                    # Update curseur avec protection contre fenêtre fermée
                    try:
                        current_pos_ms = start_ms + (time.time() - start_time) * 1000
                        # Vérifier que la fenêtre existe toujours
                        if self.winfo_exists():
                            # OPTIMISATION: Vérifier self.playing pour ne pas écraser le reset du curseur si stop a été cliqué
                            self.after_idle(lambda ms=current_pos_ms: self.timeline.set_playhead(ms) if self.playing and self.timeline.winfo_exists() else None)
                    except:
                        # Fenêtre fermée, arrêter
                        break
                    
                    time.sleep(0.03) # ~30fps update
                
                self.playing = False
                
                try:
                    if self.winfo_exists():
                        self.after_idle(lambda: self.btn_play.configure(text="▶ Lire (Espace)", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"]))
                except:
                    pass
                
                # Si lecture finie naturellement (pas stoppée), on ne fait rien de spécial
                if not self.stop_playback.is_set():
                    pass
                    
                temp_path.unlink(missing_ok=True)
                
            except Exception as e:
                print(f"Erreur lecture: {e}")
                self.playing = False
                try:
                    if self.winfo_exists():
                        self.after_idle(lambda: self.btn_play.configure(text="▶ Lire (Espace)", fg_color=["#3B8ED0", "#1F6AA5"]))
                except:
                    pass
        
        threading.Thread(target=run, daemon=True).start()

    def play_from_cursor(self):
        self.play_audio_thread(self.timeline.playhead_ms)


    def stop_audio(self):
        self.stop_playback.set()
        sd.stop()
        self.playing = False
        self.btn_play.configure(text="▶ Lire (Espace)", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])
        # Remettre le curseur à la position de départ
        self.timeline.set_playhead(self.playback_start_ms)

    def save_trimmed(self):
        try:
            start, end = self.timeline.get_selection()
            
            segment = self.audio[start:end]
            segment.export(str(self.audio_path), format=self.audio_path.suffix[1:])
            
            if self.callback:
                self.callback(str(self.audio_path))
            
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder:\n{e}")
