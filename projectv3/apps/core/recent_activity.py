RECENT_ACTIVITY_SESSION_KEY = 'techfix_recent_activity'
MAX_RECENT_ACTIVITIES = 5


def _validated_activities(activities):
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


def get_recent_activities(request):
    if not request.user.is_authenticated:
        return []

    from .models import RecentActivity

    legacy_activities = _validated_activities(
        request.session.pop(RECENT_ACTIVITY_SESSION_KEY, [])
    )
    if legacy_activities and not RecentActivity.objects.filter(
        user=request.user
    ).exists():
        for activity in reversed(legacy_activities):
            RecentActivity.objects.create(user=request.user, **activity)

    return list(
        RecentActivity.objects.filter(user=request.user)
        .order_by('-created_at', '-pk')
        .values('kind', 'title', 'url')[:MAX_RECENT_ACTIVITIES]
    )


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

    from .models import RecentActivity

    get_recent_activities(request)
    RecentActivity.objects.filter(user=request.user, **activity).delete()
    RecentActivity.objects.create(user=request.user, **activity)
    older_activity_ids = RecentActivity.objects.filter(user=request.user).order_by(
        '-created_at', '-pk'
    ).values_list('pk', flat=True)[MAX_RECENT_ACTIVITIES:]
    RecentActivity.objects.filter(pk__in=older_activity_ids).delete()


def recent_activity_context(request):
    return {'recent_activities': get_recent_activities(request)}
