# world_tools.py
# Unreal Engine 5.6 all-in-one "World Tools"
# Includes:
# - Visibility Tools (Isolate / Ghost / Restore)
# - Missing Reference Finder
# - Focused Editor prototype (save a working set of actors and operate on just them)

import unreal
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QVBoxLayout,
    QLabel, QGroupBox, QListWidget, QListWidgetItem
)


class WorldToolsUI(QWidget):
    """PySide6 user interface."""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("World Tools")
        self.setMinimumWidth(400)

        main_layout = QVBoxLayout(self)

        # -------------------------------------------------
        # VISIBILITY TOOLS SECTION
        # -------------------------------------------------
        vis_group = QGroupBox("Visibility Tools (Global)")
        vis_layout = QVBoxLayout(vis_group)
        self.btn_isolate = QPushButton("🟢 Isolate Selected Actors")
        self.btn_restore = QPushButton("🔄 Restore Visibility")
        self.btn_ghost = QPushButton("👻 Enable Ghost Mode")
        self.btn_normal = QPushButton("🎨 Disable Ghost Mode")
        vis_layout.addWidget(self.btn_isolate)
        vis_layout.addWidget(self.btn_restore)
        vis_layout.addWidget(self.btn_ghost)
        vis_layout.addWidget(self.btn_normal)
        main_layout.addWidget(vis_group)

        # -------------------------------------------------
        # FOCUSED EDITOR SECTION
        # -------------------------------------------------
        focus_group = QGroupBox("Focused Editor")
        focus_layout = QVBoxLayout(focus_group)

        focus_layout.addWidget(QLabel("Focused Actor Set (your working chunk):"))
        self.focus_list = QListWidget()
        focus_layout.addWidget(self.focus_list)

        self.btn_set_focus = QPushButton("📌 Create/Replace Focused Set From Current Selection")
        self.btn_add_to_focus = QPushButton("➕ Add Current Selection To Focused Set")
        self.btn_focus_isolate = QPushButton("🔍 Show Only Focused Set (Hide Everything Else)")
        self.btn_focus_ghost_world = QPushButton("👻 Ghost World (Keep Focused Normal)")
        self.btn_focus_restore = QPushButton("🌎 Restore World Visibility / Materials")

        focus_layout.addWidget(self.btn_set_focus)
        focus_layout.addWidget(self.btn_add_to_focus)
        focus_layout.addWidget(self.btn_focus_isolate)
        focus_layout.addWidget(self.btn_focus_ghost_world)
        focus_layout.addWidget(self.btn_focus_restore)

        main_layout.addWidget(focus_group)

        # -------------------------------------------------
        # MISSING REF FINDER SECTION
        # -------------------------------------------------
        missing_group = QGroupBox("Missing Reference Finder")
        missing_layout = QVBoxLayout(missing_group)
        self.btn_missing_refs = QPushButton("🔍 Find Missing Mesh / Material References")
        missing_layout.addWidget(self.btn_missing_refs)
        main_layout.addWidget(missing_group)

        # -------------------------------------------------
        # LOG
        # -------------------------------------------------
        main_layout.addWidget(QLabel("Output Log:"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Logs will appear here...")
        main_layout.addWidget(self.log_box)

        # -------------------------------------------------
        # WIRE UP SIGNALS
        # -------------------------------------------------
        # visibility tools
        self.btn_isolate.clicked.connect(self.controller.isolate_selected)
        self.btn_restore.clicked.connect(self.controller.restore_visibility)
        self.btn_ghost.clicked.connect(self.controller.enable_ghost_mode)
        self.btn_normal.clicked.connect(self.controller.disable_ghost_mode)

        # focused editor tools
        self.btn_set_focus.clicked.connect(self.controller.create_focused_set_from_selection)
        self.btn_add_to_focus.clicked.connect(self.controller.add_selection_to_focused_set)
        self.btn_focus_isolate.clicked.connect(self.controller.focus_isolate_only_focused)
        self.btn_focus_ghost_world.clicked.connect(self.controller.focus_ghost_world_except_focused)
        self.btn_focus_restore.clicked.connect(self.controller.focus_restore_world)

        # missing ref tool
        self.btn_missing_refs.clicked.connect(self.controller.find_missing_references)

    def refresh_focus_list(self, focused_actors):
        """Update the UI list showing which actors are in the Focused Set."""
        self.focus_list.clear()
        for actor in focused_actors:
            name = "(deleted?)"
            if actor:
                try:
                    name = actor.get_name()
                except Exception:
                    pass
            QListWidgetItem(name, self.focus_list)

    def log(self, text: str):
        self.log_box.append(text)


class WorldTools:
    """Main logic controller that talks to Unreal and drives the UI."""
    def __init__(self):
        # visibility system storage
        self.hidden_actors = []
        self.ghosted_actors = []
        self.original_materials = {}

        # focused editor storage
        self.focused_actors = []              # actors user cares about
        self.focus_hidden_actors = []         # actors hidden due to focus isolate
        self.focus_original_materials = {}    # for focused ghost mode

        # build UI / QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        self.ui = WorldToolsUI(controller=self)
        self.ui.show()

    # ==========================================================
    # GLOBAL VISIBILITY TOOLS (you already had these)
    # ==========================================================
    def isolate_selected(self):
        selected = unreal.EditorLevelLibrary.get_selected_level_actors()
        all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
        self.hidden_actors.clear()

        if not selected:
            self.ui.log("⚠️ No actors selected for isolate_selected()")
            return

        for actor in all_actors:
            if actor not in selected:
                actor.set_is_temporarily_hidden_in_editor(True)
                self.hidden_actors.append(actor)

        self.ui.log(f"🟢 Isolated {len(selected)} actor(s), hid {len(self.hidden_actors)} others.")

    def restore_visibility(self):
        for actor in self.hidden_actors:
            if actor:
                actor.set_is_temporarily_hidden_in_editor(False)
        count = len(self.hidden_actors)
        self.hidden_actors.clear()
        self.ui.log(f"🔄 Restored visibility for {count} actors hidden by isolate_selected().")

    def enable_ghost_mode(self):
        selected = unreal.EditorLevelLibrary.get_selected_level_actors()
        all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
        ghost_mat = unreal.load_asset("/Engine/EngineDebugMaterials/WireframeMaterial.WireframeMaterial")

        if not ghost_mat:
            self.ui.log("⚠️ Could not find wireframe material for ghost mode.")
            return

        self.ghosted_actors.clear()
        self.original_materials.clear()

        for actor in all_actors:
            if actor not in selected:
                static_comp = actor.get_component_by_class(unreal.StaticMeshComponent)
                if static_comp:
                    mats = static_comp.get_materials()
                    self.original_materials[actor] = mats
                    # apply ghost mat only to slot 0 for now
                    static_comp.set_material(0, ghost_mat)
                    self.ghosted_actors.append(actor)

        self.ui.log(f"👻 Ghost mode applied to {len(self.ghosted_actors)} non-selected actors.")

    def disable_ghost_mode(self):
        restored = 0
        for actor, mats in self.original_materials.items():
            static_comp = actor.get_component_by_class(unreal.StaticMeshComponent)
            if static_comp:
                for i, mat in enumerate(mats):
                    static_comp.set_material(i, mat)
                restored += 1

        self.original_materials.clear()
        self.ghosted_actors.clear()
        self.ui.log(f"🎨 Restored {restored} actors from ghost mode.")

    # ==========================================================
    # FOCUSED EDITOR SYSTEM (your new idea 💡)
    # ==========================================================
    def create_focused_set_from_selection(self):
        """Replace the current focused set with whatever's selected in the level."""
        selected = unreal.EditorLevelLibrary.get_selected_level_actors()
        if not selected:
            self.ui.log("⚠️ No actors selected. Focused Set not updated.")
            return

        self.focused_actors = list(selected)
        self.ui.refresh_focus_list(self.focused_actors)
        self.ui.log(f"📌 Focused Set created with {len(self.focused_actors)} actor(s).")

    def add_selection_to_focused_set(self):
        """Add currently selected actors to the focused set."""
        selected = unreal.EditorLevelLibrary.get_selected_level_actors()
        if not selected:
            self.ui.log("⚠️ No actors selected. Nothing added.")
            return

        # only add new actors that aren't already tracked
        existing = set(self.focused_actors)
        added_count = 0
        for actor in selected:
            if actor not in existing:
                self.focused_actors.append(actor)
                added_count += 1

        self.ui.refresh_focus_list(self.focused_actors)
        self.ui.log(f"➕ Added {added_count} new actor(s) to Focused Set "
                    f"(total now {len(self.focused_actors)}).")

    def _get_all_level_actors(self):
        """Helper: safe wrapper so we only call this once per op."""
        return unreal.EditorLevelLibrary.get_all_level_actors()

    def focus_isolate_only_focused(self):
        """
        Hide everything in the world except the Focused Set.
        This is like isolate_selected(), but persistent to your chosen set.
        """
        if not self.focused_actors:
            self.ui.log("⚠️ Focused Set is empty. Can't isolate.")
            return

        all_actors = self._get_all_level_actors()
        self.focus_hidden_actors.clear()

        for actor in all_actors:
            if actor not in self.focused_actors:
                actor.set_is_temporarily_hidden_in_editor(True)
                self.focus_hidden_actors.append(actor)

        self.ui.log(
            f"🔍 Focused isolate active. "
            f"Showing {len(self.focused_actors)} actor(s), hid {len(self.focus_hidden_actors)} others."
        )

    def focus_ghost_world_except_focused(self):
        """
        Ghost everything except the Focused Set.
        This keeps your set normal and makes everything else wireframe.
        """
        if not self.focused_actors:
            self.ui.log("⚠️ Focused Set is empty. Can't ghost world.")
            return

        ghost_mat = unreal.load_asset("/Engine/EngineDebugMaterials/WireframeMaterial.WireframeMaterial")
        if not ghost_mat:
            self.ui.log("⚠️ Could not find wireframe material for focus ghost.")
            return

        all_actors = self._get_all_level_actors()
        self.focus_original_materials.clear()

        ghosted_count = 0

        for actor in all_actors:
            if actor in self.focused_actors:
                continue  # leave focused actors alone

            static_comp = actor.get_component_by_class(unreal.StaticMeshComponent)
            if static_comp:
                mats = static_comp.get_materials()
                # store full list so we can restore every slot later
                self.focus_original_materials[actor] = mats
                static_comp.set_material(0, ghost_mat)
                ghosted_count += 1

        self.ui.log(
            f"👻 Focus Ghost Mode applied to {ghosted_count} actor(s) "
            f"(focused actors left normal)."
        )

    def focus_restore_world(self):
        """
        Restore world after either focus_isolate_only_focused() or focus_ghost_world_except_focused().
        """
        # Un-hide actors hidden by focus_isolate_only_focused
        for actor in self.focus_hidden_actors:
            if actor:
                actor.set_is_temporarily_hidden_in_editor(False)
        unhid = len(self.focus_hidden_actors)
        self.focus_hidden_actors.clear()

        # Restore materials after focus_ghost_world_except_focused
        restored_visuals = 0
        for actor, mats in self.focus_original_materials.items():
            static_comp = actor.get_component_by_class(unreal.StaticMeshComponent)
            if static_comp:
                for i, mat in enumerate(mats):
                    static_comp.set_material(i, mat)
                restored_visuals += 1

        self.focus_original_materials.clear()

        self.ui.log(
            f"🌎 Focus view cleared. Unhid {unhid} actors and restored materials on {restored_visuals} actor(s)."
        )

    # ==========================================================
    # MISSING REF FINDER
    # ==========================================================
    def find_missing_references(self):
        """
        Scan for missing StaticMesh or Material assignments.
        Checks selected actors; if none selected, scans full level.
        """
        self.ui.log("🟡 Running Missing Reference Finder...")

        selected = unreal.EditorLevelLibrary.get_selected_level_actors()
        if not selected:
            selected = unreal.EditorLevelLibrary.get_all_level_actors()
            self.ui.log("ℹ️ No actors selected — scanning entire level.")

        missing_meshes = []
        missing_mats = []

        for actor in selected:
            comps = actor.get_components_by_class(unreal.StaticMeshComponent)
            if not comps:
                continue

            for comp in comps:
                mesh = comp.get_static_mesh()
                if mesh is None:
                    missing_meshes.append(actor.get_name())

                # Check materials
                for idx, mat in enumerate(comp.get_materials()):
                    if mat is None:
                        missing_mats.append(f"{actor.get_name()} [Mat Slot {idx}]")

        if not missing_meshes and not missing_mats:
            self.ui.log("✅ No missing meshes or materials found.")
            return

        if missing_meshes:
            self.ui.log("⚠️ Missing Meshes:")
            for m in missing_meshes:
                self.ui.log(f"  • {m}")

        if missing_mats:
            self.ui.log("⚠️ Missing Materials:")
            for m in missing_mats:
                self.ui.log(f"  • {m}")

        total = len(missing_meshes) + len(missing_mats)
        self.ui.log(f"🔍 Finished scan — found {total} issue(s).")

    # ==========================================================
    # FUTURE SECTIONS (NOT IMPLEMENTED YET)
    # Material Audit Tool
    # Project Info Dashboard
    # Actor Stats Panel
    # ==========================================================


# --------------------------------------------------------------
# LAUNCHER
# --------------------------------------------------------------
def launch():
    WorldTools()


if __name__ == "__main__":
    launch()
