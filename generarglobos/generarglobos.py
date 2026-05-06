import requests
import os
from PIL import Image, ImageDraw, ImageChops

# 🔹 URL del servicio bd
BD_SERVICE_URL = os.environ.get("BD_SERVICE_URL", "http://bd:3001")

def generar_globos():
    """Función principal que genera los globos. Retorna (success, message)"""
    # 🔹 Obtener problemas y colores desde el servicio bd
    try:
        response = requests.get(f"{BD_SERVICE_URL}/api/problems", timeout=10)
        if response.status_code != 200:
            return False, f"Error obteniendo problemas: {response.text}"
        
        data = response.json()
        if not data.get("success"):
            return False, f"Error en la respuesta: {data.get('error')}"
        
        colores = [(row["problemnumber"], row["problemcolor"]) for row in data["rows"]]
        print(f"Obtenidos {len(colores)} problemas desde el servicio bd")
    except Exception as e:
        return False, f"Error de conexión al servicio bd: {e}"

    def generar_globo(nombre_globo, color_hex):
        # 🔹 cargar imágenes
        relleno = Image.open("bigballoon.png").convert("RGBA")
        contorno = Image.open("bigballoontransp.png").convert("RGBA")

        color_hex = color_hex.replace("#", "")
        r = int(color_hex[0:2], 16)
        g = int(color_hex[2:4], 16)
        b = int(color_hex[4:6], 16)

        # 🔹 crear color sólido
        color_img = Image.new("RGBA", relleno.size, (r, g, b, 255))

        # 🔹 usar alpha del relleno como máscara
        alpha = relleno.split()[3]
        color_img.putalpha(alpha)

        # 🔹 superponer contorno ENCIMA
        result = color_img.copy()
        result.alpha_composite(contorno)
        result.alpha_composite(contorno, (-1,0))
        result.alpha_composite(contorno, (1,0))
        result.alpha_composite(contorno, (0,-1))
        result.alpha_composite(contorno, (0,1))

        result.save("globosgenerados/" + nombre_globo)

    for problemnumber, color in colores:
        nombre_globo = chr(64 + problemnumber) + ".png"
        generar_globo(nombre_globo, color)
    
    return True, "Globos generados exitosamente"

if __name__ == "__main__":
    # Modo standalone (para pruebas)
    success, msg = generar_globos()
    if success:
        print(msg)
    else:
        print(f"Error: {msg}")
        exit(1)
