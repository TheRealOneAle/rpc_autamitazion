import os
import re
import requests
from PIL import Image

# 🔹 URL del servicio bd
BD_SERVICE_URL = os.environ.get("BD_SERVICE_URL", "http://boca-scraper:3001")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBOS_DIR = os.path.join(BASE_DIR, "globosgenerados")


def _normalize_hex(color_hex):
    if not color_hex:
        return "CCCCCC"
    color_hex = str(color_hex).lstrip("#").strip()
    if len(color_hex) == 3:
        return f"{color_hex[0]*2}{color_hex[1]*2}{color_hex[2]*2}".upper()
    if len(color_hex) == 6:
        return color_hex.upper()
    return "CCCCCC"


def _fetch_from_db():
    """Consulta directa opcional a PostgreSQL de BOCA (problemtable) si está configurado."""
    db_host = os.environ.get("BOCA_DB_HOST")
    if not db_host:
        return None
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=db_host,
            port=int(os.environ.get("BOCA_DB_PORT", "5432")),
            dbname=os.environ.get("BOCA_DB_NAME", "bkboca"),
            user=os.environ.get("BOCA_DB_USER", "postgres"),
            password=os.environ.get("BOCA_DB_PASS", "1234"),
            connect_timeout=5,
        )
        try:
            with conn.cursor() as cur:
                contest_num = os.environ.get("BOCA_CONTEST_NUMBER")
                if contest_num:
                    cur.execute(
                        "SELECT problemnumber, problemname, problemcolor, problemcolorname "
                        "FROM problemtable WHERE contestnumber = %s ORDER BY problemnumber ASC",
                        (contest_num,)
                    )
                else:
                    cur.execute(
                        "SELECT problemnumber, problemname, problemcolor, problemcolorname "
                        "FROM problemtable ORDER BY problemnumber ASC"
                    )
                rows = cur.fetchall()
                colores = []
                for r in rows:
                    p_num = int(r[0])
                    p_name = (r[1] or chr(64 + p_num)).strip()
                    p_color = r[2] or r[3] or "CCCCCC"
                    colores.append((p_num, p_name, p_color))
                print(f"[generarglobos] {len(colores)} problemas leídos directamente de BD BOCA", flush=True)
                return colores if colores else None
        finally:
            conn.close()
    except Exception as e:
        print(f"[generarglobos] aviso: error al leer BD BOCA: {e}", flush=True)
        return None


def generar_globos():
    """Función principal que genera los globos. Retorna (success, message)"""
    os.makedirs(GLOBOS_DIR, exist_ok=True)

    # 1. Intentar lectura directa de BD BOCA
    colores = _fetch_from_db()

    # 2. Si no hay BD o falló, consultar al microservicio bd (boca-scraper)
    if not colores:
        try:
            response = requests.get(f"{BD_SERVICE_URL}/api/problems", timeout=15)
            if response.status_code != 200:
                return False, f"Error obteniendo problemas: {response.text}"

            data = response.json()
            if not data.get("success"):
                return False, f"Error en la respuesta: {data.get('error')}"

            colores = [
                (
                    row.get("problemnumber", idx + 1),
                    row.get("problemname", chr(64 + row.get("problemnumber", idx + 1))),
                    row.get("problemcolor", "#CCCCCC"),
                )
                for idx, row in enumerate(data.get("rows", []))
            ]
            print(f"[generarglobos] Obtenidos {len(colores)} problemas desde {BD_SERVICE_URL}", flush=True)
        except Exception as e:
            return False, f"Error de conexión al servicio bd: {e}"

    if not colores:
        return False, "No se encontraron problemas para generar globos"

    def generar_globo(nombre_globo, color_hex):
        relleno_path = os.path.join(BASE_DIR, "bigballoon.png")
        contorno_path = os.path.join(BASE_DIR, "bigballoontransp.png")

        relleno = Image.open(relleno_path).convert("RGBA")
        contorno = Image.open(contorno_path).convert("RGBA")

        hex_clean = _normalize_hex(color_hex)
        r = int(hex_clean[0:2], 16)
        g = int(hex_clean[2:4], 16)
        b = int(hex_clean[4:6], 16)

        color_img = Image.new("RGBA", relleno.size, (r, g, b, 255))
        alpha = relleno.split()[3]
        color_img.putalpha(alpha)

        result = color_img.copy()
        result.alpha_composite(contorno)
        result.alpha_composite(contorno, (-1, 0))
        result.alpha_composite(contorno, (1, 0))
        result.alpha_composite(contorno, (0, -1))
        result.alpha_composite(contorno, (0, 1))

        output_path = os.path.join(GLOBOS_DIR, nombre_globo)
        result.save(output_path)

    for item in colores:
        problemnumber, problemname, color = item[0], item[1], item[2]
        letter = str(problemname).strip().upper() if problemname else chr(64 + int(problemnumber))
        nombre_globo = f"{letter}.png"
        generar_globo(nombre_globo, color)
        # También guardar por letra por si acaso
        if problemnumber and str(problemnumber).isdigit():
            num_letter = chr(64 + int(problemnumber))
            if num_letter != letter:
                generar_globo(f"{num_letter}.png", color)

    return True, f"Globos generados exitosamente ({len(colores)} problemas)"


if __name__ == "__main__":
    success, msg = generar_globos()
    if success:
        print(msg)
    else:
        print(f"Error: {msg}")
        exit(1)
