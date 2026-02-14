# Anki Add-on Development Guide for Agents

This repository contains an Anki Add-on. Use this guide to understand the structure and development patterns.

## Documentation
Official Documentation: [Anki Add-on Docs](https://addon-docs.ankiweb.net/)

## Directory Structure
- Anki 2.1+ add-ons reside in `addons21/` (on the user's machine). In this repository, the root usually maps to the add-on folder itself (containing `__init__.py`), or a subfolder if it's a multi-addon repo.
- The add-on **must** have an `__init__.py` file to be loaded.
- **Persistence**: Do not store user data in the add-on folder; it is deleted on upgrade. Use Anki's configuration manager (`config.json` + `mw.addonManager`) or standard user data directories.

## Core Modules
- `anki`: The backend library (database, scheduling, collection).
    - `mw.col`: The current Collection object (access via `aqt.mw`).
- `aqt`: The frontend (Qt) library.
    - `mw`: The main window instance (`aqt.mw`).
    - `aqt.qt`: Qt constants and classes (PyQt6/PyQt5 wrapper).
    - `aqt.utils`: Helpers like `showInfo`, `tooltip`, `askUser`.

## Common Patterns

### Entry Point
`__init__.py` is loaded on Anki startup.
```python
from aqt import mw
from aqt.utils import showInfo, qconnect
from aqt.qt import *

def my_action():
    showInfo("Hello from Agent Add-on!")

action = QAction("My Add-on", mw)
qconnect(action.triggered, my_action)
mw.form.menuTools.addAction(action)
```

### Hooks
Use `aqt.gui_hooks` for UI events and `anki.hooks` for backend events.
**New Style Hooks** (Preferred):
```python
from aqt import gui_hooks

def on_question_shown(card):
    print(f"Card shown: {card.id}")

gui_hooks.reviewer_did_show_question.append(on_question_shown)
```
Inspect `pylib/tools/genhooks.py` and `qt/tools/genhooks_gui.py` in Anki source or use code completion to find hooks.

### Background Operations
**NEVER** run long operations on the main thread (UI thread). Use `aqt.operations`.
```python
from aqt.operations import QueryOp

def my_heavy_task(col):
    # This runs in background
    # Do NOT access UI widgets here
    return col.card_count()

def on_success(count):
    # This runs on main thread
    # Safe to update UI
    print(f"Count: {count}")

op = QueryOp(parent=mw, op=lambda col: my_heavy_task(col), success=on_success)
op.with_progress("Calculating...").run_in_background()
```

### Webview & Reviewer JS
To inject JS into the reviewer:
```python
from aqt import gui_hooks

def on_card_will_show(html, card, context):
    # context is 'reviewQuestion', 'reviewAnswer', etc.
    return html + "<script>console.log('Injected');</script>"

gui_hooks.card_will_show.append(on_card_will_show)
```

## Testing & Debugging
- **Console**: `print()` output goes to the standard out. Start Anki from a terminal to see it.
- **Debug Console**: Inside Anki, press `Ctrl+Shift+;` (or `Cmd+Shift+;` on Mac) to open the interactive debug console.
- **Reloading**: Anki usually needs a restart to reload add-on code, unless using specific hot-reloading tools (rare).
