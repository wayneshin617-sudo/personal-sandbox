from __future__ import annotations

import numpy as np

from src.identity_gallery import (
    IdentityHit,
    assign_identities,
    format_times,
    join_thumbs,
    match_identity,
    sample_times,
    scene_near,
    scenes_from_identities,
)


def _hit(t: float, emb, local: int = 1) -> IdentityHit:
    vec = np.asarray(emb, dtype=np.float32)
    vec = vec / max(float(np.linalg.norm(vec)), 1e-8)
    return IdentityHit(
        time_sec=t,
        box=[0, 0, 10, 10],
        person_box=[0, 0, 20, 40],
        crop_rgb=np.zeros((8, 8, 3), dtype=np.uint8),
        kps=None,
        embedding=vec,
        local_index=local,
    )


def test_sample_times_covers_clip() -> None:
    times = sample_times(20.0, count=5)
    assert times[0] < 2
    assert times[-1] > 15
    assert len(times) == 5


def test_same_face_keeps_one_id_across_scenes() -> None:
    a = [1.0, 0.0, 0.0]
    people = assign_identities(
        [
            _hit(1.0, a, local=2),
            _hit(8.0, a, local=1),
            _hit(15.0, a, local=3),
        ]
    )
    assert len(people) == 1
    assert people[0].id == 1
    assert [round(t) for t in people[0].times] == [1, 8, 15]


def test_two_faces_get_stable_ids() -> None:
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    people = assign_identities(
        [
            _hit(0.5, a, local=1),
            _hit(0.5, b, local=2),
            _hit(9.0, b, local=1),
            _hit(9.0, a, local=2),
        ]
    )
    assert {p.id for p in people} == {1, 2}
    matched = match_identity(np.array(a, dtype=np.float32), people)
    assert matched is not None
    later = match_identity(np.array(a, dtype=np.float32), people)
    assert later is not None and later.id == matched.id


def test_join_thumbs_makes_one_wide_image() -> None:
    left = np.zeros((20, 10, 3), dtype=np.uint8)
    right = np.ones((20, 12, 3), dtype=np.uint8) * 200
    strip = join_thumbs([left, right], gap=4)
    assert strip.shape[0] == 20
    assert strip.shape[1] == 10 + 4 + 12
    assert strip.ndim == 3


def test_format_times_is_short() -> None:
    text = format_times([1.0, 1.05, 8.2, 15.0])
    assert "1.0초" in text
    assert "8.2초" in text


def test_scene_cards_keep_stable_ids_when_local_order_flips() -> None:
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    people = assign_identities(
        [
            _hit(0.5, a, local=1),
            _hit(0.5, b, local=2),
            _hit(9.0, b, local=1),
            _hit(9.0, a, local=2),
        ]
    )
    scenes = scenes_from_identities(people)
    assert [round(s.time_sec, 1) for s in scenes] == [0.5, 9.0]
    first_ids = [pid for pid, _hit in scenes[0].people]
    later_ids = [pid for pid, _hit in scenes[1].people]
    assert first_ids == later_ids == [1, 2]
    later = scene_near(scenes, 9.0)
    assert later is not None
    assert {pid for pid, _hit in later.people} == {1, 2}


def test_ids_follow_first_appearance_not_local_number() -> None:
    late_star = [0.0, 1.0, 0.0]
    early_extra = [1.0, 0.0, 0.0]
    people = assign_identities(
        [
            _hit(1.0, early_extra, local=1),
            _hit(8.0, late_star, local=1),
        ]
    )
    assert people[0].id == 1
    assert people[1].id == 2
    assert match_identity(np.array(late_star, dtype=np.float32), people).id == 2
