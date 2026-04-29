import psycopg2
from PIL import Image, ImageDraw, ImageChops

# 🔹 Conexión
conn = psycopg2.connect(
    host="localhost",
    database="bkboca",
    user="postgres",
    password="1234"
)

cur = conn.cursor()

problemCol = """ select problemnumber, problemcolor from problemtable 
where problemnumber != 0; """

cur.execute(problemCol)

colores = cur.fetchall()

cur.close()
conn.close()


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
