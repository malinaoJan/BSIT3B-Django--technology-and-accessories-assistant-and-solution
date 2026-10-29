RECENT_ACTIVITY_SESSION_KEY = 'techfix_recent_activity'
MAX_RECENT_ACTIVITIES = 5


def get_recent_activities(request):
    if not request.user.is_authenticated:
        return []

    activities = request.session.get(RECENT_ACTIVITY_SESSION_KEY, [])
    if not isinstance(activities, list):
        return []

    return [
        activity for activity in activities
        if isinstance(activity, dict)
        and isinstance(activity.get('kind'), str)
        and isinstance(activity.get('title'), str)
        and isinstance(activity.get('url'), str)
        and activity['url'].startswith('/')
        and not activity['url'].startswith('//')
    ][:MAX_RECENT_ACTIVITIES]


def record_recent_activity(request, kind, title, url):
    if not request.user.is_authenticated:
        return

    activity = {
        'kind': kind,
        'title': str(title).strip()[:120],
        'url': url,
    }
    if not activity['title'] or not url.startswith('/') or url.startswith('//'):
        return

    activities = get_recent_activities(request)
    activities = [
        existing for existing in activities
        if not (
            existing.get('kind') == kind
            and existing.get('title') == activity['title']
            and existing.get('url') == url
        )
    ]
    request.session[RECENT_ACTIVITY_SESSION_KEY] = [
        activity, *activities
    ][:MAX_RECENT_ACTIVITIES]


def recent_activity_context(request):
    return {'recent_activities': get_recent_activities(request)}
