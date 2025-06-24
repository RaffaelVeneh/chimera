from django.shortcuts import render
from .models import Paper
from django.db.models import Q # Import Q objects

def paper_search(request):
    # Get the search query from the URL's 'q' parameter
    query = request.GET.get('q', '')
    papers = []

    if query:
        # If a query exists, filter papers
        # Q() objects allow us to build complex queries with OR (|) logic
        papers = Paper.objects.filter(
            Q(title__icontains=query) | Q(abstract__icontains=query)
        )

    context = {
        'papers': papers,
        'query': query,
    }
    return render(request, 'knowledge_hub/paper_search.html', context)