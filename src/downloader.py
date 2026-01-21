import os


class Downloader:
    def __init__(self, download_path="sounds"):
        self.download_path = download_path
        if not os.path.exists(self.download_path):
            os.makedirs(self.download_path)

    def download_sound(self, url, filename=None):
        """
        Télécharge l'audio d'une vidéo YouTube et le convertit en mp3.
        Retourne un tuple (path, title) ou (None, None) en cas d'erreur.
        """
        import yt_dlp
        import re
        
        try:
            # D'abord, extraire les infos pour avoir le titre
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Sans_titre')
                # Nettoyer le titre pour en faire un nom de fichier valide
                clean_title = re.sub(r'[\\/*?:"<>|]', '', title)
                clean_title = clean_title.replace(' ', '_')[:50]  # Limiter à 50 caractères
            
            # Utiliser le titre comme nom de fichier si non fourni
            if filename is None:
                filename = clean_title
            
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
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            return (os.path.join(self.download_path, f"{filename}.mp3"), title)
        
        except Exception as e:
            print(f"Erreur lors du téléchargement : {e}")
            return (None, None)
        except Exception as e:
            print(f"Erreur lors du téléchargement : {e}")
            return None
