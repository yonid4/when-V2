import random
import string


def generate_uid(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choices(chars, k=length))
