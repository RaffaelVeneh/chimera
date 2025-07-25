from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse

from allauth.account.forms import ChangePasswordForm, AddEmailForm

from .forms import ProfileUpdateForm
from .models import FriendRequest, Profile

@login_required
def find_friends(request):
    query = request.GET.get('q', '')
    results = []
    
    if query:
        # Find users matching the query, excluding only the user themselves.
        found_users = User.objects.filter(
            Q(username__icontains=query)
        ).exclude(id=request.user.id)

        # For each found user, determine the friendship status with the current user.
        for user in found_users:
            status = 'none'
            request_obj = None
            
            # Check for existing requests in either direction
            sent_request = FriendRequest.objects.filter(from_user=request.user, to_user=user).first()
            received_request = FriendRequest.objects.filter(from_user=user, to_user=request.user).first()

            if sent_request:
                if sent_request.status == 'pending':
                    status = 'pending_sent'
                    request_obj = sent_request
                elif sent_request.status == 'accepted':
                    status = 'friends'
            elif received_request:
                 if received_request.status == 'pending':
                    status = 'pending_received'
                 elif received_request.status == 'accepted':
                    status = 'friends'

            # Only add to results if they are not already friends
            if status != 'friends':
                results.append({'user': user, 'status': status, 'request_object': request_obj})

    context = {
        'results': results, # Pass 'results' instead of 'users'
        'query': query,
    }
    return render(request, 'users/find_friends.html', context)

@login_required
def send_friend_request(request, user_id):
    to_user = get_object_or_404(User, id=user_id)
    if FriendRequest.objects.filter(from_user=request.user, to_user=to_user).exists() or \
       FriendRequest.objects.filter(from_user=to_user, to_user=request.user).exists():
        messages.warning(request, 'A friend request already exists with this user.')
    else:
        FriendRequest.objects.create(from_user=request.user, to_user=to_user)
        messages.success(request, f'Friend request sent to {to_user.username}.')
    
    query = request.GET.get('q', '')
    return redirect(f"{reverse('manage-friends')}?q={query}&tab=search")

@login_required
def process_friend_request(request, request_id, action):
    friend_request = get_object_or_404(FriendRequest, id=request_id, to_user=request.user)
    
    if action == 'accept':
        friend_request.status = 'accepted'
        friend_request.save()
        messages.success(request, f'You are now friends with {friend_request.from_user.username}.')
    elif action == 'decline':
        friend_request.status = 'declined'
        friend_request.save() # Or you could delete it: friend_request.delete()
        messages.info(request, f'You have declined the friend request from {friend_request.from_user.username}.')
        
    return redirect(f"{reverse('manage-friends')}?tab=requests")

@login_required
def remove_friend(request, user_id):
    friend_to_remove = get_object_or_404(User, id=user_id)
    
    # Find and delete the friend request object that represents the friendship
    FriendRequest.objects.filter(
        (Q(from_user=request.user) & Q(to_user=friend_to_remove) & Q(status='accepted')) |
        (Q(from_user=friend_to_remove) & Q(to_user=request.user) & Q(status='accepted'))
    ).delete()
    
    messages.info(request, f'You have removed {friend_to_remove.username} from your friends.')
    return redirect('manage-friends')

@login_required
def manage_friends(request):
    """
    A dedicated page for managing friends, incoming requests,
    sent requests, and finding new friends.
    """
    # Friend list and request logic
    profile = request.user.profile
    friends = profile.get_friends()
    incoming_requests = FriendRequest.objects.filter(to_user=request.user, status='pending')
    sent_requests = FriendRequest.objects.filter(from_user=request.user, status='pending')

    # --- START: Merged Search Logic ---
    query = request.GET.get('q', '')
    search_results = []
    if query:
        found_users = User.objects.filter(
            Q(username__icontains=query)
        ).exclude(id=request.user.id)

        for user in found_users:
            status = 'none'
            request_obj = None
            
            # Check for existing requests
            sent_request = FriendRequest.objects.filter(from_user=request.user, to_user=user).first()
            received_request = FriendRequest.objects.filter(from_user=user, to_user=request.user).first()

            if sent_request:
                status = sent_request.status # 'pending' or 'accepted'
                request_obj = sent_request
            elif received_request:
                status = received_request.status # 'pending' or 'accepted'
            
            # Use a slightly different status name for clarity in the template
            if status == 'accepted':
                final_status = 'friends'
            elif status == 'pending' and sent_request:
                final_status = 'pending_sent'
            elif status == 'pending' and received_request:
                final_status = 'pending_received'
            else:
                final_status = 'none'

            search_results.append({'user': user, 'status': final_status, 'request_object': request_obj})

    context = {
        'friends': friends,
        'incoming_requests': incoming_requests,
        'sent_requests': sent_requests,
        'query': query,
        'search_results': search_results,
    }
    return render(request, 'users/manage_friends.html', context)

@login_required
def cancel_friend_request(request, request_id):
    """Cancels a friend request sent by the logged-in user."""
    friend_request = get_object_or_404(FriendRequest, id=request_id, from_user=request.user)
    friend_request.delete()
    messages.info(request, "Friend request cancelled.")
    
    tab = request.GET.get('tab', 'search')
    query = request.GET.get('q', '')
    
    if tab == 'search':
        return redirect(f"{reverse('manage-friends')}?q={query}&tab=search")
    else: # Default to the pending tab if not search
        return redirect(f"{reverse('manage-friends')}?tab=pending")
    
@login_required
def profile_view(request, public_id):
    """Displays a user's profile page and handles settings forms."""
    profile = get_object_or_404(Profile, public_id=public_id)
    is_own_profile = (request.user == profile.user)
    
    context = {
        'profile': profile,
        'is_own_profile': is_own_profile,
    }

    # If the user is viewing their own profile, add the necessary forms to the context
    if is_own_profile:
        context['profile_form'] = ProfileUpdateForm(instance=profile)
        # These forms are from django-allauth
        context['password_change_form'] = ChangePasswordForm()
        context['add_email_form'] = AddEmailForm()

    return render(request, 'users/profile.html', context)

@login_required
def get_profile_display(request, public_id):
    """Returns the read-only display partial for a profile."""
    profile = get_object_or_404(Profile, public_id=public_id)
    return render(request, 'users/partials/_profile_display.html', {'profile': profile})


@login_required
def get_profile_edit_form(request, public_id):
    """Returns the profile editing form partial."""
    profile = get_object_or_404(Profile, public_id=public_id)
    form = ProfileUpdateForm(instance=profile)
    return render(request, 'users/partials/_profile_edit_form.html', {'profile': profile, 'form': form})


@require_POST
@login_required
def edit_profile(request):
    """Handles profile form submission and returns the updated display partial."""
    profile = request.user.profile
    form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
    
    if form.is_valid():
        form.save()
        messages.success(request, 'Your profile has been updated successfully.')
        # --- FIX: Return the display partial instead of redirecting ---
        return render(request, 'users/partials/_profile_display.html', {'profile': profile})
    
    # If form is invalid, re-render the edit form with errors
    return render(request, 'users/partials/_profile_edit_form.html', {'profile': profile, 'form': form})

@require_POST
@login_required
def upload_profile_picture(request):
    """
    Handles the AJAX request to upload a cropped profile picture.
    """
    try:
        # The file is sent from the frontend
        cropped_image = request.FILES.get('cropped_image')
        if not cropped_image:
            return JsonResponse({'status': 'error', 'message': 'No image file provided.'}, status=400)

        # Get the user's profile and update the picture
        profile = request.user.profile
        profile.profile_picture.save(cropped_image.name, cropped_image)
        
        # Return a success response with the new image URL
        return JsonResponse({
            'status': 'success',
            'new_picture_url': profile.profile_picture.url
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@require_POST
@login_required
def upload_banner_picture(request):
    """
    Handles the AJAX request to upload a cropped banner picture.
    """
    try:
        cropped_image = request.FILES.get('cropped_image')
        if not cropped_image:
            return JsonResponse({'status': 'error', 'message': 'No image file provided.'}, status=400)

        profile = request.user.profile
        profile.banner_picture.save(cropped_image.name, cropped_image)
        
        return JsonResponse({
            'status': 'success',
            'new_banner_url': profile.banner_picture.url
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)