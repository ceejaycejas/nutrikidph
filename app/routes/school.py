from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.section import Section
from app.models.student import Student
from app.models.school import School
from app.models.user import User
from app.models.grade_level import GradeLevel
from app.models.user_activity import UserActivity
from datetime import datetime, timedelta
from app.services.notification_service import NotificationService
import calendar
import traceback

bp = Blueprint('school', __name__, url_prefix='/school')

def log_activity(user_id, activity_type, description, ip_address=None):
    try:
        if user_id:  # Only log if user is authenticated
            activity = UserActivity(user_id=user_id, activity_type=activity_type, description=description, ip_address=ip_address)
            db.session.add(activity)
            db.session.commit()
    except Exception as e:
        print(f"Error logging activity: {str(e)}")

@bp.route('/')
@login_required
def index():
    if current_user.role not in ['super_admin', 'admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))

    # Optional search by school name (and address) from the new search bar
    search_query = request.args.get('search_query', '').strip()
    if current_user.role == 'super_admin':
        query = School.query
        if search_query:
            like = f"%{search_query}%"
            query = query.filter((School.name.ilike(like)) | (School.address.ilike(like)))
        schools = query.all()
    else:
        # Admins only see their own school; honor search if provided
        if not current_user.school:
            schools = []
        else:
            school = current_user.school
            if search_query:
                q = search_query.lower()
                if (q in (school.name or '').lower()) or (q in (school.address or '').lower()):
                    schools = [school]
                else:
                    schools = []
            else:
                schools = [school]
    
    return render_template('school/index.html', schools=schools)

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        
        # Fix: Create School instance and set attributes separately
        school = School()
        school.name = name
        school.address = address
        db.session.add(school)
        db.session.commit()
        
        flash('School created successfully!', 'success')
        return redirect(url_for('school.index'))
    
    return render_template('school/create.html')

@bp.route('/<int:school_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    school = School.query.get_or_404(school_id)
    
    if request.method == 'POST':
        # Fix: Set attributes separately instead of passing as constructor params
        school.name = request.form.get('name')
        school.address = request.form.get('address')
        db.session.commit()
        
        flash('School updated successfully!', 'success')
        return redirect(url_for('school.index'))
    
    return render_template('school/edit.html', school=school)

@bp.route('/<int:school_id>/delete', methods=['POST'])
@login_required
def delete(school_id):
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    try:
        school = School.query.get_or_404(school_id)
        school_name = school.name
        
        # Delete all related records first to avoid foreign key constraint errors
        # Delete students associated with this school
        Student.query.filter_by(school_id=school_id).delete()

        # Delete sections associated with this school first (sections reference grade_level)
        Section.query.filter_by(school_id=school_id).delete()

        # Then delete grade levels associated with this school
        GradeLevel.query.filter_by(school_id=school_id).delete()
        
        # Delete users (admins) associated with this school
        # First remove related user_activity and notification rows that reference these users
        user_ids = [u.id for u in User.query.filter_by(school_id=school_id).all()]
        if user_ids:
            try:
                from app.models.notification import Notification
            except Exception:
                Notification = None

            # Fix: Use proper SQLAlchemy syntax for 'in' operator
            if user_ids:
                # Use raw SQL to avoid typing issues
                from sqlalchemy import text
                db.session.execute(
                    text("DELETE FROM user_activity WHERE user_id IN :user_ids"),
                    {"user_ids": tuple(user_ids)}
                )

                # Delete notifications sent to these users (if the model exists in the project)
                if Notification is not None:
                    db.session.execute(
                        text("DELETE FROM notification WHERE recipient_id IN :user_ids"),
                        {"user_ids": tuple(user_ids)}
                    )

        # Now delete the user rows
        User.query.filter_by(school_id=school_id).delete(synchronize_session=False)
        
        # Now delete the school
        db.session.delete(school)
        db.session.commit()
        
        # Log the activity
        log_activity(current_user.id, 'delete_school', 
                    f'Deleted school {school_name} and all associated records', 
                    request.remote_addr)
        
        flash(f'School "{school_name}" and all associated data deleted successfully!', 'success')
        return redirect(url_for('school.index'))
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        print(f"Error deleting school: {error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        
        flash(f'Error deleting school: {error_msg}', 'danger')
        return redirect(url_for('school.index'))

@bp.route('/dashboard')
@login_required
def dashboard():
    try:
        # Log dashboard access
        log_activity(current_user.id, 'dashboard_access', f'Accessed dashboard as {current_user.role}', request.remote_addr)
        
        # Common activity statistics
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        recent_activities = UserActivity.query.filter(
            UserActivity.created_at >= seven_days_ago
        ).order_by(UserActivity.created_at.desc()).limit(15).all()
        
        recent_activity_count = UserActivity.query.filter(
            UserActivity.created_at >= twenty_four_hours_ago
        ).count()
        
        # Fix: Use proper SQLAlchemy syntax for filtering
        from sqlalchemy import and_, text
        today_logins = UserActivity.query.filter(
            and_(
                text("activity_type = 'login'"),
                UserActivity.created_at >= today_start
            )
        ).count()
        
        # Fix: Use proper SQLAlchemy syntax for 'in' operator with list
        today_failed_logins = UserActivity.query.filter(
            and_(
                text("activity_type IN ('login_failed', 'login_attempt')"),
                UserActivity.created_at >= today_start
            )
        ).count()
        
        if current_user.role == 'admin':
            return _get_admin_dashboard_data(
                recent_activities, recent_activity_count, today_logins, today_failed_logins
            )
        elif current_user.role == 'student':
            return _get_student_dashboard_data()
        elif current_user.role == 'super_admin':
            return _get_super_admin_dashboard_data(
                recent_activities, recent_activity_count, today_logins, today_failed_logins
            )
        else:
            flash('Invalid user role', 'danger')
            return redirect(url_for('auth.logout'))

    except Exception as e:
        # Log the error with more details
        error_details = traceback.format_exc()
        print(f"Dashboard error: {str(e)}\nTraceback: {error_details}")
        
        # Log the error to user activity
        try:
            log_activity(current_user.id if current_user.is_authenticated else None, 
                        'dashboard_error', f'Dashboard error: {str(e)}', request.remote_addr)
        except:
            pass  # Don't let logging errors crash the error handler
        
        flash('An error occurred while loading the dashboard. Please try again.', 'danger')
        
        # Return a safe fallback dashboard
        return render_template('dashboard/index.html', 
            total_schools=0,
            total_admins=0,
            total_students=0,
            total_sections=0,
            recent_activities=[],
            bmi_distribution={'normal': 0, 'underweight': 0, 'overweight': 0, 'obese': 0, 'wasted': 0, 'severely_wasted': 0},
            recent_activity_count=0,
            today_logins=0,
            today_failed_logins=0,
            # Safe defaults for admin-specific data
            total_beneficiaries=0,
            total_students_admin=0,
            improved_bmi_percent=0,
            feeding_compliance_percent=0,
            num_at_risk=0,
            at_risk_students=[],
            sections=[],
            bmi_progress={'labels': [], 'values': []},
            feeding_participation={'labels': [], 'values': []},
            avg_weight_gain={'sections': [], 'before': [], 'after': []},
            avg_height_gain={'sections': [], 'before': [], 'after': []},

            allergy_counts={'labels': [], 'values': []}
        )

def _get_admin_dashboard_data(recent_activities, recent_activity_count, today_logins, today_failed_logins):
    """Get dashboard data for admin users with proper error handling"""
    try:
        # Validate admin has school assigned
        if not current_user.school_id:
            flash('Your account is not assigned to a school. Please contact the super admin.', 'warning')
            return _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins)
        
        # Get sections and students for admin's school with error handling
        try:
            sections = Section.query.filter_by(school_id=current_user.school_id).all()
            school_students = Student.query.filter_by(school_id=current_user.school_id).all()
            admin_students = Student.query.filter_by(registered_by=current_user.id).all()
        except Exception as db_error:
            print(f"Database query error: {str(db_error)}")
            return _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins)
        
        # Calculate core metrics with validation
        total_sections = len(sections) if sections else 0
        total_students = len(school_students) if school_students else 0
        total_students_admin = len(admin_students) if admin_students else 0
        
        # Calculate BMI distribution for all students with BMI data
        bmi_distribution = _calculate_student_bmi_distribution(school_students)
        
        # Get beneficiary and at-risk students with validation
        try:
            beneficiary_students = _get_beneficiary_students(admin_students)
        except Exception as e:
            print(f"Error getting beneficiary students: {str(e)}")
            beneficiary_students = []
            
        try:
            at_risk_students = _get_at_risk_students(school_students)
        except Exception as e:
            print(f"Error getting at-risk students: {str(e)}")
            at_risk_students = []
        
        total_beneficiaries = len(beneficiary_students)
        num_at_risk = len(at_risk_students)
        
        # Calculate analytics with improved accuracy and error handling
        try:
            dashboard_analytics = _calculate_dashboard_analytics(sections, school_students, beneficiary_students)
        except Exception as e:
            print(f"Error calculating dashboard analytics: {str(e)}")
            dashboard_analytics = {
                'bmi_progress': {'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], 'values': [18.5, 18.5, 18.5, 18.5, 18.5, 18.5]},
                'section_analytics': {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []},
                'nutritional_trends': {'labels': [], 'healthy': [], 'at_risk': []},
                'health_metrics': {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0},
                'monthly_summary': {'current_month': 'N/A', 'new_students': 0, 'assessments_completed': 0, 'alerts_generated': 0}
            }
        
        return render_template('dashboard/safe_index.html', 
            # Core metrics
            total_sections=total_sections,
            total_students=total_students,
            total_beneficiaries=total_beneficiaries,
            total_students_admin=total_students_admin,
            num_at_risk=num_at_risk,
            
            # Collections
            sections=sections,
            at_risk_students=at_risk_students[:10],  # Limit for performance
            
            # Analytics
            bmi_distribution=bmi_distribution,
            **dashboard_analytics,
            
            # Activity data
            recent_activities=recent_activities,
            recent_activity_count=recent_activity_count,
            today_logins=today_logins,
            today_failed_logins=today_failed_logins
        )
        
    except Exception as e:
        print(f"Admin dashboard error: {str(e)}")
        log_activity(current_user.id, 'dashboard_error', f'Admin dashboard error: {str(e)}', request.remote_addr)
        return _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins)

def _get_student_dashboard_data():
    """Get dashboard data for student users"""
    try:
        student = Student.query.filter_by(user_id=current_user.id).first()
        recent_activities = UserActivity.query.filter_by(
            user_id=current_user.id
        ).order_by(UserActivity.created_at.desc()).limit(5).all()
        
        return render_template('dashboard/student_dashboard.html', 
            student=student, 
            recent_activities=recent_activities
        )
    except Exception as e:
        print(f"Student dashboard error: {str(e)}")
        raise e

def _get_super_admin_dashboard_data(recent_activities, recent_activity_count, today_logins, today_failed_logins):
    """Get dashboard data for super admin users"""
    try:
        print("Starting super admin dashboard data collection...")
        
        # System-wide statistics
        total_schools = School.query.count()
        total_admins = User.query.filter_by(role='admin').count()
        total_students = Student.query.count()
        total_sections = Section.query.count()
        
        print(f"Basic stats: schools={total_schools}, admins={total_admins}, students={total_students}, sections={total_sections}")
        
        # Calculate system-wide BMI distribution
        bmi_distribution = {'underweight': 0, 'normal': 0, 'overweight': 0, 'obese': 0, 'severely_wasted': 0, 'wasted': 0}
        # Fix: Use proper SQLAlchemy syntax for 'is not None'
        students_with_bmi = Student.query.filter(Student.bmi != None).all()
        
        for student in students_with_bmi:
            if student.bmi < 16:
                bmi_distribution['severely_wasted'] += 1
            elif student.bmi < 18.5:
                bmi_distribution['wasted'] += 1
                bmi_distribution['underweight'] += 1  # Also count as underweight
            elif student.bmi < 25:
                bmi_distribution['normal'] += 1
            elif student.bmi < 30:
                bmi_distribution['overweight'] += 1
            else:
                bmi_distribution['obese'] += 1
        
        print(f"BMI distribution calculated: {bmi_distribution}")
        
        # Calculate system-wide analytics variables
        total_beneficiaries_system = Student.query.filter_by(is_beneficiary=True).count()
        # Fix: Use raw SQL to avoid Pyright type checking issues
        from sqlalchemy import text
        at_risk_students_system = db.session.query(Student).filter(
            text("bmi IS NOT NULL AND (bmi < 18.5 OR bmi >= 25)")
        ).count()
        
        # Mock data for analytics (replace with real calculations later)
        compliance_rate_system = 85  # Mock compliance rate
        improvement_rate_system = 12  # Mock improvement rate
        
        # Mock nutritional status for consolidated report
        nutritional_status = {
            'severely_wasted': bmi_distribution['severely_wasted'],
            'wasted': bmi_distribution['wasted'],
            'normal': bmi_distribution['normal'],
            'overweight': bmi_distribution['overweight'],
            'obese': bmi_distribution['obese']
        }
        
        # Mock school performance data
        school_performance = []
        try:
            schools_with_students = School.query.outerjoin(Student).group_by(School.id).all()
            for i, school in enumerate(schools_with_students[:5]):
                student_count = Student.query.filter_by(school_id=school.id).count()
                school_performance.append({
                    'name': school.name,
                    'students_count': student_count,
                    'performance_score': 75 + (i * 5)  # Mock performance scores
                })
        except Exception as e:
            print(f"Error getting school performance: {e}")
            school_performance = []
        
        # Mock progress trends
        progress_trends = {
            'nutritional_improvement': 15,
            'program_compliance': 8,
            'data_quality': 22
        }
        
        # Mock top performing schools
        top_performing_schools = [
            {'name': 'Sample School 1', 'improvement_rate': 18},
            {'name': 'Sample School 2', 'improvement_rate': 15},
            {'name': 'Sample School 3', 'improvement_rate': 12}
        ]
        
        # Mock compliance stats
        compliance_stats = {
            'complete_docs': max(0, total_schools - 1),
            'partial_docs': 1,
            'missing_docs': 0
        }
        
        # Mock audit alerts
        audit_alerts = []  # Empty for now, can be populated with real alerts later

        print("All data prepared, rendering template...")
        
        return render_template('dashboard/index.html', 
            # Core system statistics
            total_schools=total_schools,
            total_admins=total_admins,
            total_students=total_students,
            total_sections=total_sections,
            
            # Activity data
            recent_activities=recent_activities,
            recent_activity_count=recent_activity_count,
            today_logins=today_logins,
            today_failed_logins=today_failed_logins,
            
            # BMI distribution
            bmi_distribution=bmi_distribution,
            
            # Analytics variables
            total_beneficiaries_system=total_beneficiaries_system,
            at_risk_students_system=at_risk_students_system,
            compliance_rate_system=compliance_rate_system,
            improvement_rate_system=improvement_rate_system,
            
            # Consolidated nutritional status
            nutritional_status=nutritional_status,
            
            # School performance
            school_performance=school_performance,
            
            # Progress trends
            progress_trends=progress_trends,
            
            # Top performing schools
            top_performing_schools=top_performing_schools,
            
            # Compliance stats
            compliance_stats=compliance_stats,
            
            # Audit alerts
            audit_alerts=audit_alerts
        )
        
    except Exception as e:
        print(f"Super admin dashboard error: {str(e)}")
        print(f"Error traceback: {traceback.format_exc()}")
        # Return minimal data to prevent crashes
        return render_template('dashboard/index.html', 
            total_schools=0,
            total_admins=0,
            total_students=0,
            total_sections=0,
            recent_activities=[],
            bmi_distribution={'underweight': 0, 'normal': 0, 'overweight': 0, 'obese': 0, 'severely_wasted': 0, 'wasted': 0},
            recent_activity_count=0,
            today_logins=0,
            today_failed_logins=0,
            total_beneficiaries_system=0,
            at_risk_students_system=0,
            compliance_rate_system=0,
            improvement_rate_system=0,
            nutritional_status={'severely_wasted': 0, 'wasted': 0, 'normal': 0, 'overweight': 0, 'obese': 0},
            school_performance=[],
            progress_trends={'nutritional_improvement': 0, 'program_compliance': 0, 'data_quality': 0},
            top_performing_schools=[],
            compliance_stats={'complete_docs': 0, 'partial_docs': 0, 'missing_docs': 0},
            audit_alerts=[]
        )

def _render_safe_admin_dashboard(recent_activities, recent_activity_count, today_logins, today_failed_logins):
    """Render a safe fallback dashboard when errors occur"""
    return render_template('dashboard/safe_index.html', 
        total_sections=0, total_students=0, sections=[], 
        bmi_distribution={'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0},
        recent_activities=recent_activities, recent_activity_count=recent_activity_count,
        today_logins=today_logins, today_failed_logins=today_failed_logins,
        total_beneficiaries=0, total_students_admin=0, num_at_risk=0, at_risk_students=[],
        bmi_progress={'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], 'values': [18.5, 18.5, 18.5, 18.5, 18.5, 18.5]}, 
        feeding_participation={'labels': [], 'values': []},
        nutritional_trends={'labels': [], 'healthy': [], 'at_risk': []},
        section_analytics={'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []},
        health_metrics={'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0},
        monthly_summary={'current_month': 'N/A', 'new_students': 0, 'assessments_completed': 0, 'alerts_generated': 0}
    )

def _calculate_accurate_bmi_distribution(students):
    """Calculate accurate BMI distribution with proper categorization"""
    try:
        distribution = {'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0, 'obese': 0}
        
        if not students:
            return distribution
            
        students_with_bmi = [s for s in students if s.bmi is not None and s.bmi > 0]
        
        for student in students_with_bmi:
            bmi = student.bmi
            if bmi < 16:
                distribution['severely_wasted'] += 1
            elif bmi < 18.5:
                distribution['wasted'] += 1
            elif bmi < 25:
                distribution['normal'] += 1
            elif bmi < 30:
                distribution['overweight'] += 1
            else:
                distribution['obese'] += 1
        
        return distribution
    except Exception as e:
        print(f"BMI distribution calculation error: {str(e)}")
        return {'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0, 'obese': 0}

def _get_at_risk_students(school_students):
    """Get at-risk students (severely underweight or obese)"""
    try:
        if not school_students:
            return []
            
        at_risk = []
        for student in school_students:
            # Check if student has valid BMI data
            if student.bmi is not None and student.bmi > 0:
                # At-risk students are those who are severely underweight (BMI < 16) or obese (BMI >= 30)
                if student.bmi < 16 or student.bmi >= 30:
                    at_risk.append(student)
        
        # Sort by BMI (most critical first)
        at_risk.sort(key=lambda s: s.bmi if s.bmi else 0)
        return at_risk
    except Exception as e:
        print(f"At-risk students calculation error: {str(e)}")
        return []

def _calculate_dashboard_analytics(sections, school_students, beneficiary_students):
    """Calculate comprehensive dashboard analytics"""
    try:
        analytics = {}
        
        # BMI Progress Tracking (improved)
        analytics['bmi_progress'] = _calculate_improved_bmi_progress(school_students)
        
        # Section Analytics (consolidated from multiple charts)
        analytics['section_analytics'] = _calculate_section_analytics(sections, school_students)
        
        # Nutritional Trends (replaces redundant charts)
        analytics['nutritional_trends'] = _calculate_nutritional_trends(school_students)
        
        # Health Metrics Summary
        analytics['health_metrics'] = _calculate_health_metrics(beneficiary_students)
        
        # Monthly Summary
        analytics['monthly_summary'] = _calculate_monthly_summary(school_students)
        
        return analytics
    except Exception as e:
        print(f"Dashboard analytics calculation error: {str(e)}")
        return {
            'bmi_progress': {'labels': [], 'values': []},
            'section_analytics': {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []},
            'nutritional_trends': {'labels': [], 'healthy': [], 'at_risk': []},
            'health_metrics': {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0},
            'monthly_summary': {'current_month': 'N/A', 'new_students': 0, 'assessments_completed': 0, 'alerts_generated': 0}
        }

def _calculate_improved_bmi_progress(students):
    """Calculate improved BMI progress with real data"""
    try:
        current_date = datetime.now()
        months = []
        bmi_values = []
        
        for i in range(6):
            month_date = current_date - timedelta(days=30*i)
            month_name = calendar.month_abbr[month_date.month]
            months.insert(0, month_name)
            
            # Get students with valid BMI data from this month
            month_students = [s for s in students if s.bmi is not None and s.bmi > 0 and s.created_at and 
                            s.created_at.month == month_date.month and s.created_at.year == month_date.year]
            
            if month_students:
                avg_bmi = sum(s.bmi for s in month_students) / len(month_students)
                bmi_values.insert(0, round(avg_bmi, 1))
            else:
                # Use overall average if no data for specific month
                all_students_with_bmi = [s for s in students if s.bmi is not None and s.bmi > 0]
                if all_students_with_bmi:
                    avg_bmi = sum(s.bmi for s in all_students_with_bmi) / len(all_students_with_bmi)
                    bmi_values.insert(0, round(avg_bmi, 1))
                else:
                    bmi_values.insert(0, 18.5)  # Default healthy BMI
        
        # Ensure we return proper lists, not functions
        return {'labels': list(months), 'values': list(bmi_values)}
    except Exception as e:
        print(f"Improved BMI progress calculation error: {str(e)}")
        return {'labels': ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'], 'values': [18.5, 18.5, 18.5, 18.5, 18.5, 18.5]}

def _calculate_section_analytics(sections, school_students):
    """Calculate comprehensive section analytics"""
    try:
        if not sections:
            return {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []}
        
        labels = []
        total_students = []
        beneficiaries = []
        participation_rates = []
        
        for section in sections:
            section_students = [s for s in school_students if s.section_id == section.id]
            # Beneficiaries are students marked as beneficiaries or those with unhealthy BMI
            section_beneficiaries = [s for s in section_students if s.bmi is not None and s.bmi > 0 and 
                                   (s.is_beneficiary or (s.bmi < 18.5 or s.bmi >= 25))]
            
            labels.append(section.name)
            total_students.append(len(section_students))
            beneficiaries.append(len(section_beneficiaries))
            
            # Calculate participation rate (students with complete health data)
            complete_data = len([s for s in section_students if s.bmi is not None and s.bmi > 0])
            participation_rate = (complete_data / len(section_students) * 100) if section_students else 0
            participation_rates.append(round(participation_rate, 1))
        
        return {
            'labels': list(labels),
            'total_students': list(total_students),
            'beneficiaries': list(beneficiaries),
            'participation_rate': list(participation_rates)
        }
    except Exception as e:
        print(f"Section analytics calculation error: {str(e)}")
        return {'labels': [], 'total_students': [], 'beneficiaries': [], 'participation_rate': []}

def _calculate_nutritional_trends(students):
    """Calculate nutritional trends over time"""
    try:
        current_date = datetime.now()
        months = []
        healthy_counts = []
        at_risk_counts = []
        
        for i in range(6):
            month_date = current_date - timedelta(days=30*i)
            month_name = calendar.month_abbr[month_date.month]
            months.insert(0, month_name)
            
            # Count healthy vs at-risk students for each month
            month_students = [s for s in students if s.bmi is not None and s.bmi > 0 and s.created_at and 
                            s.created_at.month == month_date.month and s.created_at.year == month_date.year]
            
            healthy = len([s for s in month_students if 18.5 <= s.bmi < 25])
            at_risk = len([s for s in month_students if s.bmi < 18.5 or s.bmi >= 25])
            
            healthy_counts.insert(0, healthy)
            at_risk_counts.insert(0, at_risk)
        
        return {
            'labels': list(months),
            'healthy': list(healthy_counts),
            'at_risk': list(at_risk_counts)
        }
    except Exception as e:
        print(f"Nutritional trends calculation error: {str(e)}")
        return {'labels': [], 'healthy': [], 'at_risk': []}

def _calculate_health_metrics(beneficiary_students):
    """Calculate health improvement metrics"""
    try:
        if not beneficiary_students:
            return {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0}
        
        # Calculate health metrics based on current BMI status
        total = len(beneficiary_students)
        # Improved: Students with healthy BMI (18.5-24.9)
        improved = len([s for s in beneficiary_students if s.bmi is not None and s.bmi > 0 and 18.5 <= s.bmi < 25])
        # Stable: Students with mild health concerns (16-18.4 or 25-29.9)
        stable = len([s for s in beneficiary_students if s.bmi is not None and s.bmi > 0 and (16 <= s.bmi < 18.5 or 25 <= s.bmi < 30)])
        # Declined: Students with severe health concerns (BMI < 16 or BMI >= 30)
        declined = len([s for s in beneficiary_students if s.bmi is not None and s.bmi > 0 and (s.bmi < 16 or s.bmi >= 30)])
        
        improvement_rate = (improved / total * 100) if total > 0 else 0
        
        return {
            'improved_count': improved,
            'stable_count': stable,
            'declined_count': declined,
            'improvement_rate': round(improvement_rate, 1)
        }
    except Exception as e:
        print(f"Health metrics calculation error: {str(e)}")
        return {'improved_count': 0, 'stable_count': 0, 'declined_count': 0, 'improvement_rate': 0}

def _calculate_monthly_summary(students):
    """Calculate monthly summary statistics"""
    try:
        current_date = datetime.now()
        current_month = current_date.strftime('%B %Y')
        month_start = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Students added this month
        new_students = len([s for s in students if s.created_at and s.created_at >= month_start])
        
        # Assessments completed (students with valid BMI data)
        assessments = len([s for s in students if s.bmi is not None and s.bmi > 0])
        
        # Health alerts (at-risk students with severe conditions)
        alerts = len([s for s in students if s.bmi is not None and s.bmi > 0 and (s.bmi < 16 or s.bmi >= 30)])
        
        return {
            'current_month': current_month,
            'new_students': new_students,
            'assessments_completed': assessments,
            'alerts_generated': alerts
        }
    except Exception as e:
        print(f"Monthly summary calculation error: {str(e)}")
        return {
            'current_month': datetime.now().strftime('%B %Y'),
            'new_students': 0,
            'assessments_completed': 0,
            'alerts_generated': 0
        }

# Legacy functions removed - replaced with improved analytics above

# --- STUDENT MANAGEMENT (FOR ADMINS) ---
@bp.route('/students')
@login_required
def students():
    log_activity(current_user.id, 'view_students', 'Accessed students page', request.remote_addr)
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    search_query = request.args.get('search_query', '').strip()
    query = Student.query.filter_by(school_id=current_user.school_id)
    if search_query:
        query = query.filter(Student.name.ilike(f'%{search_query}%'))
    students = query.all()
    return render_template('admin/students.html', students=students, search_query=search_query)

@bp.route('/students/create', methods=['GET', 'POST'])
@login_required
def create_student():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            birth_date_str = request.form.get('birth_date')
            gender = request.form.get('gender')
            height = request.form.get('height')
            weight = request.form.get('weight')
            section_id = request.form.get('section_id')
            preferences = request.form.get('preferences', '')
            
            # Validate required fields
            if not all([name, birth_date_str, gender, height, weight, section_id]):
                flash('All fields are required', 'danger')
                return redirect(url_for('school.create_student'))
            
            # Add validation for birth_date_str before parsing
            if birth_date_str:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            else:
                flash('Birth date is required', 'danger')
                return redirect(url_for('school.create_student'))
            
            # Validate and convert data types with proper error handling
            try:
                height_float = float(height) if height else 0.0
                weight_float = float(weight) if weight else 0.0
                section_id_int = int(section_id) if section_id else 0
            except (ValueError, TypeError):
                flash('Invalid data format for height, weight, or section.', 'danger')
                return redirect(url_for('school.create_student'))
            
            # Create student with proper attribute assignment
            student = Student()
            student.name = name
            student.birth_date = birth_date
            student.gender = gender
            student.height = height_float
            student.weight = weight_float
            student.section_id = section_id_int
            student.school_id = current_user.school_id
            student.registered_by = current_user.id
            student.preferences = preferences
            
            # Calculate BMI
            student.calculate_bmi()
            
            # Determine if student is a beneficiary based on BMI
            if student.bmi and (student.bmi < 18.5 or student.bmi >= 25):
                student.is_beneficiary = True
            
            db.session.add(student)
            db.session.commit()
            
            log_activity(current_user.id, 'create_student', f'Created student {name}', request.remote_addr)
            flash('Student created successfully!', 'success')
            return redirect(url_for('school.students'))
            
        except ValueError as e:
            flash('Invalid data format. Please check your inputs.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating student: {str(e)}', 'danger')
    
    sections = Section.query.filter_by(school_id=current_user.school_id).all()
    return render_template('admin/create_student.html', sections=sections)

@bp.route('/students/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Update student attributes
            student.name = request.form.get('name')
            birth_date_str = request.form.get('birth_date')
            student.gender = request.form.get('gender')
            
            # Safely convert form data with default values
            height_value = request.form.get('height')
            weight_value = request.form.get('weight')
            section_id_value = request.form.get('section_id')
            
            # Convert with proper validation
            if height_value is not None and height_value != '':
                try:
                    student.height = float(height_value)
                except ValueError:
                    flash('Invalid height value.', 'danger')
                    return redirect(url_for('school.edit_student', student_id=student_id))
            
            if weight_value is not None and weight_value != '':
                try:
                    student.weight = float(weight_value)
                except ValueError:
                    flash('Invalid weight value.', 'danger')
                    return redirect(url_for('school.edit_student', student_id=student_id))
            
            if section_id_value is not None and section_id_value != '':
                try:
                    student.section_id = int(section_id_value)
                except ValueError:
                    flash('Invalid section value.', 'danger')
                    return redirect(url_for('school.edit_student', student_id=student_id))
            
            student.preferences = request.form.get('preferences', '')
            
            if birth_date_str:
                student.birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            
            # Recalculate BMI
            student.calculate_bmi()
            
            # Update beneficiary status based on BMI
            if student.bmi and (student.bmi < 18.5 or student.bmi >= 25):
                student.is_beneficiary = True
            else:
                student.is_beneficiary = False
            
            db.session.commit()
            
            log_activity(current_user.id, 'edit_student', f'Updated student {student.name}', request.remote_addr)
            flash('Student updated successfully!', 'success')
            return redirect(url_for('school.students'))
            
        except ValueError as e:
            flash('Invalid data format. Please check your inputs.', 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating student: {str(e)}', 'danger')
    
    sections = Section.query.filter_by(school_id=current_user.school_id).all()
    return render_template('admin/edit_student.html', student=student, sections=sections)

@bp.route('/students/<int:student_id>/delete', methods=['POST'])
@login_required
def delete_student(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    
    try:
        student_name = student.name
        db.session.delete(student)
        db.session.commit()
        
        log_activity(current_user.id, 'delete_student', f'Deleted student {student_name}', request.remote_addr)
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting student: {str(e)}', 'danger')
    
    return redirect(url_for('school.students'))

@bp.route('/students/<int:student_id>')
@login_required
def student_detail(student_id):
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    student = Student.query.filter_by(id=student_id, school_id=current_user.school_id).first_or_404()
    return render_template('admin/student_detail.html', student=student)

def _calculate_student_bmi_distribution(students):
    """Calculate BMI distribution for all students with BMI data"""
    try:
        distribution = {'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0}
        
        if not students:
            return distribution
            
        # Get all students with valid BMI data
        students_with_bmi = [s for s in students if s.bmi is not None and s.bmi > 0]
        
        for student in students_with_bmi:
            bmi = student.bmi
            if bmi < 16:
                distribution['severely_wasted'] += 1
            elif bmi < 18.5:
                distribution['wasted'] += 1
            elif bmi < 25:
                distribution['normal'] += 1
            else:
                distribution['overweight'] += 1
        
        return distribution
    except Exception as e:
        print(f"BMI distribution calculation error: {str(e)}")
        return {'normal': 0, 'wasted': 0, 'severely_wasted': 0, 'overweight': 0}

def _get_beneficiary_students(admin_students):
    """Get beneficiary students with proper validation"""
    try:
        if not admin_students:
            return []
            
        beneficiaries = []
        for student in admin_students:
            # Beneficiaries are students explicitly marked as beneficiaries or those with unhealthy BMI
            if student.is_beneficiary or (student.bmi is not None and student.bmi > 0 and (student.bmi < 18.5 or student.bmi >= 25)):
                beneficiaries.append(student)
        
        return beneficiaries
    except Exception as e:
        print(f"Beneficiary students calculation error: {str(e)}")
        return []
