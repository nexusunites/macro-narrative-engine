from mne.storage import get_last_two_result_files, get_recent_daily_runs, load_json


def trend_direction(delta, epsilon=0):
    if delta > epsilon:
        return "UP"
    if delta < -epsilon:
        return "DOWN"
    return "FLAT"


def classify_trend(values, epsilon=0):
    if len(values) < 3:
        return "stable"

    prev = values[-2]
    prev2 = values[-3]
    current = values[-1]

    d1 = current - prev
    d2 = prev - prev2

    current_up = d1 > epsilon
    current_down = d1 < -epsilon
    prev_up = d2 > epsilon
    prev_down = d2 < -epsilon

    if current_up and prev_up:
        return "building"
    if current_down and prev_down:
        return "fading"
    if current_down and (prev_up or abs(d2) <= epsilon):
        return "cooling"
    if current_up and (prev_down or abs(d2) <= epsilon):
        return "re-accelerating"
    if abs(d1) <= epsilon:
        return "flat"

    return "stable"


def print_momentum(results_dir):
    latest, previous = get_last_two_result_files(results_dir)

    print()
    print("=== Momentum (vs previous run) ===")

    if previous is None:
        print("Not enough history yet (need 2 runs).")
        return

    current = load_json(latest)
    prior = load_json(previous)

    cur_counts = current.get("theme_counts", {})
    prev_counts = prior.get("theme_counts", {})
    all_themes = sorted(set(cur_counts.keys()) | set(prev_counts.keys()))

    printed_any = False
    for theme in all_themes:
        cur = int(cur_counts.get(theme, 0))
        prev = int(prev_counts.get(theme, 0))
        delta = cur - prev
        if delta != 0:
            printed_any = True
            sign = "+" if delta > 0 else ""
            print(f"{theme}: {cur} ({sign}{delta})")

    cur_share = float(current.get("dominant_share", 0))
    prev_share = float(prior.get("dominant_share", 0))
    cur_gap = int(current.get("concentration_gap", 0))
    prev_gap = int(prior.get("concentration_gap", 0))
    cur_cov = float(current.get("coverage_pct", 0))
    prev_cov = float(prior.get("coverage_pct", 0))

    print(f"Dominant theme: {current.get('dominant_theme')} (was {prior.get('dominant_theme')})")
    print(f"Coverage: {cur_cov:.1f}% ({cur_cov - prev_cov:+.1f}pp)")
    print(f"Dominant share: {cur_share * 100:.1f}% ({(cur_share - prev_share) * 100:+.1f}pp)")
    print(f"Concentration gap: {cur_gap} ({cur_gap - prev_gap:+d})")

    if not printed_any:
        print("(No per-theme count changes)")


def print_daily_count_trends(results_dir, lookback, epsilon):
    print()
    print("=== Narrative Trends (Daily) ===")

    recent_runs = get_recent_daily_runs(results_dir, lookback)

    if len(recent_runs) < 2:
        print("Not enough daily history for trend analysis.")
        return

    theme_history = {}

    for run in recent_runs:
        counts = run.get("theme_counts", {})

        for theme, count in counts.items():
            theme_history.setdefault(theme, []).append(count)

    for theme, values in sorted(theme_history.items()):
        if len(values) < 2:
            continue

        delta = values[-1] - values[-2]
        direction = trend_direction(delta, epsilon)
        label = classify_trend(values, epsilon)
        series = " -> ".join(str(value) for value in values)

        print(f"{theme}: {series} {direction}  {label}")


def print_daily_share_trends(results_dir, lookback, epsilon, top_n=3):
    print()
    print("=== Narrative Trends (Daily - Share) ===")

    recent_runs = get_recent_daily_runs(results_dir, lookback)

    if len(recent_runs) < 2:
        print("Not enough daily history for share trend analysis.")
        return

    theme_share_history = {}

    for run in recent_runs:
        counts = run.get("theme_counts", {})
        total = sum(count for count in counts.values() if count > 0)

        if total == 0:
            continue

        for theme, count in counts.items():
            share = count / total if total > 0 else 0.0
            theme_share_history.setdefault(theme, []).append(share)

    sorted_themes = sorted(
        theme_share_history.items(),
        key=lambda item: item[1][-1],
        reverse=True,
    )

    print()
    print("Top Narratives:")

    for theme, values in sorted_themes[:top_n]:
        if len(values) < 2:
            continue

        delta = values[-1] - values[-2]
        direction = trend_direction(delta, epsilon)
        label = classify_trend(values, epsilon)
        series = " -> ".join(f"{value * 100:.1f}%" for value in values)

        print(f"{theme}: {series} {direction}  {label}")

    if len(sorted_themes) > top_n:
        print()
        print("Other Narratives:")

        for theme, values in sorted_themes[top_n:]:
            if len(values) < 2:
                continue

            delta = values[-1] - values[-2]
            direction = trend_direction(delta, epsilon)
            series = " -> ".join(f"{value * 100:.1f}%" for value in values)

            print(f"{theme}: {series} {direction}")

    print()
    print("=============================")
