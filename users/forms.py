from django import forms
from .models import Profile

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'name', 
            'headline', 
            'bio', 
            'institution', 
            'website_url', 
            'research_interests', 
            'skills',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'research_interests': forms.Textarea(attrs={'rows': 2}),
            'skills': forms.Textarea(attrs={'rows': 2}),
        }
        
        labels = {
            'name': 'Full Name',
        }