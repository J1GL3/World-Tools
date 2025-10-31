import unreal
import sys
import re
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QTextEdit, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt

# 1. HELPERS ----------------------------------------------------------------------------------------------------------------

#Creating a function that:
#gets the package path
#gets the objects short name
#and then returns the final full unreal object path
def build_object_path(asset_data: unreal.AssetData) -> str:
    pkg = asset_data.package_name
    name = asset_data.asset_name
    return f"{pkg}.{name}"

#checking whether the asset is inside the /game folder
def is_under_game(asset_data: unreal.AssetData) -> bool:
    #try incase something goes wrong when converting to a string
    try:
        #returning true if path starts with /Game otherwise returns false
        return str(asset_data.package_name).startswith("/Game")
    except Exception:
        return False

#Attempting to load an asset from unreal
def load_asset_safe(asset_path: str):
    try:
        return unreal.EditorAssetLibrary.load_asset(asset_path)
    #if it fails to load the asset because its missing or corrupted it returns None
    except Exception:
        return None

#checking to see if the assets class name is eaqual to "Static Mesh"
#this is to help identify mesh assets that can use nanite
def is_static_mesh_asset(asset_data: unreal.AssetData) -> bool:
    try:
        return asset_data.asset_class_path.asset_name == "StaticMesh"
    #if anything goes wrong returns False
    except Exception:
        return False

#checking if the assets name breaks nameing rules
def bad_name(asset_name: str) -> str | None:
    #checks if theres a space in the assets name
    if " " in asset_name:
        return "Contains spaces"
    #checks if it starts with new or untitled
    if asset_name.startswith("New") or asset_name.startswith("Untitled"):
        return "Temp/placeholder name"
    #checks if first letter is lowercase
    first_char = asset_name[0]
    if first_char.lower() == first_char:
        return "Starts lowercase"
    #if none of these are the case it returns none
    return None

#based on the asset class string returns the correct prefix
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

#making sure the asset has a clean name
def clean_asset_name(name: str) -> str:
    #replaces any characters that arent letters, numbers or underscores
    name = re.sub(r"[^A-Za-z0-9_]", "_", name)
    #replaces spaces with underscores
    name = name.replace(" ", "_")
    #makes sure each appropriate letter is uppercase
    #first letter of each word
    #first letter after each underscore
    name = "_".join(w.capitalize() for w in name.split("_") if w)
    return name

# Scan Functions ----------------------------------------------------------------------------------------------------------------

#creating a function that finds missing or brokewn assets
def find_missing_or_broken_assets():
    #creating an empty list called issues that will have the bad assets funeld into
    issues = []
    #using unreals API to access the Asset Registry which contains information of every asset
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    #filters and keeps only the assets in the game folder
    all_assets = [a for a in asset_reg.get_all_assets() if is_under_game(a)]
    #creating a loop that goes through each asset and adds it to the issues list if theres anything wrong
    for asset_data in all_assets:
        path = build_object_path(asset_data)
        if not load_asset_safe(path):
            issues.append((path, "Asset failed to load / possibly missing"))
    return issues

#creating a function that checks the naming conventions of assets and if nanite is enabled
def audit_naming_and_nanite():
    #creating 2 empty lists to store any problems
    naming_issues = []
    nanite_issues = []
    #getting the asset registry like before
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    #filters so it only includes assets in the /game
    all_assets = [a for a in asset_reg.get_all_assets() if is_under_game(a)]
    #creating a loop to go through each asset
    for asset_data in all_assets:
        path = build_object_path(asset_data)
        #getting the asset's name and passing it through the helper function that checks its naming
        name_problem = bad_name(str(asset_data.asset_name))
        #if a problem is found it is stored in the list with the path and the problem
        if name_problem:
            naming_issues.append((path, f"Naming issue: {name_problem}"))
        # checking nanite for meshes
        #checking if the asset is a static mesh
        if is_static_mesh_asset(asset_data):
            mesh = load_asset_safe(path)
            #checking if the mesh loaded successfully and if it did run the nanite check
            #if noy it skips to the next one
            if mesh:
                #trys accessing nanite settings and checks if they are enabled
                try:
                    nanite_settings = mesh.get_editor_property("nanite_settings")
                    enabled = nanite_settings.get_editor_property("enabled")
                #if anything is wrong it jsut assumes nanite is disabled so it doesnt crash!!!!
                except Exception:
                    enabled = False
                #if it is not enabled the asset is added ot the list.
                if not enabled:
                    nanite_issues.append((path, "StaticMesh has Nanite DISABLED"))
    return naming_issues, nanite_issues

#creatung a function that finds unused assets
def find_unused_assets():
    unused = []
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    all_assets = [a for a in asset_reg.get_all_assets() if is_under_game(a)]
    for asset_data in all_assets:
        path = build_object_path(asset_data)
        refs = unreal.EditorAssetLibrary.find_package_referencers_for_asset(path)
        #adds everything not used to a list
        if not refs:
            unused.append((path, "Unused asset (no referencers)"))
    return unused

#Fix Functions ----------------------------------------------------------------------------------------------------------------

#creating a function that will turn on nanite for every static mesh in the /game that has it disabled
def enable_nanite_for_all_flagged():
    changed = 0
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    #loops through every asset unreal knows about
    #checks if its under /game
    #checks if its a static mesh
    for asset_data in asset_reg.get_all_assets():
        if not is_under_game(asset_data):
            continue
        if not is_static_mesh_asset(asset_data):
            continue
        #gets the meshes object path
        path = build_object_path(asset_data)
        mesh = load_asset_safe(path)
        #if load fails skip it
        if not mesh:
            continue
        #changing nanite on meshes
        try:
            #get the meshes nanite settings
            nanite_settings = mesh.get_editor_property("nanite_settings")
            #check fi they are enabled
            if not nanite_settings.get_editor_property("enabled"):
                #if not enable them
                nanite_settings.set_editor_property("enabled", True)
                #write the modified settings back and save the asset so its permanent
                mesh.set_editor_property("nanite_settings", nanite_settings)
                unreal.EditorAssetLibrary.save_loaded_asset(mesh)
                changed += 1
        except Exception:
            continue
    return changed

#creating the function to fix the naming of assets
def auto_fix_naming():
    asset_reg = unreal.AssetRegistryHelpers.get_asset_registry()
    #get asset registry and create new list
    renamed = []
    #skipping any asset not in /game
    for asset_data in asset_reg.get_all_assets():
        if not is_under_game(asset_data):
            continue
        #gets the assets current name and class type
        old_name = str(asset_data.asset_name)
        try:
            asset_class = asset_data.asset_class_path.asset_name
        except Exception:
            asset_class = str(asset_data.asset_class)
        #fetches the correct prefix and checks to see if its applied
        prefix = get_prefix_for_class(str(asset_class))
        if old_name.startswith(prefix):
            continue
        #generating a new name by cleaning the old name with helper functions created previously
        new_name = clean_asset_name(old_name)
        new_name = prefix + new_name
        old_path = build_object_path(asset_data)
        pkg_path = str(asset_data.package_path)
        try:
            #renaming the asset
            success = unreal.EditorAssetLibrary.rename_asset(old_path, f"{pkg_path}/{new_name}")
            #if successful append the old_name and new_name tuple to renamed
            if success:
                renamed.append((old_name, new_name))
        #any excepting log it and move on
        except Exception as e:
            unreal.log_warning(f"Failed to rename {old_name}: {e}")
            continue
    return renamed

# UI ----------------------------------------------------------------------------------------------------------------

#defining a QT window class to represent the UI
class AuditLogUI(QWidget):
    #controller is passed from another class that handles the button actions logic
    def __init__(self, controller):
        #calling the base QT initialiser to set up the window
        super().__init__()
        self.controller = controller
        #creating the window title and giving it a minimum width of 540
        self.setWindowTitle("Audit Log Tool")
        self.setMinimumWidth(540)
        #keeping the tool ontop of any other windows
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        #telling unreal to treat this as a utility panel. not a main window
        self.setWindowFlag(Qt.Tool, True)
        #creating a verticle layout and adding a title to it
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Project Audit Tools"))
        #creating all of the 4 main buttons and adding them to the "layout"
        self.btn_audit = QPushButton("Run Project Audit")
        self.btn_nanite = QPushButton("Enable Nanite on Flagged Meshes")
        self.btn_unused = QPushButton("Find Unused Assets/Materials")
        self.btn_fix_names = QPushButton("Auto-Fix Naming")
        layout.addWidget(self.btn_audit)
        layout.addWidget(self.btn_nanite)
        layout.addWidget(self.btn_unused)
        layout.addWidget(self.btn_fix_names)
        #adds a place to list all of the results in the "layout"
        layout.addWidget(QLabel("Results"))
        self.results = QListWidget()
        #disable selection mode
        self.results.setSelectionMode(QListWidget.NoSelection)
        layout.addWidget(self.results)
        #adds a scrollable textbox where the "log" is outputted to
        layout.addWidget(QLabel("Log"))
        self.log_box = QTextEdit()
        #set to read only
        self.log_box.setReadOnly(True)
        layout.addWidget(self.log_box)
        # Connecting the Buttons to their corresponding functions
        self.btn_audit.clicked.connect(self.controller.on_audit)
        self.btn_nanite.clicked.connect(self.controller.on_enable_nanite)
        self.btn_unused.clicked.connect(self.controller.on_find_unused)
        self.btn_fix_names.clicked.connect(self.controller.on_fix_names)

    #extra utility methods to update the UI during scans
    def log(self, msg):
        self.log_box.append(msg)

    def clear(self):
        self.results.clear()

    def add(self, msg):
        self.results.addItem(QListWidgetItem(msg))

# 5. Controller + Toggle System ----------------------------------------------------------------------------------------------------------------

#creating a class for the core manager of the tool
class AuditLogController:
    # Singleton instance so it can be toggled and doesnt duplicate
    instance = None

    #creating a function that checks to see if a QT function is already running in unreal
    #if not creates a new one
    def __init__(self):
        app = QApplication.instance()
        if not app:
            app = QApplication([])
        #creates the "AuditLogUI" and passes itself so the buttons can trigger controller functions
        self.ui = AuditLogUI(controller=self)
        self.ui.show()

    #creating a class method to check if we need to creat a new AuditLogController(ALC)
    @classmethod
    def toggle(cls):
        """Create or toggle the window visibility."""
        if cls.instance is None:
            #if it doesnt exist create a new ALC
            cls.instance = AuditLogController()
        else:
            #if it does exist simply show or hide the current UI window
            if cls.instance.ui.isVisible():
                cls.instance.ui.hide()
            else:
                cls.instance.ui.show()

    # Audit Actions
    def on_audit(self):
        #clears all previous results and shows that the audit is starting
        self.ui.clear()
        self.ui.log("Running Project Audit...\n")
        #finds missing or broken assets
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

        #checking for naming and nanite issues
        #naming issues
        naming_issues, nanite_issues = audit_naming_and_nanite()
        self.ui.log("────────────────────────────")
        self.ui.log("🔠 Naming Issues")
        self.ui.log("────────────────────────────")
        if naming_issues:
            for path, issue in naming_issues:
                self.ui.add(f"{path}: {issue}")
                self.ui.log(f"⚠️ {path}: {issue}")
        else:
            self.ui.log("✅ None found.\n")

        #nanite issues
        self.ui.log("────────────────────────────")
        self.ui.log("🧱 Nanite Disabled Meshes")
        self.ui.log("────────────────────────────")
        if nanite_issues:
            for path, issue in nanite_issues:
                self.ui.add(f"{path}: {issue}")
                self.ui.log(f"⚠️ {path}: {issue}")
        else:
            self.ui.log("✅ All static meshes have Nanite enabled.\n")

        #find unused assets
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

        #logs the results to both the results area and the log area
        #totals up all issues and prints a summary of them
        total = len(missing) + len(naming_issues) + len(nanite_issues) + len(unused)
        self.ui.log("────────────────────────────")
        #checks if there were any issues and outputs the appropriate statement
        if total == 0:
            self.ui.log("🎉 Project is clean — no major issues detected!")
        else:
            self.ui.log(f"🚨 Audit complete — {total} issue(s) found.")
        self.ui.log("────────────────────────────\n")

    #creating a function for the nanite enabling on each mesh
    def on_enable_nanite(self):
        #shows it has started
        self.ui.log("⚡ Enabling Nanite on all flagged meshes...")
        #calls the fixing function
        count = enable_nanite_for_all_flagged()
        #displays how many meshes it has enabled nanite on
        self.ui.log(f"✅ Nanite enabled on {count} mesh(es).\n")

    #creating a function to call the find usused assets function and display them
    def on_find_unused(self):
        self.ui.clear()
        #shows that it has started
        self.ui.log("🧹 Scanning for unused assets/materials...")
        #calls the function
        unused = find_unused_assets()
        self.ui.log("────────────────────────────")
        self.ui.log("🧹 Unused Assets")
        self.ui.log("────────────────────────────")
        #displaus all unused assets, their path and their issues
        if unused:
            for path, issue in unused:
                self.ui.add(f"{path}: {issue}")
                self.ui.log(f"🗑️ {path}: {issue}")
        else:
            self.ui.log("✅ No unused assets found.\n")

    #creating a function to call the functiion to fix the naming of the assets
    def on_fix_names(self):
        #show that it has started
        self.ui.log("🪄 Auto-fixing asset names...")
        #calls the function
        fixed = auto_fix_naming()
        #displays which assets were renamed and which ones weren
        if fixed:
            for old, new in fixed:
                self.ui.add(f"Renamed {old} → {new}")
                self.ui.log(f"✅ Renamed {old} → {new}")
        else:
            self.ui.log("✨ All asset names already follow conventions!")
        self.ui.log("\n")

# 6. Unreal Toolbar Integration ----------------------------------------------------------------------------------------------------------------

#creating a class to handle to handle the tools menu entry in unreal
class AuditLogMenu:
    #prepareing variables and references so the class can add the tool to unreals editor
    def __init__(self):
        #getting and assigning unreals tool menu system which controls everythnig in the Editors menu, bar and context menus
        self.tool_menus = unreal.ToolMenus.get()
        #Assigning the name for the tools menu
        self.menu_owner = "AuditLogTool"
        #specifying where it will appear (the top bar(LevelEditor.MainMenu))
        self.menu_name = "LevelEditor.MainMenu.AuditLogTool"
        self.menu = None

    #creating a function to add the tool to unreals top menu bar
    def create_menu(self):
        #shows in unreals output log that its running
        unreal.log("🧾 Creating Audit Log Tool Menu...")
        #finding the top bar in unreal
        main_menu = self.tool_menus.find_menu("LevelEditor.MainMenu")
        #add a new submenu called Audit Log Tool
        self.menu = main_menu.add_sub_menu(
            #help unreal organise and track who owns the menu
            section_name="AuditLogTool",
            name=self.menu_owner,
            owner=self.menu_owner,
            #the visible title in the tool bar
            label="Audit Log Tool"
        )
        #calling register menu to register it in unreals menu system
        self.menu = self.tool_menus.register_menu(
            self.menu_name, "", unreal.MultiBoxType.MENU, True
        )
        #refresh the toolbar UI so the new menu appears instantly
        self.tool_menus.refresh_all_widgets()

    #creating a function that creates the menu item and finalises the setup in unreal
    def create_menu_entry(self):
        #shows that the menu entry is being added
        unreal.log("🧾 Adding Audit Log Tool menu entry...")
        module_name = "AuditLogTool"
        #imports the python script and call the function that shows/hides the UI
        command = f"import {module_name}; {module_name}.AuditLogController.toggle()"
        #creating a clickable commans inside new meny (menu entry object)
        menu_entry = unreal.ToolMenuEntryExtensions.init_menu_entry(
            #identifying it
            owner=self.menu_owner,
            name=self.menu_owner,
            #the text that appeats in the menu
            label="Toggle Audit Log Tool",
            #what appears when u hover over it
            tool_tip="Show/Hide Audit Log Tool UI",
            #setting the variable to python so it runs a python command
            command_type=unreal.ToolMenuStringCommandType.PYTHON,
            custom_command_type="",
            #calling the controllers toggle function
            command_string=command
        )
        #choses an icon for the menu item using unreal
        icon = "EditorStyle.EditorPreferences"
        menu_entry.set_icon("EditorStyle", icon)
        #adds the entry into the submenu under the catagory "utils"
        self.menu.add_menu_entry("Utils", menu_entry)
        #refreshers again to update the tool bar
        self.tool_menus.refresh_all_widgets()

# 7. Entry Point for Unreal ----------------------------------------------------------------------------------------------------------------

#creating a function to create and register the toolbar menu for the tool
def register_audit_log_menu():
    #creates an instance of the AuditLogMenu class already created
    menu = AuditLogMenu()
    #adds the tools submenu to unreals toolbar
    menu.create_menu()
    #adds a clickable entry inside the submenu
    menu.create_menu_entry()
    #show that it was registered successfully in the unreal output log
    unreal.log("✅ Audit Log Tool menu registered successfully.")

# making the script selft starting inside of unreal
if __name__ == "__main__":
    register_audit_log_menu()