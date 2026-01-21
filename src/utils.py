def center_window(window, width, height, parent=None):
    """
    Centre la fenêtre sur son parent ou sur l'écran.
    :param window: L'instance de la fenêtre (CTk, Toplevel, etc.)
    :param width: Largeur souhaitée
    :param height: Hauteur souhaitée
    :param parent: La fenêtre parente (si None, centre sur l'écran)
    """
    # Mettre à jour les tâches en attente pour avoir les bonnes coordonnés du parent
    if parent:
        parent.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
    else:
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        
    # S'assurer que x et y ne sont pas négatifs (hors écran en haut/gauche)
    x = max(0, x)
    y = max(0, y)
    
    window.geometry(f"{width}x{height}+{int(x)}+{int(y)}")
