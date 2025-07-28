import fitz  # PyMuPDF, para trabajar con PDFs como imágenes
import pytesseract  # OCR para reconocimiento de texto en imágenes
import cv2  # OpenCV, para procesar imágenes
import pdfplumber  # Para extraer texto directamente desde PDFs
import re  # Expresiones regulares
import os  # Para manejo de archivos
import datetime  # Para obtener fecha y hora actual

# Extrae texto de un archivo PDF, usando pdfplumber o, si no es posible, OCR sobre imágenes de las páginas
def extraer_texto_pdf(ruta_pdf):
    texto = ''

    # Intenta extraer texto directamente con pdfplumber
    with pdfplumber.open(ruta_pdf) as pdf:
        for pagina in pdf.pages:
            pagina_texto = pagina.extract_text()
            if pagina_texto:
                texto += pagina_texto + '\n'

    # Si se extrajo texto, retornarlo
    if texto.strip():
        return texto

    # Si no hay texto, se hace OCR sobre las páginas como imágenes
    texto = ''
    documento = fitz.open(ruta_pdf)
    for pagina in documento:
        # Renderiza la página como imagen
        pix = pagina.get_pixmap()
        output = f'pagina_temp.png'
        pix.save(output)

        # Lee la imagen, la convierte a escala de grises y aplica binarización
        imagen = cv2.imread(output)
        imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        imagen = cv2.threshold(imagen, 150, 255, cv2.THRESH_BINARY)[1]
        # Extrae texto con OCR
        texto += pytesseract.image_to_string(imagen, lang='spa')

        # Elimina el archivo temporal
        os.remove(output)

    return texto

# Extrae texto de una imagen con OCR
def extraer_texto_imagen(ruta_imagen):
    imagen = cv2.imread(ruta_imagen)
    imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    imagen = cv2.threshold(imagen, 150, 255, cv2.THRESH_BINARY)[1]
    texto = pytesseract.image_to_string(imagen, lang='spa')
    return texto

# Extrae el valor simple que sigue después de una etiqueta en el texto
def extraer_valor_simple(texto, etiqueta):
    indice = texto.find(etiqueta)
    if indice == -1:
        return None

    inicio = indice + len(etiqueta)
    fin = texto.find('\n', inicio)
    if fin == -1:
        fin = len(texto)

    return texto[inicio:fin].strip()

# Extrae múltiples datos estructurados desde un texto completo
def extraer_datos(texto):
    datos = {}
    datos['rfc'] = extraer_valor_simple(texto, 'RFC: ')
    datos['fecha_emision'] = extraer_fecha_emision(texto)

    # Si es persona moral (empresa)
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
        # Si es persona física
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

    # Validación mínima de datos esenciales
    if datos['rfc'] is None or datos['fecha_emision'] is None:
        print("⚠️ Faltan datos esenciales:", datos)
        return None

    return datos

# Extrae el valor que sigue a una etiqueta usando expresiones regulares
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

# Busca una fecha en el texto y la normaliza al formato dd/mm/yyyy
def extraer_fecha_emision(texto):
    patron = r'Lugar y Fecha de Emisión\s+.*?A\s+(\d{2} DE [A-ZÑÁÉÍÓÚ]+ DE \d{4})'
    match = re.search(patron, texto, re.IGNORECASE)

    if match:
        fecha_texto = match.group(1).strip()
        fecha_texto = normalizar_fecha(fecha_texto)
        return fecha_texto

    return None

# Convierte una fecha tipo "28 DE JULIO DE 2025" a "28/07/2025"
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

    return fecha_texto  # Si falla el formato, se devuelve como estaba

# Extrae un código postal de exactamente 5 dígitos después de la etiqueta
def extraer_codigo_postal(texto):
    indice = texto.find('CódigoPostal:')
    if indice == -1:
        return None

    inicio = indice + len('CódigoPostal:')
    fin = inicio + 5
    valor = texto[inicio:fin]

    return valor.strip()

# Corrige errores de OCR en textos que juntan palabras en mayúscula
def corregir_texto_concatenado(texto):
    if not texto:
        return texto
    # Agrega espacio antes de cada letra mayúscula que no sea inicial
    texto_corregido = re.sub(r'(?<!^)([A-ZÑÁÉÍÓÚ])', r' \1', texto)
    return texto_corregido.strip()

# Función principal: procesa un archivo PDF o imagen y devuelve los datos extraídos
def procesar_archivo(ruta_archivo):
    extension = os.path.splitext(ruta_archivo)[1].lower()

    # Selección según tipo de archivo
    if extension == '.pdf':
        texto = extraer_texto_pdf(ruta_archivo)
    elif extension in ['.png', '.jpg', '.jpeg']:
        texto = extraer_texto_imagen(ruta_archivo)
    else:
        return None

    # Guarda el texto extraído en archivo temporal para revisar
    with open('texto_extraido.txt', 'w', encoding='utf-8') as f:
        f.write(texto)

    # Extrae datos estructurados
    datos = extraer_datos(texto)
    datos['archivo_origen'] = os.path.basename(ruta_archivo)
    datos['fecha_procesado'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return datos
