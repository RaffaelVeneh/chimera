import pandas as pd
import plotly.express as px

from django.http import HttpResponse
from django.urls import reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

from .models import Project, Task, User
from .forms import ProjectForm, TaskForm, CommentForm, ProjectFileForm, ProjectFile

# View for the project list page
def index(request):
    projects_list = Project.objects.all()
    context = {
        'projects': projects_list,
    }
    return render(request, 'projects/index.html', context)

# View for the single project detail page
def project_detail(request, project_id):
    project = Project.objects.get(pk=project_id)
    
    if project.owner != request.user and request.user not in project.collaborators.all():
        return HttpResponseForbidden("You do not have permission to view this project.")

    tasks = project.tasks.all()
    comments = project.comments.all()
    comment_form = CommentForm()
    project_files = project.files.all()
    file_form = ProjectFileForm()
    
    context = {
        'project': project,
        'tasks': tasks,
        'comments': comments,
        'comment_form': comment_form,
        'project_files': project_files,
        'file_form': file_form,   
    }
    return render(request, 'projects/project_detail.html', context)

@login_required
def create_project(request):
    if request.method == 'POST':
        # This is for processing the submitted form data
        form = ProjectForm(request.POST)
        if form.is_valid():
            # form.save(commit=False) creates the project object but doesn't save it to the DB yet
            project = form.save(commit=False)
            # We need to manually set the owner before saving
            project.owner = request.user
            project.save()
            messages.success(request, f"Project '{project.title}' was created successfully!")
            return redirect('projects-index')
    else:
        # This is for when a user first visits the page (a GET request)
        # We just show them a blank form.
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
        # If the form is being submitted, process the data
        # We pass 'instance=project' to tell the form which existing object to update
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your project has been updated successfully!')
            return redirect('project-detail', project_id=project.id)
    else:
        # If it's a GET request, show the form pre-filled with the project's current data
        # We pass 'instance=project' here as well
        form = ProjectForm(instance=project)

    context = {
        'form': form,
        'project': project  # Pass the project object for the template
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
            # If it's an HTMX request, send back an empty response with a special
            # HX-Redirect header. This tells HTMX to do a full page refresh/redirect.
            response = HttpResponse(status=204) # 204 means "No Content"
            response['HX-Redirect'] = reverse('projects-index')
            return response
        else:
            # For non-HTMX requests, do the standard redirect
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
    form = TaskForm(request.POST)
    
    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to edit this project.")

    if form.is_valid():
        task = form.save(commit=False)
        task.project = project
        task.save()

    # After saving, fetch ALL tasks for the project again
    tasks = project.tasks.all()
    # Render just the list of tasks using a partial template
    return render(request, 'projects/partials/task_list.html', {'tasks': tasks})

@login_required
def toggle_task(request, task_id):
    task = Task.objects.get(pk=task_id)
    # Flip the boolean status
    task.is_completed = not task.is_completed
    task.save()

    # Return the updated HTML for just this one task item
    return render(request, 'projects/partials/task_item.html', {'task': task})

@login_required
def add_comment(request, project_id):
    project = Project.objects.get(pk=project_id)
    
    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to edit this project.")
    
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.project = project
            comment.author = request.user
            comment.save()

    # After saving, fetch ALL comments for the project again
    comments = project.comments.all()
    # Render just the list of comments using a partial template
    return render(request, 'projects/partials/comment_list.html', {'comments': comments})

@login_required
def manage_collaborators(request, project_id):
    project = Project.objects.get(pk=project_id)

    # Authorization: Only the project owner can access this page
    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to manage collaborators for this project.")

    # Get users who are not the owner and not already collaborators
    potential_collaborators = User.objects.exclude(pk=project.owner.pk).exclude(pk__in=project.collaborators.all())

    context = {
        'project': project,
        'potential_collaborators': potential_collaborators,
    }
    return render(request, 'projects/manage_collaborators.html', context)

@login_required
def add_collaborator(request, project_id, user_id):
    project = Project.objects.get(pk=project_id)
    user_to_add = User.objects.get(pk=user_id)

    # Authorization: Only owner can add
    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to perform this action.")

    if request.method == 'POST':
        project.collaborators.add(user_to_add)

    # After adding, re-render the lists partial
    potential_collaborators = User.objects.exclude(pk=project.owner.pk).exclude(pk__in=project.collaborators.all())
    context = {'project': project, 'potential_collaborators': potential_collaborators}
    return render(request, 'projects/partials/collaborator_lists.html', context)


@login_required
def remove_collaborator(request, project_id, user_id):
    project = Project.objects.get(pk=project_id)
    user_to_remove = User.objects.get(pk=user_id)

    # Authorization: Only owner can remove
    if project.owner != request.user:
        return HttpResponseForbidden("You are not allowed to perform this action.")

    if request.method == 'POST':
        project.collaborators.remove(user_to_remove)

    # After removing, re-render the lists partial
    potential_collaborators = User.objects.exclude(pk=project.owner.pk).exclude(pk__in=project.collaborators.all())
    context = {'project': project, 'potential_collaborators': potential_collaborators}
    return render(request, 'projects/partials/collaborator_lists.html', context)

def paper_search(request):
    # Get the search query from the URL's 'q' parameter
    query = request.GET.get('q', '')
    papers = []

    if query:
        # If a query exists, filter papers
        # Q() objects allow us to build complex queries with OR (|) logic
        papers = Paper.objects.filter(
            Q(title__icontains=query) | Q(abstract__icontains=query)
        )

    context = {
        'papers': papers,
        'query': query,
    }
    return render(request, 'knowledge_hub/paper_search.html', context)

@login_required
def add_file(request, project_id):
    project = Project.objects.get(pk=project_id)

    # Authorization check for collaborators can go here if desired
    if project.owner != request.user and request.user not in project.collaborators.all():
        return HttpResponseForbidden("You do not have permission to add files to this project.")

    if request.method == 'POST':
        # We pass request.POST for form data and request.FILES for file data
        form = ProjectFileForm(request.POST, request.FILES)
        if form.is_valid():
            file_instance = form.save(commit=False)
            file_instance.project = project
            file_instance.save()
            messages.success(request, 'File uploaded successfully!')
            return redirect('project-detail', project_id=project.id)

    # This view only processes POST requests and redirects, so a direct GET isn't needed
    # or could redirect back. For simplicity, we'll just redirect if GET.
    return redirect('project-detail', project_id=project.id)

@login_required
def view_file(request, file_id):
    file_instance = ProjectFile.objects.get(pk=file_id)
    project = file_instance.project

    # Authorization Check
    if project.owner != request.user and request.user not in project.collaborators.all():
        return HttpResponseForbidden("You do not have permission to view this file.")

    chart_html = None
    data_html = None  # To hold the HTML table of the data
    error_message = None

    try:
        file_path = file_instance.file.path
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            
            # Convert the dataframe to an HTML table to always show a preview
            data_html = df.head().to_html(classes='table table-striped table-bordered', index=False)

            # --- Smart Charting Logic ---
            if len(df.columns) >= 2:
                # If we have at least 2 columns, create a scatter plot
                fig = px.scatter(df, x=df.columns[0], y=df.columns[1], title=f"Data from {file_instance.file.name}")
                chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
            else:
                # If less than 2 columns, we can't make a scatter plot
                error_message = "Cannot generate a 2D chart: The CSV file has fewer than two columns."

    except Exception as e:
        error_message = f"Could not process file: {e}"
        messages.error(request, error_message)

    context = {
        'file': file_instance,
        'project': project,
        'chart_html': chart_html,
        'data_html': data_html, # Pass the data table to the template
        'error_message': error_message
    }
    return render(request, 'projects/file_viewer.html', context)