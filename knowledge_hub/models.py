from django.db import models

# Create your models here.
class Paper(models.Model):
    title = models.CharField(max_length=512)
    authors = models.CharField(max_length=1024)
    abstract = models.TextField()
    arxiv_id = models.CharField(max_length=100, unique=True) # To prevent duplicates
    publication_date = models.DateField()

    class Meta:
        ordering = ['-publication_date']

    def __str__(self):
        return self.title