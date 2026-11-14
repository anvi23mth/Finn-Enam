def unit_class(u):
    t = (u or "").lower()
    if "%" in t or "percent" in t:
        return "pct"
    if "day" in t:
        return "days"
    if "crore" in t or t.strip() == "cr":
        return "inr_cr"
    if "million" in t and "usd" in t:
        return "usd_m"
    if "billion" in t and "usd" in t:
        return "usd_b"
    return t or None
