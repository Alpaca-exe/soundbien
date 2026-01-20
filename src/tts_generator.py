from gtts import gTTS
import os

class TTSGenerator:
    def __init__(self, output_dir="sounds"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate(self, text, name, lang='fr'):
        """
        Génère un fichier mp3 à partir du texte donné.
        Retourne le chemin du fichier généré ou None en cas d'erreur.
        """
        try:
            filename = name.replace(" ", "_") + ".mp3"
            filepath = os.path.join(self.output_dir, filename)
            
            tts = gTTS(text=text, lang=lang)
            tts.save(filepath)
            
            return filepath
        except Exception as e:
            print(f"Erreur TTS: {e}")
            return None
