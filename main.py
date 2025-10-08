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

# OPTIMIZACIÓN POSIBLE:
# Para mejorar el rendimiento, se puede hacer una pasada rápida de OCR sobre una pequeña región de la imagen (por ejemplo, la primera línea),
# detectar el idioma con una librería rápida como langdetect o fastText, y luego hacer el OCR completo solo con el idioma detectado.
# Esto evita cargar todos los paquetes de idiomas en cada ciclo. Además, para evitar hacer dos OCR cada 700 ms, esta detección inicial
# podría ejecutarse solo cuando el usuario pulse la pantalla (por ejemplo, al mover o hacer clic en la ventana), y no en cada ciclo automático.
# Otra mejora posible: buscar una forma de pausar el OCR si la imagen no ha cambiado, o evitar traducir/mostrar resultados si el texto es el mismo que el anterior. Esto puede mejorar el rendimiento y la experiencia de usuario.
# Comprobar lógica y optimizacion del código.
#Nuevo enfoque: botón para seleccionar región de pantalla (similar a la herramienta de recorte de Windows). Opción de hacer OCR en tiempo real o en snapshots. Añadir botón para cambiar de modo. Ver posibilidad de pausar y reiniciar OCR.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) ##Ajusta el proceso para el escalado de la pantalla
except Exception:
    pass

# Ruta por defecto de Tesseract (mira a ver si puedes hacer que lo encuentre solo)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCRWindow(QMainWindow):
    ocr_result_signal = pyqtSignal(str)
    
    # ...existing code...
    def __init__(self):
        super().__init__()
        
        ## Configuración de la ventana ##
        self.setWindowTitle("Traductor Automático")
        self.setGeometry(100, 100, 900, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setWindowOpacity(0.7)
        # Botones en la parte superior
        self.select_button = QPushButton("⬚", self)
        self.select_button.setGeometry(10, 5, 30, 30)
        
        self.pause_button = QPushButton("⏸", self)
        self.pause_button.setGeometry(50, 5, 30, 30)
        
        self.snapshot_button = QPushButton("📷", self)
        self.snapshot_button.setGeometry(90, 5, 30, 30)
        
        self.lang_combo = QComboBox(self)
        self.lang_combo.setGeometry(130, 5, 80, 30)
        self.lang_combo.addItems(["Español", "Inglés", "Francés", "Alemán", "Italiano", "Japonés", "Chino", "Portugués"])
        
        self.color_button = QPushButton("●", self)
        self.color_button.setGeometry(220, 5, 30, 30)
        
        self.minimize_button = QPushButton("−", self)
        self.minimize_button.setGeometry(830, 5, 30, 30)
        
        self.close_button = QPushButton("×", self)
        self.close_button.setGeometry(870, 5, 30, 30)
        
        self.text_label = QLabel("Selecciona una región para comenzar", self)
        self.text_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold; padding: 10px;")
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setGeometry(10, 50, 880, 240)
        ## Variables de control de OCR##
        self.ocr_running = False
        self.ocr_paused = False
        self.continuous_mode = True
        self.ocr_region = None
        self.bg_color = QColor(0, 120, 215)
        self.lang_map = {
            'Español': 'spa', 'Inglés': 'eng', 'Francés': 'fra', 'Alemán': 'deu',
            'Italiano': 'ita', 'Japonés': 'jpn', 'Chino': 'chi_sim', 'Portugués': 'por'
        }
        self.ocr_result_signal.connect(self.update_label)
        self.timer = None
        
        # Conectar botones
        self.select_button.clicked.connect(self.select_region)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.snapshot_button.clicked.connect(self.take_snapshot)
        self.color_button.clicked.connect(self.change_color)
        self.minimize_button.clicked.connect(self.showMinimized)
        self.close_button.clicked.connect(self.close)

    def select_region(self):
        self.hide()
        self.region_selector = RegionSelector()
        self.region_selector.region_selected.connect(self.set_ocr_region)
        self.region_selector.show()
        
    def set_ocr_region(self, x, y, w, h):
        self.ocr_region = (x, y, w, h)
        self.show()
        if self.continuous_mode and not self.ocr_paused:
            self.start_continuous_ocr()
        self.text_label.setText("Región seleccionada")
        
    def toggle_pause(self):
        self.ocr_paused = not self.ocr_paused
        self.pause_button.setText("▶" if self.ocr_paused else "⏸")
        if self.ocr_paused:
            self.stop_continuous_ocr()
            self.text_label.setText("OCR pausado")
        elif self.continuous_mode and self.ocr_region:
            self.start_continuous_ocr()
            
    def take_snapshot(self):
        if not self.ocr_region:
            self.text_label.setText("Selecciona una región primero")
            return
        self.continuous_mode = False
        self.stop_continuous_ocr()
        if not self.ocr_running:
            self.ocr_running = True
            threading.Thread(target=self.perform_ocr, daemon=True).start()
            
    def start_continuous_ocr(self):
        self.continuous_mode = True
        if self.timer:
            self.killTimer(self.timer)
        self.timer = self.startTimer(700)
        
    def stop_continuous_ocr(self):
        if self.timer:
            self.killTimer(self.timer)
            self.timer = None
            
    def timerEvent(self, event):
        if event.timerId() == self.timer and self.continuous_mode and not self.ocr_paused and not self.ocr_running and self.ocr_region:
            self.ocr_running = True
            threading.Thread(target=self.perform_ocr, daemon=True).start()

    def perform_ocr(self):
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                self.ocr_result_signal.emit("No se pudo obtener la pantalla.")
                return
                
            x, y, w, h = self.ocr_region
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
            selected_lang = self.lang_combo.currentText()
            tesseract_lang = self.lang_map[selected_lang]
            
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
            self.ocr_result_signal.emit(shown_text)
        finally:
            self.ocr_running = False

    def update_label(self, shown_text):
        self.text_label.setText(shown_text)
        self.text_label.repaint()


        
    def change_color(self):
        color = QColorDialog.getColor(self.bg_color, self)
        if color.isValid():
            self.bg_color = color
            self.update_button_styles()
            self.update()
    
    def update_button_styles(self):
        darker_color = self.bg_color.darker(130)
        
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
        
        self.select_button.setStyleSheet(button_style)
        self.pause_button.setStyleSheet(button_style)
        self.snapshot_button.setStyleSheet(button_style)
        self.color_button.setStyleSheet(button_style)
        self.minimize_button.setStyleSheet(button_style)
        self.close_button.setStyleSheet(button_style)
        
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
        self.lang_combo.setStyleSheet(combo_style)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.bg_color)
        
        # Barra superior más oscura
        darker_color = self.bg_color.darker(130)
        painter.fillRect(0, 0, self.width(), 40, darker_color)
        
        self.update_button_styles()

    ##Funciones para mover la ventana##
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.ocr_paused = True
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()
    def mouseReleaseEvent(self, event):
        self.ocr_paused = False
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
    window = OCRWindow()
    window.show()
    sys.exit(app.exec_())
