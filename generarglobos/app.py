from flask import Flask, jsonify, send_file, request
import os
from io import BytesIO

app = Flask(__name__)

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'generarglobos.py')
GLOBOS_DIR = os.path.join(os.path.dirname(__file__), 'globosgenerados')
CARDS_DIR = os.path.join(os.path.dirname(__file__), 'cards')
os.makedirs(CARDS_DIR, exist_ok=True)

# Default colors used when BD service is unavailable
FALLBACK_COLORS = {
    'A': '#FF8C94', 'B': '#8B0000', 'C': '#FF00FF', 'D': '#C8C8C8',
    'E': '#006400', 'F': '#FF0000', 'G': '#32CD32', 'H': '#AAAAAA',
    'I': '#FFD700', 'J': '#0000FF', 'K': '#111111', 'L': '#0055CC', 'M': '#FF8C00',
}


def _generate_balloon(letter, output_path, color_hex):
    """Generates a balloon PNG using the template images and the given hex color."""
    from PIL import Image
    base = os.path.dirname(__file__)
    relleno = Image.open(os.path.join(base, 'bigballoon.png')).convert('RGBA')
    contorno = Image.open(os.path.join(base, 'bigballoontransp.png')).convert('RGBA')

    color_hex = color_hex.lstrip('#')
    if len(color_hex) == 3:
        color_hex = f"{color_hex[0]*2}{color_hex[1]*2}{color_hex[2]*2}"
    r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

    color_img = Image.new('RGBA', relleno.size, (r, g, b, 255))
    color_img.putalpha(relleno.split()[3])

    result = color_img.copy()
    for offset in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
        result.alpha_composite(contorno, offset)

    result.save(output_path)


def _generate_first_solution_card(letter, team_name, university, time_minutes, language, color_hex, output_path):
    """Renders a graphical micro-card for a First Solution event."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 800, 420
    bg_color = (24, 28, 36)  # Dark sleek background
    card = Image.new('RGB', (w, h), bg_color)
    draw = ImageDraw.Draw(card)

    # Accent top border with problem color
    color_clean = color_hex.lstrip('#')
    if len(color_clean) == 3:
        color_clean = f"{color_clean[0]*2}{color_clean[1]*2}{color_clean[2]*2}"
    try:
        r, g, b = int(color_clean[0:2], 16), int(color_clean[2:4], 16), int(color_clean[4:6], 16)
        prob_rgb = (r, g, b)
    except Exception:
        prob_rgb = (207, 31, 74)

    draw.rectangle([(0, 0), (w, 8)], fill=prob_rgb)

    # Card inner container
    draw.rounded_rectangle([(30, 25), (w - 30, h - 25)], radius=12, fill=(33, 38, 48), outline=(50, 58, 70), width=1)

    # Header badge
    draw.rounded_rectangle([(55, 45), (320, 85)], radius=6, fill=prob_rgb)
    draw.text((65, 52), "🎈 FIRST SOLUTION 🎈", fill=(255, 255, 255))

    # Problem letter and title
    draw.text((55, 105), f"PROBLEMA {letter.upper()}", fill=(255, 255, 255))
    
    # Team Name
    draw.text((55, 160), f"Equipo: {team_name}", fill=(240, 240, 240))

    # University
    if university and university != "Desconocida":
        draw.text((55, 210), f"Universidad: {university}", fill=(180, 190, 205))

    # Time and language info
    draw.text((55, 265), f"Minuto {time_minutes}  •  Lenguaje: {language}", fill=(130, 210, 150))

    # Footer
    draw.text((55, 335), "#RedProgramacionCompetitiva  #RPC", fill=(120, 130, 145))

    # Insert Balloon graphic on the right
    globo_path = os.path.join(GLOBOS_DIR, f"{letter.upper()}.png")
    if not os.path.exists(globo_path):
        _generate_balloon(letter.upper(), globo_path, color_hex)

    if os.path.exists(globo_path):
        try:
            balloon = Image.open(globo_path).convert('RGBA')
            balloon = balloon.resize((150, 200), Image.Resampling.LANCZOS)
            card.paste(balloon, (w - 220, 100), balloon)
        except Exception as e:
            print(f"[warn] paste balloon failed: {e}", flush=True)

    card.save(output_path, 'PNG', quality=95)


def _parse_contest_params():
    """Extrae (year, contest) desde query params o JSON body."""
    year = (request.args.get("year") or "").strip()
    contest = (request.args.get("contest") or "").strip()
    if "/" in contest:
        parts = contest.split("/")
        year = parts[0].strip()
        contest = parts[1].strip()

    if not year and request.is_json:
        data = request.get_json(silent=True) or {}
        year = str(data.get("year", "")).strip()
        contest = str(data.get("contest", "")).strip()
        if "/" in contest:
            parts = contest.split("/")
            year = parts[0].strip()
            contest = parts[1].strip()

    return year, contest


@app.route('/globo/<letter>.png')
def serve_globo(letter):
    upper = letter.upper()
    year, contest = _parse_contest_params()
    file_key = f"{year}_{str(int(contest)).zfill(2)}" if year and contest else ""
    contest_dir = os.path.join(GLOBOS_DIR, file_key) if file_key else GLOBOS_DIR
    os.makedirs(contest_dir, exist_ok=True)
    os.makedirs(GLOBOS_DIR, exist_ok=True)

    path = os.path.join(contest_dir, f'{upper}.png')

    if not os.path.exists(path):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("generarglobos_mod", SCRIPT_PATH)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.generar_globos(year=year, contest=contest)
        except Exception as e:
            print(f"[warn] generar_globos falló: {e}", flush=True)

    if not os.path.exists(path):
        root_path = os.path.join(GLOBOS_DIR, f'{upper}.png')
        if os.path.exists(root_path):
            path = root_path

    if not os.path.exists(path):
        color = FALLBACK_COLORS.get(upper, '#CCCCCC')
        try:
            _generate_balloon(upper, path, color)
            print(f"[info] globo {upper} generado con color fallback {color}", flush=True)
        except Exception as e:
            return jsonify({"error": f"No se pudo generar globo: {e}"}), 500

    if not os.path.exists(path):
        return jsonify({"error": "globo no generado"}), 404

    return send_file(path, mimetype='image/png')


@app.route('/card/first-solution', methods=['GET', 'POST'])
def first_solution_card():
    """Genera y sirve una tarjeta visual gráfica de First Solution."""
    if request.method == 'POST' and request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.args

    letter = (data.get('problem_letter') or data.get('letter') or 'A').upper()
    team_name = data.get('team_name') or data.get('team') or 'Equipo Ganador'
    university = data.get('university') or data.get('univ') or ''
    time_min = data.get('time_minutes') or data.get('min') or 0
    language = data.get('language') or data.get('lang') or 'C++'
    color = data.get('problem_color') or data.get('color') or FALLBACK_COLORS.get(letter, '#CF1F4A')

    card_name = f"fs_{letter}_{abs(hash(team_name)) % 10000}.png"
    card_path = os.path.join(CARDS_DIR, card_name)

    try:
        _generate_first_solution_card(letter, team_name, university, time_min, language, color, card_path)
        return send_file(card_path, mimetype='image/png')
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/generate', methods=['POST'])
def generate_globos():
    year, contest = _parse_contest_params()
    os.makedirs(GLOBOS_DIR, exist_ok=True)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("generarglobos_mod", SCRIPT_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        success, msg = mod.generar_globos(year=year, contest=contest)
        if success:
            return jsonify({"status": "success", "message": msg, "contest": f"{year}/{contest}" if year else "default"}), 200
        else:
            return jsonify({"status": "error", "message": msg}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    expected = [f"{chr(i)}.png" for i in range(65, 78)]
    missing = [g for g in expected if not os.path.exists(os.path.join(GLOBOS_DIR, g))]
    if missing:
        return jsonify({"status": "pending", "missing": missing}), 200
    return jsonify({"status": "complete"}), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
