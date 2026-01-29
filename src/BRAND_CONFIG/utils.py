def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def calculate_text_contrast(hex_color: str) -> str:
    """
    Determina si el texto sobre este color debe ser blanco o negro.
    Retorna '#FFFFFF' si el fondo es oscuro, '#1A1A1A' si es claro.
    """
    if not hex_color:
        return '#1A1A1A' # Default
        
    try:
        r, g, b = hex_to_rgb(hex_color)
        # Formula de luminosidad relativa estándar (o aproximación simple)
        # Image prompt suggestions:
        luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
        
        # Umbral 128
        if luma < 128:
            return '#FFFFFF'
        else:
            return '#1A1A1A'
    except Exception:
        return '#1A1A1A'
