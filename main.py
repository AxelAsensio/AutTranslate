import sys
import ctypes
import pytesseract
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QGuiApplication
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PIL import Image, ImageEnhance
from langdetect import detect
from deep_translator import GoogleTranslator

# Forzar DPI awareness en Windows (mejora la precisión de captura)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # DPI por monitor
except Exception:
    pass

# Ruta a Tesseract (ajústala si es necesario)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class OCRWindow(QMainWindow):
    
    # ...existing code...
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traductor Automático")
        self.setGeometry(100, 100, 900, 300)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.text_label = QLabel("Output", self)
        self.text_label.setStyleSheet("background-color: white; padding: 5px; font-size: 16px; border-radius: 8px;")
        self.text_label.setWordWrap(True)
        # Fixed geometry: wide and near the bottom
        self.text_label.setGeometry(20, 220, 860, 60)

        self.timer = self.startTimer(200)

    def timerEvent(self, event):
        if event.timerId() == self.timer:
            self.perform_ocr()

    def perform_ocr(self):
        screen = QGuiApplication.primaryScreen()
        if not screen:
            self.text_label.setText("No se pudo obtener la pantalla.")
            return

        # Capturar el área de pantalla debajo de la ventana (no la ventana en sí)
        geo = self.geometry()
        x = self.x()
        y = self.y()
        w = geo.width()
        h = geo.height()
        screenshot = screen.grabWindow(0, x, y, w, h).toImage()
        screenshot = screenshot.convertToFormat(4)
        width = screenshot.width()
        height = screenshot.height()

        ptr = screenshot.bits()
        ptr.setsize(screenshot.byteCount())
        img = Image.frombytes("RGBA", (width, height), ptr.asstring())

        # Procesamiento de imagen: escala de grises y aumento de contraste
        img = img.convert('L')
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # OCR con configuración mejorada
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img, config=custom_config)

        print(f"[OCR] Recognized: {text!r}")
        shown_text = ""
        if text.strip():
            try:
                detected_lang = detect(text)
                if detected_lang != 'es':
                    shown_text = GoogleTranslator(source=detected_lang, target='es').translate(text)
                else:
                    shown_text = text
            except Exception as e:
                shown_text = f"Error: {str(e)}"
        else:
            shown_text = "No text found"
        self.text_label.setText(shown_text)
        self.text_label.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setBrush(QColor(0, 0, 0, 100))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            delta = event.globalPos() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPos()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OCRWindow()
    window.show()
    sys.exit(app.exec_())
