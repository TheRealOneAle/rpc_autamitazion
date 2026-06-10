import hashlib
import requests
from bs4 import BeautifulSoup

BASE = "https://redprogramacioncompetitiva.com/contests/2025/10"
SALT = "kbjmohlr4o7tbvmnbp8qdihs0k"

def js_myhash(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

session = requests.Session()
session.get(f"{BASE}/index.php", params={
    "name": "board",
    "password": js_myhash(js_myhash("") + SALT)
})

score = session.get(f"{BASE}/score/index.php")
soup = BeautifulSoup(score.text, "html.parser")

tabla = soup.find("table", {"id": "myscoretable"})
filas = tabla.find_all("tr")

encabezado = None
equipos = {}  # nombre -> datos

for fila in filas:
    ths = fila.find_all("th")
    if ths:
        encabezado = [th.get_text(strip=True) for th in ths]
        encabezado.insert(3, "Country")  # insertar columna país
        continue

    celdas = fila.find_all("td")
    if not celdas:
        continue

    pos        = celdas[0].get_text(strip=True)
    # extraer país del alt de la bandera
    flag_img   = celdas[1].find("img")
    pais       = flag_img["alt"] if flag_img else ""
    nombre     = celdas[1].get_text(strip=True)
    universidad = celdas[2].get_text(strip=True)
    problemas  = [td.get_text(strip=True) for td in celdas[3:]]

    if nombre in equipos:
        continue

    equipos[nombre] = [pos, nombre, universidad, pais] + problemas

# Imprimir tabla
todas = list(equipos.values())
col_widths = [max(len(str(f[i])) for f in todas) for i in range(len(encabezado))]
col_widths = [max(col_widths[i], len(encabezado[i])) for i in range(len(encabezado))]

header = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(encabezado))
print(header)
print("-" * len(header))

for fila in todas:
    print(" | ".join(str(fila[i]).ljust(col_widths[i]) for i in range(len(fila))))