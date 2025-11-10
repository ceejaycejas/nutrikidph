from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.password_reset import PasswordResetRequest
from app.services.password_reset_service import PasswordResetService
from datetime import datetime

bp = Blueprint('password_reset', __name__, url_prefix='/password-reset')

@bp.route('/request', methods=['GET', 'POST'])
def request_reset():
    """Student/Admin request password reset"""
    if request.method == 'POST':
        email = request.form.get('email')
        reason = request.form.get('reason', '').strip()
        
        if not email:
            flash('Email address is required', 'danger')
            return redirect(url_for('password_reset.request_reset'))
        
        # Find user by email
        user = User.query.filter_by(email=email).first()
        if not user:
            # Don't reveal if email exists or not for security
            flash('If an account with that email exists, a password reset request has been submitted.', 'info')
            return redirect(url_for('auth.login'))
        
        # Only students and admins can request password reset
        if user.role not in ['student', 'admin']:
            flash('Password reset is not available for your account type.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Create reset request
        reset_request, message = PasswordResetService.create_reset_request(user.id, reason)
        
        if reset_request:
            return redirect(url_for('password_reset.request_success'))
        else:
            flash(message, 'danger')
    
    return render_template('password_reset/request.html')

@bp.route('/success')
def request_success():
    """Show success page after password reset request submission"""
    return render_template('password_reset/request_success.html')

@bp.route('/admin/requests')
@login_required
def admin_requests():
    """Admin view pending student password reset requests"""
    if current_user.role not in ['admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    try:
        # Type cast current_user to satisfy type checker
        from app.models.user import User
        admin_user: User = current_user  # type: ignore
        
        pending_requests = PasswordResetService.get_pending_requests_for_admin(admin_user)
        all_requests = PasswordResetService.get_all_requests_for_admin(admin_user, limit=20)
        
        return render_template('password_reset/admin_requests.html', 
                             pending_requests=pending_requests,
                             all_requests=all_requests)
    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error in admin_requests: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        flash('An error occurred while loading the password reset requests. Please try again.', 'danger')
        return redirect(url_for('school.dashboard'))

@bp.route('/super-admin/requests')
@login_required
def super_admin_requests():
    """Super admin view pending admin password reset requests"""
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    try:
        # Type cast current_user to satisfy type checker
        from app.models.user import User
        admin_user: User = current_user  # type: ignore
        
        pending_requests = PasswordResetService.get_pending_requests_for_admin(admin_user)
        all_requests = PasswordResetService.get_all_requests_for_admin(admin_user, limit=50)
        
        return render_template('password_reset/super_admin_requests.html',
                             pending_requests=pending_requests,
                             all_requests=all_requests)
    except Exception as e:
        # Log the error for debugging
        current_app.logger.error(f"Error in super_admin_requests: {str(e)}")
        import traceback
        current_app.logger.error(f"Traceback: {traceback.format_exc()}")
        flash(f'An error occurred while loading the password reset requests: {str(e)}. Please try again.', 'danger')
        return redirect(url_for('school.dashboard'))

@bp.route('/approve/<int:request_id>', methods=['POST'])
@login_required
def approve_request(request_id):
    """Approve a password reset request"""
    if current_user.role not in ['admin', 'super_admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    admin_notes = request.form.get('admin_notes', '').strip()
    
    success, message = PasswordResetService.approve_request(
        request_id, 
        current_user.id, 
        admin_notes
    )
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    
    # Redirect based on user role
    if current_user.role == 'super_admin':
        return redirect(url_for('password_reset.super_admin_requests'))
    else:
        return redirect(url_for('password_reset.admin_requests'))

@bp.route('/reject/<int:request_id>', methods=['POST'])
@login_required
def reject_request(request_id):
    """Reject a password reset request"""
    if current_user.role not in ['admin', 'super_admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    admin_notes = request.form.get('admin_notes', '').strip()
    
    if not admin_notes:
        flash('Please provide a reason for rejection', 'danger')
        if current_user.role == 'super_admin':
            return redirect(url_for('password_reset.super_admin_requests'))
        else:
            return redirect(url_for('password_reset.admin_requests'))
    
    success, message = PasswordResetService.reject_request(
        request_id, 
        current_user.id, 
        admin_notes
    )
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')
    
    # Redirect based on user role
    if current_user.role == 'super_admin':
        return redirect(url_for('password_reset.super_admin_requests'))
    else:
        return redirect(url_for('password_reset.admin_requests'))

@bp.route('/request/<int:request_id>/details')
@login_required
def request_details(request_id):
    """View details of a password reset request"""
    if current_user.role not in ['admin', 'super_admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    reset_request = PasswordResetRequest.query.get_or_404(request_id)
    
    # Check if user has permission to view this request
    if current_user.role == 'admin':
        if reset_request.user.school_id != current_user.school_id:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('password_reset.admin_requests'))
    
    return render_template('password_reset/request_details.html', reset_request=reset_request)

@bp.route('/my-requests')
@login_required
def my_requests():
    """View user's own password reset requests"""
    if current_user.role not in ['student', 'admin']:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('school.dashboard'))
    
    user_requests = PasswordResetRequest.query.filter_by(
        user_id=current_user.id
    ).order_by(PasswordResetRequest.created_at.desc()).limit(10).all()
    
    return render_template('password_reset/my_requests.html', requests=user_requests)

@bp.route('/cleanup-expired', methods=['POST'])
@login_required
def cleanup_expired():
    """Cleanup expired password reset requests (Super admin only)"""
    if current_user.role != 'super_admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    cleaned_count = PasswordResetService.cleanup_expired_requests()
    
    return jsonify({
        'success': True,
        'message': f'Cleaned up {cleaned_count} expired requests'
    })

@bp.route('/clear-all', methods=['POST'])
@login_required
def clear_all():
    """Clear all password reset requests (Super admin only)"""
    if current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('password_reset.super_admin_requests'))
    
    cleared = PasswordResetService.clear_all_requests()
    
    # Always redirect for form submissions
    flash(f'Successfully cleared {cleared} password reset request(s).', 'success')
    return redirect(url_for('password_reset.super_admin_requests'))

# Add to auth routes - forgot password link
@bp.route('/forgot-password')
def forgot_password():
    """Redirect to password reset request page"""
    return redirect(url_for('password_reset.request_reset'))