def normalize_email(email: str) -> str:
    """Normalize an email address.

    Lowercases the whole address (email addresses are treated
    case-insensitively by mainstream providers, so invite matching must be
    case-insensitive too). For Gmail addresses, also strips dots from the local
    part since Gmail treats them as insignificant (john.doe@gmail.com ==
    johndoe@gmail.com).
    """
    email = email.lower()
    local, _, domain = email.partition('@')
    if domain == 'gmail.com':
        local = local.replace('.', '')
    return f'{local}@{domain}'
