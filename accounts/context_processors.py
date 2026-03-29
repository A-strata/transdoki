from organizations.models import Organization


def current_org_context(request):
    if not request.user.is_authenticated:
        return {"current_org": None, "own_orgs": Organization.objects.none()}

    return {
        "current_org": getattr(request, "current_org", None),
        "own_orgs": getattr(request, "own_orgs", Organization.objects.none()),
    }
