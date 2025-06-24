import arxiv
from django.core.management.base import BaseCommand
from knowledge_hub.models import Paper

class Command(BaseCommand):
    help = 'Seeds the database with papers from arXiv'

    def handle(self, *args, **options):
        self.stdout.write("Searching for papers on arXiv...")

        # Search for recent papers in the 'cs.AI' (Artificial Intelligence) category
        search = arxiv.Search(
            query="cat:cs.AI",
            max_results=20,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        papers_created = 0
        for result in search.results():
            # Check if the paper already exists to avoid duplicates
            if not Paper.objects.filter(arxiv_id=result.entry_id).exists():
                Paper.objects.create(
                    title=result.title,
                    authors=', '.join(author.name for author in result.authors),
                    abstract=result.summary,
                    arxiv_id=result.entry_id,
                    publication_date=result.published.date()
                )
                papers_created += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully created {papers_created} new papers."))
