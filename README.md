# Soundboard Alpaca 🦙🔊

Une Soundboard moderne pour Windows développée en Python. Elle permet de jouer des sons vers un périphérique virtuel (comme VB-Cable) tout en les écoutant via un périphérique de monitoring (votre casque).

Elle intègre également un téléchargeur YouTube et un générateur de voix (TTS).

## ✨ Fonctionnalités

- **Lecture de sons** : Interface graphique simple pour lancer vos sons.
- **Support Multi-Périphériques** : 
  - **Sortie Principale** : Envoyez le son vers un câble virtuel (pour Discord, OBS, etc.).
  - **Monitoring** : Écoutez ce que vous jouez dans votre propre casque.
- **Téléchargement YouTube** : Ajoutez facilement des sons depuis une URL YouTube.
- **Text-to-Speech (TTS)** : Générez et jouez des phrases à la volée.
- **Persistance** : Vos configuration et votre liste de sons sont sauvegardées automatiquement (`config.json`).
- **Thème Sombre** : Interface utilisateur agréable (via `customtkinter`).

## 🛠️ Pré-requis

- **Python 3.8+**
- **FFmpeg** : Nécessaire pour le traitement audio (téléchargement et conversion).
  - Téléchargez-le depuis [ffmpeg.org](https://ffmpeg.org/download.html).
  - Ajoutez-le à votre PATH système ou placez `ffmpeg.exe` dans le dossier du projet.

## 📦 Installation

### Option 1 : Exécutable (Recommandé)
Téléchargez simplement la dernière version (`.exe`) depuis la page des releases :
👉 **[Dernière Release](https://github.com/Alpaca-exe/soundbien/releases/latest)**

### Option 2 : Depuis les sources (Pour les développeurs)

1. Clonez ce dépôt ou téléchargez les fichiers.
2. Ouvrez un terminal dans le dossier du projet.
3. Installez les dépendances :

```bash
pip install -r requirements.txt
```

## 🚀 Utilisation

Lancez l'application avec :

```bash
python main.py
```

### Configuration Audio
1. **Sortie Audio (Menu déroulant)** : Choisissez le périphérique où le son doit être envoyé (ex: "CABLE Input"). C'est ce que vos amis/viewers entendront.
2. **Monitoring (Switch)** : Activez-le pour entendre également les sons dans votre périphérique par défaut (votre casque/haut-parleurs).

### Ajouter un son (YouTube)
1. Cliquez sur `+ Ajouter Youtube`.
2. Collez l'URL de la vidéo.
3. Donnez un nom au son.
4. Cliquez sur `Télécharger`. Le son sera converti et ajouté à votre liste.

### Text-to-Speech (TTS)
1. En bas de la fenêtre, tapez votre texte dans la zone "Texte à dire...".
2. Cliquez sur `▶ Jouer Direct`.
3. Le son est généré et joué immédiatement.

## 📂 Structure du projet

- `main.py` : Point d'entrée et interface graphique.
- `sound_manager.py` : Gestion de la lecture audio et des périphériques.
- `downloader.py` : Logique de téléchargement YouTube (via `yt-dlp`).
- `tts_generator.py` : Logique de génération de voix (via `gTTS`).
- `sounds/` : Dossier contenant vos fichiers `.mp3`.
- `config.json` : Sauvegarde de vos paramètres et liste de sons.

---
*Créé avec ❤️ par l'équipe Alpaca.*
