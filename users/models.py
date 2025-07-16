import uuid
from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    """
    A profile model linked to each User.
    It holds the public-facing unique ID and other user-specific info.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    public_id = models.UUIDField(
        default=uuid.uuid4, 
        editable=False, 
        unique=True
    )
    
    name = models.CharField(max_length=100, blank=True, help_text="Your full name, e.g., Dr. Eva Rostova")
    headline = models.CharField(max_length=150, blank=True, help_text="A short headline, e.g., Quantum Biologist at Chimera University")
    bio = models.TextField(blank=True, help_text="A short biography describing your work and research interests.")
    institution = models.CharField(max_length=150, blank=True, help_text="Your university, company, or institution.")
    website_url = models.URLField(max_length=200, blank=True, help_text="A link to your personal website, blog, or portfolio.")
    
    # For profile pictures, we'll store them in a 'profile_pics' directory inside your media folder.
    profile_picture = models.ImageField(default='profile_pics/default.jpg', upload_to='profile_pics')
    banner_picture = models.ImageField(default='banner_pics/default.jpg', upload_to='banner_pics')
    
    research_interests = models.TextField(
        blank=True, 
        help_text="Comma-separated list of your research interests (e.g., Quantum Computing, Machine Learning)."
    )
    skills = models.TextField(
        blank=True, 
        help_text="Comma-separated list of your skills (e.g., Python, Data Analysis, R)."
    )
    
    def __str__(self):
        return f'{self.user.username} Profile'

    def get_friends(self):
        """Helper method to get a list of this user's friends."""
        friends = []
        # Get accepted requests where this user was the sender
        sent_requests = FriendRequest.objects.filter(from_user=self.user, status='accepted')
        for request in sent_requests:
            friends.append(request.to_user)
            
        # Get accepted requests where this user was the receiver
        received_requests = FriendRequest.objects.filter(to_user=self.user, status='accepted')
        for request in received_requests:
            friends.append(request.from_user)
            
        return friends


class FriendRequest(models.Model):
    """
    A model to represent a friend request from one user to another.
    This model now manages the entire friendship lifecycle.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    )
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # A user can only send one friend request to another user at a time.
        unique_together = ('from_user', 'to_user')

    def __str__(self):
        return f"Friend request from {self.from_user.username} to {self.to_user.username}"
