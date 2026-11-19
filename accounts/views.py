import random
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, update_session_auth_hash
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from accounts.models import UserProfile, Team, HackathonRegistration, Notification, TeamChatMessage
from django.db.models import Q
from django.http import JsonResponse


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            profile, created = UserProfile.objects.get_or_create(
                user=user
            )

            login(request, user)
            role = profile.role

            if role == 'Student':
                return redirect('studenthome')
            elif role == 'Organizer':
                return redirect('orihome')
            elif role == 'Judge':
                return redirect('judgehome')
            elif role == 'Admin':
                return redirect('admin_view')

        else:
            return render(request, 'login.html', {
                'error': 'Invalid email or password.'
            })

    return render(request, 'login.html')


def signup_view(request):
    if request.method == 'POST':
        fullname = request.POST.get('fullname')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Check if user already exists
        if User.objects.filter(username=email).exists():
            return render(request, 'signup.html', {'error': 'An account with this email already exists.'})
            
        try:
            # Generate random 6-digit OTP
            otp = f"{random.randint(100000, 999999)}"
            
            # Store in session
            request.session['pending_signup'] = {
                'fullname': fullname,
                'email': email,
                'password': password,
                'otp': otp
            }
            
            # Send verification mail
            subject = "Your HackNest Account Verification OTP"
            message = f"Welcome to HackNest! Your 6-digit verification code is: {otp}\n\nEnter this code on the verification screen to complete your registration."
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
            
            return redirect('otp_verify')
        except Exception as e:
            return render(request, 'signup.html', {'error': f'Registration failed: {str(e)}'})
            
    return render(request, 'signup.html')

def otp_verify_view(request):
    pending = request.session.get('pending_signup')
    if not pending:
        return redirect('signup')
        
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        
        if entered_otp == pending['otp']:
            # Create user
            email = pending['email']
            password = pending['password']
            fullname = pending['fullname']
            
            # Check if user already exists (double safety check)
            if not User.objects.filter(username=email).exists():
                user = User.objects.create_user(username=email, email=email, password=password)
                if fullname:
                    parts = fullname.split(' ', 1)
                    user.first_name = parts[0]
                    if len(parts) > 1:
                        user.last_name = parts[1]
                    user.save()
                # Create profile
                UserProfile.objects.create(user=user)
            
            # Clear pending session data
            del request.session['pending_signup']
            return redirect('login')
        else:
            return render(request, 'otp_verify.html', {'error': 'Invalid verification code. Please try again.'})
            
    return render(request, 'otp_verify.html')


def orilogin_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            profile, created = UserProfile.objects.get_or_create(
                user=user
            )

            login(request, user)
            role = profile.role

            if role == 'Student':
                return redirect('studenthome')
            elif role == 'Organizer':
                return redirect('orihome')
            elif role == 'Judge':
                return redirect('judgehome')
            elif role == 'Admin':
                return redirect('admin_view')

        else:
            return render(request, 'orilogin.html', {
                'error': 'Invalid User ID or password.'
            })

    return render(request, 'orilogin.html')




from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required(login_url='orilogin')
def orihome_view(request):

    if not hasattr(request.user, 'profile'):
        return redirect('orilogin')

    if request.user.profile.role != 'Organizer':
        return redirect('studenthome')

    return render(request, 'orihome.html')


def studenthome_view(request):
    
    if not request.user.is_authenticated:
        return redirect('login')

    if not hasattr(request.user, 'profile'):
        return redirect('login')

    if request.user.profile.role != 'Student':
        return redirect('home')
    
    
    profile = None
    teams = []
    registered_hackathons = []
    notifications = []
    error = None
    success = None

    if request.user.is_authenticated:
        student_id = f"HN-2026-{1000 + request.user.pk}"
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        
        # Handle POST requests
        if request.method == 'POST':
            action = request.POST.get('action')
            
            if action == 'register_hackathon':
                hackathon = request.POST.get('hackathon', '').strip()
                if not hackathon:
                    error = "Hackathon name is required."
                else:
                    reg, created_reg = HackathonRegistration.objects.get_or_create(
                        user=request.user,
                        hackathon=hackathon
                    )
                    if created_reg:
                        success = f"Successfully registered for '{hackathon}'!"
                        # Create notification
                        Notification.objects.create(
                            user=request.user,
                            message=f"Successfully registered for the '{hackathon}' hackathon!",
                            notification_type='INFO'
                        )
                        # Send email
                        try:
                            send_mail(
                                subject="HackNest - Hackathon Registration Successful",
                                message=f"Hi {request.user.first_name or request.user.username},\n\nYou have successfully registered for the '{hackathon}' hackathon on HackNest.\n\nBest of luck,\nThe HackNest Team",
                                from_email=settings.DEFAULT_FROM_EMAIL,
                                recipient_list=[request.user.email],
                                fail_silently=True
                            )
                        except Exception as e:
                            print("Email error:", e)
                    else:
                        error = f"You are already registered for '{hackathon}'."

            elif action == 'create_team':
                team_name = request.POST.get('team_name', '').strip()
                hackathon = request.POST.get('hackathon', '').strip()
                if not team_name or not hackathon:
                    error = "Team name and Hackathon selection are required."
                elif not HackathonRegistration.objects.filter(user=request.user, hackathon=hackathon).exists():
                    error = f"You must register for the '{hackathon}' hackathon first before creating a team."
                elif Team.objects.filter(name=team_name).exists():
                    error = f"Team name '{team_name}' is already taken."
                else:
                    team = Team.objects.create(
                        name=team_name,
                        hackathon=hackathon,
                        creator=request.user
                    )
                    team.members.add(request.user)
                    success = f"Team '{team_name}' created successfully! Share this code with members: {team.code}"
                    
                    # Create notification
                    Notification.objects.create(
                        user=request.user,
                        message=f"Successfully created team '{team_name}' for '{hackathon}'! Invite Code: {team.code}",
                        notification_type='INFO'
                    )

            
            elif action == 'join_team':
                team_code = request.POST.get('team_code', '').strip().upper()
                if not team_code:
                    error = "Invite code is required."
                else:
                    try:
                        team = Team.objects.get(code=team_code)
                        if not HackathonRegistration.objects.filter(user=request.user, hackathon=team.hackathon).exists():
                            error = f"You must register for the '{team.hackathon}' hackathon first before joining this team."
                        elif request.user in team.members.all():
                            error = "You are already a member of this team."
                        elif team.members.count() >= 4:
                            error = "This team is already full (maximum 4 members)."
                        elif Notification.objects.filter(
                            user=team.creator,
                            notification_type='REQUEST',
                            request_user=request.user,
                            team=team,
                            status='PENDING'
                        ).exists():
                            error = f"You have already requested to join team '{team.name}'. Please wait for the host to approve."
                        else:
                            # Create Join Request notification for the host
                            Notification.objects.create(
                                user=team.creator,
                                message=f"{request.user.email} has requested to join your team '{team.name}' for '{team.hackathon}'.",
                                notification_type='REQUEST',
                                request_user=request.user,
                                team=team,
                                status='PENDING'
                            )
                            # Create Info notification for the requester
                            Notification.objects.create(
                                user=request.user,
                                message=f"Request to join team '{team.name}' sent to the host.",
                                notification_type='INFO'
                            )
                            success = f"Your request to join team '{team.name}' has been successfully sent to the host!"
                    except Team.DoesNotExist:
                        error = "Invalid invite code. Please check and try again."
            
            elif action == 'respond_request':
                notification_id = request.POST.get('notification_id')
                response_type = request.POST.get('response')
                
                try:
                    notification = Notification.objects.get(id=notification_id, user=request.user)
                    if notification.notification_type == 'REQUEST' and notification.status == 'PENDING':
                        team = notification.team
                        request_user = notification.request_user
                        
                        if response_type == 'accept':
                            if team.members.count() >= 4:
                                error = "Cannot accept member. Team is already full (maximum 4 members)."
                            else:
                                team.members.add(request_user)
                                notification.status = 'ACCEPTED'
                                notification.message = f"You accepted {request_user.email} into your team '{team.name}'."
                                notification.is_read = True
                                notification.save()
                                
                                Notification.objects.create(
                                    user=request_user,
                                    message=f"Your request to join team '{team.name}' has been ACCEPTED by the host!",
                                    notification_type='INFO'
                                )
                                success = f"Successfully accepted {request_user.email} into your team!"
                                

                                    
                        elif response_type == 'reject':
                            notification.status = 'REJECTED'
                            notification.message = f"You rejected {request_user.email}'s request to join '{team.name}'."
                            notification.is_read = True
                            notification.save()
                            
                            Notification.objects.create(
                                user=request_user,
                                message=f"Your request to join team '{team.name}' has been REJECTED by the host.",
                                notification_type='INFO'
                            )
                            success = f"You have rejected {request_user.email}'s join request."
                            

                except Notification.DoesNotExist:
                    error = "Notification not found."

            elif action == 'clear_notifications':
                Notification.objects.filter(user=request.user).update(is_read=True)
                success = "Notifications cleared."

            elif action == 'mark_read':
                notification_id = request.POST.get('notification_id')
                try:
                    notification = Notification.objects.get(id=notification_id, user=request.user)
                    notification.is_read = True
                    notification.save()
                    success = "Notification marked as read."
                except Notification.DoesNotExist:
                    error = "Notification not found."

            elif action == 'delete_team':
                team_id = request.POST.get('team_id')
                try:
                    team = Team.objects.get(id=team_id)
                    if team.creator == request.user:
                        team_name = team.name
                        # Send email/notifications to all members before deleting
                        for member in team.members.all():
                            if member != request.user:
                                Notification.objects.create(
                                    user=member,
                                    message=f"The team '{team_name}' has been permanently disbanded by the host.",
                                    notification_type='INFO'
                                )

                        team.delete()
                        success = f"Team '{team_name}' has been permanently deleted, and the name is now freed up!"
                    else:
                        error = "Only the team creator can delete the team."
                except Team.DoesNotExist:
                    error = "Team not found."

            elif action == 'remove_member':
                team_id = request.POST.get('team_id')
                member_id = request.POST.get('member_id')
                try:
                    team = Team.objects.get(id=team_id)
                    if team.creator == request.user:
                        try:
                            member_to_remove = User.objects.get(id=member_id)
                            if member_to_remove == team.creator:
                                error = "You cannot remove yourself (the creator) from the team."
                            elif member_to_remove in team.members.all():
                                team.members.remove(member_to_remove)
                                Notification.objects.create(
                                    user=member_to_remove,
                                    message=f"You have been removed from the team '{team.name}' by the host.",
                                    notification_type='INFO'
                                )

                                success = f"Successfully removed {member_to_remove.email} from the team."
                            else:
                                error = "This user is not a member of your team."
                        except User.DoesNotExist:
                            error = "User not found."
                    else:
                        error = "Only the team creator can remove members."
                except Team.DoesNotExist:
                    error = "Team not found."

            elif action == 'leave_team':
                team_id = request.POST.get('team_id')
                try:
                    team = Team.objects.get(id=team_id)
                    if request.user in team.members.all():
                        if request.user == team.creator:
                            error = "As the creator, you must delete the team to leave it."
                        else:
                            team.members.remove(request.user)
                            # Notify the creator that a member left
                            Notification.objects.create(
                                user=team.creator,
                                message=f"{request.user.email} has left your team '{team.name}'.",
                                notification_type='INFO'
                            )
                            success = "You have successfully left the team."
                    else:
                        error = "You are not a member of this team."
                except Team.DoesNotExist:
                    error = "Team not found."
        
        
        # Fetch current user's teams, registered hackathons, and notifications
        teams = request.user.joined_teams.all()
        registered_hackathons = list(request.user.registrations.values_list('hackathon', flat=True))
        notifications = request.user.notifications.all().order_by('-created_at')
        unread_count = notifications.filter(is_read=False).count()
    else:
        student_id = "HN-2026-9999"
        unread_count = 0
        
    return render(request, 'studenthome.html', {
        'student_id': student_id,
        'profile': profile,
        'teams': teams,
        'registered_hackathons': registered_hackathons,
        'notifications': notifications,
        'unread_count': unread_count,
        'error': error,
        'success': success
    })

def profile_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    student_id = f"HN-2026-{1000 + request.user.pk}"
    
    success_msg = None
    error_msg = None
    
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            
            request.user.first_name = first_name or ''
            request.user.last_name = last_name or ''
            request.user.save()
                
            profile.college = request.POST.get('college')
            profile.department = request.POST.get('department')
            profile.year_of_study = request.POST.get('year_of_study')
            profile.about_me = request.POST.get('about_me')
            profile.skills = request.POST.get('skills')
            
            if 'remove_photo' in request.POST:
                if profile.profile_photo:
                    profile.profile_photo.delete()
                    profile.profile_photo = None
                success_msg = "Profile photo removed successfully!"
            else:
                if 'profile_photo' in request.FILES:
                    profile.profile_photo = request.FILES['profile_photo']
                success_msg = "Profile updated successfully!"
                
            profile.save()
            
        elif 'change_email' in request.POST:
            new_email = request.POST.get('new_email')
            email_password = request.POST.get('email_password')
            
            if not request.user.check_password(email_password):
                error_msg = "Incorrect password. Email update failed."
            elif User.objects.filter(username=new_email).exclude(pk=request.user.pk).exists():
                error_msg = "An account with this email already exists."
            else:
                request.user.email = new_email
                request.user.username = new_email
                request.user.save()
                success_msg = "Email address updated successfully!"
                
        elif 'change_password' in request.POST:
            current_pwd = request.POST.get('current_password')
            new_pwd = request.POST.get('new_password')
            confirm_pwd = request.POST.get('confirm_password')
            
            if not request.user.check_password(current_pwd):
                error_msg = "Current password is incorrect."
            elif new_pwd != confirm_pwd:
                error_msg = "New passwords do not match."
            else:
                request.user.set_password(new_pwd)
                request.user.save()
                update_session_auth_hash(request, request.user)
                success_msg = "Password changed successfully!"
                
    skills_list = [s.strip() for s in profile.skills.split(',')] if profile.skills else []
    
    return render(request, 'profile.html', {
        'profile': profile,
        'student_id': student_id,
        'skills_list': skills_list,
        'success': success_msg,
        'error': error_msg
    })


def get_chat_messages(request, team_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    
    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        return JsonResponse({'error': 'Team not found'}, status=404)
        
    if request.user not in team.members.all() and team.creator != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)
        
    messages = team.messages.all().order_by('created_at')
    data = []
    for msg in messages:
        sender_name = msg.sender.first_name or msg.sender.username
        data.append({
            'id': msg.id,
            'sender': sender_name,
            'is_self': msg.sender == request.user,
            'message': msg.message,
            'created_at': msg.created_at.strftime('%H:%M'),
        })
    return JsonResponse({'messages': data})


def send_chat_message(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
        
    if request.method == 'POST':
        team_id = request.POST.get('team_id')
        message_text = request.POST.get('message', '').strip()
        
        if not message_text or not team_id:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
            
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            return JsonResponse({'error': 'Team not found'}, status=404)
            
        if request.user not in team.members.all() and team.creator != request.user:
            return JsonResponse({'error': 'Forbidden'}, status=403)
            
        msg = TeamChatMessage.objects.create(
            team=team,
            sender=request.user,
            message=message_text
        )
        return JsonResponse({
            'success': True,
            'message': {
                'id': msg.id,
                'sender': msg.sender.first_name or msg.sender.username,
                'is_self': True,
                'message': msg.message,
                'created_at': msg.created_at.strftime('%H:%M')
            }
        })
    return JsonResponse({'error': 'Invalid request method'}, status=405)


def admin_view(request):
    
    if not request.user.is_authenticated:
        return redirect('login')

    if not hasattr(request.user, 'profile'):
        return redirect('login')

    if request.user.profile.role != 'Admin':
        return redirect('home')
    if request.method == 'POST':
        action = request.POST.get('action')
        user_id_to_delete = request.POST.get('delete_user_id')
        
        if action == 'delete_user' or user_id_to_delete:
            target_id = user_id_to_delete or request.POST.get('delete_user_id')
            if target_id:
                try:
                    user_to_delete = User.objects.get(pk=target_id)
                    if user_to_delete != request.user:
                        user_to_delete.delete()
                except User.DoesNotExist:
                    pass
                    
        elif action == 'toggle_block':
            user_id = request.POST.get('user_id')
            if user_id:
                try:
                    user_to_toggle = User.objects.get(pk=user_id)
                    if user_to_toggle != request.user:
                        user_to_toggle.is_active = not user_to_toggle.is_active
                        user_to_toggle.save()
                except User.DoesNotExist:
                    pass
                    
        elif action == 'change_role':
            user_id = request.POST.get('user_id')
            role = request.POST.get('role')

            valid_roles = dict(UserProfile.ROLE_CHOICES)

            if user_id and role in valid_roles:
                try:
                    user_to_change = User.objects.get(pk=user_id)

                    if user_to_change != request.user:
                        profile, created = UserProfile.objects.get_or_create(
                            user=user_to_change
                        )

                        profile.role = role
                        profile.save(update_fields=['role'])

                except User.DoesNotExist:
                    pass
                    
        return redirect('admin_view')

    users = User.objects.all()
    
    # Parse search queries
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(profile__college__icontains=search_query) |
            Q(profile__department__icontains=search_query) |
            Q(profile__skills__icontains=search_query)
        )
        
    # Build list containing the details of each profile (ensuring UserProfile exists)
    students_list = []
    colleges = set()
    for u in users:
        p, created = UserProfile.objects.get_or_create(user=u)
        student_id = f"HN-2026-{1000 + u.pk}"
        skills_tags = [s.strip() for s in p.skills.split(',')] if p.skills else []
        if p.college:
            colleges.add(p.college)
            
        students_list.append({
            'profile': p,
            'student_id': student_id,
            'skills_tags': skills_tags,
        })
        
    total_students = len(students_list)
    total_colleges = len(colleges)
        
    return render(request, 'admin.html', {
        'students': students_list,
        'total_students': total_students,
        'total_colleges': total_colleges,
        'search_query': search_query
    })
    
    
def judgehome_view(request):

    if not request.user.is_authenticated:
        return redirect('login')

    if not hasattr(request.user, 'profile'):
        return redirect('login')

    if request.user.profile.role != 'Judge':
        return redirect('home')

    return render(request, 'judgehome.html')
