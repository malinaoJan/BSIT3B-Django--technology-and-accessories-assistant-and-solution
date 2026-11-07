"""Template helpers for the TechFix assistant."""

import re

from django import template

register = template.Library()

_VIDEO_ID = re.compile(
    r'(?:v=|youtu\.be/|/embed/|/shorts/|/live/)([0-9A-Za-z_-]{6,20})'
)


@register.filter
def youtube_embed(url):
    """Return an embeddable YouTube URL, or '' for other video links."""
    match = _VIDEO_ID.search(str(url or ''))
    if not match:
        return ''
    return 'https://www.youtube-nocookie.com/embed/%s' % match.group(1)
