import requests
import webbrowser
import os
import sys
from packaging import version

# Get version from __init__.py
sys.path.insert(0, os.path.dirname(__file__))
import __init__ as src_init
__version__ = src_init.__version__

class Updater:
    """Vérifie les mises à jour sur GitHub"""
    
    GITHUB_REPO = "Alpaca-exe/soundbien"
    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    
    def __init__(self):
        self.current_version = __version__
        self.latest_version = None
        self.download_url = None
        self.release_url = None
    
    def check_for_updates(self):
        """
        Vérifie si une nouvelle version est disponible sur GitHub.
        Retourne True si une mise à jour est disponible, False sinon.
        """
        try:
            response = requests.get(self.GITHUB_API_URL, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            self.latest_version = data['tag_name'].lstrip('v')
            self.release_url = data['html_url']
            
            # Trouver l'installateur dans les assets
            for asset in data.get('assets', []):
                if asset['name'].endswith('-setup.exe'):
                    self.download_url = asset['browser_download_url']
                    break
            
            # Comparer les versions
            if version.parse(self.latest_version) > version.parse(self.current_version):
                return True
            return False
            
        except Exception as e:
            print(f"Erreur lors de la vérification des mises à jour: {e}")
            return False
    
    def open_release_page(self):
        """Ouvre la page de la release dans le navigateur"""
        if self.release_url:
            webbrowser.open(self.release_url)
    
    def get_update_info(self):
        """Retourne les informations de mise à jour"""
        return {
            'current': self.current_version,
            'latest': self.latest_version,
            'url': self.release_url,
            'download': self.download_url
        }
