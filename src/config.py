from aqt import mw, gui_hooks
from aqt.qt import *
from aqt.utils import showInfo


# Global Config Manager
class ConfigManager:
    _callback = None

    @classmethod
    def get(cls):
        return mw.addonManager.getConfig(__name__) or {}

    @classmethod
    def save(cls, new_config):
        mw.addonManager.writeConfig(__name__, new_config)
        # Notify listeners
        if cls._callback:
            cls._callback()

    @classmethod
    def set_callback(cls, callback):
        cls._callback = callback


def on_addon_config_did_change(new_config):
    if ConfigManager._callback:
        ConfigManager._callback()


class ColorButton(QPushButton):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.setObjectName("ColorBtn")
        self.set_color(color)
        self.clicked.connect(self._choose_color)

    def set_color(self, color):
        self._color = color
        self.setStyleSheet(
            f"#ColorBtn {{ background-color: {color}; border: 1px solid #999; min-width: 60px; }}"
        )

    def color(self):
        return self._color

    def _choose_color(self):
        color = QColorDialog.getColor(
            QColor(self._color), self.parentWidget(), "Select Color"
        )
        if color.isValid():
            self.set_color(color.name())


class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Anki Progress Bar Options")
        # Working copy
        self.config = dict(ConfigManager.get())
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        form = QFormLayout()

        # Position
        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["top", "bottom"])
        self.pos_combo.setCurrentText(self.config.get("position", "top"))
        form.addRow("Position:", self.pos_combo)

        # Color Mode
        self.color_combo = QComboBox()
        self.color_combo.addItems(["dynamic", "simple"])
        self.color_combo.setCurrentText(self.config.get("color_mode", "dynamic"))
        form.addRow("Color Mode:", self.color_combo)

        # Colors
        self.text_color_btn = ColorButton(self.config.get("text_color", "#333333"))
        form.addRow("Text Color:", self.text_color_btn)

        self.text_shadow_color_btn = ColorButton(
            self.config.get("text_shadow_color", "#f7f7f7")
        )
        form.addRow("Text Shadow:", self.text_shadow_color_btn)

        self.correct_color_btn = ColorButton(
            self.config.get("correct_color", "#4CAF50")
        )
        form.addRow("Correct Color:", self.correct_color_btn)

        self.incorrect_color_btn = ColorButton(
            self.config.get("incorrect_color", "#F44336")
        )
        form.addRow("Incorrect Color:", self.incorrect_color_btn)

        self.ghost_new_color_btn = ColorButton(
            self.config.get("ghost_new_color", "#0066FF")
        )
        form.addRow("New Color:", self.ghost_new_color_btn)

        self.ghost_learn_color_btn = ColorButton(
            self.config.get("ghost_learn_color", "#FF0000")
        )
        form.addRow("Learn Color:", self.ghost_learn_color_btn)

        self.ghost_review_color_btn = ColorButton(
            self.config.get("ghost_review_color", "#009900")
        )
        form.addRow("Review Color:", self.ghost_review_color_btn)

        # Max Time
        self.max_time_spin = QSpinBox()
        self.max_time_spin.setRange(1, 3600)
        self.max_time_spin.setSuffix(" sec")
        self.max_time_spin.setValue(self.config.get("max_time_per_card", 60))
        form.addRow("Max Time Per Card:", self.max_time_spin)

        layout.addLayout(form)

        # Advanced Section
        adv_group = QGroupBox("Advanced")
        adv_layout = QFormLayout()

        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.01, 1.0)
        self.alpha_spin.setSingleStep(0.05)
        self.alpha_spin.setValue(self.config.get("smoothing_alpha", 0.2))
        self.alpha_spin.setToolTip(
            "Determines how quickly the estimated time adapts to your recent performance.\n"
            "Higher values (closer to 1.0) prioritize recent cards,\n"
            "while lower values (closer to 0.0) favor long-term historical averages."
        )
        adv_layout.addRow("Smoothing Alpha:", self.alpha_spin)
        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def accept(self):
        self.config["position"] = self.pos_combo.currentText()
        self.config["color_mode"] = self.color_combo.currentText()
        self.config["text_color"] = self.text_color_btn.color()
        self.config["text_shadow_color"] = self.text_shadow_color_btn.color()
        self.config["correct_color"] = self.correct_color_btn.color()
        self.config["incorrect_color"] = self.incorrect_color_btn.color()
        self.config["max_time_per_card"] = self.max_time_spin.value()
        self.config["smoothing_alpha"] = self.alpha_spin.value()
        self.config["ghost_new_color"] = self.ghost_new_color_btn.color()
        self.config["ghost_learn_color"] = self.ghost_learn_color_btn.color()
        self.config["ghost_review_color"] = self.ghost_review_color_btn.color()

        ConfigManager.save(self.config)
        super().accept()
        showInfo("Configuration saved.")


def show_config():
    dialog = ConfigDialog(mw)
    dialog.exec()


# Global action reference
config_action = None


def on_state_did_change(next_state, previous_state):
    if config_action:
        config_action.setVisible(next_state == "review")


def setup_menu():
    global config_action
    config_action = QAction("Anki Progress Bar Options", mw)
    config_action.triggered.connect(show_config)
    mw.form.menuTools.addAction(config_action)
    # Register with Anki's Add-on Manager
    mw.addonManager.setConfigAction(__name__, show_config)
    mw.addonManager.setConfigUpdatedAction(__name__, on_addon_config_did_change)
    # Initial state
    config_action.setVisible(mw.state == "review")


# Setup on load
setup_menu()
gui_hooks.state_did_change.append(on_state_did_change)
