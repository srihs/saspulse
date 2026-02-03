from django.shortcuts import render


def dashboard(request):
    """
    Main dashboard view
    """
    context = {
        'page_title': 'Dashboard',
    }
    return render(request, 'base.html', context)
