from django.contrib import admin
from .models import Project, Task, Comment, ProjectMembership, AccessRequest

class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    # You can specify which fields to show in the inline form
    fields = ('user', 'role')
    extra = 1 # How many empty extra rows to show
    
@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'created_at')
    list_filter = ('owner', 'is_public')
    inlines = [ProjectMembershipInline]


# We can keep the simple registration for these models
admin.site.register(Task)
admin.site.register(Comment)
admin.site.register(AccessRequest)