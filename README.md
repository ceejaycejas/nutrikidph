# NutriKid - School Nutrition Management System

A comprehensive web application for managing student nutrition, meal planning, and health monitoring in schools.

## 🌟 Features

### Core Functionality
- **Multi-Role User Management**: Super Admin, School Admin, and Student roles
- **School Management**: Complete school administration system
- **Student Registration**: Comprehensive student profile management
- **BMI Monitoring**: Automatic BMI calculation and health status tracking
- **Meal Planning**: Create, assign, and manage nutritional meal plans
- **Dashboard Analytics**: Real-time insights and health metrics
- **Reports & Export**: Generate detailed reports in Excel format
- **Notification System**: In-app notifications for important updates

### Advanced Features
- **Health Risk Assessment**: Automatic identification of at-risk students
- **Nutritional Analysis**: Detailed breakdown of meal nutritional content
- **Progress Tracking**: Monitor student health improvements over time
- **Beneficiary Management**: Track and manage nutrition program beneficiaries
- **Password Reset System**: Secure password recovery workflow
- **Activity Logging**: Complete audit trail of user actions

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- MySQL Server 5.7 or higher
- Web browser (Chrome, Firefox, Safari, Edge)

### Option 1: Automated Deployment (Recommended)

1. **Clone or download the project**
   ```bash
   git clone <repository-url>
   cd nutrikid
   ```

2. **Run the deployment script**
   ```bash
   python deploy.py
   ```
   This script will:
   - Check system requirements
   - Install dependencies
   - Set up the database
   - Create sample data
   - Verify the installation

3. **Start the application**
   ```bash
   python app.py
   ```
   The application will automatically open in your browser.

### Option 2: Manual Setup

1. **Install Dependencies**
   ```bash
   # Create virtual environment (optional but recommended)
   python -m venv .venv
   
   # Activate virtual environment
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   
   # Install requirements
   pip install -r requirements.txt
   ```

2. **Configure Database**
   - Ensure MySQL is running
   - Create database: `CREATE DATABASE meal_planner;`
   - Update `.env` file with your database credentials

3. **Initialize Database**
   ```bash
   python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
   ```

4. **Start Application**
   ```bash
   python app.py
   ```

## 🔐 Default Login Credentials

After deployment, use these credentials to access the system:

- **Super Admin**
  - Username: `superadmin`
  - Password: `admin123`

- **School Admin**
  - Username: `admin`
  - Password: `admin123`

## 📁 Project Structure

```
nutrikid/
├── app/                    # Main application package
│   ├── models/            # Database models
│   ├── routes/            # Application routes/controllers
│   ├── templates/         # HTML templates
│   ├── static/           # Static files (CSS, JS, images)
│   └── __init__.py       # App factory
├── migrations/            # Database migrations
├── .env                  # Environment configuration
├── config.py             # Application configuration
├── app.py               # Application entry point
├── deploy.py            # Deployment script
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## 🛠️ Configuration

### Environment Variables (.env)
```env
DATABASE_URL=mysql://root:root@127.0.0.1:3306/meal_planner
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

### Database Configuration
The application uses MySQL as the primary database. Ensure your MySQL server is running and accessible with the credentials specified in the `.env` file.

## 📊 User Roles & Permissions

### Super Admin
- Manage all schools and administrators
- View system-wide reports and analytics
- Access all application features
- Manage user accounts and permissions

### School Admin
- Manage students within their school
- Create and assign meal plans
- Generate school-specific reports
- Monitor student health metrics
- Manage school sections and grade levels

### Student
- View personal profile and health information
- Access assigned meal plans
- Provide feedback on meal plans
- View personal nutrition history

## 🔧 Key Features Explained

### BMI Monitoring
- Automatic BMI calculation based on height, weight, and age
- WHO standard BMI categories for children
- Health risk assessment and alerts
- Progress tracking over time

### Meal Planning
- Create detailed meal plans with nutritional information
- Assign meal plans to specific students or groups
- Track meal plan effectiveness
- Collect feedback from students

### Dashboard Analytics
- Real-time health metrics
- BMI distribution charts
- Progress tracking graphs
- At-risk student identification
- Monthly summary reports

### Reports System
- Student health reports
- Meal plan effectiveness reports
- School-wide nutrition analytics
- Excel export functionality

## 🚨 Troubleshooting

### Common Issues

1. **MySQL Connection Error**
   - Ensure MySQL server is running
   - Check database credentials in `.env` file
   - Verify database exists: `meal_planner`

2. **Port Already in Use**
   - The application will automatically find an available port
   - Default ports tried: 8000, 5000, then 8001-8100

3. **Import Errors**
   - Ensure all dependencies are installed: `pip install -r requirements.txt`
   - Activate virtual environment if using one
   - Run deployment script: `python deploy.py`

4. **Database Migration Issues**
   - Delete migration files and recreate: `flask db init && flask db migrate && flask db upgrade`
   - Or use the deployment script which handles this automatically

### Getting Help

1. **Check the Console**: Look for error messages in the terminal
2. **Verify Installation**: Run `python deploy.py` to check system status
3. **Database Issues**: Ensure MySQL is running and accessible
4. **Browser Issues**: Try a different browser or clear cache

## 🔄 Updates and Maintenance

### Updating the Application
1. Backup your database
2. Pull latest changes
3. Run `python deploy.py` to update dependencies and database
4. Restart the application

### Database Backup
```bash
mysqldump -u root -p meal_planner > backup.sql
```

### Database Restore
```bash
mysql -u root -p meal_planner < backup.sql
```

## 📈 Performance Optimization

### For Production Deployment
1. Use a production WSGI server (Gunicorn, uWSGI)
2. Configure a reverse proxy (Nginx, Apache)
3. Use environment-specific configuration
4. Enable database connection pooling
5. Implement caching (Redis, Memcached)

### Recommended Production Setup
```bash
# Install production server
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the troubleshooting section above
- Review the console output for error messages
- Ensure all prerequisites are met
- Run the deployment script for automated setup

## 🎯 Roadmap

### Upcoming Features
- Mobile application
- Advanced reporting with charts
- Integration with external nutrition databases
- Multi-language support
- API for third-party integrations
- Advanced meal recommendation algorithms

---

**NutriKid** - Empowering schools with comprehensive nutrition management tools.