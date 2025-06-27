from django.shortcuts import render
from .models import Paper
from django.db.models import Q # Import Q objects

def paper_search(request):
    query = request.GET.get('q', '')
    papers = []

    if query:
        papers = Paper.objects.filter(
            Q(title__icontains=query) | Q(abstract__icontains=query)
        )

    context = {
        'papers': papers,
        'query': query,
    }
    return render(request, 'knowledge_hub/paper_search.html', context)