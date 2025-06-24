from django.contrib import admin
from .models import Project, Task, Comment

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    # This will show a nice filterable interface for many-to-many fields
    filter_horizontal = ('collaborators',)
    # You can also customize what's shown in the list view
    list_display = ('title', 'owner', 'created_at')
    list_filter = ('owner',)


# We can keep the simple registration for these models
admin.site.register(Task)
admin.site.register(Comment)