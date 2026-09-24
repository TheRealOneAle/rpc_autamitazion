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


def _truncate_text(text, font, max_w):
    if not text:
        return ""
    bbox = font.getbbox(text)
    if bbox[2] - bbox[0] <= max_w:
        return text
    while len(text) > 3:
        text = text[:-1]
        bbox = font.getbbox(text + "...")
        if bbox[2] - bbox[0] <= max_w:
            return text + "..."
    return text


def _get_font(bold=False, size=20):
    from PIL import ImageFont
    base = os.path.dirname(__file__)
    font_file = 'arialbd.ttf' if bold else 'arial.ttf'
    font_path = os.path.join(base, 'fonts', font_file)
    if os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass
    return ImageFont.load_default(size=size)


def _generate_first_solution_card(letter, team_name, university, time_minutes, language, color_hex, output_path, problem_name=None, rpc_name="RPC", datetime_str=None):
    """Renders a high-definition (1200x630) graphical micro-card for a First Solution event."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 1200, 630
    card = Image.new('RGB', (w, h), (244, 246, 247))  # Fondo clarito idéntico a las tablas de ranking (#f4f6f7)
    draw = ImageDraw.Draw(card)

    if not rpc_name:
        rpc_name = "RPC"

    if not datetime_str:
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            bogota_tz = ZoneInfo('America/Bogota')
        except ImportError:
            from datetime import timezone, timedelta
            bogota_tz = timezone(timedelta(hours=-5))
        datetime_str = datetime.now(bogota_tz).strftime("%d/%m/%Y %H:%M")

    color_clean = color_hex.lstrip('#')
    if len(color_clean) == 3:
        color_clean = f"{color_clean[0]*2}{color_clean[1]*2}{color_clean[2]*2}"
    try:
        r, g, b = int(color_clean[0:2], 16), int(color_clean[2:4], 16), int(color_clean[4:6], 16)
        prob_rgb = (r, g, b)
    except Exception:
        prob_rgb = (207, 31, 74)

    red_color = (207, 31, 74)  # Rojo oficial RPC #CF1F4A

    # Accent top border in red
    draw.rectangle([(0, 0), (w, 8)], fill=red_color)

    # Inner container: blanco elegante con borde sutil (#ffffff con outline #e2e8f0)
    draw.rounded_rectangle([(35, 30), (w - 35, h - 30)], radius=24, fill=(255, 255, 255), outline=(226, 232, 240), width=2)

    font_fs = _get_font(bold=True, size=32)
    font_badge = _get_font(bold=True, size=18)
    font_date = _get_font(bold=False, size=18)
    font_prob = _get_font(bold=True, size=74)
    font_label = _get_font(bold=True, size=20)
    font_team = _get_font(bold=True, size=38)
    font_univ = _get_font(bold=False, size=26)
    font_stats = _get_font(bold=True, size=22)
    font_footer = _get_font(bold=False, size=18)

    # 1. "FIRST SOLUTION" en rojo RPC
    draw.text((80, 75), "FIRST SOLUTION", font=font_fs, fill=red_color)

    # 1b. Badge RPC y fecha/hora al lado de FIRST SOLUTION
    fs_bbox = font_fs.getbbox("FIRST SOLUTION")
    fs_w = fs_bbox[2] - fs_bbox[0]
    badge_x = 80 + fs_w + 24
    badge_text = rpc_name.strip().upper()
    badge_bbox = font_badge.getbbox(badge_text)
    badge_w = (badge_bbox[2] - badge_bbox[0]) + 18
    badge_h = 28
    badge_y = 78
    draw.rounded_rectangle([(badge_x, badge_y), (badge_x + badge_w, badge_y + badge_h)], radius=6, fill=red_color)
    draw.text((badge_x + 9, badge_y + 4), badge_text, font=font_badge, fill=(255, 255, 255))

    date_text = str(datetime_str).strip()
    draw.text((badge_x + badge_w + 14, badge_y + 4), date_text, font=font_date, fill=(100, 116, 139))

    # 2. Letra del problema en rojo: "PROBLEMA {letter}"
    let_str = letter.upper()
    draw.text((80, 125), f"PROBLEMA {let_str}", font=font_prob, fill=red_color)

    # 3. "Equipo" y nombre del equipo de competencia (oscuro de alto contraste)
    draw.text((80, 235), "Equipo", font=font_label, fill=(100, 116, 139))
    disp_team = _truncate_text(team_name, font_team, 730)
    draw.text((80, 268), disp_team, font=font_team, fill=(26, 26, 26))

    # 4. Universidad abajo del nombre del equipo
    if university and university != "Desconocida":
        disp_univ = _truncate_text(university, font_univ, 730)
        draw.text((80, 325), disp_univ, font=font_univ, fill=(71, 85, 105))

    # 5. Stats Pill (tiempo y lenguaje) con fondo suave y texto azul legible
    draw.rounded_rectangle([(80, 415), (750, 475)], radius=12, fill=(241, 245, 249), outline=(203, 213, 225), width=2)
    stats_text = f"Minuto {time_minutes}   |   Lenguaje: {language}"
    draw.text((105, 433), stats_text, font=font_stats, fill=(2, 132, 199))

    # 6. Hashtags en tono gris sutil
    draw.text((80, 530), "#RedProgramacionCompetitiva   #RPC   #FirstSolution", font=font_footer, fill=(148, 163, 184))

    # 6. Logo RPC y Globo con letra
    balloon_cx = w - 240  # Centro horizontal del área derecha (x=960)

    # 6a. Logo oficial RPC ubicado arriba del globo
    logo_path = os.path.join(os.path.dirname(__file__), "logorpc", "rpc.png")
    if not os.path.exists(logo_path):
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "generartabla", "logorpc", "rpc.png")

    if os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert('RGBA')
            logo_h = 74
            logo_w = int(logo_img.width * (logo_h / logo_img.height))
            logo_img = logo_img.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
            logo_x = balloon_cx - (logo_w // 2)
            logo_y = 52
            card.paste(logo_img, (logo_x, logo_y), logo_img)
        except Exception as e:
            print(f"[warn] paste logo failed: {e}", flush=True)

    # 6b. Balloon Graphic with Letter (bajado para dar espacio al logo)
    globo_path = os.path.join(GLOBOS_DIR, f"{let_str}.png")
    if not os.path.exists(globo_path):
        _generate_balloon(let_str, globo_path, color_hex)

    if os.path.exists(globo_path):
        try:
            balloon = Image.open(globo_path).convert('RGBA')
            bw, bh = 220, 390
            balloon = balloon.resize((bw, bh), Image.Resampling.LANCZOS)

            # Draw prominent letter on balloon
            bdraw = ImageDraw.Draw(balloon)
            bfont = _get_font(bold=True, size=70)
            bbox_bl = bfont.getbbox(let_str)
            blw = bbox_bl[2] - bbox_bl[0]
            blh = bbox_bl[3] - bbox_bl[1]
            cx = bw // 2
            cy = int(bh * 0.28)
            blx = cx - blw // 2 - bbox_bl[0]
            bly = cy - blh // 2 - bbox_bl[1]
            bdraw.text((blx, bly), let_str, font=bfont, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))

            balloon_x = balloon_cx - (bw // 2)
            balloon_y = 150
            card.paste(balloon, (balloon_x, balloon_y), balloon)
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
    rpc_name = data.get('rpc_name') or data.get('contest_name') or 'RPC'
    datetime_str = data.get('datetime_str') or ''

    prob_name = data.get('problem_name') or f"Problema {letter}"

    card_name = f"fs_{letter}_{abs(hash(team_name)) % 10000}.png"
    card_path = os.path.join(CARDS_DIR, card_name)

    try:
        _generate_first_solution_card(
            letter, team_name, university, time_min, language, color, card_path,
            problem_name=prob_name, rpc_name=rpc_name, datetime_str=datetime_str
        )
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
