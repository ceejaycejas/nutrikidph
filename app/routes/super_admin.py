from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.school import School
from app.models.section import Section
from app.models.student import Student
from datetime import datetime
from app.routes.school import log_activity
from app.services.notification_service import NotificationService
import io
import xlsxwriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

bp = Blueprint('super_admin', __name__, url_prefix='/super-admin')

@bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    log_activity(current_user.id, 'dashboard_access', 'Accessed super admin dashboard', request.remote_addr)
    
    # Get system-wide statistics
    total_schools = School.query.count()
    total_admins = User.query.filter_by(role='admin').count()
    total_students = Student.query.count()
    total_super_admins = User.query.filter_by(role='super_admin').count()
    
    # Get recent activities (last 10)
    recent_activities = db.session.query(
        User.name.label('user_name'),
        User.role.label('user_role'),
        School.name.label('school_name'),
        Student.name.label('activity_description'),
        Student.created_at.label('activity_time')
    ).select_from(Student)\
     .join(User, Student.registered_by == User.id)\
     .outerjoin(School, Student.school_id == School.id)\
     .order_by(Student.created_at.desc())\
     .limit(10).all()
    
    # Enhanced BMI distribution for all students with BMI data
    bmi_distribution = {
        'normal': 0,
        'underweight': 0,
        'overweight': 0,
        'obese': 0,
        'severely_underweight': 0
    }
    
    # Get all students with BMI data
    students_with_bmi = Student.query.filter(Student.bmi.isnot(None)).all()
    
    for student in students_with_bmi:
        if student.bmi < 16:
            bmi_distribution['severely_underweight'] += 1
        elif student.bmi < 18.5:
            bmi_distribution['underweight'] += 1
        elif student.bmi < 25:
            bmi_distribution['normal'] += 1
        elif student.bmi < 30:
            bmi_distribution['overweight'] += 1
        else:
            bmi_distribution['obese'] += 1
    
    # Schools with most students
    school_stats = db.session.query(
        School.name,
        db.func.count(Student.id).label('student_count')
    ).outerjoin(Student, School.id == Student.school_id)\
     .group_by(School.id, School.name)\
     .order_by(db.func.count(Student.id).desc())\
     .limit(5).all()
    
    # Monthly student registrations for the past 12 months
    from datetime import datetime, timedelta
    from sqlalchemy import extract
    
    monthly_registrations = db.session.query(
        extract('month', Student.created_at).label('month'),
        extract('year', Student.created_at).label('year'),
        db.func.count(Student.id).label('count')
    ).filter(Student.created_at >= datetime.utcnow() - timedelta(days=365))\
     .group_by(extract('year', Student.created_at), extract('month', Student.created_at))\
     .order_by(extract('year', Student.created_at), extract('month', Student.created_at)).all()
    
    # Gender distribution
    gender_distribution = db.session.query(
        Student.gender,
        db.func.count(Student.id).label('count')
    ).filter(Student.gender.isnot(None))\
     .group_by(Student.gender).all()
    
    # Beneficiary vs Non-beneficiary distribution
    beneficiary_distribution = {
        'beneficiaries': Student.query.filter_by(is_beneficiary=True).count(),
        'non_beneficiaries': Student.query.filter_by(is_beneficiary=False).count()
    }
    
    # Students by age groups
    age_groups = {
        '5-8': 0,
        '9-12': 0,
        '13-16': 0,
        '17+': 0
    }
    
    for student in Student.query.all():
        if student.age:
            if 5 <= student.age <= 8:
                age_groups['5-8'] += 1
            elif 9 <= student.age <= 12:
                age_groups['9-12'] += 1
            elif 13 <= student.age <= 16:
                age_groups['13-16'] += 1
            elif student.age >= 17:
                age_groups['17+'] += 1
    
    # Recent system activity (last 7 days)
    from app.models.user_activity import UserActivity
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_system_activity = UserActivity.query.filter(
        UserActivity.created_at >= seven_days_ago
    ).order_by(UserActivity.created_at.desc()).limit(15).all()
    
    # Students at risk (BMI-based)
    at_risk_students = Student.query.filter(
        Student.bmi.isnot(None),
        (Student.bmi < 18.5) | (Student.bmi >= 25)
    ).count()
    
    # System health metrics
    system_metrics = {
        'total_users': total_super_admins + total_admins + total_students,
        'active_schools': total_schools,
        'students_with_bmi': len(students_with_bmi),
        'at_risk_students': at_risk_students,
        'beneficiary_coverage': (beneficiary_distribution['beneficiaries'] / max(total_students, 1)) * 100
    }
    
    return render_template('super_admin/dashboard.html',
                         total_schools=total_schools,
                         total_admins=total_admins,
                         total_students=total_students,
                         total_super_admins=total_super_admins,
                         recent_activities=recent_activities,
                         bmi_distribution=bmi_distribution,
                         school_stats=school_stats,
                         monthly_registrations=monthly_registrations,
                         gender_distribution=gender_distribution,
                         beneficiary_distribution=beneficiary_distribution,
                         age_groups=age_groups,
                         recent_system_activity=recent_system_activity,
                         system_metrics=system_metrics)

@bp.route('/users')
@login_required
def super_admins():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    users = User.query.filter(User.role == 'super_admin').all()
    return render_template('super_admin/users.html', users=users)

@bp.route('/users/create', methods=['GET', 'POST'])
@login_required
def create_user():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('super_admin.create_user'))
        
        user = User(name=name, email=email, role=role)
        user.set_password(password)
        
        # Set school if role is admin
        if role == 'admin':
            school_id = request.form.get('school_id')
            if school_id:
                user.school_id = int(school_id)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Send notification to the new user
            NotificationService.notify_account_created(
                user_id=user.id,
                password=password,
                created_by_name=current_user.name
            )
            
            flash('User created successfully!', 'success')
            return redirect(url_for('super_admin.super_admins'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
    
    schools = School.query.all()
    return render_template('super_admin/create_user.html', schools=schools)

@bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.name = request.form.get('name')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        
        # Update school if role is admin
        if user.role == 'admin':
            school_id = request.form.get('school_id')
            if school_id:
                user.school_id = int(school_id)
        else:
            user.school_id = None
        
        # Update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        try:
            db.session.commit()
            
            # Prepare changes summary
            changes = []
            if user.name != request.form.get('name'):
                changes.append(f"Name updated")
            if user.email != request.form.get('email'):
                changes.append(f"Email updated")
            if user.role != request.form.get('role'):
                changes.append(f"Role changed to {user.role}")
            if new_password:
                changes.append("Password changed")
                # Send separate notification for password change
                NotificationService.notify_password_changed(
                    user_id=user.id,
                    changed_by_name=current_user.name
                )
            
            # Send general update notification
            if changes:
                NotificationService.notify_account_updated(
                    user_id=user.id,
                    updated_by_name=current_user.name,
                    changes="\n".join(changes)
                )
            
            flash('User updated successfully!', 'success')
            return redirect(url_for('super_admin.super_admins'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')
    
    schools = School.query.all()
    return render_template('super_admin/edit_user.html', user=user, schools=schools)

@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    try:
        # First, delete all user activities associated with this user
        from app.models.user_activity import UserActivity
        UserActivity.query.filter_by(user_id=user_id).delete()
        
        # Delete associated student profile if exists
        if user.student_profile:
            db.session.delete(user.student_profile)
        
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {str(e)}', 'danger')
    
    return redirect(url_for('super_admin.super_admins'))

# --- ADMIN MANAGEMENT ---
@bp.route('/admins')
@login_required
def admins():
    log_activity(current_user.id, 'view_admins', 'Accessed admins management page', request.remote_addr)
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    search_query = request.args.get('search_query', '').strip()
    query = User.query.filter(User.role == 'admin')
    if search_query:
        query = query.filter((User.name.ilike(f'%{search_query}%')) | (User.email.ilike(f'%{search_query}%')))
    admins = query.all()
    return render_template('super_admin/admins.html', admins=admins, search_query=search_query)

@bp.route('/admins/create', methods=['GET', 'POST'])
@login_required
def create_admin():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        school_id = request.form.get('school_id')
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('super_admin.create_admin'))
        admin = User(name=name, email=email, role='admin', school_id=school_id)
        admin.set_password(password)
        try:
            db.session.add(admin)
            db.session.commit()
            school = School.query.get(school_id) if school_id else None
            
            # Send notifications
            NotificationService.notify_account_created(
                user_id=admin.id,
                password=password,
                created_by_name=current_user.name
            )
            
            if school:
                NotificationService.notify_admin_assignment(
                    user_id=admin.id,
                    school_name=school.name,
                    assigned_by_name=current_user.name
                )
            
            log_activity(current_user.id, 'create_admin', f'Created admin {name} ({email}) for {school.name if school else "no school"}', request.remote_addr)
            flash('Admin created successfully!', 'success')
            return redirect(url_for('super_admin.admins'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating admin: {str(e)}', 'danger')
    schools = School.query.all()
    return render_template('super_admin/create_admin.html', schools=schools)

@bp.route('/admins/<int:admin_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_admin(admin_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    admin = User.query.filter_by(id=admin_id, role='admin').first_or_404()
    if request.method == 'POST':
        admin.name = request.form.get('name')
        admin.email = request.form.get('email')
        admin.school_id = request.form.get('school_id')
        new_password = request.form.get('new_password')
        if new_password:
            admin.set_password(new_password)
        try:
            db.session.commit()
            flash('Admin updated successfully!', 'success')
            return redirect(url_for('super_admin.admins'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating admin: {str(e)}', 'danger')
    schools = School.query.all()
    return render_template('super_admin/edit_admin.html', admin=admin, schools=schools)

@bp.route('/admins/<int:admin_id>/delete', methods=['POST'])
@login_required
def delete_admin(admin_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    admin = User.query.filter_by(id=admin_id, role='admin').first_or_404()
    
    # Store admin info for logging before deletion
    admin_name = admin.name
    admin_email = admin.email
    school_name = admin.school.name if admin.school else "no school"
    
    try:
        # First, delete all notifications associated with this admin
        from app.models.notification import Notification
        Notification.query.filter_by(recipient_id=admin_id).delete()
        
        # Delete all user activities associated with this admin
        from app.models.user_activity import UserActivity
        UserActivity.query.filter_by(user_id=admin_id).delete()
        
        # Then delete the admin user
        db.session.delete(admin)
        db.session.commit()
        
        # Log the deletion activity
        log_activity(current_user.id, 'delete_admin', f'Deleted admin {admin_name} ({admin_email}) from {school_name}', request.remote_addr)
        flash('Admin deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting admin: {str(e)}', 'danger')
    return redirect(url_for('super_admin.admins'))

# --- STUDENT MANAGEMENT ---
@bp.route('/students')
@login_required
def students():
    log_activity(current_user.id, 'view_students', 'Accessed students management page', request.remote_addr)
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    search_query = request.args.get('search_query', '').strip()
    school_id = request.args.get('school_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Number of students per page
    
    # Get all schools for the filter dropdown
    schools = School.query.all()
    schools_count = len(schools)
    
    # Build the query
    query = Student.query.join(School, Student.school_id == School.id)
    
    if school_id:
        query = query.filter(Student.school_id == school_id)
    
    if search_query:
        query = query.filter(Student.name.ilike(f'%{search_query}%'))
    
    # Get all students (no pagination for grouped view)
    students = query.all()
    
    # Group students by school for better organization (include school id and name)
    students_by_school = {}
    for student in students:
        school_id = student.school.id if student.school else 0
        school_name = student.school.name if student.school else 'No School'
        if school_id not in students_by_school:
            students_by_school[school_id] = {'name': school_name, 'students': []}
        students_by_school[school_id]['students'].append(student)
    
    # Ensure schools with zero students are also listed
    for school in schools:
        if school.id not in students_by_school:
            students_by_school[school.id] = {'name': school.name, 'students': []}
    
    # Stats
    total_students = Student.query.count()
    active_students = Student.query.count()  # Assuming all students are active for now
    
    return render_template('super_admin/students.html', 
                         students_by_school=students_by_school,
                         schools=schools, 
                         schools_count=schools_count,
                         total_students=total_students,
                         active_students=active_students,
                         search_query=search_query, 
                         selected_school_id=school_id)

@bp.route('/students/<int:student_id>/view')
@login_required
def view_student(student_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    log_activity(current_user.id, 'view_student', f'Viewed student {student.name} profile', request.remote_addr)
    
    return render_template('student/view.html', student=student)

@bp.route('/students/create', methods=['GET', 'POST'])
@login_required
def create_student():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        age = int(request.form.get('age')) if request.form.get('age') else None
        gender = request.form.get('gender')
        height = float(request.form.get('height')) if request.form.get('height') else None
        weight = float(request.form.get('weight')) if request.form.get('weight') else None
        school_id = request.form.get('school_id')
        section_id = request.form.get('section_id')
        
        # Calculate birth_date from age if provided
        birth_date = None
        if age:
            from datetime import date
            current_year = date.today().year
            birth_date = date(current_year - age, 1, 1)  # Approximate birth date
        
        # Create user account for student
        password = request.form.get('password')
        user = User(name=name, email=email, role='student')
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.flush()  # Get the user ID
            
            # Create student
            student = Student(
                name=name,
                birth_date=birth_date,
                gender=gender,
                height=height,
                weight=weight,
                school_id=int(school_id) if school_id else None,
                section_id=int(section_id) if section_id else None,
                user_id=user.id,
                registered_by=current_user.id
            )
            
            # Calculate BMI if height and weight are provided
            if height and weight:
                height_m = height / 100  # Convert cm to meters
                student.bmi = round(weight / (height_m ** 2), 2)
            
            db.session.add(student)
            db.session.commit()
            
            # Send notification to student
            NotificationService.notify_account_created(
                user_id=user.id,
                password=password,
                created_by_name=current_user.name
            )
            
            log_activity(current_user.id, 'create_student', f'Created student {name}', request.remote_addr)
            flash('Student created successfully!', 'success')
            return redirect(url_for('super_admin.students'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating student: {str(e)}', 'danger')
    
    schools = School.query.all()
    sections = Section.query.all()
    return render_template('super_admin/create_student.html', schools=schools, sections=sections)

@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        student.name = request.form.get('name')
        
        # Handle age by converting to birth_date
        age = int(request.form.get('age')) if request.form.get('age') else None
        if age:
            from datetime import date
            current_year = date.today().year
            student.birth_date = date(current_year - age, 1, 1)  # Approximate birth date
        
        student.gender = request.form.get('gender')
        student.height = float(request.form.get('height')) if request.form.get('height') else None
        student.weight = float(request.form.get('weight')) if request.form.get('weight') else None
        
        # Calculate BMI if height and weight are provided
        if student.height and student.weight:
            height_m = student.height / 100  # Convert cm to meters
            student.bmi = round(student.weight / (height_m ** 2), 2)
        
        # Update school and section
        school_id = request.form.get('school_id')
        section_id = request.form.get('section_id')
        
        if school_id:
            student.school_id = int(school_id)
        if section_id:
            student.section_id = int(section_id)
        
        try:
            db.session.commit()
            
            # Send notification to student
            changes = []
            if request.form.get('name') != student.name:
                changes.append("Name updated")
            if age and age != student.age:
                changes.append("Age updated")
            if request.form.get('height') and float(request.form.get('height')) != student.height:
                changes.append("Height updated")
            if request.form.get('weight') and float(request.form.get('weight')) != student.weight:
                changes.append("Weight updated")
            
            if changes:
                NotificationService.notify_student_updated(
                    student_id=student.id,
                    updated_by_name=current_user.name,
                    changes="\n".join(changes)
                )
            
            log_activity(current_user.id, 'edit_student', f'Updated student {student.name} profile information', request.remote_addr)
            flash('Student updated successfully!', 'success')
            return redirect(url_for('super_admin.students'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'danger')
    
    schools = School.query.all()
    sections = Section.query.filter_by(school_id=student.school_id).all() if student.school_id else []
    
    return render_template('super_admin/edit_student.html', 
                         student=student, 
                         schools=schools, 
                         sections=sections)

@bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    
    try:
        # Store student details before deletion
        student_name = student.name
        school_name = student.school.name if student.school else "unknown school"
        
        # Delete associated user account if exists
        if student.user:
            # First, delete all notifications associated with this student's user account
            from app.models.notification import Notification
            Notification.query.filter_by(recipient_id=student.user.id).delete()
            
            # Delete all user activities associated with this student's user account
            from app.models.user_activity import UserActivity
            UserActivity.query.filter_by(user_id=student.user.id).delete()
            db.session.delete(student.user)
        
        db.session.delete(student)
        db.session.commit()
        log_activity(current_user.id, 'delete_student', f'Deleted student {student_name} from {school_name}', request.remote_addr)
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
    
    return redirect(url_for('super_admin.students'))

@bp.route('/reports')
@login_required
def reports():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    log_activity(current_user.id, 'view_reports', 'Accessed reports dashboard', request.remote_addr)
    
    # Get report notifications sent to super admins
    from app.models.notification import Notification
    admin_id = request.args.get('admin_id', type=int)
    
    # Get all report notifications
    reports_query = Notification.query.filter_by(
        notification_type='report_generated'
    ).order_by(Notification.created_at.desc())
    
    # Filter by admin if specified
    if admin_id:
        # Get the admin's school to filter notifications
        admin = User.query.get(admin_id)
        if admin and admin.school_id:
            reports_query = reports_query.filter_by(related_entity_id=admin.school_id)
    
    reports = reports_query.all()
    
    # Get admin and school data for display
    admins = {u.id: u for u in User.query.filter_by(role='admin').all()}
    schools = {s.id: s for s in School.query.all()}
    
    # Create a mapping of reports with additional data
    report_data = []
    for report in reports:
        school = schools.get(report.related_entity_id) if report.related_entity_id else None
        admin = None
        student_count = 0
        
        if school:
            # Find the admin for this school
            admin = next((a for a in admins.values() if a.school_id == school.id), None)
            # Get student count for this school
            student_count = Student.query.filter_by(school_id=school.id).count()
        
        report_data.append({
            'notification': report,
            'admin': admin,
            'school': school,
            'student_count': student_count
        })
    
    return render_template('super_admin/reports.html', 
                         reports=report_data, 
                         admins=admins, 
                         schools=schools, 
                         selected_admin_id=admin_id) 

@bp.route('/reports/<int:notification_id>/view')
@login_required
def view_report_details(notification_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    from app.models.notification import Notification
    notification = Notification.query.get_or_404(notification_id)
    
    # Get school and admin details
    school = School.query.get(notification.related_entity_id) if notification.related_entity_id else None
    admin = None
    students = []
    
    if school:
        admin = User.query.filter_by(school_id=school.id, role='admin').first()
        students = Student.query.filter_by(school_id=school.id).all()
    
    # Mark as read if not already
    if not notification.is_read:
        notification.mark_as_read()
    
    log_activity(current_user.id, 'view_report_details', f'Viewed report details for notification {notification_id}', request.remote_addr)
    
    return render_template('super_admin/view_report_details.html', 
                         notification=notification, 
                         admin=admin, 
                         school=school, 
                         students=students)

@bp.route('/reports/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_report_read(notification_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('super_admin.reports'))
    
    from app.models.notification import Notification
    notification = Notification.query.get_or_404(notification_id)
    
    try:
        notification.mark_as_read()
        log_activity(current_user.id, 'mark_report_read', f'Marked report notification {notification_id} as read', request.remote_addr)
        flash('Report marked as read!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking report as read: {str(e)}', 'danger')
    
    return redirect(url_for('super_admin.reports'))

@bp.route('/reports/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_report_notification(notification_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('super_admin.reports'))
    
    from app.models.notification import Notification
    notification = Notification.query.get_or_404(notification_id)
    
    try:
        # Store notification details for logging before deletion
        notification_title = notification.title
        school_id = notification.related_entity_id
        school_name = "Unknown School"
        
        if school_id:
            school = School.query.get(school_id)
            if school:
                school_name = school.name
        
        # Delete the notification
        db.session.delete(notification)
        db.session.commit()
        
        log_activity(current_user.id, 'delete_report', f'Deleted report notification "{notification_title}" from {school_name}', request.remote_addr)
        flash('Report deleted successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting report: {str(e)}', 'danger')
        log_activity(current_user.id, 'delete_report_error', f'Failed to delete report notification {notification_id}: {str(e)}', request.remote_addr)
    
    return redirect(url_for('super_admin.reports'))
    return redirect(url_for('super_admin.reports'))

# --- EXPORT SCHOOL REPORT FILES (SUPER ADMIN) ---
@bp.route('/reports/school/<int:school_id>/export')
@login_required
def export_school_excel(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))

    school = School.query.get_or_404(school_id)
    students = Student.query.filter_by(school_id=school_id).all()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Students')

    header = workbook.add_format({'bold': True, 'bg_color': '#667eea', 'font_color': 'white'})
    center = workbook.add_format({'align': 'center'})

    headers = ['Name', 'Section', 'Gender', 'Birthdate', 'Age', 'Height (cm)', 'Weight (kg)', 'BMI']
    for col, h in enumerate(headers):
        worksheet.write(0, col, h, header)

    row = 1
    for s in students:
        worksheet.write(row, 0, s.name or '')
        worksheet.write(row, 1, s.section.name if s.section else '')
        worksheet.write(row, 2, s.gender or '', center)
        worksheet.write(row, 3, s.birth_date.strftime('%Y-%m-%d') if s.birth_date else '', center)
        worksheet.write(row, 4, s.age if hasattr(s, 'age') and s.age is not None else '', center)
        worksheet.write(row, 5, s.height if s.height is not None else '', center)
        worksheet.write(row, 6, s.weight if s.weight is not None else '', center)
        worksheet.write(row, 7, s.bmi if s.bmi is not None else '', center)
        row += 1

    worksheet.set_column(0, 0, 28)
    worksheet.set_column(1, 1, 22)
    worksheet.set_column(2, 7, 14)

    workbook.close()
    output.seek(0)

    filename = f'{school.name.replace(" ", "_")}_students.xlsx'
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     download_name=filename, as_attachment=True)

@bp.route('/reports/school/<int:school_id>/export_pdf')
@login_required
def export_school_pdf(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))

    school = School.query.get_or_404(school_id)
    students = Student.query.filter_by(school_id=school_id).all()

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    styles = getSampleStyleSheet()
    flow = []

    flow.append(Paragraph(f'Student Report - {school.name}', styles['Title']))
    flow.append(Spacer(1, 12))

    data = [['Name', 'Section', 'Gender', 'Birthdate', 'Age', 'Height (cm)', 'Weight (kg)', 'BMI']]
    for s in students:
        data.append([
            s.name or '',
            s.section.name if s.section else '',
            s.gender or '',
            s.birth_date.strftime('%Y-%m-%d') if s.birth_date else '',
            s.age if hasattr(s, 'age') and s.age is not None else '',
            s.height if s.height is not None else '',
            s.weight if s.weight is not None else '',
            f'{s.bmi:.1f}' if s.bmi is not None else ''
        ])

    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e9eefb')),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('ALIGN', (2,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fafbff')]),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    flow.append(tbl)

    doc.build(flow)
    output.seek(0)

    filename = f'{school.name.replace(" ", "_")}_students.pdf'
    return send_file(output, mimetype='application/pdf', download_name=filename, as_attachment=True)
@bp.route('/schools')
@login_required
def schools():
    log_activity(current_user.id, 'view_schools', 'Accessed schools management page', request.remote_addr)
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    search_query = request.args.get('search_query', '').strip()
    schools_query = School.query
    
    if search_query:
        like = f"%{search_query}%"
        # Case-insensitive match on name or address
        schools_query = schools_query.filter(
            (School.name.ilike(like)) | (School.address.ilike(like))
        )
    
    schools = schools_query.all()
    return render_template('super_admin/schools.html', schools=schools, search_query=search_query)

@bp.route('/schools/create', methods=['GET', 'POST'])
@login_required
def create_school():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        email = request.form.get('email')
        
        # Check if school name already exists
        if School.query.filter_by(name=name).first():
            flash('School name already exists', 'danger')
            return render_template('super_admin/create_school.html')
        
        school = School(
            name=name,
            address=address,
            contact_number=contact_number,
            email=email
        )
        
        try:
            db.session.add(school)
            db.session.commit()
            log_activity(current_user.id, 'create_school', f'Created school {name} at {address}', request.remote_addr)
            flash('School created successfully!', 'success')
            return redirect(url_for('super_admin.schools'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating school: {str(e)}', 'danger')
    
    return render_template('super_admin/create_school.html')

@bp.route('/schools/<int:school_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_school(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    school = School.query.get_or_404(school_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        contact_number = request.form.get('contact_number')
        email = request.form.get('email')
        
        # Check if school name already exists (excluding current school)
        existing_school = School.query.filter(School.name == name, School.id != school_id).first()
        if existing_school:
            flash('School name already exists', 'danger')
            return render_template('super_admin/edit_school.html', school=school)
        
        school.name = name
        school.address = address
        school.contact_number = contact_number
        school.email = email
        
        try:
            db.session.commit()
            log_activity(current_user.id, 'edit_school', f'Updated school {name} information', request.remote_addr)
            flash('School updated successfully!', 'success')
            return redirect(url_for('super_admin.schools'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating school: {str(e)}', 'danger')
    
    return render_template('super_admin/edit_school.html', school=school)

@bp.route('/schools/<int:school_id>/delete', methods=['POST'])
@login_required
def delete_school(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    school = School.query.get_or_404(school_id)
    
    # Check if school has associated admins or students
    admin_count = User.query.filter_by(school_id=school_id).count()
    student_count = Student.query.filter_by(school_id=school_id).count()
    
    if admin_count > 0 or student_count > 0:
        flash(f'Cannot delete school. It has {admin_count} administrators and {student_count} students associated with it.', 'danger')
        return redirect(url_for('super_admin.schools'))
    
    try:
        db.session.delete(school)
        db.session.commit()
        log_activity(current_user.id, 'delete_school', f'Deleted school {school.name} and all associated data', request.remote_addr)
        flash('School deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting school: {str(e)}', 'danger')
    
    return redirect(url_for('super_admin.schools')) 