import customtkinter as ctk
from tkinter import messagebox
from pydub import AudioSegment
from pathlib import Path
import sounddevice as sd
import soundfile as sf
import numpy as np
import threading


class AudioTrimDialog(ctk.CTkToplevel):
    """Dialog pour trimmer (couper) un fichier audio"""
    
    def __init__(self, parent, audio_path, callback):
        super().__init__(parent)
        self.audio_path = Path(audio_path)
        self.callback = callback
        
        self.title("Trimmer l'audio")
        self.geometry("600x300")
        self.resizable(False, False)
        
        # Charger l'audio
        try:
            self.audio = AudioSegment.from_file(str(self.audio_path))
            self.duration_ms = len(self.audio)
            self.duration_sec = self.duration_ms / 1000.0
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger l'audio:\n{e}")
            self.destroy()
            return
        
        self.start_ms = 0
        self.end_ms = self.duration_ms
        self.playing = False
        
        self.setup_ui()
    
    def setup_ui(self):
        # Titre
        title_label = ctk.CTkLabel(self, text="Ajuster le début et la fin du son", font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Info durée
        info_label = ctk.CTkLabel(self, text=f"Durée totale: {self.duration_sec:.2f}s")
        info_label.pack(pady=5)
        
        # Frame pour les sliders
        sliders_frame = ctk.CTkFrame(self)
        sliders_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Slider début
        start_label = ctk.CTkLabel(sliders_frame, text="Début (secondes):")
        start_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.start_slider = ctk.CTkSlider(
            sliders_frame, 
            from_=0, 
            to=self.duration_sec,
            command=self.on_start_change,
            width=300
        )
        self.start_slider.set(0)
        self.start_slider.grid(row=0, column=1, padx=10, pady=10)
        
        self.start_value_label = ctk.CTkLabel(sliders_frame, text="0.00s")
        self.start_value_label.grid(row=0, column=2, padx=10, pady=10)
        
        # Slider fin
        end_label = ctk.CTkLabel(sliders_frame, text="Fin (secondes):")
        end_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
        
        self.end_slider = ctk.CTkSlider(
            sliders_frame,
            from_=0,
            to=self.duration_sec,
            command=self.on_end_change,
            width=300
        )
        self.end_slider.set(self.duration_sec)
        self.end_slider.grid(row=1, column=1, padx=10, pady=10)
        
        self.end_value_label = ctk.CTkLabel(sliders_frame, text=f"{self.duration_sec:.2f}s")
        self.end_value_label.grid(row=1, column=2, padx=10, pady=10)
        
        # Durée résultante
        self.result_label = ctk.CTkLabel(sliders_frame, text=f"Durée après trim: {self.duration_sec:.2f}s", font=("Arial", 12, "bold"))
        self.result_label.grid(row=2, column=0, columnspan=3, pady=10)
        
        # Boutons
        buttons_frame = ctk.CTkFrame(self)
        buttons_frame.pack(pady=10, fill="x", padx=20)
        
        self.btn_preview = ctk.CTkButton(buttons_frame, text="▶ Prévisualiser", command=self.preview_audio, fg_color="#2b825b", hover_color="#1f5d42")
        self.btn_preview.pack(side="left", padx=5, expand=True)
        
        self.btn_save = ctk.CTkButton(buttons_frame, text="✓ Sauvegarder", command=self.save_trimmed, fg_color="#0078D4", hover_color="#005a9e")
        self.btn_save.pack(side="left", padx=5, expand=True)
        
        self.btn_cancel = ctk.CTkButton(buttons_frame, text="✗ Annuler", command=self.destroy, fg_color="#d13438", hover_color="#a02a2e")
        self.btn_cancel.pack(side="left", padx=5, expand=True)
    
    def on_start_change(self, value):
        self.start_ms = int(float(value) * 1000)
        self.start_value_label.configure(text=f"{float(value):.2f}s")
        
        # S'assurer que début < fin
        if self.start_ms >= self.end_ms:
            self.end_ms = self.start_ms + 100  # Au moins 100ms
            self.end_slider.set(self.end_ms / 1000.0)
        
        self.update_result_label()
    
    def on_end_change(self, value):
        self.end_ms = int(float(value) * 1000)
        self.end_value_label.configure(text=f"{float(value):.2f}s")
        
        # S'assurer que fin > début
        if self.end_ms <= self.start_ms:
            self.start_ms = self.end_ms - 100  # Au moins 100ms
            self.start_slider.set(self.start_ms / 1000.0)
        
        self.update_result_label()
    
    def update_result_label(self):
        duration = (self.end_ms - self.start_ms) / 1000.0
        self.result_label.configure(text=f"Durée après trim: {duration:.2f}s")
    
    def preview_audio(self):
        """Jouer un aperçu du segment sélectionné"""
        if self.playing:
            return
        
        self.playing = True
        self.btn_preview.configure(state="disabled", text="Lecture...")
        
        def play_thread():
            try:
                # Extraire le segment
                segment = self.audio[self.start_ms:self.end_ms]
                
                # Exporter vers un buffer temporaire
                temp_path = self.audio_path.parent / "temp_preview.wav"
                segment.export(str(temp_path), format="wav")
                
                # Lire avec sounddevice
                data, sample_rate = sf.read(str(temp_path))
                sd.play(data, sample_rate)
                sd.wait()
                
                # Nettoyer
                temp_path.unlink()
                
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Erreur", f"Impossible de prévisualiser:\n{e}"))
            finally:
                self.playing = False
                self.after(0, lambda: self.btn_preview.configure(state="normal", text="▶ Prévisualiser"))
        
        threading.Thread(target=play_thread, daemon=True).start()
    
    def save_trimmed(self):
        """Sauvegarder le segment trimmé"""
        try:
            # Extraire le segment
            segment = self.audio[self.start_ms:self.end_ms]
            
            # Sauvegarder par-dessus le fichier original
            segment.export(str(self.audio_path), format=self.audio_path.suffix[1:])
            
            messagebox.showinfo("Succès", "Le son a été trimmé avec succès !")
            
            # Appeler le callback avec le chemin du fichier trimmé
            if self.callback:
                self.callback(str(self.audio_path))
            
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de sauvegarder:\n{e}")
