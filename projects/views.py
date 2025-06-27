import pandas as pd
import plotly.express as px

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
from itertools import chain
from operator import attrgetter

from .models import Project, Task, Comment, User, ProjectMembership, AccessRequest, TaskAssignment, PersonalTodo
from .forms import ProjectForm, TaskForm, CommentForm, ProjectFileForm, ProjectFile

def get_user_role(project, user):
    """Helper function to get a user's role on a specific project."""
    if not user.is_authenticated:
        return None
    
    if project.owner == user:
        return 'owner'
    try:
        membership = ProjectMembership.objects.get(project=project, user=user)
        return membership.role
    except ProjectMembership.DoesNotExist:
        return None
    
@login_required
def dashboard(request, username):
    page_user = get_object_or_404(User, username=username)
    if page_user != request.user:
        return HttpResponseForbidden("You can only view your own dashboard.")

    # Get Projects
    owned_projects = Project.objects.filter(owner=page_user)
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
    }
    return render(request, 'projects/dashboard.html', context)
    
def index(request):
    user = request.user
    active_tab = request.GET.get('tab', 'public')

    owned_projects = Project.objects.none()
    team_projects = Project.objects.none()

    if user.is_authenticated:
        # All the counting logic should be INSIDE this "if" block.

        # Get the querysets
        owned_projects = Project.objects.filter(owner=user)
        team_project_ids = ProjectMembership.objects.filter(user=user).exclude(project__owner=user).values_list('project_id', flat=True)
        team_projects = Project.objects.filter(id__in=team_project_ids)

        # Do the notification counts
        for project in owned_projects:
            project.unread_tasks_count = project.tasks.exclude(read_by=user).count()
            project.unread_comments_count = project.comments.exclude(read_by=user).count()
            project.pending_requests_count = project.access_requests.filter(status='pending').count()
            project.unread_files_count = project.files.exclude(read_by=user).count()

        for project in team_projects:
            project.unread_tasks_count = project.tasks.exclude(read_by=user).count()
            project.unread_comments_count = project.comments.exclude(read_by=user).count()
            project.unread_files_count = project.files.exclude(read_by=user).count()

    # Public projects are fetched for everyone
    public_projects = Project.objects.filter(is_public=True)

    # Filter public projects if there is a search query
    query = request.GET.get('q', '')
    if query:
        public_projects = public_projects.filter(Q(title__icontains=query) | Q(description__icontains=query))

    context = {
        'owned_projects': owned_projects,
        'team_projects': team_projects,
        'public_projects': public_projects,
        'active_tab': active_tab,
        'query': query,
    }
    return render(request, 'projects/index.html', context)

@login_required
def project_detail(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    role = get_user_role(project, request.user)

    # The authorization check is now simpler:
    # Deny access if the project is private AND the user has no role.
    if not project.is_public and role is None:
        # We will now create a dedicated page for this, as per your earlier request.
        # For now, let's keep the simple forbidden response. We'll build the page next.
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
            messages.success(request, f"Project '{project.title}' was created successfully!")
            return redirect('projects-index')
    else:
        form = ProjectForm()

    context = {
        'form': form,
    }
    return render(request, 'projects/create_project.html', context)

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
            return render(request, 'projects/partials/task_item.html', {'task': task, 'project': project, 'role': role})
        
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
            task.read_by.add(request.user)
            task.assigned_user_ids = list(task.assignments.values_list('assignee_id', flat=True))

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
            members = [task.project.owner] + list(task.project.collaborators.all())
            for member in members:
                TaskAssignment.objects.get_or_create(task=task, assignee=member, assigner=assigner)
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

def comment_list(request, project_id):
    project = Project.objects.get(pk=project_id)
    
    if not project.is_public and not request.user.is_authenticated:
        return HttpResponseForbidden() # Or an empty response
    
    role = get_user_role(project, request.user)

    if not project.is_public and role is None:
        return HttpResponseForbidden()

    # --- NEW: Sorting Logic ---
    valid_sorts = {
        '-created_at': 'Newest First',
        'created_at': 'Oldest First',
    }
    sort_by = request.GET.get('sort', '-created_at')
    if sort_by not in valid_sorts:
        sort_by = '-created_at'

    comments_queryset = project.comments.all().order_by(sort_by)

    # --- NEW: Pagination Logic (20 per page) ---
    paginator = Paginator(comments_queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Mark as read logic
    if request.user.is_authenticated:
        for comment in page_obj:
            comment.read_by.add(request.user)

    context = {
        'project': project,
        'comments_page': page_obj, # Pass the page object
        'role': role,
        'current_sort': sort_by,
        'current_sort_name': valid_sorts.get(sort_by),
        'valid_sorts': valid_sorts,
    }

    # This view now renders a new, more powerful comment list component
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


@login_required
def delete_comment(request, comment_id):
    comment = Comment.objects.get(pk=comment_id)
    project = comment.project
    role = get_user_role(project, request.user)

    # Authorization: You can delete your own comment, OR if you are an owner/admin.
    if not (comment.author == request.user or role in ['owner', 'admin']):
        return HttpResponseForbidden("You do not have permission to delete this comment.")

    if request.method == 'POST':
        comment.delete()
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('project-detail', kwargs={'project_id': project.id})
        return response
    
    context = {'comment': comment}
    return render(request, 'projects/partials/delete_comment_modal.html', context)

@login_required
def manage_collaborators(request, project_id):
    project = Project.objects.get(pk=project_id)

    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to manage collaborators for this project.")

    memberships = ProjectMembership.objects.filter(project=project)
    involved_user_ids = [project.owner.id] + [m.user.id for m in memberships]
    potential_collaborators = User.objects.exclude(pk=project.owner.pk).exclude(pk__in=project.collaborators.all())

    context = {
        'project': project,
        'memberships': memberships,
        'potential_collaborators': potential_collaborators,
    }
    return render(request, 'projects/manage_collaborators.html', context)

def render_collaborator_lists(request, project):
    """A helper function to prevent repeating code."""
    memberships = ProjectMembership.objects.filter(project=project)
    involved_user_ids = [project.owner.id] + [m.user.id for m in memberships]
    potential_collaborators = User.objects.exclude(id__in=involved_user_ids)
    context = {
        'project': project,
        'memberships': memberships,
        'potential_collaborators': potential_collaborators
    }
    return render(request, 'projects/partials/collaborator_lists.html', context)

@login_required
def add_collaborator(request, project_id, user_id):
    project = Project.objects.get(pk=project_id)
    if project.owner != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        user_to_add = User.objects.get(pk=user_id)
        role = request.POST.get('role')
        ProjectMembership.objects.create(project=project, user=user_to_add, role=role)
    return render_collaborator_lists(request, project)

@login_required
def remove_membership(request, membership_id):
    membership = ProjectMembership.objects.get(pk=membership_id)
    project = membership.project
    if project.owner != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        membership.delete()
    return render_collaborator_lists(request, project)

@login_required
def change_role(request, membership_id):
    membership = ProjectMembership.objects.get(pk=membership_id)
    project = membership.project
    if project.owner != request.user:
        return HttpResponseForbidden()
    if request.method == 'POST':
        membership.role = request.POST.get('role')
        membership.save()
    return render_collaborator_lists(request, project)

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

    return dashboard_pinned_tasks(request)

@login_required
def dismiss_assignment(request, assignment_id):
    assignment = get_object_or_404(TaskAssignment, pk=assignment_id)
    # Check that the person dismissing is the person it was assigned to
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