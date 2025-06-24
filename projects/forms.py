from django import forms
from .models import Project, Task, Comment, ProjectFile

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        # We only want the user to fill out these two fields
        fields = ['title', 'description']
        # We don't include 'owner' because we'll set that automatically
        
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        # We only need the user to provide a title
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