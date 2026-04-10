def normalize_email(email: str) -> str:
    """Normalize an email address.

    For Gmail addresses, strips dots from the local part since Gmail treats
    them as insignificant (john.doe@gmail.com == johndoe@gmail.com).
    Non-Gmail addresses are returned unchanged.
    """
    local, _, domain = email.partition('@')
    if domain.lower() == 'gmail.com':
        local = local.replace('.', '')
    return f'{local}@{domain}'
