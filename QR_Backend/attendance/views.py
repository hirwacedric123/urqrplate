from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import  SignupForm, LoginForm, ProfileImageForm,UpdateProfileForm,IssueForm
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
import qrcode
from io import BytesIO
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse

from .models import UserProfile, Attendance

from django.conf import settings
import base64
from django.views.decorators.csrf import csrf_exempt  # For bypassing CSRF protection for QR scanners
from django.contrib.admin.views.decorators import staff_member_required 
from uuid import UUID
import uuid
import random
from django.core.mail import send_mail
from datetime import timedelta
from django.utils.crypto import get_random_string


from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated,IsAdminUser

from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.authentication import JWTAuthentication
from .serializers import SignupSerializer, LoginSerializer, OTPSerializer, AttendanceSerializer
from rest_framework.views import APIView
import datetime
from django.contrib.sessions.models import Session
from datetime import date
import json
from django.utils import timezone
from django.utils.text import slugify
import uuid
import logging
from django.contrib.auth.hashers import check_password
from rest_framework import status

from django.template.loader import get_template
from xhtml2pdf import pisa

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.contrib.staticfiles.storage import staticfiles_storage
import os
from django.db.models import Q

from django.shortcuts import get_list_or_404

logger = logging.getLogger(__name__)





def handler404(request, exception):
    return render(request, '404.html', status=404)

def handler403(request, exception):
    return render(request, '403.html', status=403)

def handler500(request):
    return render(request, '500.html', status=500)

def handler400(request, exception):
    return render(request, '400.html', status=400)

# Set OTP expiration time (e.g., 5 minutes)
OTP_EXPIRATION_TIME = datetime.timedelta(minutes=5)

@login_required
def update_profile(request):
    if request.method == 'POST':
        form = UpdateProfileForm(request.POST)
        if form.is_valid():
            # Get the logged-in user profile
            user_profile = form.save(commit=False)
            user_profile.user = request.user  # Ensure user is linked to the profile
            
            user_profile.save()

            # If email is updated, ensure the linked User model is updated too
            if 'email' in form.cleaned_data:
                request.user.email = form.cleaned_data['email']
                request.user.save()

            messages.success(request, "Your profile has been updated successfully.")
            return redirect('profile')  # Redirect to the profile page or dashboard
        else:
            messages.error(request, "There was an error updating your profile. Please try again.")
    
    else:
        # Prepopulate the form with the current user's profile
        form = UpdateProfileForm(instance=request.user.userprofile)
    
    return render(request, 'attendance/index_admin.html', {'form': form})




@login_required
@staff_member_required
def scan_page(request):
    return render(request, "attendance/scan_page.html")

@login_required
def report_issue(request):
    if request.method == 'POST':
        form = IssueForm(request.POST)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.reported_by = request.user  # Set the logged-in user as the reporter
            issue.save()
            
            # Sending email to the admin
            message = render_to_string('emails/issue_reported.html', {
                'user': request.user,
                'issue': issue,
            })

            send_mail(
                subject=f"New Issue Reported: {issue.title}",
                message="This is an HTML email, please view it in a compatible client.",  # Fallback plain text
                html_message=message,  # Rendered HTML message
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=["b.uteramaho@alustudent.com"],  
                fail_silently=False,
            )

            messages.success(request, "Your issue has been reported successfully.")
            return redirect('admin_dashboard')  # Redirect back to the dashboard
        else:
            messages.error(request, "There was an error reporting the issue. Please try again.")

    return redirect('admin_dashboard')  # Redirect if accessed via GET


@login_required
@staff_member_required
def admin_dashboard(request):
    students_data = []
    students = UserProfile.objects.filter(user__is_staff=False)
    
    # Collecting student data for attendance & payment status
    for student in students:
        today = datetime.date.today()
        attendance_today = Attendance.objects.filter(user_profile=student, date=today).exists()
        present_status = "Present" if attendance_today else "Absent"
        
        students_data.append({
            "id": student.id,
            "name": f"{student.first_name} {student.last_name}",
            "email": student.email,
            "phone": student.phone,
            "scholar": "Yes" if student.is_scholar else "No",
            "paid": "Yes" if student.paid else "No",
            "present": present_status,
        })
    
    # Pass student data to the template
    context = {
        "students_json": json.dumps(students_data),
    }

    # If the request is POST (profile update form submission)
    if request.method == 'POST':
        form = UpdateProfileForm(request.POST, instance=request.user.userprofile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('admin_dashboard')  # Redirect to the dashboard or wherever you need
        else:
            messages.error(request, "There was an error updating your profile. Please try again.")

    # Fetch current user profile to populate the form for editing
    form = UpdateProfileForm(instance=request.user.userprofile)
    issue_form = IssueForm()
    context.update({
        "form": form,
        "issue_form": issue_form,
    })

    return render(request, "attendance/index_admin.html", context)



def search_students(request):
    query = request.GET.get("query", "")
    if query:
        students = UserProfile.objects.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(phone__icontains=query)
        )
        results = [{"name": f"{student.first_name} {student.last_name}", "phone": student.phone} for student in students]
        return JsonResponse({"results": results})
    return JsonResponse({"results": []})


@login_required
@csrf_exempt
def attendance_summary(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            print(data)
            date_str = data.get('content')
            print(f"Received date string: {date_str}")
            try:
                date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                logger.error("Invalid date format")
                return JsonResponse({'error': 'Invalid date format'}, status=400)
            
            attendance_records = Attendance.objects.filter(date=date)
            
            totalStudents = UserProfile.objects.filter(user__is_staff=False).count()
            totalAttended = attendance_records.count()
            
            # Count scholars who attended
            ScholarAttended = attendance_records.filter(user_profile__is_scholar=True).count()
            
            # Count paid non-scholar students who attended
            PaidNonScholarAttended = attendance_records.filter(user_profile__paid=True, user_profile__is_scholar=False).count()
            
            # Total of paid students who attended (scholars + paid non-scholars)
            total_Paid_attended = ScholarAttended + PaidNonScholarAttended
            
            # Count unpaid students who attended (non-scholars who haven't paid)
            UnpaidAttended = attendance_records.filter(user_profile__paid=False, user_profile__is_scholar=False).count()
            
            # Calculate total number of paid students (scholars + paid non-scholars)
            total_paid_students = UserProfile.objects.filter(
                Q(is_scholar=True) | Q(paid=True, is_scholar=False),
                user__is_staff=False
            ).count()
            
            # Calculate paid students who are absent
            PaidAbsent = total_paid_students - total_Paid_attended
        
            summary = {
                'totalStudents': totalStudents,
                'totalAttended': totalAttended,
                'PaidAttended': total_Paid_attended,
                'PaidAbsent': PaidAbsent,
                'UnpaidAttended': UnpaidAttended,
            }
        
            return JsonResponse(summary)
        except json.JSONDecodeError:
            logger.error("JSON decode error")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
        


@login_required
def toggle_payment_status(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            student_id = data.get("id")
            new_status = data.get("paid") == "Yes"
            
            # Update the payment status in the database
            student = UserProfile.objects.get(id=student_id)
            student.paid = new_status
            student.save()
            
            return JsonResponse({"success": True, "message": "Payment status updated."})
        except UserProfile.DoesNotExist:
            return JsonResponse({"success": False, "message": "Student not found."})
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return JsonResponse({"success": False, "message": "Invalid request method."})

@login_required
def get_attendance_data(request):
    date = request.GET.get('date')
    if date:
        students = UserProfile.objects.all()
        attendance_records = Attendance.objects.filter(date=date)

        students_with_attendance = []
        for student in students:
            attendance = attendance_records.filter(user_profile=student).first()
            students_with_attendance.append({
                "id": student.id,
                "name": f"{student.first_name} {student.last_name}",
                "email": student.email,
                "phone": student.phone,
                "scholar": "Yes" if student.is_scholar else "No",
                "paid": "Yes" if student.paid else "No",
                "present": "Present" if attendance else "Absent",
            })

        return JsonResponse({'success': True, 'students': students_with_attendance})
    
    return JsonResponse({'success': False, 'message': 'Invalid date or no records found.'})


 
def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            try:
                user_profile, password = form.save(commit=False)
                user_profile.is_scholar = 0

                # Ensure student_id is unique
                base_student_id = user_profile.student_id
                student_id = base_student_id
                max_retries = 5
                
                for _ in range(max_retries):
                    if not UserProfile.objects.filter(student_id=student_id).exists():
                        break
                    unique_suffix = uuid.uuid4().hex[:6]  # Generate a random 6-character suffix
                    student_id = f"{base_student_id}_{unique_suffix}"
                else:
                    messages.error(request, 'Failed to generate a unique student ID. Please try again.')
                    return redirect('signup')

                user_profile.student_id = student_id
                user_profile.save()
                
                messages.success(request, 'Signup successful! Please login to continue.')
                return redirect('login')
            except Exception as e:
                messages.error(request, f'An error occurred during signup: {str(e)}')
                return redirect('signup')
    else:
        form = SignupForm()

    return render(request, 'attendance/signup.html', {'form': form})


def generate_otp():
    return random.randint(100000, 999999)



def send_otp(email, otp):
    subject = 'Your OTP for Login - QR Plate'
    
    # Get base64 encoded logo
    logo_path = os.path.join(settings.STATIC_ROOT, 'assets/images/logo.jpg')
    try:
        with open(logo_path, 'rb') as img_file:
            logo_data = base64.b64encode(img_file.read()).decode()
            logo_url = f"data:image/jpeg;base64,{logo_data}"
    except Exception as e:
        print(f"Error reading logo: {e}")
        logo_url = ""  # Fallback if image can't be read
    
    html_content = render_to_string('emails/otp_email.html', {
        'otp': otp,
        'logo_url': logo_url
    })
    
    text_content = strip_tags(html_content)
    
    email_message = EmailMessage(
        subject,
        html_content,
        settings.DEFAULT_FROM_EMAIL,  # Use DEFAULT_FROM_EMAIL instead of EMAIL_HOST_USER
        [email]
    )
    
    email_message.content_subtype = 'html'
    email_message.send()

# View for Login 

def login_with_otp(request):
    if request.method == 'POST':
        email = request.POST['email']
        otp = request.POST['otp']

        try:
            user_profile = UserProfile.objects.get(email=email)
            stored_otp = request.session.get('otp')
            otp_timestamp = request.session.get('otp_timestamp')
            
            # Check if OTP has expired
            if otp_timestamp:
                otp_time = timezone.datetime.strptime(otp_timestamp, "%Y-%m-%d %H:%M:%S")
                if timezone.now() - otp_time > OTP_EXPIRATION_TIME:
                    messages.error(request, 'OTP has expired.')
                    return redirect('login')

            if stored_otp == otp:
                login(request, user_profile.user)
                return redirect('web_home')
            else:
                messages.error(request, 'Invalid OTP')
        except UserProfile.DoesNotExist:
            messages.error(request, 'No user with this email')
    
    return render(request, 'attendance/login_with_otp.html')


@login_required
def web_home(request):
    if request.user.is_authenticated:
        try:
            user_profile = UserProfile.objects.get(user=request.user)

            # Handle image upload
            if request.method == 'POST':
                form = ProfileImageForm(request.POST, request.FILES, instance=user_profile)
                if form.is_valid():
                    form.save()
                    messages.success(request, "Profile image updated successfully!")
                    return redirect('web_home')  # Reload page to show the updated image
                else:
                    messages.error(request, "Failed to upload image. Please try again.")

            # Generate the QR code URL using settings.BASE_URL
            qr_code_url = f"{settings.BASE_URL}/scan/{user_profile.qr_code_id}"

            # Generate the QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,
                border=4,
            )
            qr.add_data(qr_code_url)
            qr.make(fit=True)

            # Create an image from the QR code
            img = qr.make_image(fill_color='black', back_color='white')

            # Save the image to a BytesIO object
            img_io = BytesIO()
            img.save(img_io, format='PNG')
            img_io.seek(0)

            # Encode the QR code image to base64 to display in the template
            qr_code_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')

            form = ProfileImageForm(instance=user_profile)  # Pre-fill form with current data

            return render(request, 'attendance/home.html', {
                'qr_code': qr_code_base64,
                'user_profile': user_profile,
                'qr_code_url': qr_code_url,
                'form': form,
            })
        except UserProfile.DoesNotExist:
            messages.error(request, 'User profile not found.')
            return redirect('login')
    else:
        return redirect('login')


# View to handle email input and send OTP
@csrf_exempt
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            try:
                user_profile = UserProfile.objects.get(email=email)

                # Generate OTP
                otp = generate_otp()
                request.session['otp'] = str(otp)
                request.session['email'] = email
                request.session['otp_timestamp'] = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

                # Send OTP to user's email
                send_otp(email, otp)
                messages.success(request, 'OTP sent to your email.')

                return redirect('verify_otp')  # Redirect to OTP verification page
            except UserProfile.DoesNotExist:
                messages.error(request, "No account found with that email.")
        else:
            messages.error(request, "Please enter a valid email address.")
    else:
        form = LoginForm()

    return render(request, 'attendance/login.html', {'form': form})

# Decorate with @login_required to ensure the user is authenticated
@csrf_exempt
def verify_otp(request):
    if request.method == 'POST':
        otp_input = request.POST.get('otp')
        stored_otp = request.session.get('otp')
        email = request.session.get('email')

        if otp_input == stored_otp:
            try:
                user_profile = UserProfile.objects.get(email=email)
                user = user_profile.user

                # Authenticate and log the user in
                login(request, user)

                # Redirect to the appropriate dashboard
                if user.is_staff:
                    return redirect('admin_dashboard')  # Admin dashboard
                else:
                    return redirect('web_home')  # Student dashboard

            except UserProfile.DoesNotExist:
                messages.error(request, "No account found with that email.")
                return redirect('login')  # Redirect back to login if user profile not found
        else:
            messages.error(request, "Invalid OTP. Please try again.")
    
    return render(request, 'attendance/verify_otp.html')



def logout_view(request):
    logout(request)  # Log out the user
    return redirect('login')  # Redirect to login page after logout

@api_view(['GET'])
def home(request):
    auth_header = request.headers.get('Authorization')
    if auth_header:
        try:
            # Extract the token from the Authorization header
            token_str = auth_header.split(' ')[1]
            token = AccessToken(token_str)
            
            # Authenticate the user using the token
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token_str)
            user = jwt_auth.get_user(validated_token)
            
            user_profile = UserProfile.objects.get(user=user)

            # Generate the QR code URL using settings.BASE_URL
            qr_code_url = f"{settings.BASE_URL}/scan/{user_profile.qr_code_id}"

            # Generate the QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=8,
                border=4,
            )
            qr.add_data(qr_code_url)
            qr.make(fit=True)
            print(qr_code_url)

            img = qr.make_image(fill_color='black', back_color='white')

            img_io = BytesIO()
            img.save(img_io, format='PNG')
            img_io.seek(0)

            qr_code_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            print(user_profile.first_name)
            print(user_profile.last_name)

            return JsonResponse({
                'qr_code': qr_code_base64,
                'user_profile': {
                    'email': user_profile.email,
                    'student_id': user_profile.student_id,
                    'first_name': user_profile.first_name,
                    'last_name': user_profile.last_name,
                },
                'qr_code_url': qr_code_url,
                'profile_picture_url': user_profile.profile_picture.url if user_profile.profile_picture else None
            }, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    else:
        return JsonResponse({'error': 'Authorization header missing'}, status=401)

import logging

logger = logging.getLogger(__name__)

@login_required
@csrf_exempt
@api_view(['POST'])
def scan_qr_code(request, qr_code_id):
    try:
        logger.info(f"Received QR code ID: {qr_code_id}")

        if isinstance(qr_code_id, str):
            qr_code_id = UUID(qr_code_id)
            logger.info(f"Converted QR code ID to UUID: {qr_code_id}")

        user_profile = UserProfile.objects.get(qr_code_id=qr_code_id)
        user = user_profile.user
        logger.info(f"Found user profile for QR code ID: {qr_code_id}, user: {user.username}")

        today = timezone.now().date()
        if Attendance.objects.filter(user_profile=user_profile, date=today).exists():
            logger.info(f"Attendance for {user.username} has already been marked today.")
            return JsonResponse({
                'message': f"Attendance for {user.username} has already been marked today.",
            })

        Attendance.objects.create(
            user_profile=user_profile,
            date=today,
            time=timezone.now().time()
        )
        logger.info(f"Attendance successfully recorded for {user.username}")

        return JsonResponse({
            'message': f"Attendance successfully recorded for {user.username}.",
            'attendance_time': timezone.now().strftime("%H:%M:%S"),
        })

    except UserProfile.DoesNotExist:
        logger.error(f"UserProfile with QR code ID {qr_code_id} does not exist.")
        return JsonResponse({'message': 'Invalid QR code ID'}, status=400)
    except ValueError:
        logger.error(f"Invalid QR code ID format: {qr_code_id}")
        return JsonResponse({'message': 'Invalid QR code ID format'}, status=400)
    except Exception as e:
        logger.error(f"Error processing the QR code: {str(e)}")
        return JsonResponse({'message': f'Error processing the QR code: {str(e)}'}, status=500)

    

# Generate OTP
def generate_otp():
    return str(random.randint(100000, 999999))

@api_view(['POST'])
@permission_classes([AllowAny])
def send_otp_api(request):
    serializer = LoginSerializer(data=request.data) 
    session_id = request.data.get('sessionId')
    if serializer.is_valid():
        email = serializer.validated_data['email']
        try:
            # Validate the session ID
            session = Session.objects.get(session_key=session_id)
            session_data = session.get_decoded()

            # Ensure the session matches the correct user
            email = session_data.get('email')
            if not email:
                return Response({'message': 'Invalid session or session has expired.'}, status=status.HTTP_400_BAD_REQUEST)

            user_profile = UserProfile.objects.get(email=email)
            otp = generate_otp()

            request.session['otp'] = otp
            request.session['otp_timestamp'] = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

            # Get base64 encoded logo
            logo_path = os.path.join(settings.STATIC_ROOT, 'assets/images/logo.jpg')
            try:
                with open(logo_path, 'rb') as img_file:
                    logo_data = base64.b64encode(img_file.read()).decode()
                    logo_url = f"data:image/jpeg;base64,{logo_data}"
            except Exception as e:
                print(f"Error reading logo: {e}")
                logo_url = ""  # Fallback if image can't be read

            # Render HTML email template
            html_content = render_to_string('emails/otp_email.html', {
                'otp': otp,
                'logo_url': logo_url
            })
            
            text_content = strip_tags(html_content)

            # Send email using EmailMessage to support HTML content
            email_message = EmailMessage(
                'Your OTP for Login - QR Plate',
                html_content,
                settings.DEFAULT_FROM_EMAIL,  # Use DEFAULT_FROM_EMAIL instead of EMAIL_HOST_USER
                [email]
            )
            
            email_message.content_subtype = 'html'
            email_message.send()

            return Response({'message': 'OTP sent to your email.', 'sessionId': session_id}, status=status.HTTP_200_OK)
        except UserProfile.DoesNotExist:
            return Response({'message': 'No account found with that email.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def verify_otp_api(request):
    sessionId = request.COOKIES.get('sessionid')
    #otp_input = request.data.get('otp')
    #email = request.data.get('email') or request.session.get('email')
    #stored_otp = request.session.get('otp')
    #otp_timestamp = request.session.get('otp_timestamp')

    print("Session Data at Verification:")
    print(sessionId)
    #print("Email:", email)
    #print("Stored OTP:", stored_otp)
    #print("Stored OTP Timestamp:", otp_timestamp)
    print("-"*10) 
    #print(f"All Session Data: {dict(request.session)}")

    

    try:
        # Retrieve the session and decode its data
        session = Session.objects.get(session_key=sessionId)
        session_data = session.get_decoded() 
        print("Session Data at Verification:")
        print(session_data)

        # Validate session data
        stored_otp = session_data.get('otp')
        otp_timestamp = session_data.get('otp_timestamp')
        email = session_data.get('email')
        otp_input = request.data.get('otp') 
        
        # Convert otp_timestamp to a timezone-aware datetime
        otp_time = timezone.make_aware(
            timezone.datetime.strptime(otp_timestamp, "%Y-%m-%d %H:%M:%S"),
            timezone=timezone.get_current_timezone()
        )

        if not email or not stored_otp or not otp_timestamp:
            return Response(
            {"message": "OTP session has expired. Please request a new OTP."},
            status=status.HTTP_400_BAD_REQUEST
        )

        print("Current Time (timezone.now()):", timezone.now())
        print("OTP Time:", otp_time)
        print("Time Difference (seconds):", (timezone.now() - otp_time).total_seconds())

        # Check if OTP has expired
        if timezone.now() - otp_time > OTP_EXPIRATION_TIME:
            return Response(
                {"message": "OTP has expired. Please request a new OTP."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if the entered OTP matches the stored OTP
        if otp_input == stored_otp:
            # Fetch the user from the profile
            user_profile = UserProfile.objects.get(email=email)
            user = user_profile.user

            # Log the user in
            login(request, user)

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            print(access_token)

            # Clear OTP and email from the session
            request.session.pop('otp', None)
            request.session.pop('email', None)
            request.session.pop('otp_timestamp', None)

            return Response(
                {
                    "message": "Login successful.",
                    "user": {
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name
                    },
                    "tokens": {
                        "access": access_token,
                        "refresh": refresh_token
                    }
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"message": "Invalid OTP. Please try again."},
                status=status.HTTP_400_BAD_REQUEST
            )

    except UserProfile.DoesNotExist:
        return Response(
            {"message": "No account found with that email."},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {"message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




@api_view(['POST'])
@permission_classes([AllowAny])
def signup_api(request):
    try:
        form = SignupForm(request.data)
        if form.is_valid():
            user_profile, password = form.save(commit=False)
            user_profile.is_scholar = 0

            # Ensure student_id is unique
            base_student_id = user_profile.student_id
            student_id = base_student_id
            max_retries = 5
            for _ in range(max_retries):
                if not UserProfile.objects.filter(student_id=student_id).exists():
                    break
                unique_suffix = uuid.uuid4().hex[:6]  # Generate a random 6-character suffix
                student_id = f"{base_student_id}_{unique_suffix}"
            else:
                logger.error("Failed to generate a unique student_id after multiple attempts.")
                return Response({'message': 'Failed to generate a unique student_id. Please try again.'}, status=500)

            user_profile.student_id = student_id
            user_profile.save()

            return Response({
                'message': 'User created successfully.',
                'user': {
                    'email': user_profile.user.email,
                    'username': user_profile.user.username,
                    'first_name': user_profile.user.first_name,
                    'last_name': user_profile.user.last_name,
                    'student_id': user_profile.student_id,  # Access student_id from user_profile
                }
            }, status=201)
        else:
            logger.error(f"Form is not valid: {form.errors}")
            return Response({'message': 'Form is not valid', 'errors': form.errors}, status=400)
    except Exception as e:
        logger.error(f"Error during signup: {str(e)}", exc_info=True)
        return Response({'message': str(e)}, status=500)
    
# API for logout
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_api(request):
    logout(request)
    return Response({'message': 'Logout successful.'}, status=status.HTTP_200_OK)

class LoginAPI(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            try:
                user_profile = UserProfile.objects.get(email=email)
                login(request, user_profile.user)
                return Response({'message': 'Login successful.'}, status=status.HTTP_200_OK)
            except UserProfile.DoesNotExist:
                return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# filepath: /path/to/views.py


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def home_api(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        
        # Generate the QR code URL
        qr_code_url = f"{settings.BASE_URL}/scan/{user_profile.qr_code_id}"
        
        # Generate the QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=8,
            border=4,
        )
        qr.add_data(qr_code_url)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color='black', back_color='white')
        
        # Convert QR code to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return Response({
            'qr_code': qr_code_base64,
            'qr_code_url': qr_code_url,
            'user_profile': {
                'email': user_profile.email,
                'student_id': user_profile.student_id,
                'profile_picture_url': request.build_absolute_uri(user_profile.profile_picture.url) if user_profile.profile_picture else None
            }
        }, status=status.HTTP_200_OK)
        
    except UserProfile.DoesNotExist:
        return Response({
            'error': 'User profile not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)






@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_qr_code_api(request, qr_code_id):
    try:
        logger.info(f"Received QR code ID: {qr_code_id}")
        # Ensure qr_code_id is a valid UUID
        qr_code = str(qr_code_id)
        qr_code_id2 = UUID(qr_code)

        # Fetch the UserProfile associated with the QR code
        user_profile = UserProfile.objects.get(qr_code_id=qr_code_id2)
        user = user_profile.user

        # Check if attendance for today is already marked
        today = timezone.now().date()
        if Attendance.objects.filter(user_profile=user_profile, date=today).exists():
            return Response({'message': 'Attendance already marked today.'}, status=status.HTTP_200_OK)

        # Mark attendance
        Attendance.objects.create(
            user_profile=user_profile,
            date=today,
            time=timezone.now().time()
        )

        return Response({
            'message': f'Attendance successfully recorded for {user.username}.',
            'attendance_time': timezone.now().strftime("%H:%M:%S"),
        }, status=status.HTTP_201_CREATED)

    except UserProfile.DoesNotExist:
        logger.error(f"UserProfile does not exist for QR code ID: {qr_code_id2}")
        return Response({'error': 'Invalid QR code ID.'}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError:
        logger.error(f"Invalid QR code format: {qr_code_id2}")
        return Response({'error': 'Invalid QR code format.'}, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
def mark_attendance_api(request):
    serializer = AttendanceSerializer(data=request.data)
    if serializer.is_valid():
        qr_code_id = serializer.validated_data['qr_code_id']
        try:
            user_profile = UserProfile.objects.get(qr_code_id=qr_code_id)
            
            # Check if attendance already marked for today
            today = timezone.now().date()
            if Attendance.objects.filter(user_profile=user_profile, date=today).exists():
                return Response({'message': 'Attendance already marked for today.'}, status=status.HTTP_200_OK)

            # Mark attendance
            Attendance.objects.create(user_profile=user_profile, date=today, time=timezone.now().time())
            return Response({'message': 'Attendance marked successfully.'}, status=status.HTTP_201_CREATED)
        
        except UserProfile.DoesNotExist:
            return Response({'error': 'Invalid QR code ID.'}, status=status.HTTP_400_BAD_REQUEST)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def login_api(request):
    try:
        # Step 1: Validate the email form
        form = LoginForm(request.data)

        if form.is_valid():
            email = form.cleaned_data['email']

            # Step 2: Check if the user exists
            user = User.objects.filter(email=email).first()
            if user is None:
                return Response({
                    'message': 'User not found',
                }, status=404)

            # Step 3: Generate OTP
            otp = generate_otp()

            # Step 4: Send OTP to user's email
            send_otp(email, otp)

            # Store the OTP and email in the session 
            session_id = request.session.session_key
            if not session_id:
                request.session.create()  # Create a new session if none exists
                session_id = request.session.session_key

            request.session['otp'] = otp
            request.session['email'] = email
            request.session['otp_timestamp'] = timezone.now().strftime("%Y-%m-%d %H:%M:%S")

            # Debugging session data
            print("Session Data After Login:")
            print("Email:", request.session.get('email'))
            print("Stored OTP:", request.session.get('otp'))
            print("Stored OTP Timestamp:", request.session.get('otp_timestamp'))

            return Response({
                'message': 'OTP sent to your email.',
                'sessionId': session_id,
            }, status=200)

        else:
            return Response({
                'message': 'Form is not valid',
                'errors': form.errors
            }, status=400)

    except Exception as e:
        return Response({
            'message': str(e)
        }, status=500)




@api_view(['POST'])
def admin_login(request):
    try:
        username = request.data.get('username')
        password = request.data.get('password')
        print(username)
        print(password)

        if not username or not password:
            return Response({'message': 'Username and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({'message': 'Invalid username or password'}, status=status.HTTP_400_BAD_REQUEST)

        if not user.is_staff:
            return Response({'message': 'User is not authorized'}, status=status.HTTP_403_FORBIDDEN)

        if check_password(password, user.password):
            refresh = RefreshToken.for_user(user)
            return Response({
                'message': 'Login successful',
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'Invalid username or password'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_dashboard_api(request):
    try:
        # Get the user profile for the logged-in user
        user_profile = UserProfile.objects.get(user=request.user)
        
        # Get the attendance records for the student
        attendance_records = user_profile.attendance_set.all()  # Assuming there's an Attendance model
        
        # Prepare the data to send back to the student
        data = []
        for record in attendance_records:
            data.append({
                'date': record.date,
                'status': record.status  # Assuming Attendance model has status (e.g., 'present' or 'absent')
            })
        
        return Response({'attendance_records': data}, status=status.HTTP_200_OK)

    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dashboard_api(request):
    try:
        # Get all user profiles (students)
        user_profiles = UserProfile.objects.all()
        
        # Prepare the data to send back to the admin
        data = []
        for profile in user_profiles:
            data.append({
                'email': profile.email,
                'student_id': profile.student_id,
                'attendance_count': profile.attendance_set.count()  # Assuming there's an Attendance model
            })
        
        return Response({'user_profiles': data}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_profile_picture(request):
    try:
        print("Files in request:", request.FILES)  # Debug print
        user_profile = UserProfile.objects.get(user=request.user)
        
        if 'profile_picture' in request.FILES:
            file = request.FILES['profile_picture']
            print(f"Received file: {file.name}, size: {file.size}")  # Debug print
            
            if user_profile.profile_picture:
                print(f"Deleting old profile picture: {user_profile.profile_picture.path}")  # Debug print
                user_profile.profile_picture.delete(save=False)
            
            user_profile.profile_picture = file
            user_profile.save()
            
            print(f"New profile picture saved at: {user_profile.profile_picture.path}")  # Debug print
            print(f"URL: {user_profile.profile_picture.url}")  # Debug print
            
            return Response({
                'message': 'Profile picture updated successfully',
                'profile_picture_url': request.build_absolute_uri(user_profile.profile_picture.url)
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'message': 'No profile picture provided'
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"Error updating profile picture: {str(e)}")  # Add logging
        return Response({
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# downloading apps
def download_app(request):
    return render(request, 'attendance/download_apps.html')

