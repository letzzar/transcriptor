"""Interruptor de encendido/apagado con estado visible.

Los `QPushButton` marcables que había antes no dejaban claro si una opción
estaba activa: un botón "pulsado" y uno "sin pulsar" se distinguen mal, y en
una herramienta pericial el usuario tiene que poder ver de un vistazo qué se
va a ejecutar. Este widget lo dibuja explícitamente: verde con la bolita a la
derecha si está encendido, gris con la bolita a la izquierda si está apagado.

Se dibuja a mano (`QPainter`) en vez de con hoja de estilos porque Qt no ofrece
un interruptor deslizante nativo y el aspecto debe ser idéntico en Windows y
macOS, que es un requisito del proyecto.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

_ANCHO = 52
_ALTO = 28
_MARGEN = 3.0

_VERDE = QColor("#2e9e4f")
_GRIS = QColor("#8b8b8b")
_BLANCO = QColor("#ffffff")


class ToggleSwitch(QAbstractButton):
    """Interruptor on/off. `toggled(bool)` avisa de los cambios."""

    def __init__(self, parent: QWidget | None = None, *, checked: bool = False) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(_ANCHO, _ALTO)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        encendido = self.isChecked()
        fondo = _VERDE if encendido else _GRIS
        if not self.isEnabled():
            fondo = fondo.darker(130)

        # Carril.
        carril = QRectF(0, 0, _ANCHO, _ALTO)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fondo)
        painter.drawRoundedRect(carril, _ALTO / 2, _ALTO / 2)

        # Bolita: derecha = encendido, izquierda = apagado.
        radio = (_ALTO - 2 * _MARGEN) / 2
        x = _ANCHO - _MARGEN - radio if encendido else _MARGEN + radio
        painter.setBrush(_BLANCO)
        painter.drawEllipse(QPointF(x, _ALTO / 2), radio, radio)


class LabeledToggle(QWidget):
    """Un `ToggleSwitch` con su texto y la palabra ENCENDIDO / APAGADO.

    El color solo no basta: quien no distinga verde de gris debe poder leer el
    estado, así que se escribe además en texto.
    """

    toggled = Signal(bool)

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
        *,
        checked: bool = False,
        tooltip: str = "",
    ) -> None:
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout, QLabel

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.switch = ToggleSwitch(self, checked=checked)
        self.switch.toggled.connect(self._on_toggled)
        layout.addWidget(self.switch)

        self._label = QLabel(text, self)
        layout.addWidget(self._label)

        self._estado = QLabel(self)
        self._estado.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self._estado)
        layout.addStretch()

        if tooltip:
            self.setToolTip(tooltip)
        self._refresh()

    def _on_toggled(self, checked: bool) -> None:
        self._refresh()
        self.toggled.emit(checked)

    def _refresh(self) -> None:
        self._estado.setText("ENCENDIDO" if self.switch.isChecked() else "APAGADO")

    def isChecked(self) -> bool:
        return self.switch.isChecked()

    def setChecked(self, value: bool) -> None:
        self.switch.setChecked(value)
        self._refresh()

    def setEnabled(self, value: bool) -> None:
        super().setEnabled(value)
        self.switch.setEnabled(value)
