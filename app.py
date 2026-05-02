
import sys, os, re, requests
import traceback
from datetime import datetime

def exception_hook(exctype, value, tb):
    with open("error.log", "a") as f:
        f.write("".join(traceback.format_exception(exctype, value, tb)))
    sys.__excepthook__(exctype, value, tb)

sys.excepthook = exception_hook

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QHBoxLayout, QFrame, QGraphicsDropShadowEffect,
    QSizePolicy, QSpacerItem, QGraphicsOpacityEffect, QCompleter
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QByteArray, QTimer, QUrl, QPoint
)
from PyQt5.QtGui import (
    QFont, QPixmap, QColor, QLinearGradient, QPainter, QBrush, QPalette
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest

API_KEY = os.getenv("OPENWEATHER_API_KEY", os.getenv("API_KEY", ""))
API_BASE = "https://api.openweathermap.org/data/2.5/forecast"
ICON_URL = "https://openweathermap.org/img/wn/{}@2x.png"

WEATHER_ACCENTS = {
    "thunder": "#7e22ce", "drizzle": "#0369a1", "rain": "#1d4ed8",
    "snow": "#475569", "mist": "#64748b", "clear": "#ea580c",
    "clouds": "#475569", "default": "#2563eb",
}


class WeatherAPI:
    @staticmethod
    def fetch_forecast(city, api_key):
        if not api_key:
            raise EnvironmentError("API key not set. Add OPENWEATHER_API_KEY to .env")
        resp = requests.get(API_BASE, params={"q": city, "appid": api_key, "units": "metric"}, timeout=10)
        if resp.status_code == 404:
            raise ValueError(f"City '{city}' not found.")
        if resp.status_code == 401:
            raise PermissionError("Invalid API key.")
        resp.raise_for_status()
        return WeatherAPI._parse(resp.json())

    @staticmethod
    def _parse(data):
        by_date = {}
        for entry in data["list"]:
            dt = datetime.fromtimestamp(entry["dt"])
            key = dt.strftime("%Y-%m-%d")
            by_date.setdefault(key, []).append((dt, entry))

        days = []
        for date_key in sorted(by_date.keys())[:5]:
            entries = by_date[date_key]
            _, best = min(entries, key=lambda x: abs(x[0].hour - 12))
            temps = [e["main"]["temp"] for _, e in entries]
            dt_obj = datetime.strptime(date_key, "%Y-%m-%d")
            days.append({
                "day": dt_obj.strftime("%A"), "date": dt_obj.strftime("%b %d"),
                "temp": best["main"]["temp"], "feels": best["main"]["feels_like"],
                "min": min(temps), "max": max(temps),
                "humidity": best["main"]["humidity"], "wind": best["wind"]["speed"],
                "desc": best["weather"][0]["description"].title(),
                "icon": best["weather"][0]["icon"],
                "wid": best["weather"][0]["id"],
            })
        return {"city": f"{data['city']['name']}, {data['city']['country']}", "days": days}


class Recommender:
    @staticmethod
    def outfit(temp, wid):
        if 200 <= wid <= 232: return "🌩 Heavy rain gear + rubber boots"
        if 300 <= wid <= 321: return "🌂 Light jacket + umbrella"
        if 500 <= wid <= 531: return "☔ Waterproof jacket + rain boots"
        if 600 <= wid <= 622: return "🧥 Heavy coat + gloves + thermals"
        if 700 <= wid <= 781: return "😷 Light layers, mask for visibility"
        if temp < 5:  return "🧤 Heavy coat, scarf & thermals"
        if temp < 15: return "🧥 Warm jacket and jeans"
        if temp < 22: return "👕 Light jacket or hoodie"
        if temp < 30: return "🩳 T-shirt and shorts"
        return "🌞 Light, breathable fabrics"

    @staticmethod
    def activity(event, wid, temp):
        if not event: return ""
        if 200 <= wid <= 531: return f"⚠ Bad weather for {event} — stay indoors"
        if 600 <= wid <= 622: return f"❄ Snow warning — {event} risky outdoors"
        if temp < 5: return f"🥶 Too cold for {event} — bundle up"
        if temp > 36: return f"🥵 Extreme heat — hydrate for {event}"
        if wid == 800 and 18 <= temp <= 28: return f"✅ Perfect for {event}!"
        return f"🙂 Decent weather for {event}"

    @staticmethod
    def accent(wid):
        if 200 <= wid <= 232: return WEATHER_ACCENTS["thunder"]
        if 300 <= wid <= 321: return WEATHER_ACCENTS["drizzle"]
        if 500 <= wid <= 531: return WEATHER_ACCENTS["rain"]
        if 600 <= wid <= 622: return WEATHER_ACCENTS["snow"]
        if 700 <= wid <= 781: return WEATHER_ACCENTS["mist"]
        if wid == 800: return WEATHER_ACCENTS["clear"]
        if 801 <= wid <= 804: return WEATHER_ACCENTS["clouds"]
        return WEATHER_ACCENTS["default"]


class FetchWorker(QThread):
    result_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, city, api_key):
        super().__init__()
        self.city, self.api_key = city, api_key

    def run(self):
        try:
            self.result_ready.emit(WeatherAPI.fetch_forecast(self.city, self.api_key))
        except (ValueError, PermissionError, EnvironmentError) as e:
            self.error_occurred.emit(str(e))
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("No internet connection.")
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Request timed out.")
        except Exception as e:
            self.error_occurred.emit(str(e))


def shadow(widget, blur=25, y=6, alpha=100):
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(blur)
    s.setOffset(0, y)
    s.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(s)


class ForecastCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FC")
        self.setFixedSize(240, 460)
        self._build()
        shadow(self, blur=30, y=8, alpha=25)

    def _build(self):
        v = QVBoxLayout(self)
        v.setSpacing(6)
        v.setContentsMargins(18, 20, 18, 18)
        v.setAlignment(Qt.AlignHCenter)

        self.day_lbl = self._lbl("--", 18, True, "#1f2937")
        self.day_lbl.setWordWrap(False)
        self.day_lbl.setMaximumWidth(200)
        self.day_lbl.setTextInteractionFlags(Qt.NoTextInteraction)
        self.date_lbl = self._lbl("--", 13, False, "rgba(0,0,0,0.50)")

        self.icon_lbl = QLabel()
        self.icon_lbl.setAlignment(Qt.AlignCenter)
        self.icon_lbl.setFixedSize(100, 100)
        self.icon_lbl.setStyleSheet("background:transparent;")

        self.temp_lbl = self._lbl("--°", 42, True, "#ea580c")
        self.feels_lbl = self._lbl("", 13, False, "rgba(0,0,0,0.50)")
        self.desc_lbl = self._lbl("--", 14, False, "rgba(0,0,0,0.75)")
        self.desc_lbl.setWordWrap(True)
        self.range_lbl = self._lbl("", 13, False, "rgba(0,0,0,0.60)")
        self.detail_lbl = self._lbl("", 13, False, "rgba(0,0,0,0.50)")

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:rgba(0,0,0,0.08);")

        self.outfit_lbl = self._lbl("", 12, False, "#6d28d9")
        self.outfit_lbl.setWordWrap(True)

        for w in [self.day_lbl, self.date_lbl, self.icon_lbl,
                  self.temp_lbl, self.feels_lbl, self.desc_lbl,
                  self.range_lbl, self.detail_lbl, sep, self.outfit_lbl]:
            v.addWidget(w)

    def _lbl(self, text, size, bold, color):
        l = QLabel(text)
        l.setAlignment(Qt.AlignCenter)
        w = "bold" if bold else "normal"
        l.setStyleSheet(f"color:{color};font-size:{size}px;font-weight:{w};background:transparent;border:none;")
        return l

    def load(self, d, event, net):
        accent = Recommender.accent(d["wid"])
        self.day_lbl.setText(d["day"])
        self.date_lbl.setText(d["date"])
        self.temp_lbl.setText(f"{d['temp']:.0f}°C")
        self.temp_lbl.setStyleSheet(f"color:{accent};font-size:42px;font-weight:bold;background:transparent;border:none;")
        self.feels_lbl.setText(f"Feels like {d['feels']:.0f}°")
        self.desc_lbl.setText(d["desc"])
        self.range_lbl.setText(f"▲ {d['max']:.0f}°   ▼ {d['min']:.0f}°")
        self.detail_lbl.setText(f"💧{d['humidity']}%   💨{d['wind']:.1f}m/s")
        self.outfit_lbl.setText(Recommender.outfit(d["temp"], d["wid"]))

        self.setStyleSheet(f"""
            QFrame#FC {{
                background: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(0, 0, 0, 0.06);
                border-top: 1.5px solid rgba(255, 255, 255, 0.8);
                border-left: 1.5px solid rgba(255, 255, 255, 0.8);
                border-radius: 24px;
            }}
            QFrame#FC:hover {{
                background: rgba(255, 255, 255, 0.9);
                border: 1px solid rgba(0, 0, 0, 0.12);
                border-top: 1.5px solid {accent};
            }}
        """)

        reply = net.get(QNetworkRequest(QUrl(ICON_URL.format(d["icon"]))))
        reply.finished.connect(lambda: self._icon_done(reply))

    def _icon_done(self, reply):
        px = QPixmap()
        px.loadFromData(reply.readAll())
        if not px.isNull():
            self.icon_lbl.setPixmap(px.scaled(90, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        reply.deleteLater()


class SmartWeatherApp(QWidget):
    def __init__(self):
        super().__init__()
        self._worker = None
        self._net = QNetworkAccessManager(self)
        self._cards = []
        self._last_city = ""
        self._build()
        if not API_KEY:
            QTimer.singleShot(200, lambda: self._status("⚠ Set OPENWEATHER_API_KEY in .env file", True))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        p.fillRect(self.rect(), QBrush(QColor("#ffffff")))

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(124, 58, 237, 30))
        p.drawEllipse(int(self.width() * 0.75), int(self.height() * 0.05), 400, 400)
        p.setBrush(QColor(14, 165, 233, 25))
        p.drawEllipse(int(self.width() * 0.05), int(self.height() * 0.6), 450, 450)

    def _build(self):
        self.setWindowTitle("Smart Weather App")
        self.setMinimumSize(1300, 820)
        self.resize(1320, 840)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(36, 24, 36, 18)

        hdr = QVBoxLayout()
        hdr.setSpacing(2)
        t = QLabel("⛅  Smart Weather")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size:34px;font-weight:bold;color:#111827;background:transparent;letter-spacing:1px;")
        st = QLabel(datetime.now().strftime("━━  %A, %B %d %Y  ━━"))
        st.setAlignment(Qt.AlignCenter)
        st.setStyleSheet("font-size:11px;color:rgba(0,0,0,0.45);background:transparent;")
        hdr.addWidget(t)
        hdr.addWidget(st)
        root.addLayout(hdr)

        inp = QFrame()
        inp.setObjectName("InpCard")
        inp.setStyleSheet("""
            QFrame#InpCard {
                background: rgba(255, 255, 255, 0.7);
                border: 1px solid rgba(0, 0, 0, 0.06);
                border-top: 1.5px solid rgba(255, 255, 255, 0.8);
                border-left: 1.5px solid rgba(255, 255, 255, 0.8);
                border-radius: 20px;
            }
        """)
        shadow(inp, 35, 8, 25)
        ih = QHBoxLayout(inp)
        ih.setContentsMargins(22, 16, 22, 16)
        ih.setSpacing(12)

        INPUT_CSS = """
            QLineEdit {
                background: rgba(0, 0, 0, 0.03);
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-radius: 12px; padding: 12px 18px;
                color: #1f2937; font-size: 14px;
            }
            QLineEdit:focus { 
                border: 1px solid rgba(0, 0, 0, 0.2); 
                background: rgba(0, 0, 0, 0.05); 
            }
            QLineEdit::placeholder { color: rgba(0, 0, 0, 0.4); }
        """
        self.city_in = QLineEdit()
        self.city_in.setPlaceholderText("📍  City name (London, Tokyo, Mumbai...)")
        self.city_in.setStyleSheet(INPUT_CSS)
        self.city_in.setMinimumWidth(240)
        self.city_in.returnPressed.connect(self._fetch)

        try:
            import geonamescache
            gc = geonamescache.GeonamesCache()
            all_cities = [c['name'] for c in gc.get_cities().values()]
            POPULAR_CITIES = sorted(list(set(all_cities)))
        except ImportError:
            POPULAR_CITIES = [
                "London", "New York", "Tokyo", "Paris", "Berlin", "Sydney", "Mumbai", 
                "Delhi", "Beijing", "Moscow", "Dubai", "Singapore", "Los Angeles"
            ]
        self.completer = QCompleter(POPULAR_CITIES, self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.city_in.setCompleter(self.completer)

        self.act_in = QLineEdit()
        self.act_in.setPlaceholderText("🎯  Activity (hiking, cricket...)")
        self.act_in.setStyleSheet(INPUT_CSS)
        self.act_in.setMinimumWidth(210)
        self.act_in.returnPressed.connect(self._fetch)

        BTN = """QPushButton{
            background: rgba(0, 0, 0, 0.04);
            border: 1px solid rgba(0, 0, 0, 0.08);
            border-top: 1px solid rgba(255, 255, 255, 0.6);
            color: #1f2937; border-radius: 12px;
            padding: 12px 28px; font-size: 14px; font-weight: bold;
            min-width: 100px;
        }
        QPushButton:hover{
            background: rgba(0, 0, 0, 0.08);
            border: 1px solid rgba(0, 0, 0, 0.15);
        }
        QPushButton:pressed{ background: rgba(0, 0, 0, 0.12); }
        QPushButton:disabled{ background: rgba(0, 0, 0, 0.02); color: rgba(0, 0, 0, 0.25); border: none; }"""

        self.go_btn = QPushButton("🔍  Get Forecast")
        self.go_btn.setStyleSheet(BTN)
        self.go_btn.setCursor(Qt.PointingHandCursor)
        self.go_btn.clicked.connect(self._fetch)

        self.ref_btn = QPushButton("↻")
        self.ref_btn.setFixedWidth(46)
        self.ref_btn.setStyleSheet(BTN)
        self.ref_btn.setCursor(Qt.PointingHandCursor)
        self.ref_btn.setToolTip("Refresh last search")
        self.ref_btn.clicked.connect(self._refresh)

        ih.addWidget(self.city_in)
        ih.addWidget(self.act_in)
        ih.addWidget(self.go_btn)
        ih.addWidget(self.ref_btn)
        root.addWidget(inp)

        self.info_lbl = QLabel("")
        self.info_lbl.setAlignment(Qt.AlignCenter)
        self.info_lbl.setFixedHeight(42)
        self.info_lbl.setStyleSheet(
            "font-size:16px;font-weight:bold;color:#374151;"
            "background:rgba(0,0,0,0.04);border-radius:12px;"
            "border:1px solid rgba(0,0,0,0.06);padding:0 18px;"
        )
        root.addWidget(self.info_lbl)

        self.act_lbl = QLabel("")
        self.act_lbl.setAlignment(Qt.AlignCenter)
        self.act_lbl.setStyleSheet("font-size:13px;color:#d97706;background:transparent;")
        root.addWidget(self.act_lbl)

        self.cards_row = QHBoxLayout()
        self.cards_row.setSpacing(20)
        self.cards_row.setAlignment(Qt.AlignCenter)

        self.placeholder = QLabel("\n☁  Search a city to see the 5-day forecast  ☁\n")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("font-size:15px;color:rgba(0,0,0,0.35);background:transparent;padding:40px;")
        self.cards_row.addWidget(self.placeholder)

        root.addLayout(self.cards_row)
        root.addStretch()

        self.status_lbl = QLabel("Ready")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet("font-size:10px;color:rgba(0,0,0,0.40);background:transparent;")
        root.addWidget(self.status_lbl)

    def _fetch(self):
        city = self.city_in.text().strip()
        if not city:
            self._status("Please enter a city name.", True); return
        if len(city) < 2:
            self._status("City name too short.", True); return
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", city):
            self._status("Invalid characters in city name.", True); return
        if not API_KEY:
            self._status("⚠ API key missing! Add OPENWEATHER_API_KEY to .env", True); return

        self._last_city = city
        self._loading(True)
        if self._worker and self._worker.isRunning():
            self._worker.quit(); self._worker.wait()
        self._worker = FetchWorker(city, API_KEY)
        self._worker.result_ready.connect(self._on_data)
        self._worker.error_occurred.connect(self._on_err)
        self._worker.start()

    def _refresh(self):
        if self._last_city:
            self.city_in.setText(self._last_city)
            self._fetch()

    def _on_data(self, result):
        self._loading(False)
        self._clear()
        event = self.act_in.text().strip()
        city = result["city"]
        days = result["days"]

        self.info_lbl.setText(f"📍  {city}  —  {datetime.now().strftime('%A, %b %d %Y')}")

        if event and days:
            tip = Recommender.activity(event, days[0]["wid"], days[0]["temp"])
            self.act_lbl.setText(tip)

        for i, d in enumerate(days):
            card = ForecastCard()
            card.load(d, event, self._net)
            self.cards_row.addWidget(card)
            self._cards.append(card)

        self._status(f"✅  Forecast loaded for {city}", False)

    def _on_err(self, msg):
        self._loading(False)
        self._status(f"❌  {msg}", True)

    def _loading(self, on):
        self.go_btn.setEnabled(not on)
        self.ref_btn.setEnabled(not on)
        if on:
            self._status("🔄  Fetching weather data…", False)
            self.act_lbl.setText("")

    def _status(self, msg, err=False):
        c = "#ef4444" if err else "rgba(0,0,0,0.45)"
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet(f"font-size:11px;color:{c};background:transparent;")

    def _clear(self):
        if self.placeholder:
            self.placeholder.setParent(None)
            self.placeholder = None
        for c in self._cards:
            c.setParent(None); c.deleteLater()
        self._cards.clear()
        self.act_lbl.setText("")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 11))
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(255, 255, 255))
    pal.setColor(QPalette.WindowText, QColor(31, 41, 55))
    pal.setColor(QPalette.Base, QColor(249, 250, 251))
    pal.setColor(QPalette.Text, QColor(31, 41, 55))
    pal.setColor(QPalette.Highlight, QColor(99, 102, 241))
    app.setPalette(pal)

    w = SmartWeatherApp()
    w.show()
    sys.exit(app.exec_())