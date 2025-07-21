import fitz
import pytesseract
import cv2
import pdfplumber
import re
import os

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
    datos['fecha_emision'] = extraer_valor_simple(texto, 'GUADALAJARA , JALISCO A ')
    
    # Después de capturar el valor
    datos['razon_social'] = extraer_valor_simple(texto, 'Denominación/RazónSocial:')
    datos['regimen_capital'] = extraer_valor_simple(texto, 'RégimenCapital:')
    datos['nombre_comercial'] = extraer_valor_simple(texto, 'NombreComercial:')
    
    datos['estatus_padron'] = extraer_valor_simple(texto, 'Estatusenelpadrón:')
    datos['codigo_postal'] = extraer_codigo_postal(texto)

    if any(valor is None for valor in datos.values()):
        print("⚠️ Faltan datos:", datos)
        return None

    return datos

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
    return datos
