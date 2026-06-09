# Multivers Launcher Architecture

## Purpose
This project is a modular application suite accessed via a central launcher (`Launcher_Universel`). It is designed to be extremely fast to load by lazily loading heavyweight dependencies (like `yt-dlp` or `ollama`) only when a specific application is launched from the main menu.

## Architecture
- `main.py`: The lightweight entry point. Initializes `customtkinter` and displays the launcher UI.
- `launcher/`: Contains the UI for the main menu (Wheel and Carousel views) and the `app_discovery.py` module.
- `apps/`: The directory containing all modular applications.
- `build.py`: Intelligent PyInstaller script. It handles versioning and performs fast synchronization of app files to the `dist` folder to avoid full rebuilds when only app code changes.
- `versions.json`: Tracks the versions and file hashes of the launcher and apps.

## Workflow
- **Development**: Edit files in `apps/`.
- **Build**: Run `python build.py`. It will automatically detect changes, increment versions in `versions.json`, and either sync files (fast) or rebuild (if core changes).

## How to add a new app
1. Create a new folder in the `apps/` directory (e.g., `apps/my_new_app/`).
2. Inside this folder, create a `manifest.json` file with the following structure:
   ```json
   {
       "id": "my_new_app",
       "name": "My New App",
       "description": "Short description of the app.",
       "icon_text": "🌟",
       "entry_point": "app",
       "class_name": "MyAppWrapper"
   }
   ```
3. Create the Python entry point file (e.g., `app.py`) containing the class specified in `class_name`. This class MUST inherit from `customtkinter.CTkFrame` and accept `(parent, controller)` in its `__init__`.
4. The app class should implement a way to return to the launcher using `self.controller.show_menu()`.
5. Update `build.py` to add `--hidden-import=apps.my_new_app.app` so PyInstaller packages it correctly.