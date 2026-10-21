"""Processing widget helpers used by Water Network Tools algorithms."""

from pathlib import Path

from qgis.PyQt.QtWidgets import QComboBox
from qgis.PyQt.QtCore import QTimer
try:
    from processing.gui.wrappers import EnumWidgetWrapper, WidgetWrapper, FeatureSourceWidgetWrapper
except ImportError:
    class WidgetWrapper:  # type: ignore[no-redef]  # pragma: no cover - used only when Processing GUI is unavailable
        pass

    class EnumWidgetWrapper(WidgetWrapper):  # type: ignore[no-redef]  # pragma: no cover
        pass

    class FeatureSourceWidgetWrapper(WidgetWrapper):  # type: ignore[no-redef]  # pragma: no cover
        pass

from ..utils.utils_tin import surface_names
from ..utils.parameter_rules import enabled
from ..utils.safe_xml import parse as safe_xml_parse


def wrapper_value(wrapper):
    for accessor in ('widgetValue', 'parameterValue', 'value'):
        method = getattr(wrapper, accessor, None)
        if callable(method):
            try:
                return method()
            except (AttributeError, TypeError):
                continue
    return None


class DependencyMixin:
    """Coordinate dependent controls while preserving their native wrappers."""

    def postInitialize(self, wrappers):
        super().postInitialize(wrappers)
        self._rule_wrappers = list(wrappers)
        self._dependency_timer = QTimer()
        self._dependency_timer.setSingleShot(True)
        self._dependency_timer.setInterval(200)
        self._dependency_timer.timeout.connect(self._refresh_dependencies)
        for wrapper in wrappers:
            signal = getattr(wrapper, 'widgetValueHasChanged', None)
            if signal is not None:
                signal.connect(self._refresh_dependencies)
            widget = getattr(wrapper, 'widget', None)
            line_edit = getattr(widget, 'leText', None)
            if line_edit is not None:
                line_edit.textChanged.connect(lambda *_args: self._dependency_timer.start())
            for signal_name in ('currentIndexChanged', 'layerChanged', 'textChanged'):
                signal = getattr(widget, signal_name, None)
                if signal is not None:
                    signal.connect(self._refresh_dependencies)
        self._refresh_dependencies()

    def _refresh_dependencies(self, *_args):
        values = {wrapper.parameterDefinition().name(): wrapper_value(wrapper)
                  for wrapper in self._rule_wrappers}
        for wrapper in self._rule_wrappers:
            rules = wrapper.parameterDefinition().metadata().get('wnt_enabled_when', [])
            if not rules:
                continue
            widget = getattr(wrapper, 'widget', None)
            if widget is None and hasattr(wrapper, 'wrappedWidget'):
                widget = wrapper.wrappedWidget()
            if widget is not None:
                widget.setEnabled(enabled(rules, values))


class ConditionalEnumWidgetWrapper(DependencyMixin, EnumWidgetWrapper):
    """Native enum control with shared parameter dependencies."""


class ConditionalSourceWidgetWrapper(DependencyMixin, FeatureSourceWidgetWrapper):
    """Native source control with shared parameter dependencies."""


class EpanetWorkflowWidgetWrapper(EnumWidgetWrapper):
    """Enable only the parameters used by the selected EPANET workflow."""

    def postInitialize(self, wrappers):
        self._dependent_wrappers = []
        for wrapper in wrappers:
            try:
                metadata = wrapper.parameterDefinition().metadata()
            except AttributeError:
                continue
            if metadata.get("epanet_scratch_only") or metadata.get("epanet_existing_only"):
                self._dependent_wrappers.append(wrapper)
        self.widget.currentIndexChanged.connect(lambda *_args: self._update_enabled_state())
        self._update_enabled_state()

    def _update_enabled_state(self):
        try:
            scratch = int(self.value()) == 1
        except (AttributeError, TypeError, ValueError):
            scratch = False
        for wrapper in self._dependent_wrappers:
            metadata = wrapper.parameterDefinition().metadata()
            enabled = scratch if metadata.get("epanet_scratch_only") else not scratch
            widget = getattr(wrapper, "widget", None)
            if widget is None and hasattr(wrapper, "wrappedWidget"):
                widget = wrapper.wrappedWidget()
            if widget is not None:
                widget.setEnabled(enabled)


class LandXmlSurfaceWidgetWrapper(WidgetWrapper):
    """Editable combo box populated from the selected LandXML file."""

    def createWidget(self, **kwargs):
        self._file_wrapper = None
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(200)
        self._refresh_timer.timeout.connect(self._refresh_surfaces)
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
                line_edit = getattr(getattr(wrapper, 'widget', None), 'leText', None)
                if line_edit is not None:
                    line_edit.textChanged.connect(lambda *_args: self._refresh_timer.start())
                combo = getattr(wrapper, 'combo', None)
                if combo is not None:
                    combo.currentTextChanged.connect(lambda *_args: self._refresh_timer.start())
                break
        self._refresh_surfaces()

    def setWidgetValue(self, value, context):
        self._set_combo_text(str(value or ""))

    def widgetValue(self):
        return self.widget.currentText().strip()

    def _selected_file(self):
        if self._file_wrapper is None:
            return ""
        value = wrapper_value(self._file_wrapper)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ''
        return str(value or '')

    def _refresh_surfaces(self):
        current = self.value()
        names = []
        landxml_file = self._selected_file()
        if landxml_file and not Path(landxml_file).is_file() and ';' in landxml_file:
            landxml_file = landxml_file.split(';', 1)[0]
        if landxml_file and Path(landxml_file).is_file():
            try:
                names = surface_names(landxml_file)
            except Exception:
                names = []

        self.widget.blockSignals(True)
        self.widget.clear()
        self.widget.addItems(names)
        if current in names:
            self._set_combo_text(current)
        elif names:
            self.widget.setCurrentText(names[0])
        self.widget.blockSignals(False)
        if current != self.value():
            self.widgetValueHasChanged.emit(self)

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


class XmlChoiceWidgetWrapper(LandXmlSurfaceWidgetWrapper):
    """Debounced network/version choices; keep blank as the automatic choice."""

    def postInitialize(self, wrappers):
        self._network_wrapper = next((wrapper for wrapper in wrappers
                                      if wrapper.parameterDefinition().name() == 'NETWORK_NAMES'), None)
        super().postInitialize(wrappers)
        if self.parameterDefinition().name() == 'VERSION_ID' and self._network_wrapper is not None:
            self._network_wrapper.widgetValueHasChanged.connect(lambda *_args: self._refresh_timer.start())

    def _refresh_surfaces(self):
        current = self.value()
        names = []
        reason = ''
        version = self.parameterDefinition().name() == 'VERSION_ID'
        try:
            path = self._selected_file()
            if path and Path(path).is_file():
                root = safe_xml_parse(path).getroot()
                if root.tag == 'wntNetworkStore':
                    networks = root.findall('network')
                    if version:
                        selected = wrapper_value(self._network_wrapper) if self._network_wrapper is not None else ''
                        if selected:
                            networks = [network for network in networks if network.get('id') == selected]
                        sets = [{item.get('id') for item in network.findall('version')} for network in networks]
                        names = sorted(set.intersection(*sets)) if sets else []
                    else:
                        names = [network.get('id') for network in networks]
                elif not version:
                    names = [item.get('name') for item in root.iter() if item.tag.rsplit('}', 1)[-1] == 'PipeNetwork']
        except Exception as exc:
            reason = str(exc)
        self.widget.blockSignals(True)
        self.widget.clear()
        self.widget.addItems([''] + [name for name in names if name])
        if current in names:
            self.widget.setCurrentText(current)
        self.widget.setEnabled(bool(names))
        self.widget.setToolTip(reason)
        self.widget.blockSignals(False)
        if current != self.value():
            self.widgetValueHasChanged.emit(self)
