import sys
import threading
from PyQt5.QtCore import pyqtSignal
import ctypes
import pytesseract
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QGuiApplication
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QColorDialog, QComboBox, QRubberBand
from PIL import Image, ImageEnhance

from deep_translator import GoogleTranslator

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) ##Ajusta el proceso para el escalado de la pantalla
except Exception:
    pass

# Ruta por defecto de Tesseract (mira a ver si puedes hacer que lo encuentre solo)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCRWindow(QMainWindow):
    senal_resultado_ocr = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        ## Configuración de la ventana ##
        self.setWindowTitle("Traductor Automático")
        self.setGeometry(100, 100, 900, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.7)
        # Botones en la parte superior
        self.boton_seleccionar = QPushButton("⬚", self)
        self.boton_seleccionar.setGeometry(10, 5, 30, 30)
        
        self.boton_pausa = QPushButton("⏸", self)
        self.boton_pausa.setGeometry(50, 5, 30, 30)
        
        self.boton_instantanea = QPushButton("📷", self)
        self.boton_instantanea.setGeometry(90, 5, 30, 30)
        
        self.combo_idioma = QComboBox(self)
        self.combo_idioma.setGeometry(130, 5, 80, 30)
        self.combo_idioma.addItems(["Español", "Inglés", "Francés", "Alemán", "Italiano", "Japonés", "Chino", "Portugués"])
        
        self.boton_color = QPushButton("●", self)
        self.boton_color.setGeometry(220, 5, 30, 30)
        
        self.boton_minimizar = QPushButton("−", self)
        self.boton_minimizar.setGeometry(830, 5, 30, 30)
        
        self.boton_cerrar = QPushButton("×", self)
        self.boton_cerrar.setGeometry(870, 5, 30, 30)
        
        self.etiqueta_texto = QLabel("Selecciona una región para comenzar", self)
        self.etiqueta_texto.setStyleSheet("color: white; font-size: 18px; font-weight: bold; padding: 10px;")
        self.etiqueta_texto.setWordWrap(True)
        self.etiqueta_texto.setAlignment(Qt.AlignCenter)
        self.etiqueta_texto.setGeometry(10, 50, 880, 240)
        ## Variables de control de OCR##
        self.ocr_en_ejecucion = False
        self.ocr_pausado = False
        self.modo_continuo = False
        self.region_ocr = None
        self.color_fondo = QColor(0, 120, 215)
        self.mapa_idiomas = {
            'Español': 'spa', 'Inglés': 'eng', 'Francés': 'fra', 'Alemán': 'deu',
            'Italiano': 'ita', 'Japonés': 'jpn', 'Chino': 'chi_sim', 'Portugués': 'por'
        }
        self.senal_resultado_ocr.connect(self.actualizar_etiqueta)
        self.temporizador = None
        
        # Conectar botones
        self.boton_seleccionar.clicked.connect(self.seleccionar_region)
        self.boton_pausa.clicked.connect(self.alternar_pausa)
        self.boton_instantanea.clicked.connect(self.tomar_instantanea)
        self.boton_color.clicked.connect(self.cambiar_color)
        self.boton_minimizar.clicked.connect(self.showMinimized)
        self.boton_cerrar.clicked.connect(self.close)

    def seleccionar_region(self):
        self.hide()
        self.selector_region = SelectorRegion()
        self.selector_region.region_seleccionada.connect(self.establecer_region_ocr)
        self.selector_region.show()
        
    def establecer_region_ocr(self, x, y, w, h):
        self.region_ocr = (x, y, w, h)
        self.show()
        if self.modo_continuo and not self.ocr_pausado:
            self.iniciar_ocr_continuo()
        self.etiqueta_texto.setText("Región seleccionada")
        
    def alternar_pausa(self):
        self.ocr_pausado = not self.ocr_pausado
        self.boton_pausa.setText("▶" if self.ocr_pausado else "⏸")
        if self.ocr_pausado:
            self.detener_ocr_continuo()
            self.etiqueta_texto.setText("OCR pausado")
        elif self.modo_continuo and self.region_ocr:
            self.iniciar_ocr_continuo()
            
    def tomar_instantanea(self):
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
        if self.temporizador:
            self.killTimer(self.temporizador)
        self.temporizador = self.startTimer(700)
        
    def detener_ocr_continuo(self):
        if self.temporizador:
            self.killTimer(self.temporizador)
            self.temporizador = None
            
    def timerEvent(self, event):
        if event.timerId() == self.temporizador and self.modo_continuo and not self.ocr_pausado and not self.ocr_en_ejecucion and self.region_ocr:
            self.ocr_en_ejecucion = True
            threading.Thread(target=self.realizar_ocr, daemon=True).start()

    def realizar_ocr(self):
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                self.senal_resultado_ocr.emit("No se pudo obtener la pantalla.")
                return
                
            x, y, w, h = self.region_ocr
            screenshot = screen.grabWindow(0, x, y, w, h).toImage()
            screenshot = screenshot.convertToFormat(4)
            width = screenshot.width()
            height = screenshot.height()

            ptr = screenshot.bits() 
            ptr.setsize(screenshot.byteCount()) 
            img = Image.frombytes("RGBA", (width, height), ptr.asstring())

            img = img.convert('L') # Convierte a escala de gris
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0) # Aumenta el contraste

            custom_config = r'--oem 3 --psm 6'
            selected_lang = self.combo_idioma.currentText()
            tesseract_lang = self.mapa_idiomas[selected_lang]
            
            text = pytesseract.image_to_string(img, lang=tesseract_lang, config=custom_config)
            
            shown_text = ""
            if text.strip():
                try:
                    if selected_lang != 'Español':
                        source_lang = tesseract_lang
                        if tesseract_lang == 'chi_sim':
                            source_lang = 'zh'
                        elif tesseract_lang == 'jpn':
                            source_lang = 'ja'
                        shown_text = GoogleTranslator(source=source_lang, target='es').translate(text)
                    else:
                        shown_text = text
                except Exception as e:
                    shown_text = f"Error: {str(e)}"
            else:
                shown_text = "No se encontró texto"
            self.senal_resultado_ocr.emit(shown_text)
        finally:
            self.ocr_en_ejecucion = False

    def actualizar_etiqueta(self, shown_text):
        self.etiqueta_texto.setText(shown_text)
        self.etiqueta_texto.repaint()

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
        self.boton_instantanea.setStyleSheet(button_style)
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
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.color_fondo)
        
        # Barra superior más oscura
        darker_color = self.color_fondo.darker(130)
        painter.fillRect(0, 0, self.width(), 40, darker_color)
        
        self.actualizar_estilos_botones()

    ##Funciones para mover la ventana##
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.ocr_pausado = True
            self.posicion_antigua = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.posicion_antigua
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.posicion_antigua = event.globalPos()
    def mouseReleaseEvent(self, event):
        self.ocr_pausado = False
        super().mouseReleaseEvent(event)

class SelectorRegion(QMainWindow):
    region_seleccionada = pyqtSignal(int, int, int, int)
    
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
            self.region_seleccionada.emit(rect.x(), rect.y(), rect.width(), rect.height())
            self.close()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OCRWindow()
    window.show()
    sys.exit(app.exec_())
