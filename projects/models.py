from django.contrib.auth.models import User
from django.db import models

class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    collaborators = models.ManyToManyField(
        User,
        through='ProjectMembership',
        related_name='collaborations'
    )
    is_public = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def members(self):
        """Returns a queryset of all members (owner + collaborators)."""
        return [self.owner] + list(self.collaborators.all())

    def __str__(self):
        return self.title
    
class Task(models.Model):
    title = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    read_by = models.ManyToManyField(User, related_name='read_tasks', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    pinned_by = models.ManyToManyField(User, related_name='pinned_tasks', blank=True)

    @property
    def was_edited(self):
        # Check if edited_at is more than a second different from created_at
        return (self.edited_at - self.created_at).total_seconds() > 1
    
    def __str__(self):
        return self.title
    
class TaskAssignment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='assignments')
    assignee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_assignments')
    assigner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='made_assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A user cannot be assigned the same task more than once
        unique_together = ('task', 'assignee')
        ordering = ['-assigned_at']

    def __str__(self):
        return f'"{self.task.title}" assigned to {self.assignee.username} by {self.assigner.username}'
    
class Comment(models.Model):
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='comments')
    read_by = models.ManyToManyField(User, related_name='read_comments', blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Comment by {self.author.username} on {self.project.title}'
    
    @property
    def was_edited(self):
        # Check if edited_at is more than a few seconds different from created_at
        return (self.edited_at - self.created_at).total_seconds() > 2

class ProjectFile(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_files')
    file = models.FileField(upload_to='project_files/')
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    read_by = models.ManyToManyField(User, related_name='read_files', blank=True)

    def __str__(self):
        return self.file.name
    
class ProjectMembership(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('editor', 'Editor'),
        ('viewer', 'Viewer'),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ('project', 'user')

    def __str__(self):
        return f'{self.user.username} - {self.project.title} ({self.role})'
    
class AccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        DENIED = 'denied', 'Denied'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='access_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_requests')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # This ensures a user cannot send multiple requests for the same project
        unique_together = ('project', 'user')

    def __str__(self):
        return f'{self.user.username} request for {self.project.title}'
    
class PersonalTodo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todos')
    title = models.CharField(max_length=200)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class Ban(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='bans')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    banned_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='issued_bans')
    banned_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True)

    role = models.CharField(max_length=20, default='viewer')

    def __str__(self):
        return f'{self.user.username} banned from {self.project.title}'
    
class Report(models.Model):
    """Represents a report made by a user against a specific comment."""
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Resolved'
        DISMISSED = 'dismissed', 'Dismissed'

    # The comment that was reported
    reported_comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reports')
    # The user who filed the report
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='filed_reports')
    # The user who was reported
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_reports')
    
    # Details of the report
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    reported_at = models.DateTimeField(auto_now_add=True)
    
    # For resolution tracking
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_reports')
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-reported_at']

    def __str__(self):
        return f'Report by {self.reporter.username} on comment {self.reported_comment.id}'
    
class ProjectLog(models.Model):
    """Represents a single log entry for an important event in a project."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='logs')
    # The user who performed the action
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='actions_logged')
    log_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Log for {self.project.title} at {self.created_at}'