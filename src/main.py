"""
Soundbien - Application de Soundboard Windows
Permet de jouer des sons depuis YouTube, fichiers locaux, ou TTS sur des périphériques audio virtuels.
"""

import os
import sys

# === DPI Awareness pour Windows ===
# Fixe le problème de décalage curseur/slider sur les écrans avec scaling (125%, 150%, etc.)
if sys.platform == 'win32':
    try:
        import ctypes
        # Méthode moderne (Windows 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # 2 = PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            # Méthode legacy (Windows Vista+)
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass  # Pas grave si ça échoue, on continue sans

import customtkinter as ctk
import threading
from tkinter import messagebox, StringVar, filedialog, simpledialog
from pathlib import Path
import shutil

# System tray
try:
    import pystray
    from PIL import Image
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# Ensure we can import modules from the same directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from sound_manager import SoundManager
from downloader import Downloader
from tts_generator import TTSGenerator
from updater import Updater
from utils import center_window

# Version info
try:
    from __init__ import __version__
except ImportError:
    __version__ = "1.0.0"

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def get_app_data_dir():
    """Retourne le chemin vers le dossier de données de l'application dans Documents."""
    # Utiliser Path.home() pour obtenir le dossier utilisateur
    user_docs = Path.home() / "Documents" / "Soundbien"
    user_docs.mkdir(parents=True, exist_ok=True)
    return user_docs

class AddSoundDialog(ctk.CTkToplevel):
    def __init__(self, parent, callback, downloader):
        super().__init__(parent)
        self.callback = callback
        self.downloader = downloader
        self.title("Ajouter un son depuis YouTube")
        center_window(self, 400, 180, parent)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.lbl_url = ctk.CTkLabel(self, text="URL YouTube:")
        self.lbl_url.pack(pady=5)
        self.entry_url = ctk.CTkEntry(self, width=300, placeholder_text="https://youtube.com/watch?v=...")
        self.entry_url.pack(pady=5)
        
        self.lbl_info = ctk.CTkLabel(self, text="Le nom sera automatiquement extrait de la vidéo", 
                                      font=("Arial", 9), text_color="#888")
        self.lbl_info.pack(pady=5)

        self.btn_download = ctk.CTkButton(self, text="Télécharger", command=self.on_download)
        self.btn_download.pack(pady=20)

    def on_download(self):
        url = self.entry_url.get().strip()
        
        if not url:
            messagebox.showwarning("Erreur", "Veuillez entrer une URL YouTube")
            return

        self.btn_download.configure(state="disabled", text="Téléchargement en cours...")
        
        # Thread pour ne pas bloquer l'UI
        threading.Thread(target=self._download_thread, args=(url,), daemon=True).start()

    def _download_thread(self, url):
        # Télécharger et récupérer le titre automatiquement
        download_path, title = self.downloader.download_sound(url)
        
        if download_path and title:
            # Fermer d'abord, puis callback avec le titre extrait
            self.after(0, self.destroy)
            self.after(100, lambda: self.callback(title, download_path))
        else:
            self.after(0, lambda: messagebox.showerror("Erreur", "Échec du téléchargement"))
            self.after(0, lambda: self.btn_download.configure(state="normal", text="Télécharger"))
class SoundBoardApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Soundboard Windows")
        center_window(self, 1100, 700)

        # Obtenir le dossier de données de l'application
        self.app_data_dir = get_app_data_dir()
        config_path = self.app_data_dir / "config.json"
        sounds_dir = self.app_data_dir / "sounds"
        sounds_dir.mkdir(exist_ok=True)

        self.sound_manager = SoundManager(config_file=str(config_path))
        self.downloader = Downloader(download_path=str(sounds_dir))
        self.tts_generator = TTSGenerator(output_dir=str(sounds_dir))
        
        # Vérifier les mises à jour en arrière-plan
        self.updater = Updater(config_dir=str(self.app_data_dir))
        
        # Vérifier si on vient de faire une mise à jour (afficher changelog)
        if self.updater.was_just_updated():
            self.after(500, self._show_changelog_dialog)
        
        # Uniquement en version EXE pour éviter rate limit GitHub en dev
        if getattr(sys, 'frozen', False):
            threading.Thread(target=self._check_updates, daemon=True).start()
        else:
            print("Mode dev: Thread auto-update désactivé.")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        # Row 2 pour le footer TTS
        self.grid_rowconfigure(2, weight=0)

        # --- Header (Contrôles globaux & Settings) ---
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        self.btn_add_youtube = ctk.CTkButton(self.header_frame, text="+ Ajouter Youtube", command=self.open_add_dialog)
        self.btn_add_youtube.pack(side="left", padx=5)
        
        self.btn_add_file = ctk.CTkButton(self.header_frame, text="+ Ajouter Fichier", command=self.open_file_import, fg_color="#2b825b", hover_color="#1f5d42")
        self.btn_add_file.pack(side="left", padx=5)

        self.btn_stop = ctk.CTkButton(self.header_frame, text="STOP TOUT", fg_color="red", hover_color="darkred", command=self.sound_manager.stop_sound)
        self.btn_stop.pack(side="left", padx=10)
        # Context menu pour la touche STOP
        self.btn_stop.bind("<Button-3>", self.show_stop_context_menu)
        self._update_stop_button_text()

        # Device Selector
        self.device_var = StringVar(value="Périphérique par défaut")
        self.devices = [] 
        self.device_names = ["Chargement..."]
        
        self.lbl_device = ctk.CTkLabel(self.header_frame, text="Sortie Audio:")
        self.lbl_device.pack(side="left", padx=(20, 5))
        
        self.combo_device = ctk.CTkComboBox(self.header_frame, values=self.device_names, command=self.change_device, width=250)
        self.combo_device.pack(side="left", padx=5)
        self.combo_device.set("Chargement...")
        self.combo_device.configure(state="disabled") # Désactiver pendant chargement

        self.btn_refresh = ctk.CTkButton(self.header_frame, text="↻", width=30, command=self.refresh_devices)
        self.btn_refresh.pack(side="left", padx=5)

        self.switch_monitoring = ctk.CTkSwitch(self.header_frame, text="Monitoring", command=self.toggle_monitoring)
        self.switch_monitoring.pack(side="right", padx=10)
        
        # Charger les devices en background
        threading.Thread(target=self._load_devices_async, daemon=True).start()
        
        # Charger l'état du monitoring depuis la config
        if self.sound_manager.monitoring:
            self.switch_monitoring.select()
        
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


        # Volume Controls (Custom sliders sans bug)
        from volume_slider import VolumeSlider
        
        self.vol_frame = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        self.vol_frame.pack(side="right", padx=10)

        # Output Vol
        self.lbl_vol_out = ctk.CTkLabel(self.vol_frame, text="Sortie 📢", font=("Arial", 10))
        self.lbl_vol_out.grid(row=0, column=0, padx=5)
        self.slider_vol_out = VolumeSlider(self.vol_frame, 
                                           initial_value=self.sound_manager.vol_output,
                                           callback=self.on_vol_out_change)
        self.slider_vol_out.grid(row=1, column=0, padx=5)

        # Monitoring Vol
        self.lbl_vol_mon = ctk.CTkLabel(self.vol_frame, text="Moi 🎧", font=("Arial", 10))
        self.lbl_vol_mon.grid(row=0, column=1, padx=5)
        self.slider_vol_mon = VolumeSlider(self.vol_frame,
                                           initial_value=self.sound_manager.vol_monitoring,
                                           callback=self.on_vol_mon_change)
        self.slider_vol_mon.grid(row=1, column=1, padx=5)


        # Note: on n'utilise plus self.bind('<KeyPress>') car le SoundManager
        # gère tout via keyboard.hook pour le global hotkey 
        
        # System Tray
        self.tray_icon = None
        if TRAY_AVAILABLE:
            self._setup_tray_icon()
            # Intercepter fermeture et minimisation
            self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
            self.bind("<Unmap>", self._on_minimize)

    def _setup_tray_icon(self):
        """Configure l'icône de la barre d'état système"""
        # Charger l'icône
        icon_path = Path(__file__).parent.parent / "assets" / "icon.png"
        if not icon_path.exists():
            icon_path = Path(__file__).parent.parent / "assets" / "icon.ico"
        
        if icon_path.exists():
            image = Image.open(icon_path)
        else:
            # Créer une icône par défaut si pas trouvée
            image = Image.new('RGB', (64, 64), color='#2b825b')
        
        # Menu du tray
        menu = pystray.Menu(
            pystray.MenuItem("Afficher Soundbien", self._show_window, default=True),
            pystray.MenuItem("Vérifier mises à jour", self._check_updates_from_tray),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quitter", self._quit_app)
        )
        
        self.tray_icon = pystray.Icon("Soundbien", image, "Soundbien", menu)
        
        # Démarrer le tray dans un thread séparé
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def _hide_to_tray(self):
        """Cache la fenêtre dans la barre d'état système"""
        self.withdraw()
    
    def _on_minimize(self, event=None):
        """Appelé quand la fenêtre est minimisée"""
        # Vérifier que c'est bien une minimisation (pas juste un focus perdu)
        if self.state() == 'iconic':
            self._hide_to_tray()
    
    def _show_window(self, icon=None, item=None):
        """Restaure la fenêtre depuis le tray"""
        self.after(0, self._restore_window)
    
    def _restore_window(self):
        """Restaure et met au premier plan"""
        self.deiconify()
        self.lift()
        self.focus_force()
    
    def _quit_app(self, icon=None, item=None):
        """Quitte complètement l'application"""
        # Arrêter le tray proprement
        if self.tray_icon:
            self.tray_icon.stop()
        
        # Quitter proprement en évitant les callbacks Tkinter pendants
        try:
            self.quit()  # Arrête mainloop
        except:
            pass
        
        # Forcer la sortie
        import os
        os._exit(0)

    def _check_updates_from_tray(self, icon=None, item=None):
        """Vérifie les mises à jour depuis le menu tray"""
        def check():
            if self.updater.check_for_updates():
                info = self.updater.get_update_info()
                self.after(0, lambda: [self._show_window(), self._show_update_notification(info)])
            else:
                self.after(0, lambda: messagebox.showinfo("Mises à jour", f"Vous utilisez la dernière version (v{self.updater.current_version})"))
        
        threading.Thread(target=check, daemon=True).start()

    def _load_devices_async(self):
        """Charge les périphériques en background"""
        devices = self.sound_manager.get_devices()
        self.after(0, lambda: self._update_devices_ui(devices))

    def _update_devices_ui(self, devices):
        self.devices = devices
        self.device_names = [d['name'] for d in self.devices]
        self.combo_device.configure(values=self.device_names, state="normal")
        
        # Sélectionner le device actuel s'il existe
        current_id = self.sound_manager.current_device
        found = False
        if current_id is not None:
            for d in self.devices:
                if d['id'] == current_id:
                    self.combo_device.set(d['name'])
                    found = True
                    break
        
        if not found:
             self.combo_device.set("Choisir périphérique (ex: CABLE Input)")

    def change_device(self, choice):
        for d in self.devices:
            if d['name'] == choice:
                self.sound_manager.set_device(d['id'])
                print(f"Périphérique changé pour: {choice} (ID: {d['id']})")
                break

    def refresh_devices(self):
        self.combo_device.set("Actualisation...")
        self.combo_device.configure(state="disabled")
        threading.Thread(target=self._load_devices_async, daemon=True).start()

    def toggle_monitoring(self):
        enabled = self.switch_monitoring.get()
        self.sound_manager.set_monitoring(bool(enabled))
        # Sauvegarder la préférence
        self.sound_manager.save_config()

    def _update_stop_button_text(self):
        """Met à jour le texte du bouton STOP avec la touche assignée"""
        key = self.sound_manager.stop_key
        text = f"STOP TOUT [{key}]" if key else "STOP TOUT"
        self.btn_stop.configure(text=text)

    def show_stop_context_menu(self, event):
        """Menu contextuel pour le bouton STOP"""
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0, bg='#2b2b2b', fg='white',
                       activebackground='#1f6aa5', activeforeground='white',
                       font=('Segoe UI', 10))
        
        current_key = self.sound_manager.stop_key
        key_label = f" ({current_key})" if current_key else ""
        
        menu.add_command(label=f"⌨️ Assigner touche STOP{key_label}", command=self.assign_stop_key)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def assign_stop_key(self):
        """Dialogue pour assigner la touche STOP"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Assigner touche STOP")
        center_window(dialog, 400, 200, self)
        dialog.grab_set()
        
        lbl = ctk.CTkLabel(dialog, text="Appuyez sur une touche pour STOP\nou Echap pour annuler",
                          font=("Arial", 12))
        lbl.pack(pady=30)
        
        current_key = self.sound_manager.stop_key
        if current_key:
            lbl_current = ctk.CTkLabel(dialog, text=f"Touche actuelle: {current_key}",
                                      font=("Arial", 10), text_color="#888")
            lbl_current.pack(pady=5)
            
        def wait_for_key():
            import keyboard
            while keyboard.is_pressed('enter'): pass
            event = keyboard.read_event(suppress=True)
            if event.event_type == keyboard.KEY_DOWN:
                key = event.name
                if key == 'esc':
                    dialog.after(0, dialog.destroy)
                    return
                # Assigner
                self.sound_manager.set_stop_key(key)
                self.after(0, lambda: [dialog.destroy(), self._update_stop_button_text()])

        threading.Thread(target=wait_for_key, daemon=True).start()

    def on_vol_out_change(self, value):
        self.sound_manager.set_volume_output(value)

    def on_vol_mon_change(self, value):
        self.sound_manager.set_volume_monitoring(value)


    # Note: on_key_press supprimé car géré globablement par SoundManager


    def _open_trimmer_dialog(self, name, path):
        """Ouvre le dialogue de trimming de manière centralisée"""
        def on_trim_complete(trimmed_path):
            self.on_sound_added(name, trimmed_path)
        
        from audio_trimmer import AudioTrimDialog
        # Utiliser self comme parent
        trimmer = AudioTrimDialog(self, str(path), on_trim_complete)
        trimmer.grab_set()

    def open_file_import(self):
        """Ouvre un dialogue pour importer un fichier audio local"""
        filetypes = [
            ("Fichiers Audio", "*.mp3 *.wav *.ogg *.m4a *.flac"),
            ("Tous les fichiers", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Sélectionner un fichier audio",
            filetypes=filetypes
        )
        
        if filepath:
            # Utiliser le nom du fichier (sans extension) comme nom du son
            source = Path(filepath)
            name = source.stem  # Nom sans extension
            
            try:
                # Copier le fichier dans le dossier sounds
                dest = self.app_data_dir / "sounds" / f"{name.replace(' ', '_')}{source.suffix}"
                shutil.copy2(source, dest)
                
                # Ouvrir le trimmer
                self._open_trimmer_dialog(name, dest)
                
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible d'importer le fichier:\n{e}")
    
    def open_add_dialog(self):
        # Le callback sera appelé avec (name, path) une fois téléchargé
        dialog = AddSoundDialog(self, self._open_trimmer_dialog, self.downloader)
        dialog.grab_set()

    def _generate_tts_thread(self, text, name):
        # Si direct play, on utilise un nom temporaire ou fixe
        path = self.tts_generator.generate(text, name)
        
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
            # Afficher la touche assignée si existante
            key = self.sound_manager.get_sound_key(name)
            display_name = f"{name} [{key}]" if key else name
            
            btn = ctk.CTkButton(self.scrollable_frame, text=display_name, height=80, 
                                command=lambda n=name: self.sound_manager.play_sound(n))
            btn.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
            
            # Clic droit pour menu contextuel
            btn.bind("<Button-3>", lambda event, n=name, b=btn: self.show_sound_context_menu(event, n, b))

            col += 1
            if col > 3:
                col = 0
                row += 1
    
    def show_sound_context_menu(self, event, name, button):
        """Affiche le menu contextuel pour un son"""
        import tkinter as tk
        
        menu = tk.Menu(self, tearoff=0, bg='#2b2b2b', fg='white',
                       activebackground='#1f6aa5', activeforeground='white',
                       font=('Segoe UI', 10))
        
        # Afficher la touche actuelle si définie
        current_key = self.sound_manager.get_sound_key(name)
        key_label = f" ({current_key})" if current_key else ""
        
        menu.add_command(label=f"⌨️ Assigner une touche{key_label}", command=lambda: self.assign_keybind(name))
        menu.add_command(label="✏️ Renommer", command=lambda: self.rename_sound(name))
        menu.add_command(label="🗑️ Supprimer", command=lambda: self.delete_sound(name))
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def assign_keybind(self, sound_name):
        """Dialogue pour assigner une touche à un son"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Assigner une touche")
        center_window(dialog, 400, 200, self)
        dialog.grab_set()
        
        lbl = ctk.CTkLabel(dialog, text=f"Appuyez sur une touche pour '{sound_name}'\nou Echap pour annuler",
                          font=("Arial", 12))
        lbl.pack(pady=30)
        
        current_key = self.sound_manager.get_sound_key(sound_name)
        if current_key:
            lbl_current = ctk.CTkLabel(dialog, text=f"Touche actuelle: {current_key}",
                                      font=("Arial", 10), text_color="#888")
            lbl_current.pack(pady=5)
        
        def wait_for_key():
            import keyboard
            # Attendre qu'une touche soit relâchée pour éviter capture immédiate
            while keyboard.is_pressed('enter'):
                pass
                
            event = keyboard.read_event(suppress=True)
            if event.event_type == keyboard.KEY_DOWN:
                key = event.name
                
                if key == 'esc':
                    dialog.after(0, dialog.destroy)
                    return
                
                # Assigner la touche
                self.sound_manager.set_keybind(key, sound_name)
                # Revenir thread UI pour fermer
                self.after(0, lambda: [dialog.destroy(), self.refresh_sounds()])

        # Lancer l'écoute dans un thread pour ne pas bloquer l'UI
        threading.Thread(target=wait_for_key, daemon=True).start()
        # dialog.focus_set() # Plus besoin de focus widget
    
    def rename_sound(self, old_name):
        """Renomme un son"""
        new_name = simpledialog.askstring(
            "Renommer", 
            f"Nouveau nom pour '{old_name}':",
            initialvalue=old_name,
            parent=self
        )
        
        if new_name and new_name != old_name:
            # Vérifier que le nouveau nom n'existe pas déjà
            if new_name in self.sound_manager.sounds:
                messagebox.showerror("Erreur", f"Un son nommé '{new_name}' existe déjà")
                return
            
            # Renommer dans le dictionnaire
            path = self.sound_manager.sounds[old_name]
            del self.sound_manager.sounds[old_name]
            self.sound_manager.sounds[new_name] = path
            self.sound_manager.save_config()
            
            # Rafraîchir l'affichage
            self.refresh_sounds()

    def delete_sound(self, name):
        if messagebox.askyesno("Supprimer", f"Voulez-vous supprimer le son '{name}' ?"):
            self.sound_manager.remove_sound(name)
            self.refresh_sounds()

    def _check_updates(self):
        """Vérifie les mises à jour en arrière-plan"""
        try:
            if self.updater.check_for_updates():
                info = self.updater.get_update_info()
                self.after(0, lambda: self._show_update_notification(info))
        except Exception as e:
            print(f"Erreur lors de la vérification des MAJ: {e}")
    
    def _show_update_notification(self, info):
        """Affiche la dialogue de mise à jour"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Mise à jour disponible")
        center_window(dialog, 400, 250, self)
        dialog.grab_set()
        
        # Info
        ctk.CTkLabel(dialog, text="Une nouvelle version est disponible !", 
                     font=("Arial", 16, "bold"), text_color="#4CAF50").pack(pady=(20, 10))
        
        ctk.CTkLabel(dialog, text=f"Version actuelle : v{info['current']}", text_color="gray").pack()
        ctk.CTkLabel(dialog, text=f"Nouvelle version : v{info['latest']}", font=("Arial", 14)).pack(pady=5)
        
        status_label = ctk.CTkLabel(dialog, text="Voulez-vous l'installer maintenant ?", text_color="gray")
        status_label.pack(pady=10)
        
        progress_bar = ctk.CTkProgressBar(dialog, width=300)
        progress_bar.set(0)
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        def start_update():
            btn_install.configure(state="disabled")
            btn_ignore.configure(state="disabled")
            progress_bar.pack(pady=5) # Afficher la barre
            status_label.configure(text="Téléchargement en cours...")
            
            def update_progress(percent):
                progress_bar.set(percent / 100)
                status_label.configure(text=f"Téléchargement... {percent}%")
                
            def run_download():
                success = self.updater.download_update(progress_callback=update_progress)
                if success:
                    self.after(0, lambda: status_label.configure(text="Lancement de l'installation..."))
                    self.after(1000, lambda: self.updater.start_installer())
                else:
                    self.after(0, lambda: [
                        status_label.configure(text="Erreur de téléchargement."),
                        btn_install.configure(state="normal"),
                        btn_ignore.configure(state="normal")
                    ])

            threading.Thread(target=run_download, daemon=True).start()

        btn_install = ctk.CTkButton(btn_frame, text="Installer maintenant", fg_color="#4CAF50", hover_color="#388E3C", command=start_update)
        btn_install.pack(side="left", padx=10)
        
        btn_ignore = ctk.CTkButton(btn_frame, text="Ignorer", fg_color="transparent", border_width=1, command=dialog.destroy)
        btn_ignore.pack(side="left", padx=10)

    def _show_changelog_dialog(self):
        """Affiche le changelog après une mise à jour"""
        # Récupérer le changelog en background
        def fetch_and_show():
            changelog = self.updater.get_changelog_for_version()
            if changelog:
                self.after(0, lambda: self._display_changelog(changelog))
            else:
                # Pas de changelog trouvé, marquer comme vu quand même
                self.updater.mark_version_seen()
        
        threading.Thread(target=fetch_and_show, daemon=True).start()
    
    def _display_changelog(self, changelog):
        """Affiche la fenêtre de changelog"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Quoi de neuf ? - v{changelog['version']}")
        center_window(dialog, 500, 400, self)
        dialog.grab_set()
        
        # Header
        header_frame = ctk.CTkFrame(dialog, fg_color="#2b825b", corner_radius=0)
        header_frame.pack(fill="x")
        
        ctk.CTkLabel(header_frame, text="🎉 Mise à jour installée !", 
                     font=("Arial", 18, "bold"), text_color="white").pack(pady=10)
        ctk.CTkLabel(header_frame, text=f"Version {changelog['version']}", 
                     font=("Arial", 12), text_color="#ccffcc").pack(pady=(0, 10))
        
        # Changelog content (scrollable)
        content_frame = ctk.CTkScrollableFrame(dialog, label_text="Notes de version")
        content_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Formater le changelog (markdown simplifié)
        changelog_text = changelog['body'] or "Aucune note de version disponible."
        
        # Afficher le texte ligne par ligne pour un meilleur rendu
        ctk.CTkLabel(content_frame, text=changelog_text, 
                     font=("Consolas", 11), justify="left", 
                     wraplength=440, anchor="w").pack(anchor="w", pady=5)
        
        # Bouton fermer
        def on_close():
            self.updater.mark_version_seen()
            dialog.destroy()
        
        btn_close = ctk.CTkButton(dialog, text="C'est noté !", 
                                  fg_color="#2b825b", hover_color="#1f5d42",
                                  command=on_close, height=40)
        btn_close.pack(pady=15)
        
        # Fermer avec Escape
        dialog.bind("<Escape>", lambda e: on_close())

if __name__ == "__main__":
    app = SoundBoardApp()
    app.mainloop()
