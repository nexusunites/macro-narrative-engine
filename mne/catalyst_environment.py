from mne.catalysts import calculate_catalyst_density


def classify_catalyst_environment(catalysts_file=None, now=None, lookahead_days=None):
    kwargs = {}
    if catalysts_file is not None:
        kwargs["catalysts_file"] = catalysts_file
    if now is not None:
        kwargs["as_of"] = now
    if lookahead_days is not None:
        kwargs["lookahead_days"] = lookahead_days

    return calculate_catalyst_density(**kwargs)
