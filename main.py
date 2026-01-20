import customtkinter as ctk
import os
import threading
from tkinter import messagebox, StringVar
from sound_manager import SoundManager
from downloader import Downloader
from tts_generator import TTSGenerator

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class AddSoundDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("Ajouter un son")
        self.geometry("400x200")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.lbl_url = ctk.CTkLabel(self, text="URL YouTube:")
        self.lbl_url.pack(pady=5)
        self.entry_url = ctk.CTkEntry(self, width=300)
        self.entry_url.pack(pady=5)

        self.lbl_name = ctk.CTkLabel(self, text="Nom du son:")
        self.lbl_name.pack(pady=5)
        self.entry_name = ctk.CTkEntry(self, width=300)
        self.entry_name.pack(pady=5)

        self.btn_download = ctk.CTkButton(self, text="Télécharger", command=self.on_download)
        self.btn_download.pack(pady=20)

    def on_download(self):
        url = self.entry_url.get()
        name = self.entry_name.get()
        
        if not url or not name:
            messagebox.showwarning("Erreur", "Veuillez remplir tous les champs")
            return

        self.btn_download.configure(state="disabled", text="Téléchargement en cours...")
        
        # Thread pour ne pas bloquer l'UI
        threading.Thread(target=self._download_thread, args=(url, name)).start()

    def _download_thread(self, url, name):
        downloader = Downloader()
        # Nettoyer le nom pour le fichier
        download_path = downloader.download_sound(url, name.replace(" ", "_"))
        
        if download_path:
            self.after(0, lambda: self.callback(name, download_path))
            self.after(0, self.destroy)
        else:
            self.after(0, lambda: messagebox.showerror("Erreur", "Échec du téléchargement"))
class SoundBoardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Soundboard Windows")
        self.geometry("900x700")

        self.sound_manager = SoundManager()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        # Row 2 pour le footer TTS
        self.grid_rowconfigure(2, weight=0)

        # --- Header (Contrôles globaux & Settings) ---
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        self.btn_add = ctk.CTkButton(self.header_frame, text="+ Ajouter Youtube", command=self.open_add_dialog)
        self.btn_add.pack(side="left", padx=10)

        self.btn_stop = ctk.CTkButton(self.header_frame, text="STOP TOUT", fg_color="red", hover_color="darkred", command=self.sound_manager.stop_sound)
        self.btn_stop.pack(side="left", padx=10)

        # Device Selector
        self.device_var = StringVar(value="Périphérique par défaut")
        self.devices = self.sound_manager.get_devices()
        self.device_names = [d['name'] for d in self.devices]
        
        self.lbl_device = ctk.CTkLabel(self.header_frame, text="Sortie Audio:")
        self.lbl_device.pack(side="left", padx=(20, 5))
        
        self.combo_device = ctk.CTkComboBox(self.header_frame, values=self.device_names, command=self.change_device, width=250)
        self.combo_device.pack(side="left", padx=5)

        self.btn_refresh = ctk.CTkButton(self.header_frame, text="↻", width=30, command=self.refresh_devices)
        self.btn_refresh.pack(side="left", padx=5)

        self.switch_monitoring = ctk.CTkSwitch(self.header_frame, text="Monitoring", command=self.toggle_monitoring)
        self.switch_monitoring.pack(side="right", padx=10)
        
        # Charger l'état du monitoring depuis la config
        if self.sound_manager.monitoring:
            self.switch_monitoring.select()
        
        # Sélectionner le device actuel s'il existe
        current_id = self.sound_manager.current_device
        if current_id is not None:
            for d in self.devices:
                if d['id'] == current_id:
                    self.combo_device.set(d['name'])
                    break
        else:
             self.combo_device.set("Choisir périphérique (ex: CABLE Input)")


        # --- Sound Grid ---
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Mes Sons")
        self.scrollable_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.scrollable_frame.grid_columnconfigure((0, 1, 2, 3), weight=1) # 4 colonnes

        self.refresh_sounds()

        # --- Footer (TTS Generator) ---
        self.footer_frame = ctk.CTkFrame(self)
        self.footer_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)

        self.lbl_tts = ctk.CTkLabel(self.footer_frame, text="TTS Rapide :", font=("Arial", 12, "bold"))
        self.lbl_tts.pack(side="left", padx=10)

        self.entry_tts_text = ctk.CTkEntry(self.footer_frame, placeholder_text="Texte à dire...", width=300)
        self.entry_tts_text.pack(side="left", padx=5)

        self.btn_tts_play = ctk.CTkButton(self.footer_frame, text="▶ Jouer Direct", fg_color="green", hover_color="darkgreen", command=self.on_tts_play_direct)
        self.btn_tts_play.pack(side="left", padx=5)


    def change_device(self, choice):
        for d in self.devices:
            if d['name'] == choice:
                self.sound_manager.set_device(d['id'])
                print(f"Périphérique changé pour: {choice} (ID: {d['id']})")
                break

    def refresh_devices(self):
        self.devices = self.sound_manager.get_devices()
        self.device_names = [d['name'] for d in self.devices]
        self.combo_device.configure(values=self.device_names)
        
        current = self.combo_device.get()
        if current not in self.device_names:
             self.combo_device.set("Choisir périphérique")

    def toggle_monitoring(self):
        enabled = self.switch_monitoring.get()
        self.sound_manager.set_monitoring(bool(enabled))
        # Sauvegarder la préférence
        self.sound_manager.save_config()


    def open_add_dialog(self):
        dialog = AddSoundDialog(self, self.on_sound_added)
        dialog.grab_set()

    def _generate_tts_thread(self, text, name):
        generator = TTSGenerator()
        # Si direct play, on utilise un nom temporaire ou fixe
        path = generator.generate(text, name)
        
        if path:
            # Lecture directe
            self.after(0, lambda: self.sound_manager.play_file(path))
        else:
            self.after(0, lambda: messagebox.showerror("Erreur", "Échec de la génération"))
        
        self.after(0, lambda: self.reset_tts_buttons())

    def reset_tts_buttons(self):
        self.btn_tts_play.configure(state="normal", text="▶ Jouer Direct")

    def on_tts_play_direct(self):
        text = self.entry_tts_text.get()
        if not text:
            messagebox.showwarning("Erreur", "Veuillez entrer du texte")
            return
            
        name = "TTS_Direct_Play" # Nom interne pour le fichier

        self.btn_tts_play.configure(state="disabled", text="Génération...")
        threading.Thread(target=self._generate_tts_thread, args=(text, name)).start()





    def on_sound_added(self, name, path):
        self.sound_manager.add_sound(name, path)
        self.refresh_sounds()

    def refresh_sounds(self):
        # Nettoyer
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        sounds = self.sound_manager.sounds
        row = 0
        col = 0
        
        for name, path in sounds.items():
            btn = ctk.CTkButton(self.scrollable_frame, text=name, height=80, 
                                command=lambda n=name: self.sound_manager.play_sound(n))
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
            
            # Clic droit pour supprimer (simple hack bind)
            btn.bind("<Button-3>", lambda event, n=name: self.delete_sound(n))

            col += 1
            if col > 3:
                col = 0
                row += 1

    def delete_sound(self, name):
        if messagebox.askyesno("Supprimer", f"Voulez-vous supprimer le son '{name}' ?"):
            self.sound_manager.remove_sound(name)
            self.refresh_sounds()

if __name__ == "__main__":
    app = SoundBoardApp()
    app.mainloop()
