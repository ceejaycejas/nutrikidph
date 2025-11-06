from flask import Blueprint, render_template, send_file, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.models.section import Section
from app.models.student import Student
from app.models.school import School
from app.models.notification import Notification
from app.models.user import User
from app.models.user_activity import UserActivity
from app import db
import io
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import func, extract
import json

def log_activity(user_id, activity_type, description, ip_address=None):
    activity = UserActivity(user_id=user_id, activity_type=activity_type, description=description, ip_address=ip_address)
    db.session.add(activity)
    db.session.commit()

bp = Blueprint('reports', __name__, url_prefix='/reports')

@bp.route('/')
@login_required
def index():
    log_activity(current_user.id, 'view_reports', 'Accessed reports page', request.remote_addr)
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    # Get all students for the admin's school
    students = Student.query.filter_by(school_id=current_user.school_id).all()
    return render_template('reports/index.html', students=students)

@bp.route('/export')
@login_required
def export():
    try:
        log_activity(current_user.id, 'export_report', 'Exported student data report', request.remote_addr)
        if current_user.role != 'admin':
            flash('Unauthorized access', 'danger')
            return redirect(url_for('school.dashboard'))
        students = Student.query.filter_by(school_id=current_user.school_id).all()
        data = []
        for s in students:
            try:
                data.append({
                    'Name': s.name if s.name else '',
                    'Section': s.section.name if s.section else '',
                    'Gender': s.gender if s.gender else '',
                    'Birth Date': s.birth_date.strftime('%Y-%m-%d') if s.birth_date else '',
                    'Age': s.age if hasattr(s, 'age') and s.age is not None else '',
                    'Height (cm)': s.height if s.height is not None else '',
                    'Weight (kg)': s.weight if s.weight is not None else '',
                    'BMI': s.bmi if hasattr(s, 'bmi') and s.bmi is not None else '',
                    'Preferences/Allergies': s.preferences if hasattr(s, 'preferences') and s.preferences else '',
                })
            except Exception as e:
                # Skip problematic student records but log the error
                print(f"Error processing student {s.id if hasattr(s, 'id') else 'unknown'}: {str(e)}")
                continue
        
        # Create DataFrame and CSV file (no external dependencies needed)
        df = pd.DataFrame(data)
        output = io.StringIO()
        df.to_csv(output, index=False)
        
        # Convert to bytes for send_file
        output_bytes = io.BytesIO(output.getvalue().encode('utf-8'))
        output_bytes.seek(0)
        
        return send_file(
            output_bytes,
            mimetype='text/csv',
            download_name='student_nutritional_records.csv',
            as_attachment=True
        )
    
    except Exception as e:
        # Log the error
        print(f"Export error: {str(e)}")
        flash(f'Error exporting data: {str(e)}', 'danger')
        return redirect(url_for('reports.index'))

@bp.route('/send-to-super-admin', methods=['POST'])
@login_required
def send_to_super_admin():
    if current_user.role != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('reports.index'))
    
    try:
        # Find all super admins
        super_admins = User.query.filter_by(role='super_admin').all()
        admin_school = School.query.get(current_user.school_id)
        
        # Get student count for the report
        student_count = Student.query.filter_by(school_id=current_user.school_id).count()
        
        # Create notification for each super admin
        title = "New Student Nutritional Report Submitted"
        message = f"Admin {current_user.name} from {admin_school.name if admin_school else 'Unknown School'} has submitted a nutritional report for {student_count} students."
        
        for sa in super_admins:
            notif = Notification(
                recipient_id=sa.id,
                title=title,
                message=message,
                notification_type='report_generated',
                priority='medium',
                related_entity_type='school',
                related_entity_id=current_user.school_id,
                action_url='/super_admin/reports',
                action_text='View Reports'
            )
            db.session.add(notif)
        
        db.session.commit()
        log_activity(current_user.id, 'send_report', f'Sent nutritional report to super admins for {student_count} students', request.remote_addr)
        flash('Report sent successfully!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Error sending report. Please try again.', 'danger')
        log_activity(current_user.id, 'send_report_error', f'Failed to send report: {str(e)}', request.remote_addr)
    
    return redirect(url_for('reports.index'))



@bp.route('/api/nutritional-status')
@login_required
def api_nutritional_status():
    """API endpoint for Consolidated Student Nutritional Status Report (Doughnut Chart)"""
    if current_user.role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get students based on user role
        if current_user.role == 'super_admin':
            students = Student.query.all()
        else:
            students = Student.query.filter_by(school_id=current_user.school_id).all()
        
        # Categorize students by BMI status
        categories = {
            'Underweight': 0,
            'Normal Weight': 0,
            'Overweight': 0,
            'Obese': 0,
            'No Data': 0
        }
        
        for student in students:
            if student.bmi is None:
                categories['No Data'] += 1
            elif student.bmi < 18.5:
                categories['Underweight'] += 1
            elif student.bmi < 25:
                categories['Normal Weight'] += 1
            elif student.bmi < 30:
                categories['Overweight'] += 1
            else:
                categories['Obese'] += 1
        
        total_students = len(students)
        data = []
        colors = ['#ffc107', '#28a745', '#fd7e14', '#dc3545', '#6c757d']  # Yellow, Green, Orange, Red, Gray
        
        for i, (category, count) in enumerate(categories.items()):
            percentage = (count / total_students * 100) if total_students > 0 else 0
            data.append({
                'label': category,
                'value': count,
                'percentage': round(percentage, 1),
                'color': colors[i]
            })
        
        return jsonify({
            'success': True,
            'data': data,
            'total_students': total_students
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/school-performance')
@login_required
def api_school_performance():
    """API endpoint for School Performance Overview (Bar Chart)"""
    if current_user.role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get schools based on user role
        if current_user.role == 'super_admin':
            schools = School.query.all()
        else:
            schools = [School.query.get(current_user.school_id)] if current_user.school_id else []
        
        data = []
        colors = ['#007bff', '#28a745', '#ffc107', '#fd7e14', '#dc3545', '#6f42c1', '#20c997', '#e83e8c']
        
        for i, school in enumerate(schools):
            students = Student.query.filter_by(school_id=school.id).all()
            total_students = len(students)
            
            # Calculate metrics
            beneficiaries = sum(1 for s in students if s.is_beneficiary)
            at_risk = sum(1 for s in students if s.is_at_risk)
            completion_rate = (beneficiaries / total_students * 100) if total_students > 0 else 0
            
            data.append({
                'school_name': school.name,
                'total_students': total_students,
                'beneficiaries_served': beneficiaries,
                'at_risk_students': at_risk,
                'completion_rate': round(completion_rate, 1),
                'color': colors[i % len(colors)]
            })
        
        return jsonify({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/progress-report')
@login_required
def api_progress_report():
    """API endpoint for Comparative Progress Report (Line Chart)"""
    if current_user.role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get last 6 months data
        months_data = []
        current_date = datetime.now()
        
        for i in range(6):
            month_date = current_date - timedelta(days=30*i)
            month_name = month_date.strftime('%B %Y')
            
            # Get students created before this month
            if current_user.role == 'super_admin':
                students = Student.query.filter(Student.created_at <= month_date).all()
            else:
                students = Student.query.filter(
                    Student.created_at <= month_date,
                    Student.school_id == current_user.school_id
                ).all()
            
            # Calculate metrics
            total_students = len(students)
            beneficiaries = sum(1 for s in students if s.is_beneficiary)
            healthy_students = sum(1 for s in students if s.bmi and 18.5 <= s.bmi < 25)
            
            coverage_rate = (beneficiaries / total_students * 100) if total_students > 0 else 0
            health_rate = (healthy_students / total_students * 100) if total_students > 0 else 0
            
            months_data.append({
                'month': month_name,
                'total_students': total_students,
                'coverage_rate': round(coverage_rate, 1),
                'health_rate': round(health_rate, 1)
            })
        
        months_data.reverse()  # Show oldest to newest
        
        return jsonify({
            'success': True,
            'data': months_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@bp.route('/api/compliance-audit')
@login_required
def api_compliance_audit():
    """API endpoint for Compliance & Audit Report (Stacked Bar Chart)"""
    if current_user.role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        # Get schools based on user role
        if current_user.role == 'super_admin':
            schools = School.query.all()
        else:
            schools = [School.query.get(current_user.school_id)] if current_user.school_id else []
        
        data = []
        colors = ['#007bff', '#28a745', '#ffc107', '#fd7e14', '#dc3545', '#6f42c1', '#20c997', '#e83e8c']
        
        for i, school in enumerate(schools):
            students = Student.query.filter_by(school_id=school.id).all()
            total_students = len(students)
            
            if total_students == 0:
                continue
            
            # Calculate compliance metrics
            complete_records = sum(1 for s in students if s.bmi and s.height and s.weight)
            partial_records = sum(1 for s in students if (s.height or s.weight) and not (s.height and s.weight))
            incomplete_records = total_students - complete_records - partial_records
            
            # Calculate percentages
            complete_pct = (complete_records / total_students * 100) if total_students > 0 else 0
            partial_pct = (partial_records / total_students * 100) if total_students > 0 else 0
            incomplete_pct = (incomplete_records / total_students * 100) if total_students > 0 else 0
            
            data.append({
                'school_name': school.name,
                'total_students': total_students,
                'complete_records': complete_records,
                'partial_records': partial_records,
                'incomplete_records': incomplete_records,
                'complete_pct': round(complete_pct, 1),
                'partial_pct': round(partial_pct, 1),
                'incomplete_pct': round(incomplete_pct, 1),
                'color': colors[i % len(colors)]
            })
        
        return jsonify({
            'success': True,
            'data': data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500