from .recent_activity import recent_activity_context


def recent_activities(request):
    return recent_activity_context(request)
