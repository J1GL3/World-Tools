# world_tools_UI.py
from PySide6 import QtWidgets


class WorldToolsUI(QtWidgets.QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("World Tools")
        self.setMinimumWidth(320)

        # Buttons
        self.btn_isolate = QtWidgets.QPushButton("🟢 Isolate Selected Actors")
        self.btn_restore = QtWidgets.QPushButton("🔄 Restore Visibility")
        self.btn_ghost   = QtWidgets.QPushButton("👻 Enable Ghost Mode")
        self.btn_normal  = QtWidgets.QPushButton("🎨 Disable Ghost Mode")
        self.log_box     = QtWidgets.QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Logs will appear here...")

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.btn_isolate)
        layout.addWidget(self.btn_restore)
        layout.addSpacing(10)
        layout.addWidget(self.btn_ghost)
        layout.addWidget(self.btn_normal)
        layout.addSpacing(10)
        layout.addWidget(self.log_box)

        # Connect buttons
        self.btn_isolate.clicked.connect(self.controller.isolate_selected)
        self.btn_restore.clicked.connect(self.controller.restore_visibility)
        self.btn_ghost.clicked.connect(self.controller.enable_ghost_mode)
        self.btn_normal.clicked.connect(self.controller.disable_ghost_mode)

    def log(self, text: str):
        """Write a line of text into the log box."""
        self.log_box.append(text)
