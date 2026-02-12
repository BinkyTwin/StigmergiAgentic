class LegacyError(Exception):
    pass


def risky(flag):
    if flag:
        raise LegacyError, "legacy raise syntax"

    try:
        raise LegacyError("x")
    except LegacyError, err:
        return str(err)
