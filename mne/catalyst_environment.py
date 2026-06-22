from mne.catalysts import calculate_catalyst_density


def classify_catalyst_environment(
    catalysts_file=None,
    now=None,
    lookahead_days=None,
    enable_auto_company_catalysts=None,
    enable_auto_macro_catalysts=None,
    macro_calendar_status=None,
):
    kwargs = {}
    if catalysts_file is not None:
        kwargs["catalysts_file"] = catalysts_file
    if now is not None:
        kwargs["as_of"] = now
    if lookahead_days is not None:
        kwargs["lookahead_days"] = lookahead_days
    if enable_auto_company_catalysts is not None:
        kwargs["enable_auto_company_catalysts"] = enable_auto_company_catalysts
    if enable_auto_macro_catalysts is not None:
        kwargs["enable_auto_macro_catalysts"] = enable_auto_macro_catalysts
    if macro_calendar_status is not None:
        kwargs["macro_calendar_status"] = macro_calendar_status

    return calculate_catalyst_density(**kwargs)
