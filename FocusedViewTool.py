# ==============================================================
# WorldTools_Simple.py
# Unreal Engine 5.6 - Lighting Options Added
# --------------------------------------------------------------
# Provides two clean worldbuilding tools:
#   1. Isolate Selected Actors (with lighting options)
#   2. Ghost Mode (with lighting options)
# ==============================================================

import unreal
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QVBoxLayout, QLabel, QDialog, QDialogButtonBox, QComboBox
)
from PySide6.QtCore import Qt


# --------------------------------------------------------------
# Utility: Find nearby lights
# --------------------------------------------------------------
def get_lights_in_radius(selected, radius_cm=5000.0):
    actor_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    all_actors = actor_subsys.get_all_level_actors()
    nearby = []

    for sel in selected:
        sel_loc = sel.get_actor_location()
        for actor in all_actors:
            if not actor or actor in selected:
                continue
            if "Light" in actor.get_class().get_name():
                dist = sel_loc.distance_to(actor.get_actor_location())
                if dist <= radius_cm:
                    nearby.append(actor)
    return list(set(nearby))


# --------------------------------------------------------------
# Lighting Mode Dialog
# --------------------------------------------------------------
def ask_lighting_mode(parent=None):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Select Lighting Mode")
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)

    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("Include lights in this operation? (5000 cm radius for nearby)"))
    combo = QComboBox()
    combo.addItems(["No Lights", "Nearby Lights", "All Lights"])
    layout.addWidget(combo)

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    layout.addWidget(buttons)

    chosen = {"mode": None}
    buttons.accepted.connect(lambda: (dlg.accept(), chosen.update({"mode": combo.currentText()})))
    buttons.rejected.connect(dlg.reject)

    dlg.exec()
    return chosen["mode"]


# --------------------------------------------------------------
# Main UI
# --------------------------------------------------------------
class WorldToolsSimpleUI(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("World Tools – Simplified")
        self.setMinimumWidth(320)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.Tool, True)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("🌍 World Visibility Tools"))
        self.btn_isolate = QPushButton("🟢 Isolate Selected Actors")
        self.btn_restore = QPushButton("🔄 Restore Visibility")
        layout.addWidget(self.btn_isolate)
        layout.addWidget(self.btn_restore)

        layout.addSpacing(10)
        layout.addWidget(QLabel("🎨 Visual Overlay Tools"))
        self.btn_ghost_on = QPushButton("👻 Enable Ghost Mode")
        self.btn_ghost_off = QPushButton("💎 Disable Ghost Mode")
        layout.addWidget(self.btn_ghost_on)
        layout.addWidget(self.btn_ghost_off)
        layout.addSpacing(10)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Logs will appear here...")
        layout.addWidget(self.log_box)

        self.btn_isolate.clicked.connect(self.controller.isolate_selected)
        self.btn_restore.clicked.connect(self.controller.restore_visibility)
        self.btn_ghost_on.clicked.connect(self.controller.enable_ghost_mode)
        self.btn_ghost_off.clicked.connect(self.controller.disable_ghost_mode)

    def log(self, msg):
        self.log_box.append(msg)


# --------------------------------------------------------------
# Logic Controller
# --------------------------------------------------------------
class WorldToolsSimple:
    def __init__(self):
        self.hidden_actors = []
        self.ghosted_actors = []
        self.original_materials = {}

        app = QApplication.instance()
        if not app:
            app = QApplication([])

        self.ui = WorldToolsSimpleUI(controller=self)
        self.ui.show()

    # ----------------------------------------------------------
    # 🟢 Isolate selected actors (with lighting options)
    # ----------------------------------------------------------
    def isolate_selected(self):
        actor_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        selected = actor_subsys.get_selected_level_actors()
        all_actors = actor_subsys.get_all_level_actors()
        self.hidden_actors.clear()

        if not selected:
            self.ui.log("⚠️ No actors selected.")
            return

        lighting_mode = ask_lighting_mode(self.ui)
        if lighting_mode is None:
            return

        extra_lights = []
        if lighting_mode == "Nearby Lights":
            extra_lights = get_lights_in_radius(selected, 5000.0)
        elif lighting_mode == "All Lights":
            extra_lights = [a for a in all_actors if "Light" in a.get_class().get_name()]

        keep_visible = set(selected + extra_lights)

        for actor in all_actors:
            if actor not in keep_visible:
                actor.set_is_temporarily_hidden_in_editor(True)
                self.hidden_actors.append(actor)

        self.ui.log(
            f"🟢 Isolated {len(selected)} actor(s), kept {len(extra_lights)} light(s) visible, hid {len(self.hidden_actors)} others."
        )

    # ----------------------------------------------------------
    # 🔄 Restore visibility
    # ----------------------------------------------------------
    def restore_visibility(self):
        for actor in self.hidden_actors:
            if actor:
                actor.set_is_temporarily_hidden_in_editor(False)
        count = len(self.hidden_actors)
        self.hidden_actors.clear()
        self.ui.log(f"🔄 Restored visibility for {count} actors.")

    # ----------------------------------------------------------
    # 👻 Enable ghost mode (with lighting options)
    # ----------------------------------------------------------
    def enable_ghost_mode(self):
        actor_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        selected = actor_subsys.get_selected_level_actors()
        all_actors = actor_subsys.get_all_level_actors()
        lighting_mode = ask_lighting_mode(self.ui)
        if lighting_mode is None:
            return

        extra_lights = []
        if lighting_mode == "Nearby Lights":
            extra_lights = get_lights_in_radius(selected, 5000.0)
        elif lighting_mode == "All Lights":
            extra_lights = [a for a in all_actors if "Light" in a.get_class().get_name()]

        keep_visible = set(selected + extra_lights)

        ghost_mat = unreal.load_asset("/Engine/EngineDebugMaterials/WireframeMaterial.WireframeMaterial")
        if not ghost_mat:
            self.ui.log("⚠️ Wireframe material not found.")
            return

        self.ghosted_actors.clear()
        self.original_materials.clear()

        for actor in all_actors:
            if actor in keep_visible:
                continue

            mesh_components = actor.get_components_by_class(unreal.StaticMeshComponent)
            for comp in mesh_components:
                mats = comp.get_materials()
                self.original_materials[(actor, comp)] = mats
                for i in range(len(mats)):
                    comp.set_material(i, ghost_mat)
            if mesh_components:
                self.ghosted_actors.append(actor)

        self.ui.log(f"👻 Ghost mode applied to {len(self.ghosted_actors)} actors (lights preserved).")

    # ----------------------------------------------------------
    # 💎 Disable ghost mode
    # ----------------------------------------------------------
    def disable_ghost_mode(self):
        restored = 0
        for (actor, comp), mats in self.original_materials.items():
            if not comp or not actor:
                continue
            try:
                for i, mat in enumerate(mats):
                    if mat:
                        comp.set_material(i, mat)
                restored += 1
            except Exception as e:
                self.ui.log(f"⚠️ Failed to restore materials on {actor.get_name()}: {e}")

        self.original_materials.clear()
        self.ghosted_actors.clear()
        self.ui.log(f"💎 Restored {restored} mesh components from ghost mode.")


# --------------------------------------------------------------
# Entry Point
# --------------------------------------------------------------
def launch_world_tools_simple():
    WorldToolsSimple()


if __name__ == "__main__":
    launch_world_tools_simple()
