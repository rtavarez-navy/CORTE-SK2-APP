"""CORTE SK2 APP · Cliente Windows ligero, sin datos de producción locales."""
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import requests
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox,
                               QPushButton, QSpinBox, QStackedWidget, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

APP_VERSION = "0.1.0"


class APIError(Exception):
    def __init__(self, status, detail):
        super().__init__(str(detail))
        self.status = status
        self.detail = detail
        self.code = detail.get("code") if isinstance(detail, dict) else None


class APIClient:
    def __init__(self, config):
        self.base_url = config["api_base_url"].rstrip("/")
        self.workstation_key = config["workstation_key"]
        if not (self.base_url.startswith("https://") or
                self.base_url.startswith("http://127.0.0.1:") or
                self.base_url.startswith("http://localhost:")):
            raise ValueError("La API debe utilizar HTTPS (solo localhost admite HTTP para pruebas)")
        self.token = None

    def call(self, method, path, data=None):
        headers = {"X-Workstation-Key": self.workstation_key}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        try:
            response = requests.request(method, self.base_url + path, json=data,
                                        headers=headers, timeout=(5, 12))
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            if not response.ok:
                raise APIError(response.status_code, payload.get("detail", "Error del servidor"))
            return payload
        except requests.RequestException as e:
            raise APIError(0, "No hay conexión con el servidor. No se ha confirmado el registro.") from e


class TaskSignals(QObject):
    done = Signal(object, object)


class Task(QRunnable):
    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = TaskSignals()
        self.setAutoDelete(False)

    def run(self):
        try:
            self.signals.done.emit(self.fn(), None)
        except Exception as ex:
            self.signals.done.emit(None, ex)


def load_config():
    base = Path(os.getenv("PROGRAMDATA") or os.getenv("APPDATA") or str(Path.home()))
    location = base / "CORTE_SK2_APP" / "config.json"
    if not location.exists():
        raise ValueError(f"Configuración de computadora no encontrada: {location}. Solicitar a TI su instalación.")
    config = json.loads(location.read_text(encoding="utf-8"))
    if not config.get("workstation_key") or not config.get("api_base_url"):
        raise ValueError("Faltan datos de API o estación en config.json")
    return config


class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.client = APIClient(config)
        self.pool = QThreadPool.globalInstance()
        self.jobs = []
        self.machine_number = None
        self.pending = None
        self.setWindowTitle("CORTE SK2 APP — Producción Láser")
        self.setMinimumSize(670, 490)
        self.setStyleSheet("QWidget { font-size: 14px; } QPushButton { padding: 8px; } "
                           "QLineEdit, QSpinBox, QComboBox { padding: 6px; }")
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self.build_login()
        self.build_workspace()
        self.pages.setCurrentIndex(0)

    def run_task(self, fn, callback):
        job = Task(fn)
        self.jobs.append(job)
        def complete(result, error):
            try:
                callback(result, error)
            finally:
                self.jobs.remove(job)
        job.signals.done.connect(complete)
        self.pool.start(job)

    def error_dialog(self, error):
        if isinstance(error, APIError):
            detail = error.detail
            if isinstance(detail, dict):
                message = detail.get("message") or detail.get("code") or str(detail)
            else:
                message = str(detail)
        else:
            message = str(error)
        QMessageBox.warning(self, "CORTE SK2 APP", message)

    def build_login(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(70, 55, 70, 55)
        title = QLabel("CORTE SK2 APP")
        title.setStyleSheet("font-size: 27px; font-weight: bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Inicio de sesión — Producción Láser"))
        layout.addSpacing(20)
        form = QFormLayout()
        self.username = QLineEdit()
        self.username.setPlaceholderText("Usuario")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Usuario:", self.username)
        form.addRow("Contraseña:", self.password)
        layout.addLayout(form)
        self.login_btn = QPushButton("Entrar")
        self.login_btn.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)
        layout.addWidget(self.login_btn)
        layout.addStretch()
        layout.addWidget(QLabel("Versión " + APP_VERSION))
        self.pages.addWidget(page)

    def build_workspace(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        top = QHBoxLayout()
        self.laser_label = QLabel("Láser: verificando computadora…")
        self.laser_label.setStyleSheet("font-size: 19px; font-weight: bold;")
        top.addWidget(self.laser_label)
        top.addStretch()
        self.user_label = QLabel("")
        top.addWidget(self.user_label)
        logout = QPushButton("Salir")
        logout.clicked.connect(self.logout)
        top.addWidget(logout)
        outer.addLayout(top)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        reg = QWidget()
        reg_layout = QVBoxLayout(reg)
        reg_layout.addWidget(QLabel("Registra las piezas al completar una orden y línea."))
        form = QFormLayout()
        self.shift = QComboBox()
        self.shift.addItems(["T1", "T2"])
        self.order_field = QLineEdit()
        self.order_field.setPlaceholderText("Ejemplo: 3987250")
        self.line_field = QLineEdit()
        self.line_field.setPlaceholderText("Ejemplo: A")
        self.pieces_field = QSpinBox()
        self.pieces_field.setRange(1, 1_000_000)
        form.addRow("Turno:", self.shift)
        form.addRow("Número de orden:", self.order_field)
        form.addRow("Línea (Set):", self.line_field)
        form.addRow("Piezas terminadas:", self.pieces_field)
        reg_layout.addLayout(form)
        controls = QHBoxLayout()
        self.check_btn = QPushButton("Consultar CPA")
        self.check_btn.clicked.connect(self.check_cpa)
        controls.addWidget(self.check_btn)
        self.save_btn = QPushButton("Registrar producción")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.register)
        controls.addWidget(self.save_btn)
        reg_layout.addLayout(controls)
        self.cpa_info = QLabel("Consulta CPA antes de registrar.")
        self.cpa_info.setWordWrap(True)
        reg_layout.addWidget(self.cpa_info)
        reg_layout.addStretch()
        self.tabs.addTab(reg, "Registrar")

        summary = QWidget()
        sum_layout = QVBoxLayout(summary)
        h = QHBoxLayout()
        h.addWidget(QLabel("Producción de esta semana (lunes a domingo)"))
        h.addStretch()
        refresh = QPushButton("Actualizar resumen")
        refresh.clicked.connect(self.refresh_summary)
        h.addWidget(refresh)
        sum_layout.addLayout(h)
        self.sum_table = QTableWidget(0, 4)
        self.sum_table.setHorizontalHeaderLabels(["Fecha", "Láser", "Turno", "Piezas"])
        self.sum_table.horizontalHeader().setStretchLastSection(True)
        self.sum_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        sum_layout.addWidget(self.sum_table)
        self.grand_total = QLabel("Total semanal: —")
        sum_layout.addWidget(self.grand_total)
        self.tabs.addTab(summary, "Resumen")
        self.tabs.currentChanged.connect(lambda idx: self.refresh_summary() if idx == 1 else None)
        self.pages.addWidget(page)

    def login(self):
        self.login_btn.setEnabled(False)
        data = {"username": self.username.text().strip(), "password": self.password.text()}
        def finished(result, error):
            self.login_btn.setEnabled(True)
            if error:
                self.error_dialog(error)
                return
            self.client.token = result["access_token"]
            self.user_label.setText(result["username"])
            self.password.clear()
            self.run_task(lambda: self.client.call("GET", "/workstation"), self.on_machine)
        self.run_task(lambda: self.client.call("POST", "/auth/login", data), finished)

    def on_machine(self, result, error):
        if error:
            self.client.token = None
            self.error_dialog(error)
            return
        self.machine_number = result["laser_number"]
        self.laser_label.setText(f"Láser #{self.machine_number}")
        self.pages.setCurrentIndex(1)

    def logout(self):
        self.client.token = None
        self.pending = None
        self.pages.setCurrentIndex(0)

    def order_line(self):
        order = self.order_field.text().strip().upper().removeprefix("SO-")
        line = self.line_field.text().strip().upper()
        if not order or not line:
            raise ValueError("Escribe el número de orden y la línea")
        return order, line

    def check_cpa(self):
        try:
            order, line = self.order_line()
        except ValueError as ex:
            self.error_dialog(ex)
            return
        self.check_btn.setEnabled(False)
        def finished(result, error):
            self.check_btn.setEnabled(True)
            if error:
                self.cpa_info.setText("CPA: no disponible para esta orden y línea")
                self.error_dialog(error)
                return
            self.cpa_info.setText(f"CPA: {result['max_pieces']} piezas · Registradas: "
                                  f"{result['produced_pieces']} · Disponibles: {result['available_pieces']} "
                                  f"· Registros anteriores: {result['prior_entries']}")
        self.run_task(lambda: self.client.call("GET", f"/orders/{order}/{line}"), finished)

    def register(self):
        try:
            order, line = self.order_line()
        except ValueError as ex:
            self.error_dialog(ex)
            return
        payload = {"order_number": order, "line": line, "shift": self.shift.currentText(),
                   "pieces": self.pieces_field.value()}
        if self.pending is None or any(self.pending[k] != payload[k] for k in payload):
            self.pending = dict(payload, request_id=str(uuid4()))
        self._send_registration(dict(self.pending, confirm_duplicate=False))

    def _send_registration(self, payload):
        self.save_btn.setEnabled(False)
        def finished(result, error):
            self.save_btn.setEnabled(True)
            if error:
                if isinstance(error, APIError) and error.code == "DUPLICADO_REQUIERE_CONFIRMACION":
                    d = error.detail
                    answer = QMessageBox.question(
                        self, "Registro existente",
                        f"Esta orden y línea ya tienen {d['already_produced']} piezas registradas "
                        f"en {d['prior_entries']} registro(s). ¿Confirmas agregar otras "
                        f"{payload['pieces']} piezas?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if answer == QMessageBox.StandardButton.Yes:
                        self._send_registration(dict(payload, confirm_duplicate=True))
                    else:
                        self.pending = None
                elif isinstance(error, APIError) and error.code == "EXCESO_CPA":
                    self.pending = None
                    self.error_dialog(APIError(409, f"CPA permite {error.detail['max_pieces']} piezas, "
                                               f"ya registradas {error.detail['already_produced']}. "
                                               f"Solo quedan {error.detail['available_pieces']} disponibles."))
                else:
                    # Conservamos request_id: un reintento no creará un registro doble.
                    self.error_dialog(error)
                return
            self.pending = None
            QMessageBox.information(self, "Registrado", f"Producción guardada. "
                                    f"Total acumulado: {result['produced_total']} · "
                                    f"Disponibles en CPA: {result['available_pieces']}")
            self.order_field.clear()
            self.line_field.clear()
            self.pieces_field.setValue(1)
            self.cpa_info.setText("Registro guardado. Introduce la siguiente orden.")
        self.run_task(lambda: self.client.call("POST", "/production", payload), finished)

    def refresh_summary(self):
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        path = f"/summary?start={monday.isoformat()}&end={sunday.isoformat()}"
        def finished(result, error):
            if error:
                self.error_dialog(error)
                return
            items = result["items"]
            self.sum_table.setRowCount(len(items))
            for row, entry in enumerate(items):
                for col, key in enumerate(("date", "laser_number", "shift", "pieces")):
                    cell = QTableWidgetItem(str(entry[key]))
                    if col > 0:
                        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.sum_table.setItem(row, col, cell)
            self.grand_total.setText(f"Total semanal: {result['grand_total']} piezas")
        self.run_task(lambda: self.client.call("GET", path), finished)


def main():
    app = QApplication(sys.argv)
    try:
        config = load_config()
        win = MainWindow(config)
        win.show()
        return app.exec()
    except Exception as ex:
        QMessageBox.critical(None, "CORTE SK2 APP — Configuración", str(ex))
        return 1


if __name__ == "__main__":
    sys.exit(main())
