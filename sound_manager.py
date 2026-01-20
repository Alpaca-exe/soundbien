import sounddevice as sd
import soundfile as sf
import threading
import json
import os

class SoundManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.sounds = {}
        self.current_device = None
        self.load_config()
        self.playing_thread = None
        self.playing_thread = None
        self.stop_event = threading.Event()
        self.monitoring = False

    def get_devices(self):
        """Retourne la liste des périphériques de sortie disponibles (MME uniquement pour éviter doublons)."""
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

    def set_device(self, device_id):
        """Définit le périphérique de sortie actif."""
        self.current_device = device_id
        self.save_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.sounds = data.get('sounds', {})
                    self.current_device = data.get('device_id', None)
                    self.monitoring = data.get('monitoring', False)
            except Exception as e:
                print(f"Erreur chargement config: {e}")
                self.sounds = {}

    def save_config(self):
        data = {
            'sounds': self.sounds,
            'device_id': self.current_device,
            'monitoring': self.monitoring
        }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)

    def add_sound(self, name, path):
        self.sounds[name] = path
        self.save_config()

    def remove_sound(self, name):
        if name in self.sounds:
            del self.sounds[name]
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

        # Arrêter le son précédent si nécessaire
        self.stop_sound()
        
        self.stop_event.clear()
        self.playing_thread = threading.Thread(target=self._play_thread, args=(path,))
        self.playing_thread.start()

    def set_monitoring(self, enabled):
        """Active ou désactive le monitoring (écouter le son joué)."""
        self.monitoring = enabled

    def _play_thread(self, path):
        try:
            data, fs = sf.read(path, dtype='float32')
            
            # Périphérique principal (ex: Cable)
            device_out = self.current_device if self.current_device is not None else sd.default.device[1]
            # Périphérique de monitoring (ex: Casque)
            device_mon = sd.default.device[1]
            
            # Liste des streams actifs
            streams = []
            main_stream = None
            mon_stream = None

            try:
                # 1. Stream Principal
                try:
                    main_stream = sd.OutputStream(samplerate=fs, device=device_out, channels=data.shape[1] if len(data.shape) > 1 else 1)
                    main_stream.start()
                    streams.append(main_stream)
                except Exception as e:
                    print(f"Erreur main stream: {e}")

                # 2. Stream Monitoring (Toujours le créer si différent du main, pour permettre le toggle)
                # On vérifie si c'est le même device par ID ou Nom, pour éviter l'écho doublé si Main == Default
                # (Simplification: comparer les IDs si disponibles, mais ici on assume que l'utilisateur a choisi CABLE donc différent)
                if device_out != device_mon:
                    try:
                        mon_stream = sd.OutputStream(samplerate=fs, device=device_mon, channels=data.shape[1] if len(data.shape) > 1 else 1)
                        mon_stream.start()
                        streams.append(mon_stream)
                    except Exception as e:
                        print(f"Erreur mon stream: {e}")

                # Écriture par blocs
                block_size = 1024
                position = 0
                
                # Zéros pré-calculés pour l'efficacité (une seule allocation si possible, mais taille variable dernier bloc)
                # On fera data[pos:end] * 0
                
                while position < len(data) and not self.stop_event.is_set():
                    end = min(position + block_size, len(data))
                    chunk = data[position:end]
                    
                    # Écriture Main
                    if main_stream:
                        main_stream.write(chunk)
                    
                    # Écriture Monitoring
                    if mon_stream:
                        if self.monitoring:
                            mon_stream.write(chunk)
                        else:
                            # Silence (garder la synchro)
                            mon_stream.write(chunk * 0)
                    
                    position = end

            finally:
                for s in streams:
                    s.stop()
                    s.close()
                    
        except Exception as e:
            print(f"Erreur lecture audio: {e}")

    def stop_sound(self):
        if self.playing_thread and self.playing_thread.is_alive():
            self.stop_event.set()
            self.playing_thread.join()
