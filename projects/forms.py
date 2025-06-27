from django import forms
from django.contrib.auth.models import User
from .models import Project, Task, Comment, ProjectFile

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['title', 'description', 'is_public']
        
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Add a new task...'}),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        # The user only needs to provide the body of the comment
        fields = ['body']
        widgets = {
            # Add a Bootstrap class and a placeholder to the textarea
            'body': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add your comment...'
            }),
        }
        # We can also remove the auto-generated label for the 'body' field
        labels = {
            'body': '',
        }

class ProjectFileForm(forms.ModelForm):
    class Meta:
        model = ProjectFile
        fields = ['description', 'file']