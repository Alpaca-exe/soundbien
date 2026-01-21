import tkinter as tk
from tkinter import font as tkfont

class VolumeSlider(tk.Frame):
    """Slider de volume custom sans bug de décalage"""
    
    def __init__(self, parent, initial_value=1.0, callback=None, **kwargs):
        super().__init__(parent, bg='#2b2b2b', **kwargs)
        self.callback = callback
        self.value = max(0.0, min(1.0, initial_value))
        self.dragging = False
        
        # Canvas pour dessiner le slider (plus grand pour meilleure qualité)
        self.canvas = tk.Canvas(self, width=160, height=40, bg='#2b2b2b', 
                                highlightthickness=0, cursor='hand2')
        self.canvas.pack(padx=2, pady=2)
        
        # Bindings
        self.canvas.bind('<Button-1>', self.on_click)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        
        self.draw()
    
    def on_click(self, event):
        self.dragging = True
        self.update_value(event.x)
    
    def on_drag(self, event):
        if self.dragging:
            self.update_value(event.x)
    
    def on_release(self, event):
        self.dragging = False
    
    def update_value(self, x):
        # Calculer la valeur basée sur x (avec marges)
        margin = 8
        usable_width = 160 - 2 * margin
        x_clamped = max(margin, min(160 - margin, x))
        
        self.value = (x_clamped - margin) / usable_width
        self.value = max(0.0, min(1.0, self.value))
        
        self.draw()
        
        if self.callback:
            self.callback(self.value)
    
    def set(self, value):
        """Définir la valeur programmatiquement"""
        self.value = max(0.0, min(1.0, value))
        self.draw()
    
    def get(self):
        """Obtenir la valeur actuelle"""
        return self.value
    
    def draw(self):
        self.canvas.delete('all')
        
        # Dimensions
        margin = 8
        track_height = 4
        thumb_size = 16
        track_y = 18
        
        # Track background (fond gris foncé)
        self.canvas.create_rectangle(
            margin, track_y - track_height//2,
            160 - margin, track_y + track_height//2,
            fill='#3b3b3b', outline='#505050', width=1,
            tags='track'
        )
        
        # Fill (partie remplie - bleu CustomTkinter)
        fill_width = self.value * (160 - 2*margin)
        if fill_width > 1:
            self.canvas.create_rectangle(
                margin, track_y - track_height//2,
                margin + fill_width, track_y + track_height//2,
                fill='#1f6aa5', outline='',
                tags='fill'
            )
        
        # Thumb (bouton) - avec ombre pour effet 3D
        thumb_x = margin + self.value * (160 - 2*margin)
        
        # Ombre du thumb
        self.canvas.create_oval(
            thumb_x - thumb_size//2 + 1, track_y - thumb_size//2 + 1,
            thumb_x + thumb_size//2 + 1, track_y + thumb_size//2 + 1,
            fill='#1a1a1a', outline='',
            tags='shadow'
        )
        
        # Thumb principal
        self.canvas.create_oval(
            thumb_x - thumb_size//2, track_y - thumb_size//2,
            thumb_x + thumb_size//2, track_y + thumb_size//2,
            fill='#3a7ebf', outline='#ffffff', width=2,
            tags='thumb'
        )
        
        # Texte pourcentage (plus bas pour ne pas couper)
        percent_text = f"{int(self.value * 100)}%"
        self.canvas.create_text(
            80, 33, text=percent_text,
            fill='#999999', font=('Segoe UI', 9, 'bold'),
            tags='label'
        )

