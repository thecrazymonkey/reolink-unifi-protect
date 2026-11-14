from unifi.hevc_flv import smooth_ts

# Main-stream frame times (ms) measured on the Reolink doorbell: a long gap
# after the keyframe, then a burst.
MEASURED = [356, 1108, 1152, 1174, 1224, 1246, 1276, 1314, 1387, 1455, 1477,
            1542, 1556, 1574, 1632, 1638, 1692, 1705, 1735, 1793, 1844, 1907,
            1987, 2036, 2105, 2195, 2410, 2450, 2487, 2508, 2560, 2589, 2611,
            2637, 2686, 2707, 2729, 2770, 2789, 3024]


def test_steps_stay_within_2x_and_track_the_camera_clock():
    state, out, offset = {}, [], 0
    for _ in range(40):  # 40 GOPs
        out += [smooth_ts(t + offset, state) for t in MEASURED]
        last_in = MEASURED[-1] + offset
        offset += MEASURED[-1] - MEASURED[0] + 50
    steps = [b - a for a, b in zip(out[200:], out[201:])]
    assert min(steps) > 0
    assert all(b <= 2 * a for a, b in zip(steps, steps[1:]))
    assert abs(out[-1] - last_in) < 1000
