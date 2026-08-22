import re
import unicodedata

# Mapeo de códigos ISO de país a nombre común en español
COUNTRY_NAMES = {
    'CO': 'Colombia',
    'MX': 'México',
    'PE': 'Perú',
    'AR': 'Argentina',
    'CL': 'Chile',
    'EC': 'Ecuador',
    'BO': 'Bolivia',
    'VE': 'Venezuela',
    'CR': 'Costa Rica',
    'PA': 'Panamá',
    'BR': 'Brasil',
    'CU': 'Cuba',
    'DO': 'República Dominicana',
    'GT': 'Guatemala',
    'SV': 'El Salvador',
    'HN': 'Honduras',
    'NI': 'Nicaragua',
    'PY': 'Paraguay',
    'UY': 'Uruguay',
}

# Alias y nombres comunes de países para búsqueda insensible a mayúsculas/acentos
COUNTRY_ALIASES = {
    'colombia': 'CO', 'co': 'CO',
    'mexico': 'MX', 'méxico': 'MX', 'mx': 'MX',
    'peru': 'PE', 'perú': 'PE', 'pe': 'PE',
    'argentina': 'AR', 'ar': 'AR',
    'chile': 'CL', 'cl': 'CL',
    'ecuador': 'EC', 'ec': 'EC',
    'bolivia': 'BO', 'bo': 'BO',
    'venezuela': 'VE', 've': 'VE',
    'costa rica': 'CR', 'cr': 'CR',
    'panama': 'PA', 'panamá': 'PA', 'pa': 'PA',
    'brasil': 'BR', 'brazil': 'BR', 'br': 'BR',
    'cuba': 'CU', 'cu': 'CU',
    'republica dominicana': 'DO', 'república dominicana': 'DO', 'dominicana': 'DO', 'do': 'DO',
    'guatemala': 'GT', 'gt': 'GT',
    'el salvador': 'SV', 'salvador': 'SV', 'sv': 'SV',
    'honduras': 'HN', 'hn': 'HN',
    'nicaragua': 'NI', 'ni': 'NI',
    'paraguay': 'PY', 'py': 'PY',
    'uruguay': 'UY', 'uy': 'UY',
}

# Códigos de países confiables en RPC
TRUSTED_FLAGS = set(COUNTRY_NAMES.keys())

# Mapeo de códigos no estándar usados por BOCA
BOCA_COUNTRY_MAP = {
    'EV': 'EC',
    'GU': 'GT',
    'HO': 'HN',
    'RD': 'DO',
    'UR': 'UY',
    'HA': 'HT',
}

# Palabras clave por país para inferir el país de la universidad
COUNTRY_KEYWORDS = {
    'AR': [
        'universidad nacional de cordoba', 'universidad nacional de la plata',
        'utn frsf', 'famaf', 'argentina', 'buenos aires', 'uba', 'unlp', 'unc'
    ],
    'BO': [
        'la paz', 'cochabamba', 'santa cruz', 'oruro', 'potosi', 'sucre',
        'tarija', 'bolivia', 'emsi', 'umss', 'umsa', 'upb', 'udabol', 'upds',
        'salesiana de bolivia', 'catolica boliviana', 'ucb'
    ],
    'BR': [
        'brasil', 'federal do', 'universidade', 'ufpi', 'impa', 'usp', 'unicamp',
        'ufrj', 'ufmg', 'puc-rio'
    ],
    'CL': [
        'catolica de chile', 'de chile', 'concepcion', 'valparaiso',
        'la serena', 'antofagasta', 'talca', 'frontera', 'austral',
        'bio-bio', 'los lagos', 'usm', 'utfsm', 'uach', 'puc'
    ],
    'CO': [
        'nacional de colombia', 'los andes', 'javeriana', 'valle', 'antioquia',
        'santo tomas', 'sabana', 'colombia', 'bogota', 'medellin', 'cali',
        'barranquilla', 'cartagena', 'manizales', 'pasto', 'cucuta', 'ibague',
        'bucaramanga', 'pereira', 'neiva', 'tunja', 'popayan', 'magdalena',
        'cauca', 'narino', 'tde', 'pamplona', 'santander', 'cesmag',
        'francisco de paula', 'ufps', 'unicesmag', 'uniagraria', 'minuto de dios',
        'pedagogica nacional', 'catolica de colombia', 'eafit', 'icesi',
        'externado', 'sergio arboleda', 'escuela colombiana', 'pontificia bolivariana',
        'la gran colombia', 'distrital', 'pedagogica y tecnologico', 'uptc',
        'tecnologica de bolivar', 'utb', 'uniandes', 'uis', 'univalle', 'unal',
        'uniatlantico', 'unicauca', 'unimagdalena', 'unillanos', 'unisinú', 'unisinu',
        'uniquindio', 'utp', 'itm', 'politecnico grancolombiano', 'unab'
    ],
    'CR': [
        'costa rica', 'tecnologico de costa rica', 'tec costa rica', 'ucr', 'una'
    ],
    'CU': [
        'cuba', 'la habana', 'uci', 'universidad de oriente', 'uclv'
    ],
    'DO': [
        'republica dominicana', 'dominicana', 'pucmm', 'intec', 'uasd', 'unibe'
    ],
    'EC': [
        'quito', 'guayaquil', 'cuenca', 'ambato', 'loja', 'manta',
        'riobamba', 'machala', 'espejo', 'politecnica', 'ecuador', 'espol',
        'litoral', 'usfq', 'udla', 'puce', 'epn', 'ucuenca'
    ],
    'GT': [
        'guatemala', 'usac', 'del istmo', 'del valle de guatemala', 'uvg', 'url'
    ],
    'HN': [
        'honduras', 'unah', 'unitic', 'unitec'
    ],
    'MX': [
        'unam', 'ipn', 'itesm', 'udem', 'anahuac', 'uabc', 'uach', 'colima',
        'guadalajara', 'nuevo leon', 'puebla', 'sinaloa', 'sonora', 'mexico',
        'yucatan', 'chihuahua', 'baja california', 'queretaro', 'guanajuato',
        'veracruz', 'coahuila', 'morelos', 'oaxaca', 'tabasco', 'zacatecas',
        'aguascalientes', 'campeche', 'chiapas', 'durango', 'hidalgo',
        'nayarit', 'quintana roo', 'san luis potosi', 'tlaxcala',
        'tec de', 'tecnologico de', 'uady', 'cucei', 'uacj', 'uanl', 'buap',
        'uagro', 'iteso', 'itam', 'itl', 'conalep', 'cbtis',
        'cetis', 'uaeh', 'cimat', 'cinvestav', 'itcelaya', 'itmorelia'
    ],
    'NI': [
        'nicaragua', 'uni nicaragua', 'unan'
    ],
    'PA': [
        'panama', 'utp panama', 'universidad de panama', 'usma'
    ],
    'PE': [
        'pacifico', 'lima', 'cajamarca', 'cusco', 'arequipa', 'trujillo',
        'piura', 'huancayo', 'ica', 'puno', 'peru', 'uni peru', 'unsa', 'unsaac',
        'unmsm', 'ucsp', 'san agustin', 'san antonio abad',
        'peruana', 'usil', 'upc', 'upao', 'unc', 'unjbg', 'unheval',
        'unsch', 'unap', 'unt', 'unjfsc', 'pucp', 'utec', 'upch'
    ],
    'PY': [
        'paraguay', 'asuncion', 'una paraguay', 'uca paraguay'
    ],
    'SV': [
        'salvador', 'uca el salvador', 'ues'
    ],
    'UY': [
        'uruguay', 'montevideo', 'udelar', 'ort uruguay'
    ],
    'VE': [
        'caracas', 'maracaibo', 'valencia', 'barquisimeto', 'ucab', 'unimet',
        'simon bolivar', 'luz', 'ula', 'ucv', 'usb venezuela',
        'nueva esparta', 'carabobo', 'venezuela', 'yacambu', 'ucla'
    ],
}

# Catálogo canónico de universidades (Nombre canónico, Acrónimo, País)
# Mapea patrones normalizados -> (Nombre oficial, Acrónimo, Código País)
KNOWN_UNIVERSITIES = [
    # Colombia
    (r'\b(ufps|francisco de paula santander)\b', 'Universidad Francisco de Paula Santander', 'UFPS', 'CO'),
    (r'\b(unal|nacional de colombia|universidad nacional)\b', 'Universidad Nacional de Colombia', 'UNAL', 'CO'),
    (r'\b(uniandes|los andes)\b', 'Universidad de los Andes', 'UniAndes', 'CO'),
    (r'\b(javeriana|pontificia universidad javeriana)\b', 'Pontificia Universidad Javeriana', 'PUJ', 'CO'),
    (r'\b(udea|universidad de antioquia)\b', 'Universidad de Antioquia', 'UdeA', 'CO'),
    (r'\b(univalle|universidad del valle)\b', 'Universidad del Valle', 'Univalle', 'CO'),
    (r'\b(uis|industrial de santander)\b', 'Universidad Industrial de Santander', 'UIS', 'CO'),
    (r'\b(eafit)\b', 'Universidad EAFIT', 'EAFIT', 'CO'),
    (r'\b(icesi)\b', 'Universidad ICESI', 'ICESI', 'CO'),
    (r'\b(uptc|pedagogica y tecnologica de colombia)\b', 'Universidad Pedagógica y Tecnológica de Colombia', 'UPTC', 'CO'),
    (r'\b(uniatlantico|universidad del atlantico)\b', 'Universidad del Atlántico', 'UniAtlántico', 'CO'),
    (r'\b(unicauca|universidad del cauca)\b', 'Universidad del Cauca', 'Unicauca', 'CO'),
    (r'\b(unimagdalena|universidad del magdalena)\b', 'Universidad del Magdalena', 'Unimagdalena', 'CO'),
    (r'\b(uniquindio|universidad del quindio)\b', 'Universidad del Quindío', 'Uniquindío', 'CO'),
    (r'\b(utp|tecnologica de pereira)\b', 'Universidad Tecnológica de Pereira', 'UTP', 'CO'),
    (r'\b(unicesmag|cesmag)\b', 'Universidad CESMAG', 'CESMAG', 'CO'),
    (r'\b(unipamplona|universidad de pamplona)\b', 'Universidad de Pamplona', 'Unipamplona', 'CO'),
    (r'\b(unisin[uú]|universidad del sin[uú])\b', 'Universidad del Sinú', 'UniSinú', 'CO'),
    (r'\b(escuela colombiana de ingenieria|ecihg|julio garavito)\b', 'Escuela Colombiana de Ingeniería Julio Garavito', 'ECI', 'CO'),
    (r'\b(upb|pontificia bolivariana)\b', 'Universidad Pontificia Bolivariana', 'UPB', 'CO'),
    (r'\b(distrital|francisco jose de caldas)\b', 'Universidad Distrital Francisco José de Caldas', 'UDistrital', 'CO'),
    (r'\b(sabana|universidad de la sabana)\b', 'Universidad de La Sabana', 'Unisabana', 'CO'),
    (r'\b(santo tomas|usta)\b', 'Universidad Santo Tomás', 'USTA', 'CO'),
    (r'\b(tde|tecnologico de antioquia)\b', 'Tecnológico de Antioquia', 'TdeA', 'CO'),
    (r'\b(unillanos|universidad de los llanos)\b', 'Universidad de los Llanos', 'Unillanos', 'CO'),
    (r'\b(unab|autonoma de bucaramanga)\b', 'Universidad Autónoma de Bucaramanga', 'UNAB', 'CO'),
    (r'\b(itm|instituto tecnologico metropolitano)\b', 'Instituto Tecnológico Metropolitano', 'ITM', 'CO'),

    # México
    (r'\b(unam|autonoma de mexico)\b', 'Universidad Nacional Autónoma de México', 'UNAM', 'MX'),
    (r'\b(ipn|instituto politecnico nacional)\b', 'Instituto Politécnico Nacional', 'IPN', 'MX'),
    (r'\b(itesm|tec de monterrey|tecnologico de monterrey)\b', 'Tecnológico de Monterrey', 'ITESM', 'MX'),
    (r'\b(itam|instituto tecnologico autonomo de mexico)\b', 'Instituto Tecnológico Autónomo de México', 'ITAM', 'MX'),
    (r'\b(cimat)\b', 'Centro de Investigación en Matemáticas', 'CIMAT', 'MX'),
    (r'\b(uanl|autonoma de nuevo leon)\b', 'Universidad Autónoma de Nuevo León', 'UANL', 'MX'),
    (r'\b(buap|benemerita universidad autonoma de puebla)\b', 'Benemérita Universidad Autónoma de Puebla', 'BUAP', 'MX'),
    (r'\b(udg|cucei|universidad de guadalajara)\b', 'Universidad de Guadalajara', 'UdG', 'MX'),
    (r'\b(uady|autonoma de yucatan)\b', 'Universidad Autónoma de Yucatán', 'UADY', 'MX'),
    (r'\b(uacj|autonoma de ciudad juarez)\b', 'Universidad Autónoma de Ciudad Juárez', 'UACJ', 'MX'),
    (r'\b(anahuac)\b', 'Universidad Anáhuac', 'Anáhuac', 'MX'),
    (r'\b(iteso)\b', 'ITESO - Universidad Jesuita de Guadalajara', 'ITESO', 'MX'),
    (r'\b(cinvestav)\b', 'CINVESTAV', 'CINVESTAV', 'MX'),

    # Perú
    (r'\b(pucp|pontificia universidad catolica del peru)\b', 'Pontificia Universidad Católica del Perú', 'PUCP', 'PE'),
    (r'\b(uni|nacional de ingenieria)\b', 'Universidad Nacional de Ingeniería', 'UNI', 'PE'),
    (r'\b(unmsm|san marcos|nacional mayor de san marcos)\b', 'Universidad Nacional Mayor de San Marcos', 'UNMSM', 'PE'),
    (r'\b(utec|universidad de ingenieria y tecnologia)\b', 'Universidad de Ingeniería y Tecnología', 'UTEC', 'PE'),
    (r'\b(ucsp|catolica san pablo)\b', 'Universidad Católica San Pablo', 'UCSP', 'PE'),
    (r'\b(unsa|san agustin de arequipa)\b', 'Universidad Nacional de San Agustín', 'UNSA', 'PE'),
    (r'\b(unsaac|san antonio abad del cusco)\b', 'Universidad Nacional de San Antonio Abad del Cusco', 'UNSAAC', 'PE'),
    (r'\b(upc|peruana de ciencias aplicadas)\b', 'Universidad Peruana de Ciencias Aplicadas', 'UPC', 'PE'),
    (r'\b(unt|nacional de trujillo)\b', 'Universidad Nacional de Trujillo', 'UNT', 'PE'),

    # Bolivia
    (r'\b(umsa|mayor de san andres)\b', 'Universidad Mayor de San Andrés', 'UMSA', 'BO'),
    (r'\b(umss|mayor de san simon)\b', 'Universidad Mayor de San Simón', 'UMSS', 'BO'),
    (r'\b(upb bolivia|privada boliviana)\b', 'Universidad Privada Boliviana', 'UPB', 'BO'),
    (r'\b(ucb|catolica boliviana)\b', 'Universidad Católica Boliviana San Pablo', 'UCB', 'BO'),

    # Ecuador
    (r'\b(espol|escuela superior politecnica del litoral)\b', 'Escuela Superior Politécnica del Litoral', 'ESPOL', 'EC'),
    (r'\b(epn|escuela politecnica nacional)\b', 'Escuela Politécnica Nacional', 'EPN', 'EC'),
    (r'\b(usfq|san francisco de quito)\b', 'Universidad San Francisco de Quito', 'USFQ', 'EC'),
    (r'\b(ucuenca|universidad de cuenca)\b', 'Universidad de Cuenca', 'UCuenca', 'EC'),
    (r'\b(puce|catolica del ecuador)\b', 'Pontificia Universidad Católica del Ecuador', 'PUCE', 'EC'),

    # Chile
    (r'\b(uchile|universidad de chile)\b', 'Universidad de Chile', 'UChile', 'CL'),
    (r'\b(puc chile|catolica de chile)\b', 'Pontificia Universidad Católica de Chile', 'PUC', 'CL'),
    (r'\b(utfsm|usm|santa maria)\b', 'Universidad Técnica Federico Santa María', 'UTFSM', 'CL'),
    (r'\b(udec|universidad de concepcion)\b', 'Universidad de Concepción', 'UdeC', 'CL'),

    # Argentina
    (r'\b(uba|universidad de buenos aires)\b', 'Universidad de Buenos Aires', 'UBA', 'AR'),
    (r'\b(unc|nacional de cordoba|famaf)\b', 'Universidad Nacional de Córdoba', 'UNC', 'AR'),
    (r'\b(unlp|nacional de la plata)\b', 'Universidad Nacional de La Plata', 'UNLP', 'AR'),
    (r'\b(utn)\b', 'Universidad Tecnológica Nacional', 'UTN', 'AR'),

    # Venezuela
    (r'\b(usb|simon bolivar)\b', 'Universidad Simón Bolívar', 'USB', 'VE'),
    (r'\b(ucv|central de venezuela)\b', 'Universidad Central de Venezuela', 'UCV', 'VE'),
    (r'\b(ucab|catolica andres bello)\b', 'Universidad Católica Andrés Bello', 'UCAB', 'VE'),
    (r'\b(unimet|metropolitana)\b', 'Universidad Metropolitana', 'UNIMET', 'VE'),
    (r'\b(ula|universidad de los andes venezuela)\b', 'Universidad de Los Andes', 'ULA', 'VE'),
]


def strip_accents(text: str) -> str:
    """Elimina acentos y normaliza caracteres Unicode a ASCII."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def clean_text(text: str) -> str:
    """Limpia puntuaciones redundantes, espacios extra y etiquetas."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[\._\-–—/]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def normalize_country_code(raw_country: str) -> str:
    """
    Convierte un código ISO, nombre o alias de país a su código ISO estándar (ej: 'Colombia' -> 'CO').
    """
    if not raw_country:
        return None
    raw = clean_text(str(raw_country)).lower()
    raw_no_accents = strip_accents(raw)

    # 1. BOCA specific fixes
    upper_raw = raw.upper()
    if upper_raw in BOCA_COUNTRY_MAP:
        return BOCA_COUNTRY_MAP[upper_raw]
    if upper_raw in TRUSTED_FLAGS:
        return upper_raw

    # 2. Check aliases
    if raw_no_accents in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[raw_no_accents]
    if raw in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[raw]

    return None


def get_country_name(code: str) -> str:
    """Retorna el nombre oficial en español para un código de país."""
    if not code:
        return "Latinoamérica"
    norm_code = normalize_country_code(code) or code.upper()
    return COUNTRY_NAMES.get(norm_code, norm_code)


def guess_country_from_university(university_name: str) -> str:
    """Infiere el código ISO del país basándose en palabras clave del nombre de la universidad."""
    if not university_name:
        return None
    name_clean = strip_accents(university_name.lower())
    for code, keywords in COUNTRY_KEYWORDS.items():
        for kw in keywords:
            kw_clean = strip_accents(kw.lower())
            if re.search(r'\b' + re.escape(kw_clean) + r'\b', name_clean):
                return code
    return None


def normalize_university(raw_name: str, existing_country: str = None) -> dict:
    """
    Normaliza el nombre de la universidad, extrayendo:
    - name: Nombre oficial limpio y capitalizado.
    - acronym: Sigla oficial (ej: 'UFPS', 'UNAL', etc.).
    - country_code: Código ISO normalizado (ej: 'CO').
    - country_name: Nombre del país en español (ej: 'Colombia').
    """
    if not raw_name or raw_name.strip() in ('', '-', 'Desconocida', '&nbsp;', '\u00a0'):
        return {
            'raw': raw_name or '',
            'name': 'Desconocida',
            'acronym': 'N/A',
            'country_code': normalize_country_code(existing_country) or 'CO',
            'country_name': get_country_name(existing_country or 'CO'),
        }

    raw_str = raw_name.strip()
    norm_str = strip_accents(clean_text(raw_str).lower())

    # 1. Buscar en catálogo de universidades conocidas
    for pattern, canonical_name, acronym, country in KNOWN_UNIVERSITIES:
        if re.search(pattern, norm_str, re.IGNORECASE):
            country_code = normalize_country_code(existing_country) or country
            return {
                'raw': raw_str,
                'name': canonical_name,
                'acronym': acronym,
                'country_code': country_code,
                'country_name': get_country_name(country_code),
            }

    # 2. Inferencia de país si no se conoce
    inferred_country = guess_country_from_university(raw_str)
    country_code = normalize_country_code(existing_country) or inferred_country or 'CO'

    # 3. Capitalización estándar
    words = raw_str.split()
    capitalized_words = []
    stopwords = {'de', 'la', 'del', 'los', 'las', 'el', 'y', 'en', 'para', 'por', 'da', 'do', 'e'}
    for idx, w in enumerate(words):
        w_lower = w.lower()
        if idx > 0 and w_lower in stopwords:
            capitalized_words.append(w_lower)
        elif w.isupper() and len(w) <= 6:
            capitalized_words.append(w)  # Mantener siglas como UFPS, UNAL
        else:
            capitalized_words.append(w.capitalize())

    formatted_name = " ".join(capitalized_words)
    # Acrónimo genérico si no se conoce: primera letra de cada palabra capitalizada
    acronym = "".join(w[0].upper() for w in capitalized_words if w.lower() not in stopwords and w)

    return {
        'raw': raw_str,
        'name': formatted_name,
        'acronym': acronym or formatted_name[:4].upper(),
        'country_code': country_code,
        'country_name': get_country_name(country_code),
    }
