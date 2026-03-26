# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Exca Dance — Linux onedir distribution.

Build:
    .venv/bin/pyinstaller exca_dance.spec

Output:
    dist/exca_dance/exca_dance   (executable)
    dist/exca_dance/_internal/   (runtime + assets)

Notes:
    - Onedir mode chosen over onefile for better OpenGL/ModernGL compatibility.
    - Windows support can be added later by adjusting icon= and console= flags.
    - Assets (beatmaps, music, sounds) are bundled inside _internal/assets/.
    - A runtime hook sets CWD to sys._MEIPASS so relative 'assets/...' paths resolve.
"""

import os

block_cipher = None
_root = os.path.abspath(".")

a = Analysis(
    ["src/exca_dance/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("assets/beatmaps", "assets/beatmaps"),
        ("assets/music", "assets/music"),
        ("assets/sounds", "assets/sounds"),
        ("assets/fonts", "assets/fonts"),
    ],
    hiddenimports=[
        # --- ModernGL (C-extension, dynamic loader) ---
        "moderngl",
        "moderngl.mgl",
        # --- PyOpenGL ---
        "OpenGL",
        "OpenGL.GL",
        "OpenGL.platform.glx",
        "OpenGL.platform.egl",
        # --- pygame-ce / SDL2 ---
        "pygame",
        "pygame._sdl2",
        "pygame._sdl2.video",
        "pygame._sdl2.controller",
        # --- numpy (used by rendering + FK) ---
        "numpy",
        # --- dynamic import in __main__.py (import_module) ---
        "exca_dance.ui.screens.tutorial_screen",
        # --- subpackages that might be missed by static analysis ---
        "exca_dance.ros2_bridge",
        "exca_dance.editor.editor_screen",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["runtime_hooks/frozen_path.py"],
    excludes=[
        # Not needed at runtime
        "tkinter",
        "unittest",
        "email",
        "xml",
        "pydoc",
        "doctest",
        # ROS2 — only used via subprocess, never imported in main process
        "rclpy",
        "sensor_msgs",
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="exca_dance",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="exca_dance",
)
