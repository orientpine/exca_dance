"""Capture a screenshot of the excavator 3D rendering for visual inspection."""

import os
import sys

# Force a display
os.environ.setdefault("SDL_VIDEODRIVER", "x11")

import pygame
import moderngl
import numpy as np
from PIL import Image
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName
from exca_dance.rendering.renderer import GameRenderer
from exca_dance.rendering.excavator_model import ExcavatorModel
from exca_dance.rendering.viewport_layout import GameViewportLayout


def capture(filename: str, joint_angles: dict[JointName, float], width=800, height=600):
    """Render one frame and save as PNG."""
    renderer = GameRenderer(width, height, "Capture")
    fk = ExcavatorFK()
    model = ExcavatorModel(renderer, fk)
    layout = GameViewportLayout(renderer, width, height)

    # Update model with test angles
    model.update(joint_angles)

    # Render
    renderer.begin_frame()
    layout.render_all(model, joint_angles)

    # Read framebuffer
    ctx = renderer.ctx
    data = ctx.screen.read(components=3)
    img = Image.frombytes("RGB", (width, height), data)
    img = img.transpose(Image.FLIP_TOP_BOTTOM)  # OpenGL is bottom-up

    out = Path("data") / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    print(f"Saved: {out}")

    model.destroy()
    renderer.destroy()


if __name__ == "__main__":
    # Test 1: Default angles (all zeros) — baseline
    capture("screenshot_default.png", {j: 0.0 for j in JointName})

    # Re-init pygame for next capture
    pygame.quit()
    pygame.init()

    # Test 2: Boom raised 30°, arm bent, bucket rotated — stress test
    capture(
        "screenshot_angled.png",
        {
            JointName.SWING: 30.0,
            JointName.BOOM: 30.0,
            JointName.ARM: 45.0,
            JointName.BUCKET: 90.0,
        },
    )

    pygame.quit()
    print("Done. Check data/screenshot_default.png and data/screenshot_angled.png")
