"""Capture a gameplay-like sequence to verify the full rendering pipeline."""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "x11")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import pygame
import numpy as np
from PIL import Image
from pathlib import Path

from exca_dance.core.kinematics import ExcavatorFK
from exca_dance.core.models import JointName
from exca_dance.rendering.renderer import GameRenderer
from exca_dance.rendering.excavator_model import ExcavatorModel
from exca_dance.rendering.viewport_layout import GameViewportLayout


def capture_frame(renderer, layout, model, angles, filename):
    model.update(angles)
    renderer.begin_frame()
    layout.render_all(model, angles)
    ctx = renderer.ctx
    data = ctx.screen.read(components=3)
    img = Image.frombytes("RGB", (renderer.width, renderer.height), data)
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    out = Path("data") / filename
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out))
    print(f"  Saved: {out}")
    renderer.end_frame()


def main():
    W, H = 800, 600
    pygame.init()
    renderer = GameRenderer(W, H, "QA Capture")
    fk = ExcavatorFK()
    model = ExcavatorModel(renderer, fk)
    layout = GameViewportLayout(renderer, W, H)

    # Pose 1: Default (all zeros)
    print("Pose 1: Default (all zero angles)")
    capture_frame(renderer, layout, model, {j: 0.0 for j in JointName}, "qa_pose1_default.png")

    # Pose 2: Boom up 30°
    print("Pose 2: Boom raised 30°")
    capture_frame(
        renderer,
        layout,
        model,
        {JointName.SWING: 0, JointName.BOOM: 30, JointName.ARM: 0, JointName.BUCKET: 0},
        "qa_pose2_boom30.png",
    )

    # Pose 3: Full articulation
    print("Pose 3: Full articulation (swing=30, boom=30, arm=45, bucket=90)")
    capture_frame(
        renderer,
        layout,
        model,
        {JointName.SWING: 30, JointName.BOOM: 30, JointName.ARM: 45, JointName.BUCKET: 90},
        "qa_pose3_full.png",
    )

    # Pose 4: Negative angles (digging pose)
    print("Pose 4: Digging pose (boom=-10, arm=-30, bucket=120)")
    capture_frame(
        renderer,
        layout,
        model,
        {JointName.SWING: -15, JointName.BOOM: -10, JointName.ARM: -30, JointName.BUCKET: 120},
        "qa_pose4_digging.png",
    )

    # Pose 5: Swing rotated 90°
    print("Pose 5: Swing 90° with boom=20, arm=30")
    capture_frame(
        renderer,
        layout,
        model,
        {JointName.SWING: 90, JointName.BOOM: 20, JointName.ARM: 30, JointName.BUCKET: 45},
        "qa_pose5_swing90.png",
    )

    model.destroy()
    renderer.destroy()
    pygame.quit()
    print("\nAll QA poses captured in data/")


if __name__ == "__main__":
    main()
