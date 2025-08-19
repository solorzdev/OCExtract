import fitz
import pytesseract
import cv2
import pdfplumber
import re
import os
import datetime
import shutil
import logging
from wordsegment import load, segment
from database import guardar_datos, existe_rfc
from datetime import datetime


# === Configuración de logs ===
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename=os.path.join('logs', 'procesar_pdf.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# === Carpetas de salida ===
RUTA_PROCESADOS = 'procesados'
RUTA_ERRORES = 'errores'
os.makedirs(RUTA_PROCESADOS, exist_ok=True)
os.makedirs(RUTA_ERRORES, exist_ok=True)

# Inicializar el modelo de segmentación
load()

# === Separación OCR inteligente (mayúsculas pegadas) ===
def separar_palabras_mayusculas(texto):
    if not texto or ' ' in texto:
        return texto
    palabras = segment(texto.lower())
    return ' '.join(p.upper() for p in palabras)

# === Extraer texto de PDF (con OCR fallback) ===
def extraer_texto_pdf(ruta_pdf):
    texto = ''
    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            pagina_texto = pagina.extract_text()
            if pagina_texto:
                texto += pagina_texto + '\n'
    if texto.strip():
        return texto

    texto = ''
    documento = fitz.open(ruta_pdf)
    for pagina in documento:
        pix = pagina.get_pixmap()
        output = 'pagina_temp.png'
        pix.save(output)

        imagen = cv2.imread(output)
        imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        imagen = cv2.threshold(imagen, 150, 255, cv2.THRESH_BINARY)[1]
        texto += pytesseract.image_to_string(imagen, lang='spa')
        os.remove(output)

    return texto

# === Extraer texto desde imagen ===
def extraer_texto_imagen(ruta_imagen):
    imagen = cv2.imread(ruta_imagen)
    imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    imagen = cv2.threshold(imagen, 150, 255, cv2.THRESH_BINARY)[1]
    texto = pytesseract.image_to_string(imagen, lang='spa')
    return texto

# === Obtener valor después de una etiqueta directa ===
def extraer_valor_simple(texto, etiqueta):
    indice = texto.find(etiqueta)
    if indice == -1:
        return None
    inicio = indice + len(etiqueta)
    fin = texto.find('\n', inicio)
    if fin == -1:
        fin = len(texto)
    return texto[inicio:fin].strip()

# === Regex para campos flexibles ===
def extraer_campo_regex(texto, etiqueta):
    patron = re.compile(rf'{etiqueta}\s*(.*)', re.IGNORECASE)
    match = patron.search(texto)
    if match:
        valor = match.group(1).strip()
        fin = valor.find('\n')
        if fin != -1:
            valor = valor[:fin].strip()
        return valor
    return None

def extraer_fecha_emision(texto):
    lineas = texto.splitlines()
    meses = {
        'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03',
        'ABRIL': '04', 'MAYO': '05', 'JUNIO': '06',
        'JULIO': '07', 'AGOSTO': '08', 'SEPTIEMBRE': '09',
        'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12'
    }

    for i in range(len(lineas) - 1):
        l1 = lineas[i].strip()
        if re.search(r'A \d{1,2} DE$', l1):
            dia = re.search(r'A (\d{1,2}) DE$', l1).group(1).zfill(2)
            for j in range(1, 4):
                l2 = lineas[i + j].strip()
                match2 = re.match(r'^([A-ZÑÁÉÍÓÚ]+) DE (\d{4})$', l2, re.IGNORECASE)
                if match2:
                    mes = meses.get(match2.group(1).upper(), '01')
                    anio = match2.group(2)
                    return f"{dia}/{mes}/{anio}"

    for l in lineas:
        match = re.search(r'A (\d{1,2}) DE ([A-ZÑÁÉÍÓÚ]+) DE (\d{4})', l, re.IGNORECASE)
        if match:
            dia = match.group(1).zfill(2)
            mes = meses.get(match.group(2).upper(), '01')
            anio = match.group(3)
            return f"{dia}/{mes}/{anio}"

    texto_unido = texto.replace('\n', ' ')
    match = re.search(
        r'A (\d{1,2}) DE .*? ([A-ZÑÁÉÍÓÚ]+) DE (\d{4})',
        texto_unido,
        re.IGNORECASE
    )
    if match:
        dia = match.group(1).zfill(2)
        mes = meses.get(match.group(2).upper(), '01')
        anio = match.group(3)
        return f"{dia}/{mes}/{anio}"

    return None

def extraer_codigo_postal(texto):
    indice = texto.find('CódigoPostal:')
    if indice == -1:
        return None
    inicio = indice + len('CódigoPostal:')
    fin = inicio + 5
    valor = texto[inicio:fin]
    return valor.strip()

def extraer_datos(texto):
    datos = {}
    datos['rfc'] = extraer_valor_simple(texto, 'RFC: ')
    datos['fecha_emision'] = extraer_fecha_emision(texto)

    razon_social = extraer_valor_simple(texto, 'Denominación/RazónSocial:')
    if razon_social:
        datos['tipo_contribuyente'] = 'MORAL'
        datos['razon_social'] = razon_social
        datos['regimen_capital'] = extraer_valor_simple(texto, 'RégimenCapital:')
        datos['nombre_comercial'] = extraer_valor_simple(texto, 'NombreComercial:')
        if datos['nombre_comercial'] == '':
            datos['nombre_comercial'] = None
        datos['nombre'] = None
        datos['apellido_paterno'] = None
        datos['apellido_materno'] = None
    else:
        datos['tipo_contribuyente'] = 'FISICA'
        datos['razon_social'] = None
        datos['regimen_capital'] = None
        datos['nombre_comercial'] = None
        datos['nombre'] = extraer_campo_regex(texto, r'Nombre\s*\(s\)\s*:')
        if datos['nombre'] and ' ' not in datos['nombre']:
            datos['nombre'] = ' '.join(n.upper() for n in segment(datos['nombre'].lower()))
        datos['curp'] = extraer_valor_simple(texto, 'CURP:')
        datos['apellido_paterno'] = extraer_valor_simple(texto, 'PrimerApellido:')
        datos['apellido_materno'] = extraer_valor_simple(texto, 'SegundoApellido:')

    datos['estatus_padron'] = extraer_valor_simple(texto, 'Estatusenelpadrón:')
    datos['codigo_postal'] = extraer_codigo_postal(texto)

    if datos['rfc'] is None or datos['fecha_emision'] is None:
        return None

    for campo in ['razon_social', 'regimen_capital', 'nombre_comercial', 'nombre']:
        if datos.get(campo):
            datos[campo] = separar_palabras_mayusculas(datos[campo])

    return datos

def procesar_archivo(ruta_archivo):
    archivo = os.path.basename(ruta_archivo)
    nombre_sin_ext, _ = os.path.splitext(archivo)

    print(f"↪ Procesando: {archivo} ...")
    logging.info(f"Iniciando procesamiento de {archivo}")

    try:
        extension = os.path.splitext(ruta_archivo)[1].lower()
        if extension == '.pdf':
            texto = extraer_texto_pdf(ruta_archivo)
        elif extension in ['.png', '.jpg', '.jpeg']:
            texto = extraer_texto_imagen(ruta_archivo)
        else:
            logging.warning(f"Extensión no soportada: {archivo}")
            return None

        datos = extraer_datos(texto)
        if datos:
            datos['archivo_origen'] = archivo

            # Normalizar fecha_emision (formato compatible con SQL Server)
            try:
                datos['fecha_emision'] = datetime.strptime(datos['fecha_emision'], "%d/%m/%Y").date()
            except:
                datos['fecha_emision'] = None

            datos['fecha_procesado'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


            # 📌 Verificación de RFC duplicado
            if existe_rfc(datos['rfc']):
                print(f"   ⚠️ RFC duplicado, se mueve a errores: {datos['rfc']}")
                logging.warning(f"Duplicado detectado para RFC {datos['rfc']}, no se guarda.")
                shutil.move(ruta_archivo, os.path.join(RUTA_ERRORES, archivo))
                return None

            # Guardado normal
            guardar_datos(datos)
            destino_pdf = os.path.join(RUTA_PROCESADOS, archivo)
            shutil.move(ruta_archivo, destino_pdf)

            # Guardar texto extraído
            ruta_txt = os.path.join(RUTA_PROCESADOS, f"{nombre_sin_ext}_ocr.txt")
            with open(ruta_txt, 'w', encoding='utf-8') as f:
                f.write(texto)

            print(f"   ✅ OK → {datos.get('tipo_contribuyente','?').upper()} | RFC {datos.get('rfc','?')} | {destino_pdf}")
            logging.info(f"Procesado correctamente: {archivo}")
        else:
            print(f"   ⚠️ No se extrajeron datos de: {archivo}")
            logging.warning(f"No se extrajeron datos de: {archivo}")
            shutil.move(ruta_archivo, os.path.join(RUTA_ERRORES, archivo))

    except Exception as e:
        shutil.move(ruta_archivo, os.path.join(RUTA_ERRORES, archivo))
        print(f"   ❌ Error crítico con {archivo}: {e}")
        logging.error(f"Error crítico en {archivo}: {e}")

    return None
