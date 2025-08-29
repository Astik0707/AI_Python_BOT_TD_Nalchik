import bleach

ALLOWED_TAGS = [
    'b', 'strong', 'i', 'em', 'u', 'ins', 's', 'strike', 'del',
    'code', 'pre', 'a', 'span', 'tg-spoiler'
]


def _filter_span_class(tag: str, name: str, value: str) -> str | None:
    if tag == 'span' and name == 'class':
        return value if value == 'tg-spoiler' else None
    return None


ALLOWED_ATTRS = {
    'a': ['href'],
    'span': {'class': _filter_span_class}
}

def sanitize_html(html: str) -> str:
    if not html:
        return ''
    cleaned = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    return cleaned
