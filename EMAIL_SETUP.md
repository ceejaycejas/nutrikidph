# NutriKid Email Configuration Guide

## Setting up Gmail for Password Reset Emails

To enable the system to send real passwords to users' Gmail accounts, you need to configure your Gmail credentials in the `.env` file.

## Step-by-Step Setup

### 1. Enable 2-Factor Authentication
1. Go to your [Google Account settings](https://myaccount.google.com/)
2. Click on "Security" in the left sidebar
3. Under "Signing in to Google", click "2-Step Verification"
4. Follow the prompts to set up 2FA (you'll need your phone)

### 2. Generate Gmail App Password
1. Stay in your Google Account Security settings
2. Scroll down to "2-Step Verification" and make sure it's ON
3. Scroll down further and click "App passwords"
4. If prompted, enter your Google password
5. Under "Select app", choose "Mail"
6. Under "Select device", choose "Other" and type "NutriKid"
7. Click "Generate"
8. Copy the 16-character password (it will look like "abcd efgh ijkl mnop")

### 3. Update Your .env File
Open the `.env` file in your project and update these lines:

```
# Replace with your actual Gmail address
MAIL_USERNAME=your-actual-gmail@gmail.com

# Replace with the 16-character App Password you just generated
MAIL_PASSWORD=your-16-character-app-password
```

### 4. Restart the Application
1. Stop the Flask server (Ctrl+C)
2. Start it again: `python app.py`

### 5. Test the Email Functionality
1. Request a password reset for a user account
2. Approve the request from the admin panel
3. Check the user's Gmail inbox for the new password email

## Troubleshooting

### Not Receiving Emails?
- Check your Gmail Spam/Junk folder
- Verify the email address in the user's account is correct
- Check the Flask console for error messages
- Run `python check_email_config.py` to verify your configuration

### Common Issues
1. **Using regular Gmail password instead of App Password** - This won't work
2. **2FA not enabled** - App Passwords require 2FA
3. **Wrong email address** - Make sure MAIL_USERNAME is your actual Gmail address
4. **Firewall/Network issues** - Some networks block SMTP connections

## Security Notes
- Never commit your `.env` file to version control
- App Passwords are more secure than your regular password
- Each App Password can be revoked individually
- Store your App Password securely

## Testing Email Configuration
Run `python check_email_config.py` to verify your setup is correct.