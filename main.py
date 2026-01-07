import sys
import threading
from PyQt5.QtCore import pyqtSignal
import ctypes
import urllib.request
import shutil
import pytesseract
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QGuiApplication
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QColorDialog, QComboBox, QRubberBand, QProgressBar, QMessageBox
from PIL import Image, ImageEnhance
import os
from datetime import date
from deep_translator import GoogleTranslator

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) ##Ajusta el proceso para el escalado de la pantalla
except Exception:
    pass

# Ruta por defecto de Tesseract (mira a ver si puedes hacer que lo encuentre solo)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class VentanaOCR(QMainWindow):
    senalResultadoOcr = pyqtSignal(str)
    senalProgresoDescarga = pyqtSignal(int)
    senalEstadoDescarga = pyqtSignal(str)
    senalScriptDetectado = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Traductor")
        self.setGeometry(100, 100, 900, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.7)
        self.botonSeleccionar = QPushButton("⬚", self)
        self.botonSeleccionar.setGeometry(10, 5, 30, 30)

        self.botonPausa = QPushButton("▶", self)
        self.botonPausa.setGeometry(50, 5, 30, 30)

        self.botonCaptura = QPushButton("📷", self)
        self.botonCaptura.setGeometry(90, 5, 30, 30)

        # mapa (display, tesseract_code, google_code)
        idiomas = [
            ("Chino", 'chi_sim', 'zh-CN'),
            ("Español", 'spa', 'es'),
            ("Inglés", 'eng', 'en'),
            ("Hindi", 'hin', 'hi'),
            ("Bengalí", 'ben', 'bn'),
            ("Portugués", 'por', 'pt'),
            ("Ruso", 'rus', 'ru'),
            ("Japonés", 'jpn', 'ja'),
            ("Punjabi", 'pan', 'pa'),
            ("Maratí", 'mar', 'mr'),
            ("Telugú", 'tel', 'te'),
            ("Turco", 'tur', 'tr'),
            ("Coreano", 'kor', 'ko'),
            ("Francés", 'fra', 'fr'),
            ("Alemán", 'deu', 'de'),
            ("Vietnamita", 'vie', 'vi'),
            ("Italiano", 'ita', 'it'),
            ("Tailandés", 'tha', 'th'),
            ("Gujarati", 'guj', 'gu'),
            ("Polaco", 'pol', 'pl'),
            ("Ucraniano", 'ukr', 'uk'),
            ("Persa", 'fas', 'fa'),
            ("Holandés", 'nld', 'nl'),
            ("Rumano", 'ron', 'ro'),
            ("Griego", 'ell', 'el'),
            ("Checo", 'ces', 'cs'),
            ("Sueco", 'swe', 'sv'),
            ("Hebreo", 'heb', 'he'),
            ("Húngaro", 'hun', 'hu'),
            ("Kannada", 'kan', 'kn')
        ]

        self.idiomas_lista = idiomas
        self.mapa_idiomas = {name: tess for (name, tess, google) in idiomas}
        self.mapa_google = {tess: google for (name, tess, google) in idiomas}
        # Variables de UI
        self.comboIdioma = QComboBox(self)
        self.comboIdioma.setGeometry(130, 5, 120, 30)
        self.comboIdioma.addItems([name for (name, _, _) in idiomas])
        self.comboDestino = QComboBox(self)
        self.comboDestino.setGeometry(260, 5, 120, 30)
        self.comboDestino.addItems([name for (name, _, _) in idiomas])
        self.comboDestino.setCurrentText('Español')
        self.colorFondo = QColor(50, 50, 50)
        # Botones de control
        self.botonColor = QPushButton("●", self)
        self.botonColor.setGeometry(390, 5, 30, 30)
        self.botonMinimizar = QPushButton("−", self)
        self.botonMinimizar.setGeometry(830, 5, 30, 30)
        self.botonCerrar = QPushButton("×", self)
        self.botonCerrar.setGeometry(870, 5, 30, 30)
        # Etiqueta de texto
        self.etiquetaTexto = QLabel("Selecciona una región para comenzar", self)
        self.etiquetaTexto.setStyleSheet("color: white; font-size: 18px; font-weight: bold; padding: 10px;")
        self.etiquetaTexto.setWordWrap(True)
        self.etiquetaTexto.setAlignment(Qt.AlignCenter)
        self.etiquetaTexto.setGeometry(10, 50, 880, 240)
        # Variables de estado
        self.ocrEnEjecucion = False
        self.ocrPausado = True
        self.modoContinuo = False
        self.regionOcr = None
        self.timer = None
        # Conectar señales
        self.senalResultadoOcr.connect(self.actualizar_etiqueta)
        self.senalProgresoDescarga.connect(self.alProgresoDescarga)
        self.senalEstadoDescarga.connect(self.alEstadoDescarga)
        # Configurar registro
        try:
            self.logDir = os.path.join(os.getcwd(), 'registro')
            os.makedirs(self.logDir, exist_ok=True)
            fecha_base = date.today().strftime('%Y-%m-%d')
            filename = f"{fecha_base}.txt"
            i = 1
            while os.path.exists(os.path.join(self.logDir, filename)):
                filename = f"{fecha_base}-{i}.txt"
                i += 1
            self.logFilePath = os.path.join(self.logDir, filename)
        except Exception:
            self.logDir = None
            self.logFilePath = None
        # Barra de progreso para descargas
        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(10, 40, 400, 10)
        self.progressBar.setVisible(False)

        self.comboIdioma.currentIndexChanged.connect(self.alCambiarIdiomaOrigen) #Mapeo
        # Conectar señal de script detectado
        self.senalScriptDetectado.connect(self.alScriptDetectado)
        self.botonSeleccionar.clicked.connect(self.seleccionarRegion)
        self.botonPausa.clicked.connect(self.alternarPausa)
        self.botonCaptura.clicked.connect(self.tomarSnapshot)
        self.botonColor.clicked.connect(self.cambiarColor)
        self.botonMinimizar.clicked.connect(self.showMinimized)
        self.botonCerrar.clicked.connect(self.close)

    def seleccionarRegion(self):
        self.hide()
        self.regionSelector = SelectorRegion()
        self.regionSelector.region_seleccionada.connect(self.establecerRegionOcr)
        self.regionSelector.show()
        
    def establecerRegionOcr(self, x, y, w, h):
        self.regionOcr = (x, y, w, h)
        self.show()
        # Detectar script/idioma de forma ligera en background
        try:
            self.detectarScriptYConfigurarIdioma()
        except Exception:
            pass
        if self.modoContinuo and not self.ocrPausado:
            self.iniciarOcrContinuo()
        self.etiquetaTexto.setText("Región seleccionada")
        
    def alternarPausa(self):
        if not self.modoContinuo:
            self.modoContinuo = True
            self.ocrPausado = False
            self.botonPausa.setText("⏸")
            if self.regionOcr:
                self.iniciarOcrContinuo()
                self.etiquetaTexto.setText("OCR continuo iniciado")
            else:
                self.etiquetaTexto.setText("Selecciona una región primero")
        else:
            self.ocrPausado = not self.ocrPausado
            self.botonPausa.setText("▶" if self.ocrPausado else "⏸")
            if self.ocrPausado:
                self.detenerOcrContinuo()
                self.etiquetaTexto.setText("OCR pausado")
            elif self.regionOcr:
                self.iniciarOcrContinuo()
            
    def tomarSnapshot(self):
        if not self.regionOcr:
            self.etiquetaTexto.setText("Selecciona una región primero")
            return
        self.modoContinuo = False
        self.detenerOcrContinuo()
        if not self.ocrEnEjecucion:
            self.ocrEnEjecucion = True
            threading.Thread(target=self.realizar_ocr, daemon=True).start()
            
    def iniciarOcrContinuo(self):
        self.modoContinuo = True
        if self.timer:
            self.killTimer(self.timer)
        self.timer = self.startTimer(700)
        
    def detenerOcrContinuo(self):
        if self.timer:
            self.killTimer(self.timer)
            self.timer = None

    def alCambiarIdiomaOrigen(self, idx):
        # Cuando se cambia el idioma origen, comprobar si existe el traineddata
        try:
            nombre = self.comboIdioma.currentText()
            tess_code = self.mapa_idiomas.get(nombre)
            if tess_code:
                tess_path = os.path.join(r"C:\Program Files\Tesseract-OCR\tessdata", f"{tess_code}.traineddata")
                if not os.path.exists(tess_path):
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Warning)
                    msg.setWindowTitle("Falta traineddata")
                    msg.setText(f"No se encontró {tess_code}.traineddata en la carpeta de tessdata.")
                    msg.setInformativeText("¿Desea descargarlo desde el repositorio oficial? (requiere permisos de escritura en Program Files)")
                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    ret = msg.exec_()
                    if ret == QMessageBox.Yes:
                        # Iniciar descarga
                        threading.Thread(target=self.descargarTrainedData, args=(tess_code, tess_path), daemon=True).start()
        except Exception:
            pass

    def detectarScriptYConfigurarIdioma(self):
        # Lanzar detección en background para no bloquear la UI
        threading.Thread(target=self.trabajadorDeteccionScript, daemon=True).start()

    def trabajadorDeteccionScript(self):
        try:
            if not self.regionOcr:
                return
            pantalla = QGuiApplication.primaryScreen()
            if not pantalla:
                return
            x, y, w, h = self.regionOcr
            captura_pantalla = pantalla.grabWindow(0, x, y, w, h).toImage()
            captura_pantalla = captura_pantalla.convertToFormat(4)
            anchura = captura_pantalla.width()
            altura = captura_pantalla.height()

            puntero = captura_pantalla.bits()
            puntero.setsize(captura_pantalla.byteCount())
            imagen = Image.frombytes("RGBA", (anchura, altura), puntero.asstring())
            imagen = imagen.convert('L')

            # Intentar OSD y comprobar la confianza del script; reintentar si es baja (< 0.6)
            osd = ''
            script = ''
            conf_script = None
            intentos_max = 3
            intento = 0
            while intento < intentos_max:
                intento += 1
                try:
                    osd = pytesseract.image_to_osd(imagen, config='--psm 0')
                except Exception:
                    osd = ''

                # Parsear script y confianza
                script = ''
                conf_script = None
                for line in (osd or '').splitlines():
                    if ':' not in line:
                        continue
                    key_part, val_part = line.split(':', 1)
                    key_l = key_part.strip().lower()
                    val = val_part.strip()
                    if 'script' == key_l or key_l.startswith('script'):
                        # puede ser 'script' o 'script confidence'
                        # Si la línea es 'script: Han' -> key_l == 'script'
                        if key_l == 'script':
                            script = val
                        elif 'confidence' in key_l:
                            try:
                                conf_script = float(val) / 100.0
                            except Exception:
                                try:
                                    conf_script = float(val)
                                except Exception:
                                    conf_script = None

                # Si no obtuvimos confianza, buscar línea 'script confidence' explícita
                if conf_script is None:
                    for line in (osd or '').splitlines():
                        if 'script confidence' in line.lower():
                            try:
                                conf_script = float(line.split(':', 1)[1].strip()) / 100.0
                            except Exception:
                                conf_script = None

                # Si tenemos conf_script y es baja, reintentar OSD (hasta intentos_max)
                if conf_script is not None and conf_script < 0.6 and intento < intentos_max:
                    continue
                break

            # Mapeo robusto de script -> idioma a seleccionar (usar claves en minúsculas)
            script_map = {
                'latin': 'Inglés', 'latín': 'Inglés',
                'han': 'Japonés', 'han script': 'Japonés', 'chinese': 'Chino',
                'hiragana': 'Japonés', 'katakana': 'Japonés', 'japanese': 'Japonés',
                'hangul': 'Coreano', 'hangul syllables': 'Coreano',
                'cyrillic': 'Ruso', 'devanagari': 'Hindi', 'arabic': 'Persa',
                'hebrew': 'Hebreo', 'greek': 'Griego', 'thai': 'Tailandés',
                'bengali': 'Bengalí', 'kannada': 'Kannada', 'gujarati': 'Gujarati',
                'tamil': 'Tamil', 'telugu': 'Telugú'
            }

            lang_name = 'Inglés'
            if script:
                key = script.strip().lower()
                if key in script_map:
                    lang_name = script_map[key]
                else:
                    for k, v in script_map.items():
                        if k in key:
                            lang_name = v
                            break

            # Emitir también la confianza como parte del flujo (opcional)
            self.senalScriptDetectado.emit(lang_name)
        except Exception:
            try:
                self.senalScriptDetectado.emit('Inglés')
            except Exception:
                pass

    def alScriptDetectado(self, language_name):
        # Actualiza combo de idioma origen con el idioma detectado
        try:
            if language_name in self.mapa_idiomas:
                self.comboIdioma.setCurrentText(language_name)
                self.etiquetaTexto.setText(f"Idioma detectado: {language_name}")
            else:
                # Fallback a Inglés para escrituras latinas u desconocidas
                self.comboIdioma.setCurrentText('Inglés')
                self.etiquetaTexto.setText(f"Idioma detectado: Inglés")
        except Exception:
            pass

    def alProgresoDescarga(self, value):
        self.progressBar.setVisible(True)
        self.progressBar.setValue(value)

    def alEstadoDescarga(self, status_text):
        if status_text == 'done':
            self.progressBar.setVisible(False)
            self.etiquetaTexto.setText('Descarga completada')
        else:
            self.progressBar.setVisible(False)
            self.etiquetaTexto.setText(status_text)

    def descargarTrainedData(self, tess_code, dest_path):
        base_url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata/master/{tess_code}.traineddata"
        try:
            solicitud = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(solicitud) as respuesta:
                total_bytes = respuesta.getheader('Content-Length')
                if total_bytes:
                    total_bytes = int(total_bytes)
                ruta_tmp = dest_path + '.part'
                try:
                    with open(ruta_tmp, 'wb') as archivo_salida:
                        descargado = 0
                        tam_bloque = 8192
                        while True:
                            bloque = respuesta.read(tam_bloque)
                            if not bloque:
                                break
                            archivo_salida.write(bloque)
                            descargado += len(bloque)
                            if total_bytes:
                                perc = int(descargado * 100 / total_bytes)
                                self.senalProgresoDescarga.emit(perc)
                except PermissionError:
                    # No permisos para escribir en Program Files
                    self.senalEstadoDescarga.emit('No hay permisos para escribir en la carpeta de Tesseract. Ejecuta el programa como administrador o copia manualmente el archivo.')
                    # limpiar tmp
                    try:
                        if os.path.exists(ruta_tmp):
                            os.remove(ruta_tmp)
                    except Exception:
                        pass
                    return

                # Intentar mover el archivo temporal a la ruta final
                try:
                    shutil.move(ruta_tmp, dest_path)
                    self.senalEstadoDescarga.emit('done')
                except PermissionError:
                    self.senalEstadoDescarga.emit('No hay permisos para mover el archivo a la carpeta de Tesseract. Ejecuta como administrador.')
                    try:
                        if os.path.exists(ruta_tmp):
                            os.remove(ruta_tmp)
                    except Exception:
                        pass
        except Exception as e:
            self.senalEstadoDescarga.emit(f"Error descarga: {str(e)}")
            
    def timerEvent(self, event):
        if event.timerId() == self.timer and self.modoContinuo and not self.ocrPausado and not self.ocrEnEjecucion and self.regionOcr:
            self.ocrEnEjecucion = True
            threading.Thread(target=self.realizar_ocr, daemon=True).start()

    def realizar_ocr(self):
        try:
            pantalla = QGuiApplication.primaryScreen()
            if not pantalla:
                self.senalResultadoOcr.emit("No se pudo obtener la pantalla.")
                return

            x, y, w, h = self.regionOcr
            captura_pantalla = pantalla.grabWindow(0, x, y, w, h).toImage()
            captura_pantalla = captura_pantalla.convertToFormat(4)
            anchura = captura_pantalla.width()
            altura = captura_pantalla.height()

            ptr = captura_pantalla.bits()
            ptr.setsize(captura_pantalla.byteCount())
            imagen = Image.frombytes("RGBA", (anchura, altura), ptr.asstring())

            imagen = imagen.convert('L')
            enhancer = ImageEnhance.Contrast(imagen)
            imagen = enhancer.enhance(2.0)

            config_personalizada = r'--oem 3 --psm 6'
            idiomaOrigenText = self.comboIdioma.currentText()
            idiomaDestinoText = self.comboDestino.currentText()
            tesseractLang = self.mapa_idiomas[idiomaOrigenText]

            texto = pytesseract.image_to_string(imagen, lang=tesseractLang, config=config_personalizada)

            textoMostrado = ""
            if texto.strip():
                try:
                    idiomaOrigenCod = self.mapa_google.get(tesseractLang, tesseractLang)
                    tessObjetivo = self.mapa_idiomas.get(idiomaDestinoText, 'spa')
                    idiomaObjetivoCod = self.mapa_google.get(tessObjetivo, tessObjetivo)
                    # Redundante check
                    if idiomaOrigenCod == idiomaObjetivoCod:
                        textoMostrado = texto
                    else:
                        textoMostrado = GoogleTranslator(source=idiomaOrigenCod, target=idiomaObjetivoCod).translate(texto)
                except Exception as e:
                    textoMostrado = f"Error: {str(e)}"
            else:
                textoMostrado = "No se encontró texto"
            self.senalResultadoOcr.emit(textoMostrado)
        finally:
            self.ocrEnEjecucion = False

    def actualizar_etiqueta(self, shown_text):
        if self.modoContinuo and self.ocrPausado:
            self.etiquetaTexto.setText("OCR pausado")
            self.etiquetaTexto.repaint()
            return

        self.etiquetaTexto.setText(shown_text)
        self.etiquetaTexto.repaint()

        # Registro
        try:
            excluded = {
                "OCR pausado", "Región seleccionada", "Selecciona una región primero",
                "No se pudo obtener la pantalla.", "No se encontró texto"
            }
            if self.logFilePath and shown_text and shown_text.strip() and shown_text not in excluded:
                self.agregarAlRegistro(shown_text)
        except Exception:
            pass

    def agregarAlRegistro(self, text):
        if not self.logFilePath:
            return
        try:
            with open(self.logFilePath, 'a', encoding='utf-8') as f:
                f.write(text.replace('\r', '') + '\n')
        except Exception:
            pass


        
    def cambiar_color(self):
        color = QColorDialog.getColor(self.color_fondo, self)
        if color.isValid():
            self.color_fondo = color
            self.actualizar_estilos_botones()
            self.update()
    
    def actualizar_estilos_botones(self):
        darker_color = self.color_fondo.darker(130)
        
        button_style = f"""
        QPushButton {{
            background-color: rgb({darker_color.red()}, {darker_color.green()}, {darker_color.blue()});
            color: white;
            border: none;
            font-size: 16px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: #f0f0f0;
        }}
        """
        
        self.botonSeleccionar.setStyleSheet(button_style)
        self.botonPausa.setStyleSheet(button_style)
        self.botonCaptura.setStyleSheet(button_style)
        self.botonColor.setStyleSheet(button_style)
        self.botonMinimizar.setStyleSheet(button_style)
        self.botonCerrar.setStyleSheet(button_style)
        
        combo_style = f"""
        QComboBox {{
            background-color: white;
            color: black;
            border: none;
            font-size: 12px;
            padding: 2px;
        }}
        QComboBox::drop-down {{
            border: none;
        }}
        """
        self.comboIdioma.setStyleSheet(combo_style)
        if hasattr(self, 'comboDestino'):
            self.comboDestino.setStyleSheet(combo_style)

    def update_button_styles(self):
        self.actualizar_estilos_botones()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.color_fondo)
        
        # Barra superior más oscura
        darker_color = self.color_fondo.darker(130)
        painter.fillRect(0, 0, self.width(), 40, darker_color)
        
        self.update_button_styles()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.ocrPausado = True
            self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()
    def mouseReleaseEvent(self, event):
        self.ocrPausado = False
        super().mouseReleaseEvent(event)

class SelectorRegion(QMainWindow):
    region_seleccionada = pyqtSignal(int, int, int, int)
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.showFullScreen()
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubberBand.setGeometry(self.origin.x(), self.origin.y(), 0, 0)
            self.rubberBand.show()
            
    def mouseMoveEvent(self, event):
        if self.origin:
            self.rubberBand.setGeometry(min(self.origin.x(), event.x()),
                                       min(self.origin.y(), event.y()),
                                       abs(event.x() - self.origin.x()),
                                       abs(event.y() - self.origin.y()))
            
    def mouseReleaseEvent(self, event):
        if self.origin:
            rect = self.rubberBand.geometry()
            self.region_seleccionada.emit(rect.x(), rect.y(), rect.width(), rect.height())
            self.close()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VentanaOCR()
    window.show()
    sys.exit(app.exec_())