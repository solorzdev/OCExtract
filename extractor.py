import fitz
import pytesseract
import cv2
import pdfplumber
import re
import os
import datetime

def extraer_texto_pdf(ruta_pdf):
    texto = ''

    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            pagina_texto = pagina.extract_text()
            if pagina_texto:
                texto += pagina_texto + '\n'

    if texto.strip():
        return texto  # Si pdfplumber logró extraer texto, usarlo.

    # Si no extrajo texto, hacer OCR sobre las páginas como imágenes
    texto = ''
    documento = fitz.open(ruta_pdf)
    for pagina in documento:
        pix = pagina.get_pixmap()
        output = f'pagina_temp.png'
        pix.save(output)

        imagen = cv2.imread(output)
        imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        imagen = cv2.threshold(imagen, 150, 255, cv2.THRESH_BINARY)[1]
        texto += pytesseract.image_to_string(imagen, lang='spa')

        os.remove(output)

    return texto

def extraer_texto_imagen(ruta_imagen):
    imagen = cv2.imread(ruta_imagen)
    imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    imagen = cv2.threshold(imagen, 150, 255, cv2.THRESH_BINARY)[1]
    texto = pytesseract.image_to_string(imagen, lang='spa')
    return texto

def extraer_valor_simple(texto, etiqueta):
    indice = texto.find(etiqueta)
    if indice == -1:
        return None

    inicio = indice + len(etiqueta)
    fin = texto.find('\n', inicio)
    if fin == -1:
        fin = len(texto)

    return texto[inicio:fin].strip()

def extraer_datos(texto):
    datos = {}
    datos['rfc'] = extraer_valor_simple(texto, 'RFC: ')
    datos['fecha_emision'] = extraer_fecha_emision(texto)

    # Lógica simple: si encuentra razon_social, es empresa
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

    return datos

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
    # Busca luego de "Lugar y Fecha de Emisión" (permitiendo cualquier lugar antes)
    patron = r'Lugar y Fecha de Emisión\s+.*?A\s+(\d{2} DE [A-ZÑÁÉÍÓÚ]+ DE \d{4})'
    match = re.search(patron, texto, re.IGNORECASE)

    if match:
        fecha_texto = match.group(1).strip()
        # Opcional: convertir a formato dd/mm/yyyy
        fecha_texto = normalizar_fecha(fecha_texto)
        return fecha_texto

    return None

def normalizar_fecha(fecha_texto):
    meses = {
        'ENERO': '01',
        'FEBRERO': '02',
        'MARZO': '03',
        'ABRIL': '04',
        'MAYO': '05',
        'JUNIO': '06',
        'JULIO': '07',
        'AGOSTO': '08',
        'SEPTIEMBRE': '09',
        'OCTUBRE': '10',
        'NOVIEMBRE': '11',
        'DICIEMBRE': '12'
    }

    partes = fecha_texto.upper().split(' DE ')
    if len(partes) == 3:
        dia = partes[0].zfill(2)
        mes = meses.get(partes[1], '01')
        anio = partes[2]
        return f"{dia}/{mes}/{anio}"

    return fecha_texto  # Devuelve sin cambios si no pudo normalizar

def extraer_codigo_postal(texto):
    indice = texto.find('CódigoPostal:')
    if indice == -1:
        return None

    inicio = indice + len('CódigoPostal:')
    fin = inicio + 5  # Solo 5 dígitos exactos
    valor = texto[inicio:fin]

    return valor.strip()

def corregir_texto_concatenado(texto):
    if not texto:
        return texto
    # Inserta espacio antes de cada letra mayúscula interna
    texto_corregido = re.sub(r'(?<!^)([A-ZÑÁÉÍÓÚ])', r' \1', texto)
    return texto_corregido.strip()

def procesar_archivo(ruta_archivo):
    extension = os.path.splitext(ruta_archivo)[1].lower()

    if extension == '.pdf':
        texto = extraer_texto_pdf(ruta_archivo)
    elif extension in ['.png', '.jpg', '.jpeg']:
        texto = extraer_texto_imagen(ruta_archivo)
    else:
        return None

    # NUEVO: guarda el texto extraído para revisar
    with open('texto_extraido.txt', 'w', encoding='utf-8') as f:
        f.write(texto)

    datos = extraer_datos(texto)
    datos['archivo_origen'] = os.path.basename(ruta_archivo)
    datos['fecha_procesado'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return datos
