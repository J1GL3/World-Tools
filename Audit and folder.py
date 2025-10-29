# ==============================================================
# ProjectGuardian.py
# Unreal Engine 5.6
# --------------------------------------------------------------
# Project setup + QA scanner tool.
# Phase 1+2:
#   - Create default folder structure
#   - Audit project for issues:
#       * Missing / unloadable assets
#       * Bad naming
#       * Static Meshes without Nanite enabled
#
# Note: We'll skip deep dependency graph checking for now to avoid
# noisy false positives in UE5.6. We'll focus on "is this asset valid"
# and "is this asset well-formed".
# ==============================================================

import unreal
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QVBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QHBoxLayout
)
from PySide6.QtCore import Qt


# --------------------------------------------------------------
# 1. FOLDER CREATION
# --------------------------------------------------------------

FOLDER_LAYOUT = [
    "/Game/Art",
    "/Game/Art/Materials",
    "/Game/Art/Textures",
    "/Game/Art/Meshes",
    "/Game/Art/FX",
    "/Game/Art/Decals",

    "/Game/Blueprints",
    "/Game/Blueprints/Characters",
    "/Game/Blueprints/UI",
    "/Game/Blueprints/Systems",
    "/Game/Blueprints/Props",

    "/Game/Levels",
    "/Game/Levels/Environments",
    "/Game/Levels/Gameplay",
    "/Game/Levels/Test",

    "/Game/Audio",
    "/Game/Animations",
    "/Game/UI",

    "/Game/Dev",
    "/Game/Dev/Trash",
    "/Game/Dev/Temp",
]


def ensure_folder(path: str):
    """Make sure a /Game/... folder exists."""
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)
        unreal.log(f"[ProjectGuardian] Created: {path}")
        return True
    return False


def create_default_folders():
    """Create the full folder tree."""
    created_any = False
    for folder in FOLDER_LAYOUT:
        made = ensure_folder(folder)
        if made:
            created_any = True
    return created_any


# --------------------------------------------------------------
# 2. AUDIT HELPERS
# --------------------------------------------------------------

def build_object_path(asset_data: unreal.AssetData) -> str:
    """
    Reconstruct full object path from AssetData in a UE5.6-safe way.
    Example:
      package_name='/Game/Art/Meshes/SM_Crate'
      asset_name='SM_Crate'
    -> '/Game/Art/Meshes/SM_Crate.SM_Crate'
    """
    pkg = asset_data.package_name
    name = asset_data.asset_name
    return f"{pkg}.{name}"


def asset_exists(asset_path: str) -> bool:
    """Return True if an asset path points to a valid existing asset."""
    try:
        return unreal.EditorAssetLibrary.does_asset_exist(asset_path)
    except Exception:
        return False


def load_asset_safe(asset_path: str):
    """Try loading asset safely, returning None if invalid."""
    try:
        return unreal.EditorAssetLibrary.load_asset(asset_path)
    except Exception:
        return None


def is_static_mesh_asset(asset_data: unreal.AssetData) -> bool:
    try:
        return asset_data.asset_class.get_name() == "StaticMesh"
    except Exception:
        return False


def is_under_game(asset_data: unreal.AssetData) -> bool:
    """We only care about /Game, not /Engine or plugins."""
    try:
        pkg = str(asset_data.package_name)
        return pkg.startswith("/Game")
    except Exception:
        return False


def bad_name(asset_name: str) -> str | None:
    """
    Return why the name is "bad", or None if OK.
    Rules (v1):
    - no spaces
    - cannot start with lowercase
    - cannot start with 'New' or 'Untitled'
    """
    if " " in asset_name:
        return "Contains spaces"
    if asset_name.startswith("New") or asset_name.startswith("Untitled"):
        return "Temp/placeholder name"
    first_char = asset_name[0]
    if first_char.lower() == first_char:
        return "Starts lowercase"
    return None


def find_missing_references():
    """
    PASS 1:
    - For each asset in /Game, try to load it. If it can't load -> report.
    (This covers deleted/missing assets, broken blueprints, etc.)
    """
    issues = []
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    all_assets = asset_reg.get_all_assets()

    for asset_data in all_assets:
        if not is_under_game(asset_data):
            continue

        obj_path = build_object_path(asset_data)

        loaded = load_asset_safe(obj_path)
        if not loaded:
            issues.append((obj_path, "Asset failed to load / possibly missing"))
            continue

        # NOTE:
        # Real deep dependency validation (checking inside materials/blueprints for broken links)
        # would require crawling each property graph for soft references.
        # We'll keep it lean for now so it won't crash or spam.
        # We can add pass 2 later if you want deeper material/texture linking validation.

    return issues


def audit_naming_and_mesh_quality():
    """
    PASS 2:
    - Check naming rules
    - Flag Static Meshes with Nanite OFF
    Returns list[(asset_path, issue)]
    """
    results = []

    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    all_assets = asset_reg.get_all_assets()

    for asset_data in all_assets:
        if not is_under_game(asset_data):
            continue

        obj_path = build_object_path(asset_data)
        asset_name = str(asset_data.asset_name)

        # --- Naming check ---
        name_problem = bad_name(asset_name)
        if name_problem:
            results.append((obj_path, f"Naming issue: {name_problem}"))

        # --- Mesh quality check ---
        if is_static_mesh_asset(asset_data):
            mesh = load_asset_safe(obj_path)
            if mesh:
                try:
                    nanite_settings = mesh.get_editor_property("nanite_settings")
                    nanite_enabled = nanite_settings.get_editor_property("enabled")
                except Exception:
                    nanite_enabled = False

                if not nanite_enabled:
                    results.append((obj_path, "StaticMesh has Nanite DISABLED"))

    return results


# --------------------------------------------------------------
# 3. UI
# --------------------------------------------------------------

class ProjectGuardianUI(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        # Window style
        self.setWindowTitle("Project Guardian 🛡️")
        self.setMinimumWidth(520)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.Tool, True)

        main_layout = QVBoxLayout(self)

        # --- SETUP SECTION ---
        main_layout.addWidget(QLabel("🏗  Setup"))
        setup_row = QHBoxLayout()
        self.btn_create_folders = QPushButton("🗂️ Create Default Folders")
        setup_row.addWidget(self.btn_create_folders)
        main_layout.addLayout(setup_row)

        # --- AUDIT SECTION ---
        main_layout.addWidget(QLabel("🔍 Quality / Audit"))
        audit_row = QHBoxLayout()
        self.btn_run_audit = QPushButton("🔎 Run Project Audit")
        audit_row.addWidget(self.btn_run_audit)
        main_layout.addLayout(audit_row)

        # --- RESULTS LIST ---
        main_layout.addWidget(QLabel("📜 Audit Results"))
        self.results_list = QListWidget()
        self.results_list.setSelectionMode(QListWidget.NoSelection)
        main_layout.addWidget(self.results_list)

        # --- LOG BOX ---
        main_layout.addWidget(QLabel("📝 Log"))
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Project Guardian log will appear here...")
        main_layout.addWidget(self.log_box)

        # Connect signals
        self.btn_create_folders.clicked.connect(self.controller.on_create_folders)
        self.btn_run_audit.clicked.connect(self.controller.on_run_audit)

    def log(self, text: str):
        self.log_box.append(text)

    def clear_results(self):
        self.results_list.clear()

    def add_result(self, text: str):
        item = QListWidgetItem(text)
        self.results_list.addItem(item)


# --------------------------------------------------------------
# 4. Controller
# --------------------------------------------------------------

class ProjectGuardianController:
    def __init__(self):
        app = QApplication.instance()
        if not app:
            app = QApplication([])

        self.ui = ProjectGuardianUI(controller=self)
        self.ui.show()

    # ------------------------------------------
    # Setup folders
    # ------------------------------------------
    def on_create_folders(self):
        self.ui.log("📁 Creating default folder structure...")
        created_any = create_default_folders()
        if created_any:
            self.ui.log("✅ Folder structure created / updated.")
        else:
            self.ui.log("ℹ️ All folders already existed. Nothing new created.")

    # ------------------------------------------
    # Run audit
    # ------------------------------------------
    def on_run_audit(self):
        self.ui.log("🚦 Running full project audit...")
        self.ui.clear_results()

        # Pass 1: assets that can't load / missing
        self.ui.log(" - Checking asset validity...")
        broken_refs = find_missing_references()
        if broken_refs:
            for path, issue in broken_refs:
                msg = f"[LOAD] {path}: {issue}"
                self.ui.add_result(msg)
                self.ui.log(f"⚠️ {msg}")
        else:
            self.ui.log("   ✅ All assets loaded successfully (no missing assets).")

        # Pass 2: naming + mesh quality
        self.ui.log(" - Checking naming + mesh quality...")
        naming_mesh_issues = audit_naming_and_mesh_quality()
        if naming_mesh_issues:
            for path, issue in naming_mesh_issues:
                msg = f"[RULE] {path}: {issue}"
                self.ui.add_result(msg)
                self.ui.log(f"⚠️ {msg}")
        else:
            self.ui.log("   ✅ Naming + mesh quality look good.")

        total_issues = len(broken_refs) + len(naming_mesh_issues)
        if total_issues == 0:
            self.ui.log("🎉 Audit clean. No major issues found.")
        else:
            self.ui.log(f"🚨 Audit complete. {total_issues} issue(s) found. See list above.")


# --------------------------------------------------------------
# 5. Entry point
# --------------------------------------------------------------

def launch_project_guardian():
    ProjectGuardianController()


if __name__ == "__main__":
    launch_project_guardian()
