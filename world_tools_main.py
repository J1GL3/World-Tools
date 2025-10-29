# world_tools_main.py
import unreal
from PySide6 import QtWidgets
from WorldTools import world_tools_UI


class WorldTools:
    def __init__(self):
        self.hidden_actors = []
        self.ghosted_actors = []
        self.original_materials = {}

        # Make sure a QApplication exists
        app = QtWidgets.QApplication.instance()
        if not app:
            app = QtWidgets.QApplication([])

        # Create and show UI
        self.ui = world_tools_UI.WorldToolsUI(controller=self)
        self.ui.show()

    # ---------------- Isolate Selected ----------------
    def isolate_selected(self):
        selected = unreal.EditorLevelLibrary.get_selected_level_actors()
        all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
        self.hidden_actors.clear()

        if not selected:
            self.ui.log("⚠️ No actors selected.")
            return

        for actor in all_actors:
            if actor not in selected:
                actor.set_is_temporarily_hidden_in_editor(True)
                self.hidden_actors.append(actor)

        self.ui.log(f"🟢 Isolated {len(selected)} actor(s), hid {len(self.hidden_actors)} others.")

    # ---------------- Restore Visibility ----------------
    def restore_visibility(self):
        for actor in self.hidden_actors:
            if actor:
                actor.set_is_temporarily_hidden_in_editor(False)
        count = len(self.hidden_actors)
        self.hidden_actors.clear()
        self.ui.log(f"🔄 Restored visibility for {count} actors.")

    # ---------------- Enable Ghost Mode ----------------
    def enable_ghost_mode(self):
        selected = unreal.EditorLevelLibrary.get_selected_level_actors()
        all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
        ghost_mat_path = "/Engine/EngineDebugMaterials/WireframeMaterial.WireframeMaterial"
        ghost_mat = unreal.load_asset(ghost_mat_path)

        if not ghost_mat:
            self.ui.log("⚠️ Could not find wireframe material.")
            return

        self.ghosted_actors.clear()
        self.original_materials.clear()

        for actor in all_actors:
            if actor not in selected:
                static_comp = actor.get_component_by_class(unreal.StaticMeshComponent)
                if static_comp:
                    mats = static_comp.get_materials()
                    self.original_materials[actor] = mats
                    static_comp.set_material(0, ghost_mat)
                    self.ghosted_actors.append(actor)

        self.ui.log(f"👻 Ghost mode applied to {len(self.ghosted_actors)} actors.")

    # ---------------- Disable Ghost Mode ----------------
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


# ---------------- ENTRY POINT ----------------
def launch():
    tool = WorldTools()
    return tool


# If run directly (e.g. from VS Code)
if __name__ == "__main__":
    launch()
