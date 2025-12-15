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
    resultado_ocr_signal = pyqtSignal(str)
    download_progress_signal = pyqtSignal(int)
    download_status_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Traductor")
        self.setGeometry(100, 100, 900, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.7)
        self.boton_seleccionar = QPushButton("⬚", self)
        self.boton_seleccionar.setGeometry(10, 5, 30, 30)

        self.boton_pausa = QPushButton("▶", self)
        self.boton_pausa.setGeometry(50, 5, 30, 30)

        self.boton_captura = QPushButton("📷", self)
        self.boton_captura.setGeometry(90, 5, 30, 30)

        # mapa (display, tesseract_code, google_code)
        idiomas = [
            ("Chino", 'chi_sim', 'zh'),
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

        self.combo_idioma = QComboBox(self)
        self.combo_idioma.setGeometry(130, 5, 120, 30)
        self.combo_idioma.addItems([name for (name, _, _) in idiomas])
        self.combo_destino = QComboBox(self)
        self.combo_destino.setGeometry(260, 5, 120, 30)
        self.combo_destino.addItems([name for (name, _, _) in idiomas])
        self.combo_destino.setCurrentText('Español')

        self.boton_color = QPushButton("●", self)
        self.boton_color.setGeometry(390, 5, 30, 30)

        self.boton_minimizar = QPushButton("−", self)
        self.boton_minimizar.setGeometry(830, 5, 30, 30)

        self.boton_cerrar = QPushButton("×", self)
        self.boton_cerrar.setGeometry(870, 5, 30, 30)

        self.etiqueta_texto = QLabel("Selecciona una región para comenzar", self)
        self.etiqueta_texto.setStyleSheet("color: white; font-size: 18px; font-weight: bold; padding: 10px;")
        self.etiqueta_texto.setWordWrap(True)
        self.etiqueta_texto.setAlignment(Qt.AlignCenter)
        self.etiqueta_texto.setGeometry(10, 50, 880, 240)
        self.ocr_en_ejecucion = False
        self.ocr_pausado = True
        self.modo_continuo = False
        self.region_ocr = None
        self.color_fondo = QColor(0, 120, 215)
        self.resultado_ocr_signal.connect(self.actualizar_etiqueta)
        self.download_progress_signal.connect(self._on_download_progress)
        self.download_status_signal.connect(self._on_download_status)
        self.timer = None
        try:
            self.log_dir = os.path.join(os.getcwd(), 'registro')
            os.makedirs(self.log_dir, exist_ok=True)
            fecha = date.today().strftime('%Y-%m-%d')
            self.log_file_path = os.path.join(self.log_dir, f"{fecha}.txt")
        except Exception:
            self.log_dir = None
            self.log_file_path = None

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setGeometry(10, 40, 400, 10)
        self.progress_bar.setVisible(False)

        self.combo_idioma.currentIndexChanged.connect(self._on_idioma_origen_changed) #Mapeo
        
        self.boton_seleccionar.clicked.connect(self.seleccionar_region)
        self.boton_pausa.clicked.connect(self.alternar_pausa)
        self.boton_captura.clicked.connect(self.tomar_snapshot)
        self.boton_color.clicked.connect(self.cambiar_color)
        self.boton_minimizar.clicked.connect(self.showMinimized)
        self.boton_cerrar.clicked.connect(self.close)

    def seleccionar_region(self):
        self.hide()
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self.establecer_region_ocr)
        self.region_selector.show()
        
    def establecer_region_ocr(self, x, y, w, h):
        self.region_ocr = (x, y, w, h)
        self.show()
        if self.modo_continuo and not self.ocr_pausado:
            self.iniciar_ocr_continuo()
        self.etiqueta_texto.setText("Región seleccionada")
        
    def alternar_pausa(self):
        if not self.modo_continuo:
            self.modo_continuo = True
            self.ocr_pausado = False
            self.boton_pausa.setText("⏸")
            if self.region_ocr:
                self.iniciar_ocr_continuo()
                self.etiqueta_texto.setText("OCR continuo iniciado")
            else:
                self.etiqueta_texto.setText("Selecciona una región primero")
        else:
            self.ocr_pausado = not self.ocr_pausado
            self.boton_pausa.setText("▶" if self.ocr_pausado else "⏸")
            if self.ocr_pausado:
                self.detener_ocr_continuo()
                self.etiqueta_texto.setText("OCR pausado")
            elif self.region_ocr:
                self.iniciar_ocr_continuo()
            
    def tomar_snapshot(self):
        if not self.region_ocr:
            self.etiqueta_texto.setText("Selecciona una región primero")
            return
        self.modo_continuo = False
        self.detener_ocr_continuo()
        if not self.ocr_en_ejecucion:
            self.ocr_en_ejecucion = True
            threading.Thread(target=self.realizar_ocr, daemon=True).start()
            
    def iniciar_ocr_continuo(self):
        self.modo_continuo = True
        if self.timer:
            self.killTimer(self.timer)
        self.timer = self.startTimer(700)
        
    def detener_ocr_continuo(self):
        if self.timer:
            self.killTimer(self.timer)
            self.timer = None

    def _on_idioma_origen_changed(self, idx):
        # Cuando se cambia el idioma origen, comprobar si existe el traineddata
        try:
            nombre = self.combo_idioma.currentText()
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
                        # iniciar descarga en background
                        threading.Thread(target=self._download_traineddata, args=(tess_code, tess_path), daemon=True).start()
        except Exception:
            pass

    def _on_download_progress(self, value):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(value)

    def _on_download_status(self, status_text):
        if status_text == 'done':
            self.progress_bar.setVisible(False)
            self.etiqueta_texto.setText('Descarga completada')
        else:
            self.progress_bar.setVisible(False)
            self.etiqueta_texto.setText(status_text)

    def _download_traineddata(self, tess_code, dest_path):
        base_url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata/master/{tess_code}.traineddata"
        try:
            req = urllib.request.Request(base_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp:
                total = resp.getheader('Content-Length')
                if total:
                    total = int(total)
                tmp_path = dest_path + '.part'
                try:
                    with open(tmp_path, 'wb') as out_file:
                        downloaded = 0
                        chunk_size = 8192
                        while True:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            out_file.write(chunk)
                            downloaded += len(chunk)
                            if total:
                                perc = int(downloaded * 100 / total)
                                self.download_progress_signal.emit(perc)
                except PermissionError:
                    # No permisos para escribir en Program Files
                    self.download_status_signal.emit('No hay permisos para escribir en la carpeta de Tesseract. Ejecuta el programa como administrador o copia manualmente el archivo.')
                    # limpiar tmp
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
                    return

                # Intentar mover el archivo temporal a la ruta final
                try:
                    shutil.move(tmp_path, dest_path)
                    self.download_status_signal.emit('done')
                except PermissionError:
                    self.download_status_signal.emit('No hay permisos para mover el archivo a la carpeta de Tesseract. Ejecuta como administrador.')
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
        except Exception as e:
            self.download_status_signal.emit(f"Error descarga: {str(e)}")
            
    def timerEvent(self, event):
        if event.timerId() == self.timer and self.modo_continuo and not self.ocr_pausado and not self.ocr_en_ejecucion and self.region_ocr:
            self.ocr_en_ejecucion = True
            threading.Thread(target=self.realizar_ocr, daemon=True).start()

    def realizar_ocr(self):
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                self.resultado_ocr_signal.emit("No se pudo obtener la pantalla.")
                return
                
            x, y, w, h = self.region_ocr
            screenshot = screen.grabWindow(0, x, y, w, h).toImage()
            screenshot = screenshot.convertToFormat(4)
            width = screenshot.width()
            height = screenshot.height()

            ptr = screenshot.bits()
            ptr.setsize(screenshot.byteCount())
            img = Image.frombytes("RGBA", (width, height), ptr.asstring())

            img = img.convert('L')
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)

            custom_config = r'--oem 3 --psm 6'
            idioma_origen_text = self.combo_idioma.currentText()
            idioma_destino_text = self.combo_destino.currentText()
            tesseract_lang = self.mapa_idiomas[idioma_origen_text]

            text = pytesseract.image_to_string(img, lang=tesseract_lang, config=custom_config)

            texto_mostrado = ""
            if text.strip():
                try:
                    source_lang = self.mapa_google.get(tesseract_lang, tesseract_lang)
                    target_tess = self.mapa_idiomas.get(idioma_destino_text, 'spa')
                    target_lang = self.mapa_google.get(target_tess, target_tess)
                    #Redundate check
                    if source_lang == target_lang:
                        texto_mostrado = text
                    else:
                        texto_mostrado = GoogleTranslator(source=source_lang, target=target_lang).translate(text)
                except Exception as e:
                    texto_mostrado = f"Error: {str(e)}"
            else:
                texto_mostrado = "No se encontró texto"
            self.resultado_ocr_signal.emit(texto_mostrado)
        finally:
            self.ocr_en_ejecucion = False

    def actualizar_etiqueta(self, shown_text):
        if self.modo_continuo and self.ocr_pausado:
            self.etiqueta_texto.setText("OCR pausado")
            self.etiqueta_texto.repaint()
            return

        self.etiqueta_texto.setText(shown_text)
        self.etiqueta_texto.repaint()

        # Registro
        try:
            excluded = {
                "OCR pausado", "Región seleccionada", "Selecciona una región primero",
                "No se pudo obtener la pantalla.", "No se encontró texto"
            }
            if self.log_file_path and shown_text and shown_text.strip() and shown_text not in excluded:
                self.append_to_log(shown_text)
        except Exception:
            pass

    def append_to_log(self, text):
        if not self.log_file_path:
            return
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
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
        
        self.boton_seleccionar.setStyleSheet(button_style)
        self.boton_pausa.setStyleSheet(button_style)
        self.boton_captura.setStyleSheet(button_style)
        self.boton_color.setStyleSheet(button_style)
        self.boton_minimizar.setStyleSheet(button_style)
        self.boton_cerrar.setStyleSheet(button_style)
        
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
        self.combo_idioma.setStyleSheet(combo_style)
        if hasattr(self, 'combo_destino'):
            self.combo_destino.setStyleSheet(combo_style)

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
            self.ocr_pausado = True
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
    def mouseReleaseEvent(self, event):
        self.ocr_pausado = False
        super().mouseReleaseEvent(event)

class RegionSelector(QMainWindow):
    region_selected = pyqtSignal(int, int, int, int)
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.showFullScreen()
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.origin = None
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubber_band.setGeometry(self.origin.x(), self.origin.y(), 0, 0)
            self.rubber_band.show()
            
    def mouseMoveEvent(self, event):
        if self.origin:
            self.rubber_band.setGeometry(min(self.origin.x(), event.x()),
                                       min(self.origin.y(), event.y()),
                                       abs(event.x() - self.origin.x()),
                                       abs(event.y() - self.origin.y()))
            
    def mouseReleaseEvent(self, event):
        if self.origin:
            rect = self.rubber_band.geometry()
            self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
            self.close()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VentanaOCR()
    window.show()
    sys.exit(app.exec_())