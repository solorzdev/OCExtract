# -*- coding: utf-8 -*-
import os, re, logging, shutil, datetime, pathlib
import fitz
from PIL import Image
import pytesseract

from config import (
    PENDIENTES_DIR, PROCESADOS_DIR, ERRORES_DIR, LOGS_DIR,
    OCR_DPI, TESS_LANG, ARCHIVO_ID_FROM_FILENAME
)
from database import update_archivo_opinion

os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, "oc_pdf.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# ===== Patrones =====
RFC_RE = re.compile(r"\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b", re.IGNORECASE)
SENTIDO_RE = re.compile(
    r"\b(POSITIVO|POSITIVA|NEGATIVO|NEGATIVA|NO\s+INSCRITO|NO\s+LOCALIZADO|NO\s+LOCALIZADA)\b",
    re.IGNORECASE
)
FOLIO_RE = re.compile(r"\b[A-Z0-9]{8,}\b", re.IGNORECASE)
FECHA_HORA_RE = re.compile(
    r"(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})\s+a\s+las\s+(\d{1,2}):(\d{2})",
    re.IGNORECASE
)
MESES = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,"agosto":8,"septiembre":9,"setiembre":9,"octubre":10,"noviembre":11,"diciembre":12}

# ---------- Helpers ----------
def _parse_fecha_hora(linea: str):
    m = FECHA_HORA_RE.search(linea)
    if not m: return None, None
    d, mes, y, hh, mm = m.groups()
    try:
        return datetime.date(int(y), MESES[mes.lower()], int(d)), datetime.time(int(hh), int(mm), 0)
    except Exception:
        return None, None

def _next_non_empty(lines, start_idx):
    """Devuelve índice del siguiente renglón no vacío a partir de start_idx (excluyente)."""
    i = start_idx + 1
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i if i < len(lines) else None

def _extraer_cadena_original(texto: str) -> str | None:
    i = texto.find("Cadena Original")
    if i == -1: i = texto.find("CADENA ORIGINAL")
    if i == -1: return None
    sub = texto[i:].splitlines()
    sub = [x.strip() for x in sub if x.strip()]
    return sub[1] if len(sub) > 1 else None

# ---------- Parsers focalizados al layout que compartiste ----------
def _extraer_nombre_y_sentido(lines: list[str]):
    """
    Maneja el patrón:
      Nombre, denominación o razón social
      Sentido
      <RAZON SOCIAL>
      <POSITIVO|NEGATIVO|...>
    """
    up = [l.upper().strip() for l in lines]
    for i, ln in enumerate(up):
        if "NOMBRE, DENOMINACIÓN O RAZÓN SOCIAL" in ln or "NOMBRE, DENOMINACION O RAZON SOCIAL" in ln:
            j = _next_non_empty(lines, i)
            if j is not None and up[j] == "SENTIDO":
                v1 = _next_non_empty(lines, j)       # razón social
                v2 = _next_non_empty(lines, v1) if v1 is not None else None  # sentido
                nombre = lines[v1].strip() if v1 is not None else None
                sentido = None
                if v2 is not None:
                    m = SENTIDO_RE.search(lines[v2])
                    if m:
                        sentido = m.group(1).upper().replace("POSITIVA","POSITIVO").replace("NEGATIVA","NEGATIVO")
                if not sentido:
                    # fallback por si la palabra sentido viene con extra espacios
                    m2 = SENTIDO_RE.search(lines[v1]) if v1 is not None else None
                    if m2:
                        # en caso extraño de que el sentido esté pegado a la razón social (poco probable en tu layout)
                        nombre = re.sub(SENTIDO_RE, "", lines[v1]).strip()
                        sentido = m2.group(1).upper().replace("POSITIVA","POSITIVO").replace("NEGATIVA","NEGATIVO")
                return nombre, sentido
    # Fallback genérico (por si el layout cambia)
    for l in lines:
        m_all = list(SENTIDO_RE.finditer(l))
        if m_all:
            m = m_all[-1]
            sentido = m.group(1).upper().replace("POSITIVA","POSITIVO").replace("NEGATIVA","NEGATIVO")
            nombre = l[:m.start()].strip() or None
            if nombre and len(nombre) >= 5:
                return nombre, sentido
    return None, None

def _extraer_rfc_y_folio(lines: list[str]):
    """
    Maneja el patrón:
      RFC
      Folio
      <RFC>
      <Folio>
    """
    up = [l.upper().strip() for l in lines]
    for i, ln in enumerate(up):
        if ln == "RFC":
            j = _next_non_empty(lines, i)
            if j is not None and up[j] == "FOLIO":
                v1 = _next_non_empty(lines, j)       # debería ser RFC
                v2 = _next_non_empty(lines, v1) if v1 is not None else None  # debería ser Folio
                rfc = None
                folio = None
                if v1 is not None:
                    m_r = RFC_RE.search(lines[v1])
                    if m_r: rfc = m_r.group(1).upper()
                if v2 is not None:
                    m_f = FOLIO_RE.search(lines[v2])
                    if m_f: folio = m_f.group(0).upper()
                return rfc, folio
    # Fallback (por si el layout cambia): busca RFC y Folio en cualquier parte
    rfc = None
    folio = None
    for l in lines:
        if not rfc:
            m_r = RFC_RE.search(l)
            if m_r: rfc = m_r.group(1).upper()
        if not folio:
            m_f = FOLIO_RE.search(l)
            if m_f: folio = m_f.group(0).upper()
    return rfc, folio

def _extraer_fecha_y_hora(lines: list[str]):
    """
    Maneja:
      Fecha y hora de emisión
      24 de junio de 2025 a las 11:19 horas
    """
    up = [l.upper().strip() for l in lines]
    for i, ln in enumerate(up):
        if "FECHA Y HORA DE EMISIÓN" in ln or "FECHA Y HORA DE EMISION" in ln:
            v = _next_non_empty(lines, i)
            if v is not None:
                return _parse_fecha_hora(lines[v])
    # Fallback global
    for l in lines:
        f, h = _parse_fecha_hora(l)
        if f: return f, h
    # Fallback final por Cadena Original (|DD-MM-YYYY|)
    co = _extraer_cadena_original("\n".join(lines)) or ""
    m = re.search(r"\|(\d{2})-(\d{2})-(\d{4})\|", co)
    if m:
        d, mm, yy = map(int, m.groups())
        try:
            return datetime.date(yy, mm, d), None
        except Exception:
            pass
    return None, None

# ---------- Pipeline ----------
def _pdf_to_text(path: str) -> str:
    doc = fitz.open(path)
    chunks = []
    for page in doc:
        t = page.get_text("text") or ""
        t = t.strip()
        if len(t) < 20:
            pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            try:
                ocr = pytesseract.image_to_string(img, lang=TESS_LANG)
            except Exception:
                ocr = pytesseract.image_to_string(img)
            t = ocr
        chunks.append(t)
    raw = "\n".join(chunks)
    up = raw.replace("\r", "\n")
    up = "\n".join([ln.rstrip() for ln in up.splitlines()])
    return up

def _parsear(texto: str) -> dict | None:
    lines = [l for l in texto.splitlines()]  # no filtramos blanks: el parser usa _next_non_empty
    nombre, sentido = _extraer_nombre_y_sentido(lines)
    rfc, folio      = _extraer_rfc_y_folio(lines)
    fecha, hora     = _extraer_fecha_y_hora(lines)
    cadena_original = _extraer_cadena_original(texto)

    # Normalizaciones finales
    if sentido:
        sentido = sentido.upper().replace("POSITIVA","POSITIVO").replace("NEGATIVA","NEGATIVO")

    if not any([folio, nombre, sentido, rfc, fecha, cadena_original]):
        return None

    return {
        "rfc": rfc,
        "razon_social": nombre,
        "folio": folio,
        "sentido": sentido,
        "fecha_emision": fecha,   # DATE
        "hora_emision": hora,     # TIME
        "cadena_original": cadena_original,
    }

def _infer_modulo_y_archivo_id(nombre_archivo: str):
    """
    Acepta:
      - 1017_242784.pdf  -> (1017, 242784)
      - 1014-123456.pdf  -> (1014, 123456)
      - 242784.pdf       -> (None, 242784)
    """
    stem = pathlib.Path(nombre_archivo).stem
    m = re.match(r'^(1014|1017)[_\-](\d+)$', stem)
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.match(r'^(\d+)$', stem)
    if m2:
        return None, int(m2.group(1))
    return None, None

def procesar_archivo(path_pdf: str):
    archivo = os.path.basename(path_pdf)
    base, _ = os.path.splitext(archivo)
    logging.info(f"[OC] Procesando PDF: {archivo}")
    print(f"↪ [OC] {archivo}")

    try:
        txt = _pdf_to_text(path_pdf)
        data = _parsear(txt)
        if not data:
            print("   ⚠️ No se pudieron extraer campos.")
            shutil.move(path_pdf, os.path.join(ERRORES_DIR, archivo))
            return

        # === UPDATE a la misma fila de Archivo (usando modulo + id) ===
        modulo_id, archivo_id = _infer_modulo_y_archivo_id(archivo)
        if ARCHIVO_ID_FROM_FILENAME and archivo_id is not None:
            modulo_id = modulo_id if modulo_id is not None else 1017  # Opinión por defecto
            rows = update_archivo_opinion(archivo_id, modulo_id, data, marcar_procesado=True)
            if rows == 0:
                print(f"   ⚠️ No se encontró ArchivoID={archivo_id} AND ArchivoModuloID={modulo_id}.")
            else:
                print(f"   ✅ UPDATE OK → ArchivoID={archivo_id}, Modulo={modulo_id}")
        else:
            print("   ⚠️ No pude inferir ArchivoID desde el nombre. No se actualizó la DB.")

        # guardar OCR/texto y mover PDF
        with open(os.path.join(PROCESADOS_DIR, f"{base}_ocr.txt"), "w", encoding="utf-8") as f:
            f.write(txt)
        shutil.move(path_pdf, os.path.join(PROCESADOS_DIR, archivo))

        print(f"   ✅ Guardado: RFC={data.get('rfc') or '?'} | FOLIO={data.get('folio') or '?'} | SENTIDO={data.get('sentido') or '?'}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        logging.exception(f"[OC] Error con {archivo}: {e}")
        try:
            shutil.move(path_pdf, os.path.join(ERRORES_DIR, archivo))
        except Exception:
            pass
