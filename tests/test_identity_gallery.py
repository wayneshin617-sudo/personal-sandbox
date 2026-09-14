from __future__ import annotations

import numpy as np

from src.identity_gallery import IdentityHit, assign_identities, format_times, match_identity, sample_times


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


def test_format_times_is_short() -> None:
    text = format_times([1.0, 1.05, 8.2, 15.0])
    assert "1.0초" in text
    assert "8.2초" in text
