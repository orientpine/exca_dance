from __future__ import annotations

import pytest

from exca_dance.core.leaderboard import LeaderboardManager


def test_add_entry_and_get_top_scores_returns_new_entry_sorted(tmp_path) -> None:
    manager = LeaderboardManager(str(tmp_path / "leaderboard.json"))

    entry = manager.add_entry("abc", 1234, "Song A")

    top_scores = manager.get_top_scores()

    assert top_scores == [entry]
    assert top_scores[0].initials == "ABC"
    assert top_scores[0].score == 1234


@pytest.mark.parametrize("initials", ["", "ab", "abcd", "  ab  "])
def test_add_entry_rejects_initials_with_length_not_three(tmp_path, initials: str) -> None:
    manager = LeaderboardManager(str(tmp_path / "leaderboard.json"))

    with pytest.raises(ValueError):
        manager.add_entry(initials, 100, "Song A")


def test_persistence_roundtrip_loads_same_data(tmp_path) -> None:
    path = tmp_path / "nested" / "leaderboard.json"
    manager = LeaderboardManager(str(path))
    first = manager.add_entry("abc", 1200, "Song A")
    second = manager.add_entry("def", 900, "Song B")

    reloaded = LeaderboardManager(str(path))
    top_scores = reloaded.get_top_scores(limit=10)

    assert [entry.initials for entry in top_scores] == ["ABC", "DEF"]
    assert [entry.score for entry in top_scores] == [1200, 900]
    assert top_scores[0].timestamp == first.timestamp
    assert top_scores[1].timestamp == second.timestamp


def test_empty_leaderboard_returns_empty_list(tmp_path) -> None:
    manager = LeaderboardManager(str(tmp_path / "leaderboard.json"))

    assert manager.get_top_scores() == []


def test_corrupted_json_file_resets_to_empty(tmp_path) -> None:
    path = tmp_path / "leaderboard.json"
    path.write_text("{not valid json", encoding="utf-8")

    manager = LeaderboardManager(str(path))

    assert manager.get_top_scores() == []


def test_song_filter_returns_only_matching_entries(tmp_path) -> None:
    manager = LeaderboardManager(str(tmp_path / "leaderboard.json"))
    manager.add_entry("abc", 1000, "Song A")
    manager.add_entry("def", 1100, "Song B")
    manager.add_entry("ghi", 900, "Song A")

    filtered = manager.get_top_scores(song="Song A")

    assert [entry.song_title for entry in filtered] == ["Song A", "Song A"]
    assert [entry.initials for entry in filtered] == ["ABC", "GHI"]


def test_get_top_scores_sorts_multiple_entries_by_score_descending(tmp_path) -> None:
    manager = LeaderboardManager(str(tmp_path / "leaderboard.json"))
    manager.add_entry("abc", 1000, "Song A")
    manager.add_entry("def", 1500, "Song A")
    manager.add_entry("ghi", 1200, "Song A")

    top_scores = manager.get_top_scores()

    assert [entry.score for entry in top_scores] == [1500, 1200, 1000]
