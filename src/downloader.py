import os
import yt_dlp

class Downloader:
    def __init__(self, download_path="sounds"):
        self.download_path = download_path
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def download_sound(self, url, filename):
        """
        Télécharge l'audio d'une vidéo YouTube et le convertit en mp3.
        """
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': os.path.join(self.download_path, f'{filename}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return os.path.join(self.download_path, f"{filename}.mp3")
        except Exception as e:
            print(f"Erreur lors du téléchargement : {e}")
            return None
