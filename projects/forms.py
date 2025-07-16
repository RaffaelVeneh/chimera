from django import forms
from django.contrib.auth.models import User
from .models import Project, Task, Comment, ProjectFile, PersonalTodo

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
        
class PersonalTodoForm(forms.ModelForm):
    # Use a specific input format for the datetime field
    due_date = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control'}
        ),
        required=False
    )

    class Meta:
        model = PersonalTodo
        fields = ['title', 'due_date', 'priority']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
        }