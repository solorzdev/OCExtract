import fitz
import pytesseract
import cv2
import pdfplumber
import re
import os
import datetime
from wordsegment import load, segment

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

# === Fecha de emisión y normalización ===
def extraer_fecha_emision(texto):
    patron = r'Lugar y Fecha de Emisión\s+.*?A\s+(\d{2} DE [A-ZÑÁÉÍÓÚ]+ DE \d{4})'
    match = re.search(patron, texto, re.IGNORECASE)
    if match:
        fecha_texto = match.group(1).strip()
        return normalizar_fecha(fecha_texto)
    return None

def normalizar_fecha(fecha_texto):
    meses = {
        'ENERO': '01', 'FEBRERO': '02', 'MARZO': '03', 'ABRIL': '04',
        'MAYO': '05', 'JUNIO': '06', 'JULIO': '07', 'AGOSTO': '08',
        'SEPTIEMBRE': '09', 'OCTUBRE': '10', 'NOVIEMBRE': '11', 'DICIEMBRE': '12'
    }
    partes = fecha_texto.upper().split(' DE ')
    if len(partes) == 3:
        dia = partes[0].zfill(2)
        mes = meses.get(partes[1], '01')
        anio = partes[2]
        return f"{dia}/{mes}/{anio}"
    return fecha_texto

# === Código postal ===
def extraer_codigo_postal(texto):
    indice = texto.find('CódigoPostal:')
    if indice == -1:
        return None
    inicio = indice + len('CódigoPostal:')
    fin = inicio + 5
    valor = texto[inicio:fin]
    return valor.strip()

# === Extrae y limpia todos los datos ===
def extraer_datos(texto):
    datos = {}
    datos['rfc'] = extraer_valor_simple(texto, 'RFC: ')
    datos['fecha_emision'] = extraer_fecha_emision(texto)

    razon_social = extraer_valor_simple(texto, 'Denominación/RazónSocial:')
    if razon_social:
        datos['tipo_contribuyente'] = 'empresa'
        datos['razon_social'] = razon_social
        datos['regimen_capital'] = extraer_valor_simple(texto, 'RégimenCapital:')
        datos['nombre_comercial'] = extraer_valor_simple(texto, 'NombreComercial:')
        datos['nombre'] = None
        datos['apellido_paterno'] = None
        datos['apellido_materno'] = None
    else:
        datos['tipo_contribuyente'] = 'persona'
        datos['razon_social'] = None
        datos['regimen_capital'] = None
        datos['nombre_comercial'] = None
        datos['nombre'] = extraer_campo_regex(texto, r'Nombre\s*\(s\)\s*:')
        datos['curp'] = extraer_valor_simple(texto, 'CURP:')
        datos['apellido_paterno'] = extraer_valor_simple(texto, 'PrimerApellido:')
        datos['apellido_materno'] = extraer_valor_simple(texto, 'SegundoApellido:')

    datos['estatus_padron'] = extraer_valor_simple(texto, 'Estatusenelpadrón:')
    datos['codigo_postal'] = extraer_codigo_postal(texto)

    if datos['rfc'] is None or datos['fecha_emision'] is None:
        print("⚠️ Faltan datos esenciales:", datos)
        return None

    # Corrección inteligente para campos pegados
    for campo in ['razon_social', 'regimen_capital', 'nombre_comercial', 'nombre']:
        if datos.get(campo):
            datos[campo] = separar_palabras_mayusculas(datos[campo])

    return datos

# === Proceso principal ===
def procesar_archivo(ruta_archivo):
    extension = os.path.splitext(ruta_archivo)[1].lower()
    if extension == '.pdf':
        texto = extraer_texto_pdf(ruta_archivo)
    elif extension in ['.png', '.jpg', '.jpeg']:
        texto = extraer_texto_imagen(ruta_archivo)
    else:
        return None

    with open('texto_extraido.txt', 'w', encoding='utf-8') as f:
        f.write(texto)

    datos = extraer_datos(texto)
    if datos:
        datos['archivo_origen'] = os.path.basename(ruta_archivo)
        datos['fecha_procesado'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return datos
