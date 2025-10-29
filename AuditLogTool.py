# Audit Log Tool
# Core:
#   ✅ Run Audit (missing assets, bad names, Nanite off, unused)
#   ⚡ Enable Nanite on flagged meshes
#   🧹 Find unused assets/materials
#   🪄 Auto-Fix Naming (prefix + cleanup)
#   🧾 Sectioned output log for clear readability
# ==============================================================

import unreal
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QVBoxLayout,
    QLabel, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
import re


# --------------------------------------------------------------
# 0. MENU REGISTRATION (Unreal toolbar / main menu integration)
# --------------------------------------------------------------
# This class creates a new top-level menu item in the Unreal
# Level Editor main menu bar, so you can launch the tool from there.

class AudToolMenu:
    def __init__(self):
        # get access to the ToolMenus subsystem
        self.tool_menus = unreal.ToolMenus.get()

        # we define some names we're going to reuse
        self.menu_owner = "AuditToolOwner"  # just an ID string
        self.menu_name = "LevelEditor.MainMenu.AuditToolMenu"  # full path for new menu
        self.parent_menu_name = "LevelEditor.MainMenu"  # the built-in main menu
        self.section_name = "AuditToolsSection"

        # will store the menu object we register
        self.audit_menu = None

    def create_menu(self):
        """
        Creates a new top-level menu called "Audit Tool"
        inside the Level Editor menu bar.
        """
        unreal.log("Creating Audit Tool menu...")

        # first check if menu already exists (so we don't spam-register)
        existing = self.tool_menus.find_menu(self.menu_name)
        if existing:
            unreal.log("Audit Tool menu already exists, reusing it.")
            self.audit_menu = existing
            return

        # register a new menu that lives under LevelEditor.MainMenu
        self.audit_menu = self.tool_menus.register_menu(
            name=self.menu_name,
            parent=self.parent_menu_name,
            # "label" is what shows up in the editor menu bar
            # NOTE: In 5.x, you pass these as arguments instead of setting after
            # but Python API can vary a tiny bit so we also set it afterwards just in case.
            )
        # set some readable information
        self.audit_menu.menu_label = "Audit Tool"
        self.audit_menu.tool_tip = "Tools for auditing and fixing the project"

        # add a section so we have a place to put entries
        self.audit_menu.add_section(self.section_name, "Audit Actions")

        # refresh UI
        self.tool_menus.refresh_all_widgets()
        unreal.log("Audit Tool menu created.")

    def create_menu_entry(self):
        """
        Adds a menu entry that, when clicked, opens the Project Guardian window.
        """
        unreal.log("Creating Audit Tool menu entry...")

        # this is the python command we want unreal to run when you click the menu
        module_name = "AuditLogTool"  # <- THIS MUST MATCH YOUR FILE NAME (without .py)
        python_command = (
            f"import {module_name}; {module_name}.spawn_project_guardian_window()"
        )

        # build the menu entry object
        menu_entry = unreal.ToolMenuEntry(
            name="OpenProjectGuardian",
            type=unreal.MultiBlockType.MENU_ENTRY,
            insert_position=unreal.ToolMenuInsert("", unreal.ToolMenuInsertType.FIRST)
        )

        menu_entry.set_label("Open Project Guardian")
        menu_entry.set_tool_tip("Open the Project Guardian audit window")
        menu_entry.set_string_command(
            type=unreal.ToolMenuStringCommandType.PYTHON,
            custom_type="",
            string=python_command
        )

        # optionally set an icon that already exists in editor style sets
        menu_entry.set_icon("EditorStyle", "Kismet.Tabs.BlueprintDebugger")  # any valid icon

        # now add that entry to the section in our menu
        self.audit_menu.add_menu_entry(self.section_name, menu_entry)

        # refresh UI so Unreal sees it
        self.tool_menus.refresh_all_widgets()

        unreal.log("Audit Tool menu entry added.")


# --------------------------------------------------------------
# 1. HELPERS
# --------------------------------------------------------------
# building the string to load assets 

def build_object_path(asset_data: unreal.AssetData) -> str:
    pkg = asset_data.package_name
    name = asset_data.asset_name
    return f"{pkg}.{name}"


# find 
def is_under_game(asset_data: unreal.AssetData) -> bool:
    try:
        return str(asset_data.package_name).startswith("/Game")
    except Exception:
        return False


def load_asset_safe(asset_path: str):
    try:
        return unreal.EditorAssetLibrary.load_asset(asset_path)
    except Exception:
        return None


def is_static_mesh_asset(asset_data: unreal.AssetData) -> bool:
    try:
        return asset_data.asset_class_path.asset_name == "StaticMesh"
    except Exception:
        return False


def bad_name(asset_name: str) -> str | None:
    # NOTE you wrote "👌Contains spaces" before, I'm keeping that 😄
    if " " in asset_name:
        return "👌Contains spaces"
    if asset_name.startswith("New") or asset_name.startswith("Untitled"):
        return "Temp/placeholder name"
    first_char = asset_name[0]
    if first_char.lower() == first_char:
        return "Starts lowercase"
    return None


def get_prefix_for_class(asset_class: str) -> str:
    if "StaticMesh" in asset_class:
        return "SM_"
    if "MaterialInstance" in asset_class:
        return "MI_"
    if "Material" in asset_class:
        return "M_"
    if "Texture" in asset_class:
        return "T_"
    if "Blueprint" in asset_class:
        return "BP_"
    if "Sound" in asset_class:
        return "S_"
    return "A_"


def clean_asset_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    name = name.replace(" ", "_")
    name = "_".join(w.capitalize() for w in name.split("_") if w)
    return name


# --------------------------------------------------------------
# 2. SCAN FUNCTIONS
# --------------------------------------------------------------

def find_missing_or_broken_assets():
    issues = []
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    for asset_data in asset_reg.get_all_assets():
        if not is_under_game(asset_data):
            continue
        path = build_object_path(asset_data)
        if not load_asset_safe(path):
            issues.append((path, "Asset failed to load / possibly missing"))
    return issues


def audit_naming_and_nanite():
    naming_issues = []
    nanite_issues = []
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()

    for asset_data in asset_reg.get_all_assets():
        if not is_under_game(asset_data):
            continue

        path = build_object_path(asset_data)

        # naming
        name_problem = bad_name(str(asset_data.asset_name))
        if name_problem:
            naming_issues.append((path, f"Naming issue: {name_problem}"))

        # nanite
        if is_static_mesh_asset(asset_data):
            mesh = load_asset_safe(path)
            if mesh:
                try:
                    nanite_settings = mesh.get_editor_property("nanite_settings")
                    enabled = nanite_settings.get_editor_property("enabled")
                except Exception:
                    enabled = False
                if not enabled:
                    nanite_issues.append((path, "StaticMesh has Nanite DISABLED"))

    return naming_issues, nanite_issues


def find_unused_assets():
    unused = []
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    all_assets = [a for a in asset_reg.get_all_assets() if is_under_game(a)]
    for asset_data in all_assets:
        path = build_object_path(asset_data)
        refs = unreal.EditorAssetLibrary.find_package_referencers_for_asset(path)
        if not refs:
            unused.append((path, "Unused asset (no referencers)"))
    return unused


# --------------------------------------------------------------
# 3. FIX FUNCTIONS
# --------------------------------------------------------------

def enable_nanite_for_all_flagged():
    changed = 0
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()

    for asset_data in asset_reg.get_all_assets():
        if not is_under_game(asset_data):
            continue
        if not is_static_mesh_asset(asset_data):
            continue

        path = build_object_path(asset_data)
        mesh = load_asset_safe(path)
        if not mesh:
            continue

        try:
            nanite_settings = mesh.get_editor_property("nanite_settings")
            if not nanite_settings.get_editor_property("enabled"):
                nanite_settings.set_editor_property("enabled", True)
                mesh.set_editor_property("nanite_settings", nanite_settings)
                unreal.EditorAssetLibrary.save_loaded_asset(mesh)
                changed += 1
        except Exception:
            continue

    return changed


def auto_fix_naming():
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    renamed = []

    for asset_data in asset_reg.get_all_assets():
        if not is_under_game(asset_data):
            continue

        old_name = str(asset_data.asset_name)

        try:
            asset_class = asset_data.asset_class_path.asset_name
        except Exception:
            # Fallback if api changed / weird asset
            asset_class = str(asset_data.asset_class)

        prefix = get_prefix_for_class(str(asset_class))

        # if it's already good, skip
        if old_name.startswith(prefix):
            continue

        # build new name
        new_name = clean_asset_name(old_name)
        new_name = prefix + new_name

        old_path = build_object_path(asset_data)
        pkg_path = str(asset_data.package_path)

        try:
            success = unreal.EditorAssetLibrary.rename_asset(
                old_path,
                f"{pkg_path}/{new_name}"
            )
            if success:
                renamed.append((old_name, new_name))
        except Exception as e:
            unreal.log_warning(f"Failed to rename {old_name}: {e}")
            continue

    return renamed


# --------------------------------------------------------------
# 4. UI (the floating PySide6 panel)
# --------------------------------------------------------------

class ProjectGuardianUI(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.setWindowTitle("Project Guardian 🛡️")
        self.setMinimumWidth(540)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.Tool, True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("🔍 Project Audit Tools"))

        # buttons to run each feature
        self.btn_audit = QPushButton("🔎 Run Project Audit")
        self.btn_nanite = QPushButton("⚡ Enable Nanite on Flagged Meshes")
        self.btn_unused = QPushButton("🧹 Find Unused Assets/Materials")
        self.btn_fix_names = QPushButton("🪄 Auto-Fix Naming")

        layout.addWidget(self.btn_audit)
        layout.addWidget(self.btn_nanite)
        layout.addWidget(self.btn_unused)
        layout.addWidget(self.btn_fix_names)

        # results list
        layout.addWidget(QLabel("📜 Results"))
        self.results = QListWidget()
        self.results.setSelectionMode(QListWidget.NoSelection)
        layout.addWidget(self.results)

        # log output console
        layout.addWidget(QLabel("📝 Log"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)

        # hook up buttons to controller callbacks
        self.btn_audit.clicked.connect(self.controller.on_audit)
        self.btn_nanite.clicked.connect(self.controller.on_enable_nanite)
        self.btn_unused.clicked.connect(self.controller.on_find_unused)
        self.btn_fix_names.clicked.connect(self.controller.on_fix_names)

    def log(self, msg):
        self.log_box.append(msg)

    def clear(self):
        self.results.clear()

    def add(self, msg):
        self.results.addItem(QListWidgetItem(msg))


# --------------------------------------------------------------
# 5. CONTROLLER (runs logic when you click buttons)
# --------------------------------------------------------------

class ProjectGuardianController:
    def __init__(self):
        # make sure there's a Qt app instance
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        # build the UI
        self.ui = ProjectGuardianUI(controller=self)
        self.ui.show()

    # Sectioned Audit Output
    def on_audit(self):
        self.ui.clear()
        self.ui.log("🚦 Running Project Audit...\n")

        # Pass 1: Missing / Broken assets
        missing = find_missing_or_broken_assets()
        self.ui.log("────────────────────────────")
        self.ui.log("📦 Missing / Broken Assets")
        self.ui.log("────────────────────────────")
        if missing:
            for path, issue in missing:
                self.ui.add(f"{path}: {issue}")
                self.ui.log(f"⚠️ {path}: {issue}")
        else:
            self.ui.log("✅ None found.\n")

        # Pass 2: Naming + Nanite
        naming_issues, nanite_issues = audit_naming_and_nanite()

        self.ui.log("────────────────────────────")
        self.ui.log("🧩 Naming Issues")
        self.ui.log("────────────────────────────")
        if naming_issues:
            for path, issue in naming_issues:
                self.ui.add(f"{path}: {issue}")
                self.ui.log(f"⚠️ {path}: {issue}")
        else:
            self.ui.log("✅ None found.\n")

        self.ui.log("────────────────────────────")
        self.ui.log("🧱 Nanite Disabled Meshes")
        self.ui.log("────────────────────────────")
        if nanite_issues:
            for path, issue in nanite_issues:
                self.ui.add(f"{path}: {issue}")
                self.ui.log(f"⚠️ {path}: {issue}")
        else:
            self.ui.log("✅ All static meshes have Nanite enabled.\n")

        # Pass 3: Unused assets
        unused = find_unused_assets()
        self.ui.log("────────────────────────────")
        self.ui.log("🧹 Unused Assets")
        self.ui.log("────────────────────────────")
        if unused:
            for path, issue in unused:
                self.ui.add(f"{path}: {issue}")
                self.ui.log(f"🗑️ {path}: {issue}")
        else:
            self.ui.log("✅ No unused assets found.\n")

        total = len(missing) + len(naming_issues) + len(nanite_issues) + len(unused)
        self.ui.log("────────────────────────────")
        if total == 0:
            self.ui.log("🎉 Project is clean — no major issues detected!")
        else:
            self.ui.log(f"🚨 Audit complete — {total} issue(s) found. See details above.")
        self.ui.log("────────────────────────────\n")

    def on_enable_nanite(self):
        self.ui.log("⚡ Enabling Nanite on all flagged meshes...")
        count = enable_nanite_for_all_flagged()
        self.ui.log(f"✅ Nanite enabled on {count} mesh(es).\n")

    def on_find_unused(self):
        self.ui.clear()
        self.ui.log("🧹 Scanning for unused assets/materials...")
        unused = find_unused_assets()
        self.ui.log("────────────────────────────")
        self.ui.log("🧹 Unused Assets")
        self.ui.log("────────────────────────────")
        if unused:
            for path, issue in unused:
                self.ui.add(f"{path}: {issue}")
                self.ui.log(f"🗑️ {path}: {issue}")
        else:
            self.ui.log("✅ No unused assets found.\n")

    def on_fix_names(self):
        self.ui.log("🪄 Auto-fixing asset names...")
        fixed = auto_fix_naming()
        if fixed:
            for old, new in fixed:
                self.ui.add(f"Renamed {old} → {new}")
                self.ui.log(f"✅ Renamed {old} → {new}")
        else:
            self.ui.log("✨ All asset names already follow conventions!")
        self.ui.log("\n")


# --------------------------------------------------------------
# 6. ENTRY POINTS
# --------------------------------------------------------------
# We provide TWO entry points now:
# 1. spawn_project_guardian_window() - for the menu click
# 2. launch_project_guardian()       - for running manually / testing


def spawn_project_guardian_window():
    """
    This is what the Unreal menu item will call.
    It just spawns the UI.
    """
    unreal.log("Spawning Project Guardian window from menu...")
    ProjectGuardianController()


def launch_project_guardian():
    """
    Call this manually in the Python console if you want:
    import AuditLogTool
    AuditLogTool.launch_project_guardian()
    Also sets up the main menu if it's not there yet.
    """
    unreal.log("Setting up Audit Tool menu...")

    menu = AudToolMenu()
    menu.create_menu()
    menu.create_menu_entry()

    unreal.log("Launching Project Guardian controller UI...")
    ProjectGuardianController()


# When run directly, set up menu + open UI
if __name__ == "__main__":
    launch_project_guardian()
