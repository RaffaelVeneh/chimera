import pandas as pd
import plotly.express as px

from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.utils import timezone
from itertools import chain
from operator import attrgetter

from .models import Project, Task, Comment, User, ProjectMembership, AccessRequest, TaskAssignment, PersonalTodo, Ban, Report, ProjectLog
from .forms import ProjectForm, TaskForm, CommentForm, ProjectFileForm, ProjectFile
from users.models import FriendRequest

def annotate_task_with_states(task, project):
    """
    Calculates the marking/pinning state for a task and attaches it
    to the task object for use in templates.
    """
    # Get IDs of all members in the project
    project_member_ids = {member.id for member in project.members}

    # Get IDs of all users who have been assigned this task
    assigned_user_ids = {assignment.assignee_id for assignment in task.assignments.all()}
    
    # Get IDs of all users who have pinned this task
    pinned_user_ids = {user.id for user in task.pinned_by.all()}

    # Combine the sets to find all "marked" users
    all_marked_ids = assigned_user_ids.union(pinned_user_ids)

    # Attach the final boolean flag to the task object
    task.all_members_marked = project_member_ids.issubset(all_marked_ids)

    # Also attach assigned user IDs, which we still need for other button states
    task.assigned_user_ids = list(assigned_user_ids)
    
    return task

def get_user_role(project, user):
    if not user.is_authenticated: return None
    if project.owner == user: return 'owner'
    try:
        return ProjectMembership.objects.get(project=project, user=user).role
    except ProjectMembership.DoesNotExist:
        return None
    
def _get_manage_team_context(request, project):
    requesting_user_role = get_user_role(project, request.user)
    
    memberships = ProjectMembership.objects.filter(project=project).select_related('user')
    for m in memberships:
        m.is_editable = (requesting_user_role == 'owner' or (requesting_user_role == 'admin' and m.role not in ['owner', 'admin']))
        if requesting_user_role == 'owner':
            m.permissible_roles = ProjectMembership.ROLE_CHOICES
        else:
            m.permissible_roles = [r for r in ProjectMembership.ROLE_CHOICES if r[0] != 'admin']

    potential_collaborators = User.objects.none()
    if requesting_user_role in ['owner', 'admin']:
        current_member_ids = [m.user.id for m in memberships] + [project.owner.id]
        potential_collaborators = User.objects.exclude(id__in=current_member_ids)

    banned_list = Ban.objects.filter(project=project).select_related('user')
    for b in banned_list:
        # --- FIX: Admins can now unban non-admins. Owners can unban anyone. ---
        b.can_unban = (requesting_user_role == 'owner' or (requesting_user_role == 'admin' and b.role != 'admin'))
        
    return {
        'project': project, 'memberships': memberships,
        'potential_collaborators': potential_collaborators,
        'banned_list': banned_list, 'role': requesting_user_role, 'request': request,
    }
    
@login_required
def dashboard(request, username):
    page_user = get_object_or_404(User, username=username)
    if request.user != page_user:
        return redirect('project-list')
    
    all_friends = page_user.profile.get_friends()
    all_incoming_requests = FriendRequest.objects.filter(to_user=page_user, status='pending')
    
    friends_preview = all_friends[:5]
    incoming_requests_preview = all_incoming_requests[:5]
    
    total_friends_count = len(all_friends)
    total_incoming_requests_count = all_incoming_requests.count()
    
    if page_user != request.user:
        return HttpResponseForbidden("You can only view your own dashboard.")
    
    owned_projects = Project.objects.filter(owner=request.user)
    team_projects = Project.objects.filter(collaborators=page_user).exclude(owner=page_user)

    # Get Tasks for the new dashboard sections
    personal_todos = PersonalTodo.objects.filter(user=page_user)
    pinned_tasks = Task.objects.filter(pinned_by=page_user)
    assignments_for_me = TaskAssignment.objects.filter(assignee=page_user)

    # Get Activity Feed
    all_my_projects_ids = list(set(list(owned_projects.values_list('id', flat=True)) + list(team_projects.values_list('id', flat=True))))
    recent_tasks = Task.objects.filter(project_id__in=all_my_projects_ids).order_by('-created_at')[:10]
    recent_comments = Comment.objects.filter(project_id__in=all_my_projects_ids).order_by('-created_at')[:10]
    recent_files = ProjectFile.objects.filter(project_id__in=all_my_projects_ids).order_by('-uploaded_at')[:10]

    activity_list = sorted(
        chain(recent_tasks, recent_comments, recent_files),
        key=lambda instance: instance.created_at if hasattr(instance, 'created_at') else instance.uploaded_at,
        reverse=True
    )

    context = {
        'owned_projects': owned_projects,
        'team_projects': team_projects,
        'personal_todos': personal_todos,
        'pinned_tasks': pinned_tasks,
        'assignments_for_me': assignments_for_me,
        'activity_list': activity_list,
        'friends': friends_preview,
        'incoming_requests': incoming_requests_preview,
        'total_friends_count': total_friends_count,
        'total_incoming_requests_count': total_incoming_requests_count,
    }
    return render(request, 'projects/dashboard.html', context)
    
def index(request):
    # This view seems to be your project list page
    # I'll add the necessary logic based on your index.html template
    query = request.GET.get('q')
    active_tab = request.GET.get('tab', 'public')

    public_projects = Project.objects.filter(is_public=True)
    team_projects = Project.objects.filter(collaborators=request.user) if request.user.is_authenticated else Project.objects.none()
    owned_projects = Project.objects.filter(owner=request.user) if request.user.is_authenticated else Project.objects.none()

    if query:
        public_projects = public_projects.filter(Q(title__icontains=query) | Q(description__icontains=query))
        team_projects = team_projects.filter(Q(title__icontains=query) | Q(description__icontains=query))
        owned_projects = owned_projects.filter(Q(title__icontains=query) | Q(description__icontains=query))

    context = {
        'public_projects': public_projects,
        'team_projects': team_projects,
        'owned_projects': owned_projects,
        'active_tab': active_tab,
        'query': query,
    }
    return render(request, 'projects/index.html', context)

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    
    if Ban.objects.filter(project=project, user=request.user).exists():
        return render(request, 'projects/banned_page.html', {'project': project}, status=403)
    
    role = get_user_role(project, request.user)

    # The authorization check is now simpler:
    if not project.is_public and role is None:
        return render(request, '403.html', {'project': project}, status=403)

    # --- The rest of the view is unchanged ---
    file_form = ProjectFileForm()
    comment_form = CommentForm()

    context = {
        'project': project,
        'role': role,
        'comment_form': comment_form,
        'file_form': file_form,
    }
    return render(request, 'projects/project_detail.html', context)

@login_required
def create_project(request):
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            messages.success(request, 'Project created successfully!')
            return redirect('project-detail', project_id=project.id)
    else:
        form = ProjectForm()
    return render(request, 'projects/create_project.html', {'form': form})

@login_required
def edit_project(request, project_id):
    project = Project.objects.get(pk=project_id)

    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to edit this project.")
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your project has been updated successfully!')
            return redirect('project-detail', project_id=project.id)
    else:
        form = ProjectForm(instance=project)

    context = {
        'form': form,
        'project': project,
    }
    return render(request, 'projects/edit_project.html', context)

@login_required
def delete_project(request, project_id):
    project = Project.objects.get(pk=project_id)

    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to edit this project.")
    
    if request.method == 'POST':
        project_title = project.title
        project.delete()

        messages.success(request, f"Project '{project_title}' was deleted.")
        
        if request.htmx:
            response = HttpResponse(status=204) 
            response['HX-Redirect'] = reverse('projects-index')
            return response
        else:
            return redirect('projects-index')

    if request.htmx:
        template_name = 'projects/partials/delete_confirm_modal.html'
    else:
        template_name = 'projects/delete_confirm.html'

    context = {'project': project}
    return render(request, template_name, context)

def logout_view(request):
    logout(request)
    return redirect('projects-index')

@login_required
def add_task(request, project_id):
    project = Project.objects.get(pk=project_id)
    role = get_user_role(project, request.user)
    form = TaskForm(request.POST)
    
    if role not in ['owner', 'admin', 'editor']:
        return HttpResponseForbidden("You do not have permission to add tasks to this project.")
    
    if role not in ['owner', 'admin', 'editor']:
        return HttpResponseForbidden("You do not have permission to add tasks to this project.")

    if form.is_valid():
        task = form.save(commit=False)
        task.project = project
        task.created_by = request.user # ADD THIS LINE
        task.save()
        task.read_by.add(request.user)

    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'refresh-lists'
    return response

@login_required
def delete_task(request, task_id):
    task = Task.objects.get(pk=task_id)
    project = task.project
    role = get_user_role(project, request.user)

    if role not in ['owner', 'admin', 'editor']:
        return HttpResponseForbidden()

    if request.method == 'POST':
        task.delete()
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('project-detail', kwargs={'project_id': project.id})
        return response

    context = {'task': task}
    return render(request, 'projects/partials/delete_task_modal.html', context)

@login_required
def edit_task(request, task_id):
    task = Task.objects.get(pk=task_id)
    project = task.project
    role = get_user_role(project, request.user)

    if role not in ['owner', 'admin', 'editor']:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            # --- FIX: Return an empty response that triggers a list refresh ---
            response = HttpResponse(status=204) # 204 No Content
            response['HX-Trigger'] = 'refresh-lists'
            return response
        
    form = TaskForm(instance=task)
    return render(request, 'projects/partials/edit_task_form.html', {'form': form, 'task': task})

def task_list(request, project_id):
    project = Project.objects.get(pk=project_id)
    
    if not project.is_public and not request.user.is_authenticated:
        return HttpResponseForbidden()
    
    role = get_user_role(project, request.user)

    if not project.is_public and role is None:
        return HttpResponseForbidden()

    # Sorting Logic
    valid_sorts = {
        '-created_at': 'Newest First', 'created_at': 'Oldest First',
        'title': 'Title (A-Z)', '-title': 'Title (Z-A)',
    }
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by not in valid_sorts:
        sort_by = '-created_at'

    # Start with the sorted queryset
    tasks_queryset = project.tasks.all().order_by(sort_by)

    # Search Logic
    search_query = request.GET.get('search', '')
    if search_query:
        tasks_queryset = tasks_queryset.filter(title__icontains=search_query)

    # Pagination Logic
    paginator = Paginator(tasks_queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Mark as read logic
    if request.user.is_authenticated:
        for task in page_obj:
            task = annotate_task_with_states(task, project)
            task.read_by.add(request.user)

    context = {
        'project': project, 'tasks_page': page_obj, 'role': role,
        'current_sort': sort_by, 'current_sort_name': valid_sorts.get(sort_by),
        'valid_sorts': valid_sorts, 'search_query': search_query,
    }

    # THE FIX: Always render the main component template
    return render(request, 'projects/partials/task_list.html', context)

@login_required
def toggle_task(request, task_id):
    task = Task.objects.get(pk=task_id)
    project = task.project
    role = get_user_role(project, request.user)

    if role not in ['owner', 'admin', 'editor']:
        return HttpResponseForbidden("You do not have permission to modify tasks in this project.")

    task.is_completed = not task.is_completed
    task.save()
    
    task = annotate_task_with_states(task, project)

    context = {
        'task': task,
        'project': project,
        'role': role
    }
    return render(request, 'projects/partials/task_item.html', context)

@login_required
def toggle_mark_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    user = request.user

    # Check if the user has already marked this task
    if user in task.marked_by.all():
        # If yes, remove them (un-mark)
        task.marked_by.remove(user)
    else:
        # If no, add them (mark)
        task.marked_by.add(user)

    # For HTMX, we need to return the updated button partial
    # We'll pass the task back to a new partial template
    return render(request, 'projects/partials/mark_task_button.html', {'task': task})

@login_required
def get_mark_task_form(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    project = task.project
    # Get all members of the project (owner + collaborators)
    members = [project.owner] + list(project.collaborators.all())

    context = {'task': task, 'project_members': members}
    return render(request, 'projects/partials/mark_task_form.html', context)

@login_required
def confirm_mark_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    # The user we intend to mark the task for is passed as a GET parameter
    assignee_id = request.GET.get('assignee')

    # Scenario 1: The task is NOT complete, so we mark it immediately.
    if not task.is_completed:
        assigner = request.user
        if assignee_id == 'all':
            members = [task.project.owner] + list(task.project.collaborators.all())
            for member in members:
                TaskAssignment.objects.get_or_create(task=task, assignee=member, assigner=assigner)
        else:
            assignee = get_object_or_404(User, pk=assignee_id)
            TaskAssignment.objects.get_or_create(task=task, assignee=assignee, assigner=assigner)

        # Send a trigger to refresh the dashboard lists and return an empty response.
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'refresh-dashboard'
        return response

    # Scenario 2: The task IS complete, so we return the HTML for the confirmation modal.
    else:
        context = {'task': task, 'assignee_id': assignee_id}
        return render(request, 'projects/partials/mark_task_confirm_modal.html', context)

@login_required
def mark_task_for_user(request, task_id):
    # This view now only handles the final POST action
    if request.method == 'POST':
        task = get_object_or_404(Task, pk=task_id)
        assigner = request.user
        assignee_id = request.POST.get('assignee')

        if assignee_id == 'all':
            # --- START OF FIX ---

            # 1. Pin the task for the current user.
            task.pinned_by.add(request.user)

            # 2. Get all members of the project.
            members = [task.project.owner] + list(task.project.collaborators.all())

            # 3. Create an assignment for everyone ELSE.
            for member in members:
                if member != request.user:
                    TaskAssignment.objects.get_or_create(task=task, assignee=member, assigner=assigner)
            
            # --- END OF FIX ---
        else:
            assignee = get_object_or_404(User, pk=assignee_id)
            TaskAssignment.objects.get_or_create(task=task, assignee=assignee, assigner=assigner)

        # After marking, trigger a refresh of the lists
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'refresh-lists'
        return response
    return HttpResponseForbidden()

@login_required
def unpin_task(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(Task, pk=task_id)
        task.pinned_by.remove(request.user)
        # You could trigger a refresh here, but for now we'll let the user see it disappear
    return HttpResponse('') # Return an empty response to remove the item

def render_comment_list(request, project):
    """Helper function to render the entire comment list partial."""
    comments = project.comments.all()
    role = get_user_role(project, request.user)
    return render(request, 'projects/partials/comment_list.html', {'project': project, 'comments': comments, 'role': role})

@login_required
def add_comment(request, project_id):
    project = Project.objects.get(pk=project_id)
    role = get_user_role(project, request.user)
    
    if role not in ['owner', 'admin', 'editor']:
        return HttpResponseForbidden("You do not have permission to add tasks to this project.")
    
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.project = project
            comment.author = request.user
            comment.save()
            comment.read_by.add(request.user)

    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'refresh-lists'
    return response

@login_required
def comment_list(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    viewer_role = get_user_role(project, request.user)

    if viewer_role is None and not project.is_public:
        return HttpResponseForbidden("You cannot view comments for this project.")

    # --- FIX: Added sorting logic back in ---
    valid_sorts = {
        '-created_at': 'Newest First',
        'created_at': 'Oldest First',
    }
    # Get sort parameter from the request, default to newest first
    current_sort = request.GET.get('sort', '-created_at')
    if current_sort not in valid_sorts:
        current_sort = '-created_at'

    # Apply the sorting to the queryset
    comments = Comment.objects.filter(project=project).select_related('author').order_by(current_sort)
    # --- END FIX ---

    # Set permissions for each comment
    for comment in comments:
        is_self = (request.user == comment.author)
        commenter_role = get_user_role(project, comment.author)

        # Deletion logic
        can_delete = False
        if is_self or viewer_role == 'owner' or (viewer_role == 'admin' and commenter_role not in ['owner', 'admin']):
            can_delete = True
        comment.can_be_deleted = can_delete
        
        # Reporting logic
        can_report = False
        if not is_self:
            if viewer_role in ['editor', 'viewer'] or (viewer_role == 'admin' and commenter_role in ['owner', 'admin']):
                can_report = True
        comment.can_be_reported = can_report
        
    paginator = Paginator(comments, 10)
    page_number = request.GET.get('page')
    comments_page = paginator.get_page(page_number)

    context = {
        'project': project,
        'comments_page': comments_page,
        'role': viewer_role,
        # Pass sorting context to the template
        'valid_sorts': valid_sorts,
        'current_sort': current_sort,
        'current_sort_name': valid_sorts.get(current_sort)
    }
    return render(request, 'projects/partials/comment_list.html', context)

@login_required
def edit_comment(request, comment_id):
    comment = Comment.objects.get(pk=comment_id)
    project = comment.project

    # Authorization: You must be the author to edit.
    if comment.author != request.user:
        return HttpResponseForbidden("You can only edit your own comments.")

    if request.method == 'POST':
        form = CommentForm(request.POST, instance=comment)
        if form.is_valid():
            form.save()
            # After saving, we return the single, updated comment item display.
            role = get_user_role(project, request.user)
            return render(request, 'projects/partials/comment_item.html', {'comment': comment, 'project': project, 'role': role})

    # If GET, return the form for editing.
    form = CommentForm(instance=comment)
    return render(request, 'projects/partials/edit_comment_form.html', {'form': form, 'comment': comment})


@require_POST
@login_required
def delete_comment(request, comment_id):
    """Deletes a comment after checking permissions."""
    comment = get_object_or_404(Comment, id=comment_id)
    project = comment.project
    requesting_user_role = get_user_role(project, request.user)
    comment_author_role = get_user_role(project, comment.author)

    # This is the permission logic fix, matching the one above.
    can_delete = False
    if comment.author == request.user:
        can_delete = True
    elif requesting_user_role == 'owner':
        can_delete = True
    elif requesting_user_role == 'admin' and comment_author_role not in ['owner', 'admin']:
        can_delete = True

    if not can_delete:
        return HttpResponseForbidden("You do not have permission to delete this comment.")

    comment.delete()
    
    # This HX-Trigger tells the frontend to refresh the comment list
    response = HttpResponse(status=200)
    response['HX-Trigger'] = 'refresh-lists'
    return response

@login_required
def manage_collaborators(request, project_id):
    """Renders the main manage collaborators page."""
    project = get_object_or_404(Project, id=project_id)
    context = _get_manage_team_context(request, project)

    if context['role'] is None:
        return HttpResponseForbidden("You are not a member of this project.")
        
    return render(request, 'projects/manage_collaborators.html', context)

@login_required
def get_remove_user_modal(request, membership_id):
    """Renders the confirmation modal for removing a user."""
    membership = get_object_or_404(ProjectMembership, id=membership_id)
    return render(request, 'projects/partials/remove_collaborator_modal.html', {'membership': membership})

@login_required
def get_ban_user_modal(request, membership_id):
    """Renders the confirmation modal for banning a user."""
    membership = get_object_or_404(ProjectMembership, id=membership_id)
    return render(request, 'projects/partials/ban_user_modal.html', {'membership': membership})

@login_required
def get_unban_user_modal(request, ban_id):
    """Renders the confirmation modal for unbanning a user."""
    ban = get_object_or_404(Ban, id=ban_id)
    return render(request, 'projects/partials/unban_user_modal.html', {'ban': ban})

def get_manage_team_context(request, project):
    """
    A single, authoritative function to get all context needed
    for the manage_collaborators page and its partials.
    """
    current_user_role = get_user_role(project, request.user)
    memberships = ProjectMembership.objects.filter(project=project)
    
    banned_list = Ban.objects.filter(project=project)
    for member in memberships:
        member.is_editable = (current_user_role == 'owner') or (current_user_role == 'admin' and member.role in ['editor', 'viewer'])

        if current_user_role == 'owner':
            member.permissible_roles = list(ProjectMembership.Role.choices)
        else:
            member.permissible_roles = [(v, n) for v, n in ProjectMembership.Role.choices if v != 'admin']

    for ban in banned_list:
            # ... (can_unban calculation) ...
            ban.can_unban = (current_user_role == 'owner') or (current_user_role == 'admin' and ban.role_at_ban != 'admin')
                
    involved_user_ids = [project.owner.id] + [m.user.id for m in memberships]
    potential_collaborators = User.objects.exclude(id__in=involved_user_ids)
    
    return {
        'project': project,
        'memberships': memberships,
        'potential_collaborators': potential_collaborators,
        'banned_list': banned_list,
        'role': current_user_role,
    }
    
@require_POST
@login_required
def ban_user(request, membership_id):
    membership = get_object_or_404(ProjectMembership, id=membership_id)
    project = membership.project
    requesting_user_role = get_user_role(project, request.user)
    
    if not (requesting_user_role == 'owner' or (requesting_user_role == 'admin' and membership.role != 'admin')):
        return HttpResponseForbidden("You do not have permission to ban this user.")

    Ban.objects.create(
        project=project,
        user=membership.user,
        banned_by=request.user,
        role=membership.role,
    )
    
    user_banned = membership.user.username
    membership.delete()
    messages.error(request, f"{user_banned} has been BANNED from the project.")

    context = _get_manage_team_context(request, project)
    return render(request, 'projects/partials/_manage_team_content.html', context)

@require_POST
@login_required
def unban_user(request, ban_id):
    ban = get_object_or_404(Ban, id=ban_id)
    project = ban.project
    requesting_user_role = get_user_role(project, request.user)

    # --- FIX: Re-implement correct permission check using the stored role ---
    if not (requesting_user_role == 'owner' or (requesting_user_role == 'admin' and ban.role != 'admin')):
         return HttpResponseForbidden("You do not have permission to perform this action.")

    user_unbanned = ban.user.username
    ban.delete()
    messages.success(request, f"User {user_unbanned} has been unbanned.")

    context = _get_manage_team_context(request, project)
    return render(request, 'projects/partials/_manage_team_content.html', context)

@login_required
def get_unban_user_modal(request, ban_id):
    """
    This view's only purpose is to fetch the context for
    and render the unban confirmation modal.
    """
    ban = get_object_or_404(Ban, id=ban_id)
    context = {'ban': ban}
    return render(request, 'projects/partials/unban_user_modal.html', context)

@require_POST
@login_required
def add_collaborator(request, project_id, user_id):
    project = get_object_or_404(Project, id=project_id)
    user_to_add = get_object_or_404(User, id=user_id)
    requesting_user_role = get_user_role(project, request.user)

    if requesting_user_role not in ['owner', 'admin']:
        return HttpResponseForbidden("You do not have permission to add collaborators.")

    role = request.POST.get('role', 'viewer')
    ProjectMembership.objects.create(project=project, user=user_to_add, role=role)
    messages.success(request, f"{user_to_add.username} was added as a(n) {role}.")
    
    context = _get_manage_team_context(request, project)
    return render(request, 'projects/partials/_manage_team_content.html', context)

@require_POST
@login_required
def remove_membership(request, membership_id):
    membership = get_object_or_404(ProjectMembership, id=membership_id)
    project = membership.project
    requesting_user_role = get_user_role(project, request.user)

    if not (requesting_user_role == 'owner' or (requesting_user_role == 'admin' and membership.role != 'admin')):
        return HttpResponseForbidden("You do not have permission to remove this user.")

    user_removed = membership.user.username
    project = membership.project
    membership.delete()
    messages.info(request, f"{user_removed} was removed from the project.")

    context = _get_manage_team_context(request, project)
    return render(request, 'projects/partials/_manage_team_content.html', context)

@require_POST
@login_required
def change_role(request, membership_id):
    membership = get_object_or_404(ProjectMembership, id=membership_id)
    project = membership.project
    requesting_user_role = get_user_role(project, request.user)
    
    if not (requesting_user_role == 'owner' or (requesting_user_role == 'admin' and membership.role != 'admin')):
        return HttpResponseForbidden("...")

    new_role = request.POST.get('role')
    membership.role = new_role
    membership.save()
    messages.success(request, f"{membership.user.username}'s role was updated to {new_role}.")

    context = _get_manage_team_context(request, membership.project)
    return render(request, 'projects/partials/_manage_team_content.html', context)

@login_required
def remove_collaborator(request, project_id, user_id):
    project = Project.objects.get(pk=project_id)
    user_to_remove = User.objects.get(pk=user_id)

    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to perform this action.")

    if request.method == 'POST':
        project.collaborators.remove(user_to_remove)

    potential_collaborators = User.objects.exclude(pk=project.owner.pk).exclude(pk__in=project.collaborators.all())
    context = {'project': project, 'potential_collaborators': potential_collaborators}
    return render(request, 'projects/partials/collaborator_lists.html', context)

@login_required
def cancel_access_request(request, request_id):
    access_request = AccessRequest.objects.get(pk=request_id)
    project = access_request.project 
    
    if access_request.user != request.user:
        return HttpResponseForbidden("You cannot cancel this request.")

    if request.method == 'POST':
        access_request.delete()

    return render(request, 'projects/partials/request_access_button.html', {'project': project, 'existing_request': None})

@login_required
def add_file(request, project_id):
    project = Project.objects.get(pk=project_id)
    role = get_user_role(project, request.user)

    if role not in ['owner', 'admin', 'editor']:
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    if request.method == 'POST':
        # Dropzone sends files in 'request.FILES'. We loop through them.
        for f in request.FILES.getlist('file'):
            ProjectFile.objects.create(
                project=project,
                uploaded_by=request.user,
                file=f,
                description=f.name # Default description to the filename
            )
        # Return a success JSON response for Dropzone
        return JsonResponse({'status': 'success'})

    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def view_file(request, file_id):
    file_instance = ProjectFile.objects.get(pk=file_id)
    project = file_instance.project

    if project.owner != request.user and request.user not in project.collaborators.all():
        return HttpResponseForbidden("You do not have permission to view this file.")

    chart_html = None
    data_html = None 
    error_message = None

    try:
        file_path = file_instance.file.path
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            
            data_html = df.head().to_html(classes='table table-striped table-bordered', index=False)

            if len(df.columns) >= 2:
                fig = px.scatter(df, x=df.columns[0], y=df.columns[1], title=f"Data from {file_instance.file.name}")
                chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
            else:
                error_message = "Cannot generate a 2D chart: The CSV file has fewer than two columns."

    except Exception as e:
        error_message = f"Could not process file: {e}"
        messages.error(request, error_message)

    context = {
        'file': file_instance,
        'project': project,
        'chart_html': chart_html,
        'data_html': data_html,
        'error_message': error_message
    }
    return render(request, 'projects/file_viewer.html', context)

@login_required
def file_list(request, project_id):
    project = Project.objects.get(pk=project_id)
    role = get_user_role(project, request.user)

    if role is None and not project.is_public:
        return render(request, '403.html', {'project': project}, status=403)

    files_queryset = project.files.all().order_by('-uploaded_at')
    paginator = Paginator(files_queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'project': project,
        'files_page': page_obj,
        'role': role,
    }
    return render(request, 'projects/file_list.html', context)

@login_required
def delete_file(request, file_id):
    file_instance = ProjectFile.objects.get(pk=file_id)
    project = file_instance.project
    role = get_user_role(project, request.user)

    # Authorization check
    if not (file_instance.uploaded_by == request.user or role in ['owner', 'admin']):
        return HttpResponseForbidden()

    if request.method == 'POST':
        file_instance.file.delete() # Delete the actual file from storage
        file_instance.delete()      # Delete the database record
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('file-list', kwargs={'project_id': project.id})
        return response
    
    context = {'file': file_instance}
    return render(request, 'projects/partials/delete_file_modal.html', context)

@login_required
def request_inbox(request, project_id):
    project = Project.objects.get(pk=project_id)
    
    if not project.is_public and not request.user.is_authenticated:
        return HttpResponseForbidden() # Or an empty response
    role = get_user_role(project, request.user)

    # This component is only for owners and admins
    if role not in ['owner', 'admin']:
        return HttpResponseForbidden()

    # Sorting Logic
    valid_sorts = {
        '-requested_at': 'Newest First',
        'requested_at': 'Oldest First',
        'user__username': 'Username (A-Z)',
        '-user__username': 'Username (Z-A)',
    }
    sort_by = request.GET.get('sort', '-requested_at')
    if sort_by not in valid_sorts:
        sort_by = '-requested_at'

    # Get all PENDING requests and apply sorting
    requests_queryset = AccessRequest.objects.filter(project=project, status='pending').order_by(sort_by)

    # Pagination Logic (5 per page)
    paginator = Paginator(requests_queryset, 5)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'project': project,
        'requests_page': page_obj,
        'current_sort': sort_by,
        'current_sort_name': valid_sorts.get(sort_by),
        'valid_sorts': valid_sorts,
    }
    return render(request, 'projects/partials/request_inbox.html', context)

@login_required
def request_access(request, project_id):
    project = Project.objects.get(pk=project_id)

    if request.method == 'POST':
        access_request, created = AccessRequest.objects.get_or_create(
            project=project,
            user=request.user
        )

        if not created and access_request.status != 'pending':
            access_request.status = 'pending'
            access_request.save()

        if request.htmx:
            return render(request, 'projects/partials/request_access_button.html', {'project': project, 'existing_request': access_request})

        messages.success(request, 'Your request for access has been sent.')
        return redirect('project-detail', project_id=project.id)

    return redirect('project-detail', project_id=project.id)

@login_required
def approve_request(request, request_id):
    access_request = AccessRequest.objects.get(pk=request_id)
    project = access_request.project
    role = get_user_role(project, request.user)

    if role not in ['owner', 'admin']:
        return HttpResponseForbidden()

    if request.method == 'POST':
        ProjectMembership.objects.get_or_create(project=project, user=access_request.user, defaults={'role': 'editor'})
        access_request.status = 'approved'
        access_request.save()

    response = HttpResponse(status=204) # 204 No Content
    response['HX-Trigger'] = 'refresh-inbox'
    return response

@login_required
def deny_request(request, request_id):
    access_request = AccessRequest.objects.get(pk=request_id)
    project = access_request.project
    role = get_user_role(project, request.user)

    if role not in ['owner', 'admin']:
        return HttpResponseForbidden()

    if request.method == 'POST':
        access_request.status = 'denied'
        access_request.save()

    response = HttpResponse(status=204) # 204 No Content
    response['HX-Trigger'] = 'refresh-inbox'
    return response

@login_required
def mark_project_read(request, project_id):
    project = Project.objects.get(pk=project_id)
    if request.method == 'POST': 
        tasks_to_mark = project.tasks.exclude(read_by=request.user)
        for task in tasks_to_mark:
            task.read_by.add(request.user)

        comments_to_mark = project.comments.exclude(read_by=request.user)
        for comment in comments_to_mark:
            comment.read_by.add(request.user)
            
        files_to_mark = project.files.exclude(read_by=request.user)
        for file in files_to_mark:
            file.read_by.add(request.user)

    response = HttpResponse(status=204)
    response['HX-Trigger'] = 'refresh-lists'
    return response

@login_required
def toggle_pin_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    user = request.user

    if user in task.pinned_by.all():
        task.pinned_by.remove(user)
    else:
        task.pinned_by.add(user)

    # --- FIX: Return an empty response that triggers a list refresh ---
    response = HttpResponse(status=204) # 204 No Content
    response['HX-Trigger'] = 'refresh-lists'
    return response

@login_required
def dismiss_assignment(request, assignment_id):
    assignment = get_object_or_404(TaskAssignment, pk=assignment_id)
    if assignment.assignee == request.user and request.method == 'POST':
        assignment.delete()

    return dashboard_assignments(request)

@login_required
def dashboard_pinned_tasks(request):
    user = request.user
    pinned_tasks = Task.objects.filter(pinned_by=user)
    return render(request, 'projects/partials/dashboard_pinned_tasks.html', {'pinned_tasks': pinned_tasks, 'user': user})

@login_required
def dashboard_assignments(request):
    user = request.user
    assignments_for_me = TaskAssignment.objects.filter(assignee=user)
    return render(request, 'projects/partials/dashboard_assignments.html', {'assignments_for_me': assignments_for_me, 'user': user})

@login_required
def leave_project(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    
    # The owner cannot leave, they must delete the project
    if project.owner == request.user:
        return HttpResponseForbidden("The project owner cannot leave the project.")

    if request.method == 'POST':
        # Find and delete the user's membership
        membership = get_object_or_404(ProjectMembership, project=project, user=request.user)
        membership.delete()
        ProjectLog.objects.create(
            project=project,
            user=request.user,
            log_message=f"{request.user.username} has left the project."
        )
        prune_logs(project.id)
        messages.success(request, f"You have successfully left the project '{project.title}'.")
        
        # For HTMX, send a header to redirect the user away from the page
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('project-list')
        return response

    # On GET request, return the modal content
    return render(request, 'projects/partials/leave_project_modal.html', {'project': project})

@login_required
def report_comment(request, comment_id):
    comment = get_object_or_404(Comment, pk=comment_id)
    project = comment.project

    # Permission checks
    if comment.author == request.user:
        return HttpResponse("You cannot report your own comment.", status=403)
    if comment.author == project.owner:
        return HttpResponse("You cannot report the project owner.", status=403)

    if request.method == 'POST':
        # Check if this user has already reported this comment
        existing_report = Report.objects.filter(reported_comment=comment, reporter=request.user).first()
        if existing_report:
            # Re-open the existing report if it was dismissed
            existing_report.status = Report.Status.OPEN
            existing_report.reason = request.POST.get('reason', '')
            existing_report.reported_at = timezone.now()
            existing_report.save()
        else:
            # Create a new report
            Report.objects.create(
                reported_comment=comment,
                reporter=request.user,
                reported_user=comment.author,
                reason=request.POST.get('reason', '')
            )
        
        prune_reports(project.id)
        return HttpResponse('<div class="modal-body"><p class="text-success">Thank you. Your report has been submitted.</p></div>')

    # On GET, render the modal content
    context = {'comment': comment}
    return render(request, 'projects/partials/report_comment_modal.html', context)

@login_required
def project_inbox(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    role = get_user_role(project, request.user)

    # Any member of the project can view the inbox page.
    if role is None:
        return HttpResponseForbidden("You do not have permission to view this page.")

    # Fetch reports and logs
    reports = Report.objects.filter(reported_comment__project=project)
    logs = ProjectLog.objects.filter(project=project)

    context = {
        'project': project,
        'role': role,
        'reports': reports,
        'logs': logs,
    }
    return render(request, 'projects/inbox.html', context)

@login_required
def inbox_preview(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    role = get_user_role(project, request.user)

    if role is None:
        return HttpResponseForbidden()

    # Fetch the 3 most recent reports and logs for the preview
    reports = Report.objects.filter(reported_comment__project=project)[:3]
    logs = ProjectLog.objects.filter(project=project)[:3]

    context = {
        'project': project,
        'role': role,
        'reports': reports,
        'logs': logs,
    }
    return render(request, 'projects/partials/inbox_preview_modal.html', context)

def prune_reports(project_id):
    """Keeps the number of reports for a project at or below 25."""
    report_limit = 25
    report_count = Report.objects.filter(reported_comment__project_id=project_id).count()
    if report_count > report_limit:
        oldest_reports = Report.objects.filter(reported_comment__project_id=project_id).order_by('reported_at')[:report_count - report_limit]
        for report in oldest_reports:
            report.delete()

def prune_logs(project_id):
    """Keeps the number of logs for a project at or below 50."""
    log_limit = 50
    log_count = ProjectLog.objects.filter(project_id=project_id).count()
    if log_count > log_limit:
        oldest_logs = ProjectLog.objects.filter(project_id=project_id).order_by('created_at')[:log_count - log_limit]
        for log in oldest_logs:
            log.delete()
            
@login_required
def kick_user(request, membership_id):
    membership = get_object_or_404(ProjectMembership, pk=membership_id)
    project = membership.project
    kicker_role = get_user_role(project, request.user)

    # --- Permission Checks ---
    if kicker_role not in ['owner', 'admin']:
        return HttpResponseForbidden("You do not have permission to perform this action.")
    if membership.role == 'owner':
        return HttpResponseForbidden("You cannot kick the project owner.")
    if kicker_role == 'admin' and membership.role == 'admin':
        return HttpResponseForbidden("Admins cannot kick other admins.")

    if request.method == 'POST':
        log_message = f"{membership.user.username} was kicked from the project by {request.user.username}."
        membership.delete()
        ProjectLog.objects.create(project=project, user=request.user, log_message=log_message)
        prune_logs(project.id)
        
        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'refresh-lists' # Refresh the comment list
        return response

    return render(request, 'projects/partials/kick_user_modal.html', {'membership': membership})

@login_required
def kick_and_ban_user(request, membership_id):
    membership = get_object_or_404(ProjectMembership, pk=membership_id)
    project = membership.project
    kicker_role = get_user_role(project, request.user)

    # --- Permission Checks ---
    if kicker_role not in ['owner', 'admin']:
        return HttpResponseForbidden("You do not have permission to perform this action.")
    if membership.role == 'owner':
        return HttpResponseForbidden("You cannot kick the project owner.")
    if kicker_role == 'admin' and membership.role == 'admin':
        return HttpResponseForbidden("Admins cannot kick other admins.")

    if request.method == 'POST':
        log_message = f"{membership.user.username} was kicked and banned from the project by {request.user.username}."
        
        # Create the ban record BEFORE deleting the membership
        Ban.objects.get_or_create(
            project=project, user=membership.user,
            defaults={'banned_by': request.user, 'role_at_ban': membership.role}
        )
        membership.delete() # Then delete the membership
        
        ProjectLog.objects.create(project=project, user=request.user, log_message=log_message)
        prune_logs(project.id)

        response = HttpResponse(status=204)
        response['HX-Trigger'] = 'refresh-lists'
        return response

    return render(request, 'projects/partials/kick_and_ban_user_modal.html', {'membership': membership})

def get_comment_context(request, comment_id):
    """
    A helper function to gather all context and permissions for a single comment.
    """
    comment = get_object_or_404(Comment, id=comment_id)
    viewer_role = get_user_role(comment.project, request.user)
    is_self = (comment.author == request.user)
    commenter_role = get_user_role(comment.project, comment.author)

    # --- START: FIX for delete permissions ---
    can_be_deleted = False
    if is_self:
        can_be_deleted = True
    elif viewer_role == 'owner':
        can_be_deleted = True
    elif viewer_role == 'admin' and commenter_role not in ['owner', 'admin']:
        can_be_deleted = True
    comment.can_be_deleted = can_be_deleted
    # --- END: FIX ---

    # Reporting logic (remains the same)
    comment.can_be_reported = False
    if not is_self:
        if viewer_role in ['editor', 'viewer']:
            comment.can_be_reported = True
        elif viewer_role == 'admin' and commenter_role in ['owner', 'admin']:
            # This seems like an old rule, but I'll leave it. It means admins can report other admins/owners.
            comment.can_be_reported = True

    # Moderation logic (remains the same)
    comment.can_be_moderated = False
    if not is_self and commenter_role != 'owner':
        if viewer_role == 'owner' or (viewer_role == 'admin' and commenter_role in ['editor', 'viewer']):
            comment.can_be_moderated = True
            comment.membership = ProjectMembership.objects.filter(project=comment.project, user=comment.author).first()

    return {'comment': comment, 'project': comment.project, 'role': viewer_role, 'user': request.user}

@login_required
def get_comment_main_menu(request, comment_id):
    context = get_comment_context(request, comment_id)
    return render(request, 'projects/partials/_comment_main_menu.html', context)

@login_required
def get_comment_moderation_menu(request, comment_id):
    context = get_comment_context(request, comment_id)
    return render(request, 'projects/partials/_comment_moderation_menu.html', context)