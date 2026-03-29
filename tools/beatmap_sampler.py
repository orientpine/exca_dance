#!/usr/bin/env python3
"""굴착 작업 데이터 시각화 & 비트맵 샘플러.

실제 굴착기 전문 기사의 작업 로그(CSV)를 시각화하고,
마우스 클릭으로 특정 시점을 선택하면 exca_dance 비트맵 JSON으로 내보낸다.

사용법:
    .venv/bin/python tools/beatmap_sampler.py [CSV_DIR]

조작:
    좌클릭         – 시점 선택 (빨간 수직선 + 관절각 표시)
    우클릭         – 가장 가까운 선택 제거
    스크롤 위/아래  – 시간축 확대/축소
    마우스 가운데 드래그 – 시간축 이동(팬)
    Export 버튼    – 선택된 시점들을 비트맵 JSON으로 저장
    Clear 버튼     – 모든 선택 초기화
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
from matplotlib.widgets import Button

# ---------------------------------------------------------------------------
# 데이터 컬럼 매핑
# ---------------------------------------------------------------------------
COL_TS = "timestamp"
COL_SWING = "excavator/state/complete_status/inclinometer_data/swing_angle"
COL_BOOM = "excavator/state/complete_status/inclinometer_data/boom_latitude"
COL_ARM = "excavator/state/complete_status/inclinometer_data/arm_latitude"
COL_BUCKET = "excavator/state/complete_status/inclinometer_data/bucket_latitude"

# 게임 관절각 변환 (constants.py 주석 기준)
#   game_boom   = boom_latitude                     (절대값)
#   game_arm    = arm_latitude - boom_latitude       (boom 대비 상대값)
#   game_bucket = bucket_latitude - arm_latitude     (arm 대비 상대값)
#   swing       = swing_angle 그대로


def load_csv_dir(
    csv_dir: str,
) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    """CSV 디렉토리에서 전체 시계열을 로드하고 게임 관절각으로 변환."""
    csv_path = Path(csv_dir)
    files = sorted(csv_path.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없음: {csv_dir}")

    times: list[float] = []
    swings: list[float] = []
    booms: list[float] = []
    arms: list[float] = []
    buckets: list[float] = []

    first_ts: int | None = None
    for path in files:
        with path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    ts = int(row[COL_TS])
                    swing_raw = float(row[COL_SWING])
                    boom_abs = float(row[COL_BOOM])
                    arm_abs = float(row[COL_ARM])
                    bucket_abs = float(row[COL_BUCKET])
                except (ValueError, TypeError, KeyError):
                    continue

                if first_ts is None:
                    first_ts = ts

                t_sec = (ts - first_ts) / 1_000_000_000.0
                game_boom = round(boom_abs, 1)
                game_arm = round(arm_abs - boom_abs, 1)
                game_bucket = round(bucket_abs - arm_abs, 1)
                game_swing = round(swing_raw, 1)

                times.append(t_sec)
                swings.append(game_swing)
                booms.append(game_boom)
                arms.append(game_arm)
                buckets.append(game_bucket)

    return times, swings, booms, arms, buckets


class BeatmapSampler:
    """인터랙티브 시각화 + 시점 선택 도구."""

    def __init__(
        self,
        times: list[float],
        swings: list[float],
        booms: list[float],
        arms: list[float],
        buckets: list[float],
    ) -> None:
        self.times = times
        self.swings = swings
        self.booms = booms
        self.arms = arms
        self.buckets = buckets

        # 선택된 인덱스 (시간순 정렬 유지)
        self.selected_indices: list[int] = []

        # 그래프 요소 참조
        self.vlines: list[list[matplotlib.lines.Line2D]] = []  # per-selection, per-axis
        self.annotations: list[list[matplotlib.text.Annotation]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        self.fig, self.axes = plt.subplots(4, 1, figsize=(16, 9), sharex=True)
        self.fig.canvas.manager.set_window_title("굴착 작업 데이터 — 비트맵 샘플러")
        self.fig.subplots_adjust(bottom=0.12, hspace=0.35, top=0.95)

        data_sets = [
            (self.swings, "Swing (°)", "#FF6B6B"),
            (self.booms, "Boom (°)", "#4ECDC4"),
            (self.arms, "Arm (°)", "#45B7D1"),
            (self.buckets, "Bucket (°)", "#96CEB4"),
        ]

        for ax, (data, label, color) in zip(self.axes, data_sets):
            ax.plot(self.times, data, color=color, linewidth=0.6, alpha=0.85)
            ax.set_ylabel(label, fontsize=9, fontweight="bold")
            ax.grid(True, alpha=0.3)
            ax.tick_params(labelsize=8)

        self.axes[-1].set_xlabel("시간 (초)", fontsize=10)
        self.fig.suptitle(
            "좌클릭: 시점 선택  |  우클릭: 선택 제거  |  스크롤: 확대/축소  |  가운데 드래그: 이동",
            fontsize=9,
            color="gray",
        )

        # 선택 카운터 텍스트
        self.count_text = self.fig.text(
            0.5, 0.01, "선택: 0개", ha="center", fontsize=10, color="#333"
        )

        # 버튼
        ax_export = self.fig.add_axes([0.78, 0.015, 0.1, 0.04])
        ax_clear = self.fig.add_axes([0.89, 0.015, 0.08, 0.04])
        self.btn_export = Button(ax_export, "Export JSON", color="#4ECDC4", hovercolor="#45B7D1")
        self.btn_clear = Button(ax_clear, "Clear", color="#FF6B6B", hovercolor="#FF8E8E")
        self.btn_export.on_clicked(self._on_export)
        self.btn_clear.on_clicked(self._on_clear)

        # 이벤트 연결
        self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        self.fig.canvas.mpl_connect("scroll_event", self._on_scroll)

        # 팬 상태
        self._pan_start: float | None = None
        self._pan_xlim: tuple[float, float] | None = None
        self.fig.canvas.mpl_connect("button_press_event", self._on_pan_press)
        self.fig.canvas.mpl_connect("button_release_event", self._on_pan_release)
        self.fig.canvas.mpl_connect("motion_notify_event", self._on_pan_motion)

    # -----------------------------------------------------------------------
    # 시점 선택
    # -----------------------------------------------------------------------
    def _find_nearest_index(self, t: float) -> int:
        """시간 t에 가장 가까운 데이터 인덱스."""
        best = 0
        best_dist = abs(self.times[0] - t)
        for i in range(1, len(self.times)):
            d = abs(self.times[i] - t)
            if d < best_dist:
                best = i
                best_dist = d
        return best

    def _add_selection(self, idx: int) -> None:
        if idx in self.selected_indices:
            return
        self.selected_indices.append(idx)
        self.selected_indices.sort(key=lambda i: self.times[i])

        t = self.times[idx]
        vals = [self.swings[idx], self.booms[idx], self.arms[idx], self.buckets[idx]]
        labels = ["S", "B", "A", "K"]

        lines = []
        anns = []
        for i, ax in enumerate(self.axes):
            vl = ax.axvline(t, color="red", linewidth=1.0, alpha=0.7, linestyle="--")
            ann = ax.annotate(
                f"{labels[i]}={vals[i]:.1f}",
                xy=(t, vals[i]),
                xytext=(5, 10),
                textcoords="offset points",
                fontsize=7,
                color="red",
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="red", alpha=0.8),
            )
            lines.append(vl)
            anns.append(ann)

        self.vlines.append(lines)
        self.annotations.append(anns)
        self._update_count()
        self.fig.canvas.draw_idle()

    def _remove_nearest_selection(self, t: float) -> None:
        if not self.selected_indices:
            return
        best_pos = 0
        best_dist = abs(self.times[self.selected_indices[0]] - t)
        for pos, idx in enumerate(self.selected_indices):
            d = abs(self.times[idx] - t)
            if d < best_dist:
                best_pos = pos
                best_dist = d

        self.selected_indices.pop(best_pos)
        for artist in self.vlines[best_pos]:
            artist.remove()
        for artist in self.annotations[best_pos]:
            artist.remove()
        self.vlines.pop(best_pos)
        self.annotations.pop(best_pos)
        self._update_count()
        self.fig.canvas.draw_idle()

    def _update_count(self) -> None:
        self.count_text.set_text(f"선택: {len(self.selected_indices)}개")

    # -----------------------------------------------------------------------
    # 이벤트 핸들러
    # -----------------------------------------------------------------------
    def _on_click(self, event: matplotlib.backend_bases.MouseEvent) -> None:
        if event.inaxes is None or event.inaxes not in self.axes:
            return
        if event.button == 1:  # 좌클릭
            idx = self._find_nearest_index(event.xdata)
            self._add_selection(idx)
        elif event.button == 3:  # 우클릭
            self._remove_nearest_selection(event.xdata)

    def _on_scroll(self, event: matplotlib.backend_bases.MouseEvent) -> None:
        if event.inaxes is None:
            return
        ax = self.axes[0]
        xlim = ax.get_xlim()
        xdata = event.xdata if event.xdata is not None else (xlim[0] + xlim[1]) / 2
        scale = 0.8 if event.button == "up" else 1.25
        new_width = (xlim[1] - xlim[0]) * scale
        new_left = xdata - (xdata - xlim[0]) * scale
        new_right = new_left + new_width
        # 범위 제한
        t_min, t_max = self.times[0], self.times[-1]
        new_left = max(t_min - 1, new_left)
        new_right = min(t_max + 1, new_right)
        for ax in self.axes:
            ax.set_xlim(new_left, new_right)
        self.fig.canvas.draw_idle()

    def _on_pan_press(self, event: matplotlib.backend_bases.MouseEvent) -> None:
        if event.button == 2 and event.inaxes in self.axes:  # 가운데 버튼
            self._pan_start = event.xdata
            self._pan_xlim = self.axes[0].get_xlim()

    def _on_pan_release(self, event: matplotlib.backend_bases.MouseEvent) -> None:
        if event.button == 2:
            self._pan_start = None
            self._pan_xlim = None

    def _on_pan_motion(self, event: matplotlib.backend_bases.MouseEvent) -> None:
        if self._pan_start is None or event.xdata is None:
            return
        dx = self._pan_start - event.xdata
        new_left = self._pan_xlim[0] + dx
        new_right = self._pan_xlim[1] + dx
        for ax in self.axes:
            ax.set_xlim(new_left, new_right)
        self.fig.canvas.draw_idle()

    # -----------------------------------------------------------------------
    # 내보내기
    # -----------------------------------------------------------------------
    def _on_export(self, event: matplotlib.backend_bases.Event) -> None:
        if not self.selected_indices:
            print("[경고] 선택된 시점이 없습니다.")
            return

        events = []
        sorted_indices = sorted(self.selected_indices, key=lambda i: self.times[i])
        base_time_ms = int(self.times[sorted_indices[0]] * 1000)

        for idx in sorted_indices:
            t_ms = int(self.times[idx] * 1000) - base_time_ms + 3000  # 3초 오프셋
            target = {}
            if abs(self.swings[idx]) > 0.5:
                target["swing"] = self.swings[idx]
            target["boom"] = self.booms[idx]
            target["arm"] = self.arms[idx]
            target["bucket"] = self.buckets[idx]

            events.append(
                {
                    "time_ms": t_ms,
                    "target_angles": target,
                    "duration_ms": 1200,
                }
            )

        beatmap = {
            "title": "굴착 작업 데이터 수집",
            "artist": "Expert Operator",
            "bpm": 56.0,
            "offset_ms": 0,
            "audio_file": "assets/music/sample2.wav",
            "difficulty": "NORMAL",
            "events": events,
        }

        out_path = Path("assets/beatmaps/sample2.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(beatmap, f, indent=2, ensure_ascii=False)

        print(f"[완료] {len(events)}개 이벤트를 {out_path}에 저장했습니다.")
        print(f"       시간 범위: {events[0]['time_ms']}ms ~ {events[-1]['time_ms']}ms")

    def _on_clear(self, event: matplotlib.backend_bases.Event) -> None:
        for lines in self.vlines:
            for artist in lines:
                artist.remove()
        for anns in self.annotations:
            for artist in anns:
                artist.remove()
        self.selected_indices.clear()
        self.vlines.clear()
        self.annotations.clear()
        self._update_count()
        self.fig.canvas.draw_idle()

    def show(self) -> None:
        plt.show()


def main() -> None:
    default_dir = str(
        Path(__file__).resolve().parent / "csv"
    )
    csv_dir = sys.argv[1] if len(sys.argv) > 1 else default_dir

    print(f"[로딩] {csv_dir} ...")
    times, swings, booms, arms, buckets = load_csv_dir(csv_dir)
    print(f"[완료] {len(times)}개 데이터포인트 로드 (총 {times[-1]:.1f}초)")

    sampler = BeatmapSampler(times, swings, booms, arms, buckets)
    sampler.show()


if __name__ == "__main__":
    main()
