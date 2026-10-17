from django.shortcuts import get_object_or_404
from apps.info.models import Info

def scoped_infos(user):
    # Superusers see everything (including orphan records with user=None).
    # Regular users only see their own records.
    if user.is_superuser:
        return Info.objects.all()
    return Info.objects.filter(user=user)

def scoped_info(user, pk):
    return get_object_or_404(scoped_infos(user), pk=pk)
