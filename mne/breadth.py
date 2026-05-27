from mne.market_context import classify_market_move


BREADTH_TICKERS = {
    "SPY": "SPY",
    "RSP": "RSP",
    "QQQE": "QQQE",
    "IWM": "IWM",
}

UP_MOVES = {"UP", "STRONG UP"}
DOWN_MOVES = {"DOWN", "STRONG DOWN"}
FLAT_OR_DOWN_MOVES = {"FLAT", "DOWN", "STRONG DOWN"}
FLAT_OR_UP_MOVES = {"FLAT", "UP", "STRONG UP"}


def get_market_data(market_snapshot, symbol):
    if not market_snapshot:
        return None
    return market_snapshot.get(symbol)


def get_pct_change(market_snapshot, symbol):
    data = get_market_data(market_snapshot, symbol)
    if not data:
        return None
    return data.get("pct_change")


def get_move(market_snapshot, symbol):
    return classify_market_move(get_pct_change(market_snapshot, symbol))


def qqqe_is_weaker_than_qqq(market_snapshot, threshold=0.50):
    qqq = get_pct_change(market_snapshot, "QQQ")
    qqqe = get_pct_change(market_snapshot, "QQQE")

    if qqq is None or qqqe is None:
        return False

    return qqqe <= qqq - threshold


def confidence_from_alignment(aligned, mixed=0, unavailable=0):
    score = aligned - mixed - unavailable

    if score >= 4:
        return "High"
    if score >= 2:
        return "Moderate"
    return "Low"


def classify_breadth_confirmation(market_snapshot):
    moves = {
        "QQQ": get_move(market_snapshot, "QQQ"),
        "NVDA": get_move(market_snapshot, "NVDA"),
        "SPY": get_move(market_snapshot, "SPY"),
        "RSP": get_move(market_snapshot, "RSP"),
        "QQQE": get_move(market_snapshot, "QQQE"),
        "IWM": get_move(market_snapshot, "IWM"),
        "VIX": get_move(market_snapshot, "VIX"),
    }
    qqqe_available = moves["QQQE"] != "UNKNOWN"
    unavailable = sum(1 for move in moves.values() if move == "UNKNOWN")

    broad_risk_off_checks = [
        moves["QQQ"] in DOWN_MOVES,
        moves["SPY"] in DOWN_MOVES,
        moves["RSP"] in DOWN_MOVES,
        moves["IWM"] in DOWN_MOVES,
        moves["VIX"] in UP_MOVES,
    ]
    if qqqe_available:
        broad_risk_off_checks.append(moves["QQQE"] in DOWN_MOVES)

    if all(broad_risk_off_checks):
        return {
            "state": "Broad Risk-Off",
            "confidence": confidence_from_alignment(len(broad_risk_off_checks), unavailable=unavailable),
            "reason": (
                "Selling pressure is broad-based across cap-weighted, equal-weight, "
                "and small-cap participation while volatility is rising."
            ),
        }

    narrow_signals = [
        moves["RSP"] in FLAT_OR_DOWN_MOVES,
        moves["IWM"] in DOWN_MOVES,
        qqqe_available and (moves["QQQE"] in FLAT_OR_DOWN_MOVES or qqqe_is_weaker_than_qqq(market_snapshot)),
    ]
    narrow_count = sum(1 for signal in narrow_signals if signal)
    if moves["QQQ"] in UP_MOVES and moves["NVDA"] in UP_MOVES and narrow_count >= 1:
        confidence = "High" if narrow_count >= 2 and moves["QQQ"] == "STRONG UP" else "Moderate"
        if unavailable:
            confidence = "Moderate" if confidence == "High" else "Low"

        return {
            "state": "Narrow Leadership",
            "confidence": confidence,
            "reason": (
                "Large-cap leadership is driving the move, but broader equal-weight "
                "and small-cap participation remains weaker."
            ),
        }

    strong_breadth_checks = [
        moves["QQQ"] in UP_MOVES,
        moves["SPY"] in UP_MOVES,
        moves["RSP"] in UP_MOVES,
        moves["IWM"] != "STRONG DOWN",
        moves["VIX"] in FLAT_OR_DOWN_MOVES,
    ]
    if qqqe_available:
        strong_breadth_checks.append(moves["QQQE"] in UP_MOVES)

    if all(strong_breadth_checks):
        return {
            "state": "Strong Breadth Confirmation",
            "confidence": confidence_from_alignment(len(strong_breadth_checks), unavailable=unavailable),
            "reason": (
                "Price strength is supported by broad market participation across "
                "cap-weighted, equal-weight, and small-cap risk appetite proxies."
            ),
        }

    weak_breadth_checks = [
        moves["QQQ"] in {"FLAT", "UP"},
        moves["RSP"] in DOWN_MOVES,
        moves["IWM"] in DOWN_MOVES,
    ]
    if qqqe_available:
        weak_breadth_checks.append(moves["QQQE"] in DOWN_MOVES)

    if weak_breadth_checks[0] and weak_breadth_checks[1] and any(weak_breadth_checks[2:]):
        aligned = sum(1 for check in weak_breadth_checks if check)
        return {
            "state": "Weak Breadth",
            "confidence": confidence_from_alignment(aligned, unavailable=unavailable),
            "reason": (
                "Headline index performance is masking weaker underlying participation "
                "across equal-weight or small-cap breadth proxies."
            ),
        }

    return {
        "state": "Neutral Breadth",
        "confidence": "Low" if unavailable else "Moderate",
        "reason": (
            "Breadth signals are mixed, with no clear broad confirmation or "
            "deterioration across participation proxies."
        ),
    }
