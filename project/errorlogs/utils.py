from .models import ErrorLog


def replace_null(s):
    """
    It's apparently possible to get null chars in at least one of
    the error log char/text fields, which makes PostgreSQL get
    "A string literal cannot contain NUL (0x00) characters" upon
    saving the error log. So, this replaces null chars with
    a Replacement Character (question mark diamond).
    """
    return s.replace('\x00', '\uFFFD')


def instantiate_error_log(kind, html, path, info, data):
    return ErrorLog(
        kind=kind,
        html=replace_null(html),
        path=replace_null(path),
        info=info,
        data=replace_null(data),
    )
