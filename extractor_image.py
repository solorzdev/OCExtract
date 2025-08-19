import os, re, shutil, time, logging
from glob import glob
from typing import List, Tuple, Optional

import pytesseract
from PIL import Image, ImageFilter
from datetime import datetime
from datetime import datetime


# 🔹 Conexión usando config.py
import pyodbc

def conectar():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=extractinfo;"
        "Trusted_Connection=yes;"
    )

def existe_rfc(rfc: Optional[str]) -> bool:
    if not rfc:
        return False
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM constancias WHERE rfc = ?;", (rfc,))
    existe = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return existe

def guardar_datos(datos):
    conn = conectar()
    cursor = conn.cursor()

    # Asegurar que la fecha sea tipo DATE
    from datetime import datetime
    try:
        datos['fecha_emision'] = datetime.strptime(datos['fecha_emision'], "%d/%m/%Y").date()
    except:
        datos['fecha_emision'] = None

    sql = """
        INSERT INTO constancias (
            tipo_contribuyente, rfc, curp, fecha_emision, razon_social,
            regimen_capital, nombre_comercial,
            nombre, apellido_paterno, apellido_materno,
            estatus_padron, codigo_postal,
            archivo_origen, fecha_procesado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    valores = (
        datos['tipo_contribuyente'],
        datos['rfc'],
        datos.get('curp'),
        datos['fecha_emision'],
        datos.get('razon_social'),
        datos.get('regimen_capital'),
        datos.get('nombre_comercial'),
        datos.get('nombre'),
        datos.get('apellido_paterno'),
        datos.get('apellido_materno'),
        datos['estatus_padron'],
        datos['codigo_postal'],
        datos.get('archivo_origen'),
        datos.get('fecha_procesado')
    )

    cursor.execute(sql, valores)
    conn.commit()
    cursor.close()
    conn.close()

# ===============================
# Carpetas
# ===============================
DIR_IN   = "pendientes"
DIR_OUT  = "procesados"
DIR_ERR  = "errores"

# ===============================
# Logs
# ===============================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename=os.path.join("logs", "procesar_imagenes.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ===============================
# Configuración Tesseract
# ===============================
LANG = "spa"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

# ===============================
# Regex
# ===============================
REGEX_RFC     = re.compile(r"\b[A-Z&Ñ]{3,4}\d{6}[A-Z0-9]{3}\b")
REGEX_CURP    = re.compile(r"\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\w\b")
REGEX_FECHA   = re.compile(r"\b\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚ]+\s+DE\s+\d{4}\b", re.IGNORECASE)
REGEX_CP      = re.compile(r"\b\d{5}\b")
REGEX_ESTATUS = re.compile(r"\b(ACTIVO|BAJA|SUSPENDIDO|CANCELADO)\b", re.IGNORECASE)
REGEX_TOKEN   = re.compile(r"^[A-ZÑÁÉÍÓÚ]{3,20}$")

# MORAL (razón social / régimen / nombre comercial)
REGEX_RAZON   = re.compile(r"(?:DENOMINACI[ÓO]N(?:\s+O)?\s+RAZ[ÓO]N\s+SOCIAL|RAZ[ÓO]N\s+SOCIAL|NOMBRE,\s*DENOMINACI[ÓO]N\s*O\s*RAZ[ÓO]N\s*SOCIAL)\s*:\s*([A-Z0-9 .,&\-ÁÉÍÓÚÑ/]+)")
REGEX_REGCAP  = re.compile(r"REG[IÍ]MEN(?:\s+DE)?\s+CAPITAL\s*:\s*([A-Z0-9 .,&\-ÁÉÍÓÚÑ/]+)")
REGEX_NCOM    = re.compile(r"NOMBRE\s+COMERCIAL\s*:\s*([A-Z0-9 .,&\-ÁÉÍÓÚÑ/]+)")

# FISICA (etiquetas)
REGEX_NOMBRES = re.compile(r"NOMBRE\s*\(S\)\s*:\s*([A-ZÁÉÍÓÚÑ ]+)", re.IGNORECASE)
REGEX_AP_P    = re.compile(r"PRIMER\s+APELLIDO\s*:\s*([A-ZÁÉÍÓÚÑ ]+)", re.IGNORECASE)
REGEX_AP_M    = re.compile(r"SEGUNDO\s+APELLIDO\s*:\s*([A-ZÁÉÍÓÚÑ ]+)", re.IGNORECASE)

REGEX_FECHA_A = re.compile(r"\bA\s+(\d{1,2}\s+DE\s+[A-ZÁÉÍÓÚ]+\s+DE\s+\d{4})\b", re.IGNORECASE)

# ===============================
# Utilidades de nombres / prefijos
# ===============================
def primera_vocal(p: str) -> str:
    for c in p[1:]:
        if c in "AEIOU":
            return c
    return "X"

def generar_prefijo_curp(ap_p: str, ap_m: str, nombre: str) -> str:
    try:
        return (ap_p[0] + primera_vocal(ap_p) + ap_m[0] + nombre[0]).upper()
    except Exception:
        return ""

def obtener_prefijo_desde_rfc(rfc: Optional[str]) -> str:
    return rfc[:4].upper() if rfc and len(rfc) >= 4 else ""

def mejor_comb_prefijo(candidatos: List[List[str]], prefijo_objetivo: str) -> Optional[Tuple[str, str, str]]:
    if not prefijo_objetivo:
        return None
    mejor_score = -1
    mejor = None
    for grupo in candidatos:
        if len(grupo) != 3:
            continue
        n, ap, am = grupo
        prefijo = generar_prefijo_curp(ap, am, n)
        if prefijo == prefijo_objetivo:
            return (n, ap, am)
        score = sum(1 for a, b in zip(prefijo, prefijo_objetivo) if a == b)
        if score > mejor_score:
            mejor_score = score
            mejor = (n, ap, am)
    return mejor

# ===============================
# Helpers comunes
# ===============================
def grab_field(lines, label_patterns, max_lookahead=2):
    U = [l.upper() for l in lines]
    for i, lu in enumerate(U):
        for pat in label_patterns:
            if re.search(pat, lu):
                raw_line = lines[i]
                m = re.search(r":\s*(.+)$", raw_line)
                if m and m.group(1).strip():
                    val = m.group(1).strip()
                else:
                    val = None
                    for j in range(1, max_lookahead + 1):
                        if i + j < len(lines):
                            cand = lines[i + j].strip()
                            if cand:
                                val = cand
                                break
                if val:
                    val = re.sub(r"[|•·]+", " ", val)
                    val = re.sub(r"\s{2,}", " ", val).strip()
                    return val.upper()
    return None

def detectar_por_claves_fisica(lineas: List[str]) -> Optional[Tuple[str, str, str]]:
    nombre = ap_p = ap_m = None
    for line in lineas:
        l = line.replace("|", " ")
        if nombre is None:
            m = REGEX_NOMBRES.search(l)
            if m: nombre = m.group(1).strip().upper()
        if ap_p is None:
            m = REGEX_AP_P.search(l)
            if m: ap_p = m.group(1).strip().upper()
        if ap_m is None:
            m = REGEX_AP_M.search(l)
            if m: ap_m = m.group(1).strip().upper()
    if nombre and ap_p and ap_m:
        return (nombre.split()[0], ap_p.split()[0], ap_m.split()[0])
    return None

def detectar_nombre_horizontal(lineas: List[str]) -> Optional[List[str]]:
    for line in lineas:
        palabras = [p for p in line.replace("|", " ").split() if p.isalpha()]
        if len(palabras) == 3 and all(p.isupper() for p in palabras):
            return palabras
    return None

def detectar_tipo_entidad(lineas: List[str]) -> str:
    texto = " ".join(lineas).upper()
    if ("RAZÓN SOCIAL" in texto or "RAZON SOCIAL" in texto
        or "DENOMINACIÓN O RAZÓN SOCIAL" in texto or "DENOMINACION O RAZON SOCIAL" in texto
        or "RÉGIMEN CAPITAL" in texto or "REGIMEN CAPITAL" in texto):
        return "MORAL"
    if ("NOMBRE (S)" in texto or "PRIMER APELLIDO" in texto or "SEGUNDO APELLIDO" in texto):
        return "FISICA"
    if detectar_nombre_horizontal(lineas):
        return "FISICA"
    return "MORAL"

def extraer_fecha_emision(lineas: list[str]) -> str:
    U = [l.upper() for l in lineas]
    for i, line in enumerate(lineas):
        m = REGEX_FECHA_A.search(line)
        if m:
            return m.group(1).upper()
        if " A " in line.upper() and i + 1 < len(lineas):
            combinado = line + " " + lineas[i + 1]
            m2 = REGEX_FECHA_A.search(combinado)
            if m2:
                return m2.group(1).upper()
    label_pats = [r"LUGAR\s+Y\s+FECHA\s+DE\s+EMISI[ÓO]N", r"FECHA\s+DE\s+EMISI[ÓO]N"]
    for i, lu in enumerate(U):
        if any(re.search(p, lu) for p in label_pats):
            for j in range(0, 4):
                k = i + j
                if 0 <= k < len(lineas):
                    linea_actual = lineas[k]
                    if k + 1 < len(lineas):
                        linea_actual += " " + lineas[k + 1]
                    m = REGEX_FECHA.search(linea_actual)
                    if m:
                        return m.group(0).upper()
            break
    candidates = []
    for idx, raw in enumerate(lineas):
        combinado = raw
        if idx + 1 < len(lineas):
            combinado += " " + lineas[idx + 1]
        for m in REGEX_FECHA.finditer(combinado):
            date_str = m.group(0)
            window = " ".join(U[max(0, idx-1):min(len(U), idx+3)])
            score = 0
            if "EMISI" in window: score += 2
            if "LUGAR" in window: score += 1
            if any(t in window for t in ["INICIO", "ÚLTIMO", "ULTIMO", "CAMBIO", "OPERACIONES"]):
                score -= 3
            candidates.append((score, idx, date_str))
    if candidates:
        candidates.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        return candidates[0][2].upper()
    return "No detectado"

# ===============================
# Extracción FÍSICA
# ===============================
def parse_fisica(lineas: List[str], ctx: dict):
    found = detectar_por_claves_fisica(lineas)
    if found:
        n, ap, am = found
        ctx["nombre"], ctx["apellido_paterno"], ctx["apellido_materno"] = n.title(), ap.title(), am.title()
        ctx["modo"] = "palabras_clave"
        return
    tokens_verticales, tokens_horizontales = [], []
    for linea in lineas:
        if REGEX_TOKEN.fullmatch(linea.replace("|", "").strip()):
            tokens_verticales.append(linea.replace("|", "").strip())
        else:
            palabras = linea.replace("|", "").strip().split()
            if len(palabras) == 3 and all(p.isupper() and p.isalpha() for p in palabras):
                tokens_horizontales.append(palabras)
    candidatos = []
    for i in range(len(tokens_verticales) - 2):
        candidatos.append(tokens_verticales[i:i+3])
    candidatos += tokens_horizontales
    prefijo_ref = ""
    if ctx["curp"]:
        prefijo_ref = ctx["curp"][:4]
        ctx["modo"] = "CURP"
    elif ctx["rfc"]:
        prefijo_ref = obtener_prefijo_desde_rfc(ctx["rfc"])
        ctx["modo"] = "RFC"
    else:
        ctx["modo"] = "heuristica_pura"
    if prefijo_ref:
        comb = mejor_comb_prefijo(candidatos, prefijo_ref)
        if comb:
            n, ap, am = comb
            ctx["nombre"], ctx["apellido_paterno"], ctx["apellido_materno"] = n.title(), ap.title(), am.title()
            return
    trio = detectar_nombre_horizontal(lineas)
    if trio:
        n, ap, am = trio
        ctx["nombre"], ctx["apellido_paterno"], ctx["apellido_materno"] = n.title(), ap.title(), am.title()
    elif candidatos:
        n, ap, am = candidatos[0]
        ctx["nombre"], ctx["apellido_paterno"], ctx["apellido_materno"] = n.title(), ap.title(), am.title()

# ===============================
# Extracción MORAL
# ===============================
def parse_moral(lineas: List[str], ctx: dict):
    razon = grab_field(lineas, [r"DENOMINACI[ÓO]N\s*(?:O)?\s*RAZ[ÓO]N\s*SOCIAL", r"RAZ[ÓO]N\s+SOCIAL", r"NOMBRE,\s*DENOMINACI[ÓO]N\s*O\s*RAZ[ÓO]N\s*SOCIAL"], max_lookahead=2)
    regcap = grab_field(lineas, [r"R[ÉE]GIMEN\s*(?:DE\s*)?CAPITAL"], max_lookahead=2)
    ncom = grab_field(lineas, [r"NOMBRE\s+COMERCIAL"], max_lookahead=2)
    def tidy(x):
        if not x: return None
        return " ".join(p if (p.isupper() and len(p) <= 3) else p.title() for p in x.split())
    ctx["razon_social"]     = tidy(razon) if razon else None
    ctx["regimen_capital"]  = tidy(regcap) if regcap else None
    ctx["nombre_comercial"] = tidy(ncom) if ncom else None
    if not ctx["regimen_capital"]:
        rs = (ctx["razon_social"] or "").upper()
        if " DE C.V" in rs:
            ctx["regimen_capital"] = "Capital Variable"

# ===============================
# OCR + extracción común
# ===============================
def extract_from_image(path: str) -> dict:
    img = Image.open(path)
    img = img.convert("L")
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150))
    img = img.resize((img.width * 2, img.height * 2))

    ocr_text = pytesseract.image_to_string(img, lang=LANG)
    lineas = [line.strip() for line in ocr_text.splitlines() if line.strip()]

    ctx = {
        "archivo": os.path.basename(path),
        "rfc": None,
        "curp": None,
        "nombre": "No detectado",
        "apellido_paterno": "No detectado",
        "apellido_materno": "No detectado",
        "fecha_emision": "No detectado",
        "fecha_inicio": "No detectado",
        "estatus_padron": None,
        "codigo_postal": None,
        "modo": "",
        "tipo_contribuyente": None,
        "razon_social": None,
        "regimen_capital": None,
        "nombre_comercial": None
    }

    fechas_inline = []
    for linea in lineas:
        if not ctx["rfc"]:
            m = REGEX_RFC.search(linea)
            if m: ctx["rfc"] = m.group()
        if not ctx["curp"]:
            m = REGEX_CURP.search(linea)
            if m: ctx["curp"] = m.group()

        m = REGEX_FECHA.search(linea)
        if m:
            fechas_inline.append(m.group())

        if ctx["codigo_postal"] is None:
            m = REGEX_CP.search(linea)
            if m: ctx["codigo_postal"] = m.group()

        if ctx["estatus_padron"] is None:
            m = REGEX_ESTATUS.search(linea)
            if m: ctx["estatus_padron"] = m.group().upper()

    ctx["fecha_emision"] = extraer_fecha_emision(lineas)

    if len(fechas_inline) > 1:
        ctx["fecha_inicio"] = fechas_inline[1]

    tipo = detectar_tipo_entidad(lineas)
    ctx["tipo_contribuyente"] = tipo

    if tipo == "MORAL":
        parse_moral(lineas, ctx)
        ctx["nombre"] = ctx["apellido_paterno"] = ctx["apellido_materno"] = None
        ctx["modo"] = (ctx["modo"] or "moral").upper()
    else:
        parse_fisica(lineas, ctx)
        ctx["modo"] = (ctx["modo"] or "fisica").upper()

    ctx["_ocr_text"] = ocr_text
    return ctx

# ===============================
# Storage helpers
# ===============================
def convert_to_webp(img_path: str, quality: int = 80) -> str:
    base, ext = os.path.splitext(img_path)
    if ext.lower() == ".webp":
        return img_path
    try:
        im = Image.open(img_path)
        if im.mode in ("RGBA", "P"):
            im = im.convert("RGBA")
        else:
            im = im.convert("RGB")
        webp_path = base + ".webp"
        im.save(webp_path, "WEBP", quality=quality, method=6)
        os.remove(img_path)
        return webp_path
    except Exception as e:
        print(f"   ⚠️ No se pudo convertir a WebP ({img_path}): {e}")
        logging.warning(f"No se pudo convertir a WebP ({img_path}): {e}")
        return img_path

def purge_processed(retention_days: int = 7, base_dir: str = DIR_OUT):
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for root, _, files in os.walk(base_dir):
        for name in files:
            path = os.path.join(root, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except Exception:
                pass
    print(f"🧹 Purgados {removed} archivo(s) de '{base_dir}' (> {retention_days} días).")

# ===============================
# Main
# ===============================
def main():
    os.makedirs(DIR_IN, exist_ok=True)
    os.makedirs(DIR_OUT, exist_ok=True)
    os.makedirs(DIR_ERR, exist_ok=True)

    imgs = []
    for pat in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        imgs.extend(glob(os.path.join(DIR_IN, pat)))

    if not imgs:
        print(f"❌ No hay imágenes en '{DIR_IN}'")
        logging.info("No hay imágenes para procesar.")
        purge_processed(retention_days=7, base_dir=DIR_OUT)
        return

    for path in imgs:
        fname = os.path.basename(path)
        print(f"↪ Procesando: {fname} ...")
        logging.info(f"Inicia procesamiento imagen: {fname}")

        try:
            data = extract_from_image(path)

            # Validaciones mínimas
            if not data.get("rfc"):
                print(f"   ⚠️ No se detectó RFC en: {fname}")
                logging.warning(f"No se detectó RFC en {fname}")
                shutil.move(path, os.path.join(DIR_ERR, fname))
                continue

            # Duplicado por RFC
            if existe_rfc(data["rfc"]):
                print(f"   ⚠️ RFC duplicado, se mueve a errores: {data['rfc']}")
                logging.warning(f"Duplicado detectado para RFC {data['rfc']} ({fname}), no se guarda.")
                shutil.move(path, os.path.join(DIR_ERR, fname))
                continue
            
            try:
                data['fecha_emision'] = datetime.strptime(data['fecha_emision'], "%d/%m/%Y").date()
            except:
                data['fecha_emision'] = None


            # Guardar en BD
            guardar_datos({
                'tipo_contribuyente': data['tipo_contribuyente'],
                'rfc': data['rfc'],
                'curp': data.get('curp'),
                'fecha_emision': data['fecha_emision'],
                'razon_social': data.get('razon_social'),
                'regimen_capital': data.get('regimen_capital'),
                'nombre_comercial': data.get('nombre_comercial'),
                'nombre': data.get('nombre'),
                'apellido_paterno': data.get('apellido_paterno'),
                'apellido_materno': data.get('apellido_materno'),
                'estatus_padron': data.get('estatus_padron'),
                'codigo_postal': data.get('codigo_postal'),
                'archivo_origen': data.get('archivo'),
                'fecha_procesado': time.strftime('%Y-%m-%d %H:%M:%S')
            })

            # Mover a procesados y generar _ocr.txt
            new_path = os.path.join(DIR_OUT, fname)
            shutil.move(path, new_path)

            new_path = convert_to_webp(new_path, quality=80)
            debug_txt = os.path.splitext(new_path)[0] + "_ocr.txt"
            with open(debug_txt, "w", encoding="utf-8") as f:
                f.write(data["_ocr_text"])

            print(f"   ✅ OK → {data.get('tipo_contribuyente','?')} | RFC {data.get('rfc','?')} | {new_path}")
            logging.info(f"Procesado correctamente {fname} | RFC {data.get('rfc','?')}")

        except Exception as e:
            # Mover a errores y registrar
            try:
                shutil.move(path, os.path.join(DIR_ERR, fname))
            except Exception:
                pass
            print(f"   ❌ Error crítico con {fname}: {e}")
            logging.error(f"Error crítico procesando {fname}: {e}")

    purge_processed(retention_days=7, base_dir=DIR_OUT)
    print("🏁 Listo.")

if __name__ == "__main__":
    main()
