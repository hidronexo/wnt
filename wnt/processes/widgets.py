"""Processing widget helpers used by Water Network Tools algorithms."""

from pathlib import Path

from qgis.PyQt.QtWidgets import QComboBox
try:
    from processing.gui.wrappers import WidgetWrapper
except ImportError:
    class WidgetWrapper:  # type: ignore[no-redef]  # pragma: no cover - used only when Processing GUI is unavailable
        pass

from ..utils.utils_tin import surface_names


class LandXmlSurfaceWidgetWrapper(WidgetWrapper):
    """Editable combo box populated from the selected LandXML file."""

    def createWidget(self, **kwargs):
        self._file_wrapper = None
        widget = QComboBox()
        widget.setEditable(True)
        widget.currentTextChanged.connect(
            lambda _text: self.widgetValueHasChanged.emit(self)
        )
        return widget

    def postInitialize(self, wrappers):
        file_parameter = self.parameterDefinition().metadata().get("landxml_file_parameter")
        for wrapper in wrappers:
            try:
                parameter_name = wrapper.parameterDefinition().name()
            except AttributeError:
                continue
            if parameter_name == file_parameter:
                self._file_wrapper = wrapper
                wrapper.widgetValueHasChanged.connect(lambda _wrapper: self._refresh_surfaces())
                break
        self._refresh_surfaces()

    def setWidgetValue(self, value, context):
        self._set_combo_text(str(value or ""))

    def widgetValue(self):
        return self.widget.currentText().strip()

    def _selected_file(self):
        if self._file_wrapper is None:
            return ""
        try:
            return str(self._file_wrapper.widgetValue() or "")
        except AttributeError:
            return str(self._file_wrapper.parameterValue() or "")

    def _refresh_surfaces(self):
        current = self.value()
        names = []
        landxml_file = self._selected_file()
        if landxml_file and Path(landxml_file).is_file():
            try:
                names = surface_names(landxml_file)
            except Exception:
                names = []

        self.widget.blockSignals(True)
        self.widget.clear()
        self.widget.addItems(names)
        if current:
            self._set_combo_text(current)
        elif names:
            self.widget.setCurrentText(names[0])
        self.widget.blockSignals(False)

    def value(self):
        return self.widget.currentText().strip()

    def setValue(self, value):
        self._set_combo_text(str(value or ""))

    def _set_combo_text(self, value):
        index = self.widget.findText(value)
        if index >= 0:
            self.widget.setCurrentIndex(index)
        else:
            self.widget.setEditText(value)
