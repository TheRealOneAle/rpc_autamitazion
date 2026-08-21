from flask import Flask, jsonify, send_file, request
import os

app = Flask(__name__)

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'generarglobos.py')
GLOBOS_DIR = os.path.join(os.path.dirname(__file__), 'globosgenerados')

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
    r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)

    color_img = Image.new('RGBA', relleno.size, (r, g, b, 255))
    color_img.putalpha(relleno.split()[3])

    result = color_img.copy()
    for offset in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
        result.alpha_composite(contorno, offset)

    result.save(output_path)


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
        # Fallback to root globos dir if available
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
