import sys
import threading
from PyQt5.QtCore import pyqtSignal
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
    ocr_result_signal = pyqtSignal(str)
    
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

        self.ocr_running = False
        self.ocr_paused = False
        self.ocr_result_signal.connect(self.update_label)
        self.timer = self.startTimer(700)

    def timerEvent(self, event):
        if event.timerId() == self.timer and not self.ocr_paused and not self.ocr_running:
            self.ocr_running = True
            threading.Thread(target=self.perform_ocr, daemon=True).start()

    def perform_ocr(self):
        try:
            screen = QGuiApplication.primaryScreen()
            if not screen:
                self.ocr_result_signal.emit("No se pudo obtener la pantalla.")
                return

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

            img = img.convert('L')
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)

            custom_config = r'--oem 3 --psm 6'
            # Try to detect language for Tesseract
            lang_map = {
                'en': 'eng', 'es': 'spa', 'fr': 'fra', 'de': 'deu', 'it': 'ita',
                'ja': 'jpn', 'zh-cn': 'chi_sim', 'zh-tw': 'chi_tra', 'zh': 'chi_sim',
                'ru': 'rus', 'pt': 'por', 'nl': 'nld', 'ko': 'kor'
            }

            # Use multiple languages for initial OCR
            tesseract_langs = 'spa+jpn+chi_sim+rus'
            text = pytesseract.image_to_string(img, lang=tesseract_langs, config=custom_config)
            detected_lang = 'en'
            if text.strip():
                try:
                    detected_lang = detect(text)
                    tesseract_lang = lang_map.get(detected_lang, 'spa')
                    # If not English, try again with detected language
                    if tesseract_lang != 'spa':
                        text2 = pytesseract.image_to_string(img, lang=tesseract_lang, config=custom_config)
                        if text2.strip():
                            text = text2
                except Exception:
                    pass

            print(f"[OCR] Recognized: {text!r} (lang: {tesseract_lang})")
            shown_text = ""
            if text.strip():
                try:
                    if detected_lang != 'es':
                        shown_text = GoogleTranslator(source=detected_lang, target='es').translate(text)
                    else:
                        shown_text = text
                except Exception as e:
                    shown_text = f"Error: {str(e)}"
            else:
                shown_text = "No text found"
            self.ocr_result_signal.emit(shown_text)
        finally:
            self.ocr_running = False

    def update_label(self, shown_text):
        self.text_label.setText(shown_text)
        self.text_label.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        # No fill, fully transparent background
        painter.setBrush(Qt.NoBrush)
        # Draw a 1px border (e.g., blue)
        painter.setPen(QColor(0, 120, 215, 255))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = OCRWindow()
    window.show()
    sys.exit(app.exec_())
