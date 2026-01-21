import threading
import json
import os
import keyboard


class SoundManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.sounds = {}
        self.current_device = None
        self.monitoring = False
        
        # Volumes (0.0 à 1.0)
        self.vol_output = 1.0
        self.vol_monitoring = 1.0
        
        # Playback state
        self.current_play_id = 0
        self.lock = threading.Lock()
        self.fade_out = False  # Flag pour fade out progressif
        
        # Keybinds (touche -> nom du son)
        self.keybinds = {}  # Ex: {'f1': 'mon_son', '1': 'autre_son'}
        self.stop_key = None  # Touche pour arrêter tout
        
        self.playing_thread = None
        self.stop_event = threading.Event()
        
        # Charger la config (APRÈS l'initialisation des variables)
        self.load_config()
        
        # Démarrer le listener global
        self._start_global_listener()

    def _start_global_listener(self):
        """Démarre l'écoute globale du clavier"""
        try:
            keyboard.hook(self._on_global_key)
        except Exception as e:
            print(f"Erreur init clavier global: {e}")

    def _on_global_key(self, event):
        """Callback appelé à chaque événement clavier global"""
        if event.event_type == keyboard.KEY_DOWN:
            key = event.name
            
            # Stop ?
            if self.stop_key and key == self.stop_key:
                self.stop_sound()
                return

            # Sound ?
            if key in self.keybinds:
                sound_name = self.keybinds[key]
                if sound_name in self.sounds:
                    self.play_sound(sound_name)

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.sounds = data.get('sounds', {})
                    self.current_device = data.get('device_id', None)
                    self.monitoring = data.get('monitoring', False)
                    self.vol_output = data.get('vol_output', 1.0)
                    self.vol_monitoring = data.get('vol_monitoring', 1.0)
                    self.keybinds = data.get('keybinds', {})
                    self.stop_key = data.get('stop_key', None)
            except Exception as e:
                print(f"Erreur chargement config: {e}")
                self.sounds = {}

    def save_config(self):
        data = {
            'sounds': self.sounds,
            'device_id': self.current_device,
            'monitoring': self.monitoring,
            'vol_output': self.vol_output,
            'vol_monitoring': self.vol_monitoring,
            'keybinds': self.keybinds,
            'stop_key': self.stop_key
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)

    def set_volume_output(self, vol):
        """Définit le volume de sortie (0.0 à 1.0)"""
        self.vol_output = max(0.0, min(1.0, float(vol)))
        self.save_config()
        
    def set_volume_monitoring(self, vol):
        """Définit le volume de monitoring (0.0 à 1.0)"""
        self.vol_monitoring = max(0.0, min(1.0, float(vol)))
        self.save_config()

    def get_devices(self):
        """Retourne la liste des périphériques de sortie disponibles (MME uniquement pour éviter doublons)."""
        import sounddevice as sd
        try:
            devices = sd.query_devices()
            output_devices = []
            seen_names = set()
            for i, device in enumerate(devices):
                # Filtrer pour ne garder que MME (hostapi=0) et les sorties
                if device['max_output_channels'] > 0 and device['hostapi'] == 0:
                    name = device['name']
                    if name not in seen_names:
                        output_devices.append({'id': i, 'name': name})
                        seen_names.add(name)
            return output_devices
        except Exception as e:
            print(f"Erreur get_devices: {e}")
            return []

    def set_device(self, device_id):
        """Définit le périphérique de sortie actif."""
        self.current_device = device_id
        self.save_config()

    def add_sound(self, name, path):
        """Ajoute un son à la bibliothèque"""
        self.sounds[name] = path
        self.save_config()

    def remove_sound(self, name):
        """Supprime un son de la bibliothèque"""
        if name in self.sounds:
            # Nettoyer le keybind si existant
            for key, sound_name in list(self.keybinds.items()):
                if sound_name == name:
                    del self.keybinds[key]
            del self.sounds[name]
            self.save_config()
    
    def set_keybind(self, key, sound_name):
        """Assigne une touche à un son"""
        # 1. Nettoyer l'ancien keybind pour ce son (un son = une touche max)
        for k, v in list(self.keybinds.items()):
            if v == sound_name:
                del self.keybinds[k]
                
        # 2. Supprimer l'ancien binding de la NOUVELLE touche si elle était prise
        if key in self.keybinds:
            del self.keybinds[key]
            
        # 3. Assigner
        if sound_name:  # Si None, on supprime juste (déjà fait étape 1)
            self.keybinds[key] = sound_name
            
        self.save_config()
    
    def get_sound_key(self, sound_name):
        """Retourne la touche assignée à un son (ou None)"""
        for key, name in self.keybinds.items():
            if name == sound_name:
                return key
        return None
    
    def set_stop_key(self, key):
        """Définit la touche pour arrêter"""
        self.stop_key = key
        self.save_config()
    

    def play_sound(self, name):
        if name not in self.sounds:
            print(f"Son '{name}' introuvable.")
            return

        path = self.sounds[name]
        self.play_file(path)

    def play_file(self, path):
        if not os.path.exists(path):
            print(f"Fichier '{path}' introuvable.")
            return

        # Play ID system: Incrémenter l'ID pour invalider les anciens threads
        with self.lock:
            self.current_play_id += 1
            play_id = self.current_play_id
        
        # Reset stop event pour autoriser la lecture
        self.stop_event.clear()
        
        # Pas de .join() ici -> Non bloquant pour le spam !
        self.playing_thread = threading.Thread(target=self._play_thread, args=(path, play_id))
        self.playing_thread.start()

    def set_monitoring(self, enabled):
        """Active ou désactive le monitoring (écouter le son joué)."""
        self.monitoring = enabled
        self.save_config()

    def _play_thread(self, path, play_id):
        """Thread de lecture audio avec miniaudio streaming (ultra-rapide, RAM minimale)"""
        self.fade_out = False
        
        try:
            import miniaudio
            import sounddevice as sd
            import numpy as np
            
            # Décoder le fichier avec miniaudio (beaucoup plus rapide que pydub/soundfile)
            decoded = miniaudio.decode_file(path)
            samples = np.frombuffer(decoded.samples, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Copie contiguë pour éviter les artefacts de buffer
            samples = np.ascontiguousarray(samples)
            
            # Reshape pour multi-canaux
            if decoded.nchannels > 1:
                samples = samples.reshape((-1, decoded.nchannels))
            
            # Fade-in de 10ms pour éliminer le "pop" au démarrage
            fade_in_samples = min(int(decoded.sample_rate * 0.01), len(samples))
            fade_in_curve = np.linspace(0, 1, fade_in_samples).astype(np.float32)
            if decoded.nchannels > 1:
                fade_in_curve = fade_in_curve.reshape(-1, 1)
            samples[:fade_in_samples] *= fade_in_curve
            
            fs = decoded.sample_rate
            channels = decoded.nchannels
            
            # Périphérique principal (ex: Cable)
            device_out = self.current_device if self.current_device is not None else sd.default.device[1]
            # Périphérique de monitoring (ex: Casque)
            device_mon = sd.default.device[1]
            
            streams = []
            main_stream = None
            mon_stream = None

            try:
                # Création des streams
                try:
                    main_stream = sd.OutputStream(samplerate=fs, device=device_out, channels=channels)
                    main_stream.start()
                    streams.append(main_stream)
                except Exception as e:
                    print(f"Erreur main stream: {e}")

                if device_out != device_mon:
                    try:
                        mon_stream = sd.OutputStream(samplerate=fs, device=device_mon, channels=channels)
                        mon_stream.start()
                        streams.append(mon_stream)
                    except Exception as e:
                        print(f"Erreur mon stream: {e}")

                # Écriture par blocs
                block_size = 1024
                position = 0
                
                # Boucle de lecture optimisée
                fade_factor = 1.0
                while position < len(samples):
                    # Check rapide si on doit arrêter (spam ou stop button)
                    stopping = self.stop_event.is_set() or self.current_play_id != play_id
                    
                    if stopping:
                        if self.fade_out:
                            fade_factor = max(0, fade_factor - 0.10)
                        else:
                            fade_factor = 0
                        
                    end = min(position + block_size, len(samples))
                    chunk = samples[position:end]
                    
                    # Écriture Main
                    if main_stream:
                        main_stream.write(chunk * self.vol_output * fade_factor)
                    
                    # Écriture Monitoring
                    if mon_stream:
                        if self.monitoring:
                            mon_stream.write(chunk * self.vol_monitoring * fade_factor)
                        else:
                            mon_stream.write(chunk * 0)
                            
                    # Si on est en arrêt et qu'on a atteint le silence, on coupe
                    if stopping and fade_factor == 0:
                        sd.sleep(10)
                        break
                    
                    position = end


            finally:
                for s in streams:
                    s.stop()
                    s.close()
                    
        except Exception as e:
            print(f"Erreur lecture audio: {e}")

    def stop_sound(self):
        """Arrête avec un fade out doux"""
        self.fade_out = True
        self.stop_event.set()
        # Invalider aussi l'ID courant pour être sûr
        with self.lock:
            self.current_play_id += 1
