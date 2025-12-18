# PythonAnywhere Deployment Guide

This guide will help you deploy the QRPlate Django application to PythonAnywhere.

## Prerequisites

- PythonAnywhere account (username: `urqrplate`)
- Git repository access
- Environment variables configured

## Step 1: Clone the Repository

1. Log in to PythonAnywhere and open a Bash console
2. Navigate to your home directory:
   ```bash
   cd ~
   ```
3. Clone your repository:
   ```bash
   git clone https://github.com/hirwacedric123/urqrplate.git
   ```

## Step 2: Set Up Virtual Environment

1. Navigate to the backend directory:
   ```bash
   cd urqrplate/QR_Backend
   ```

2. Create a virtual environment:
   ```bash
   python3.12 -m venv venv
   ```

3. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```

4. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Step 3: Configure Environment Variables

1. Create a `.env` file in the `QR_Backend` directory:
   ```bash
   nano .env
   ```

2. Add your environment variables (copy from `env.example`):
   ```env
   SECRET_KEY=your-secret-key-here
   DEBUG=False
   ALLOWED_HOSTS=urqrplate.pythonanywhere.com
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-app-password-here
   ```

3. Save and exit (Ctrl+X, then Y, then Enter)

## Step 4: Configure WSGI File

1. Go to the **Web** tab in PythonAnywhere dashboard
2. Click on the WSGI configuration file link
3. Replace the entire content with the following:

```python
import os
import sys

# Add your project directory to the Python path
path = '/home/urqrplate/urqrplate/QR_Backend'
if path not in sys.path:
    sys.path.insert(0, path)

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'QR_Backend.settings')

# Import Django's WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

4. Save the file

## Step 5: Run Migrations and Collect Static Files

**IMPORTANT**: Run `collectstatic` BEFORE configuring static files in the Web tab!

1. Open a Bash console
2. Navigate to your project:
   ```bash
   cd ~/urqrplate/QR_Backend
   source venv/bin/activate
   ```

3. Run migrations:
   ```bash
   python manage.py migrate
   ```

4. Create a superuser (if needed):
   ```bash
   python manage.py createsuperuser
   ```

5. **Collect static files** (this copies all static files to the `staticfiles/` directory):
   ```bash
   python manage.py collectstatic --noinput
   ```
   
   You should see output like:
   ```
   Copying '/home/urqrplate/urqrplate/QR_Backend/static/assets/images/alualu.png'
   ...
   X static files copied to '/home/urqrplate/urqrplate/QR_Backend/staticfiles'
   ```

6. Verify static files were collected:
   ```bash
   ls -la staticfiles/assets/images/
   ```
   
   You should see files like `alualu.png`, `logo_alu.png`, etc.

## Step 6: Configure Static Files in PythonAnywhere Web Tab

1. In the **Web** tab, scroll down to **Static files**
2. Add the following static file mappings (make sure the paths are correct):
   - **URL**: `/static/`
   - **Directory**: `/home/urqrplate/urqrplate/QR_Backend/staticfiles/`
   
   - **URL**: `/media/`
   - **Directory**: `/home/urqrplate/urqrplate/QR_Backend/media/`

3. **Important**: Make sure there are no trailing slashes in the paths
4. Click **Save** after adding each mapping

## Step 7: Update Settings for Production

The `settings.py` file should already be configured to:
- Use environment variables from `.env` file
- Set `DEBUG=False` in production
- Include your PythonAnywhere domain in `ALLOWED_HOSTS`

## Step 8: Reload Web App

1. Go to the **Web** tab in PythonAnywhere dashboard
2. Click the green **Reload** button to restart your web app

## Step 9: Test Your Application

Visit your website at: `https://urqrplate.pythonanywhere.com`

## Troubleshooting

### Common Issues:

1. **500 Error**: Check the error log in the **Web** tab
2. **Static files not loading (images, CSS, logos)**:
   - **First**: Make sure `collectstatic` was run successfully (see Step 5)
   - **Check**: Verify files exist in `staticfiles/` directory:
     ```bash
     ls -la ~/urqrplate/QR_Backend/staticfiles/assets/images/
     ```
   - **Verify**: Static files mapping in Web tab is correct:
     - URL: `/static/` (with trailing slash)
     - Directory: `/home/urqrplate/urqrplate/QR_Backend/staticfiles/` (NO trailing slash)
   - **Check**: Make sure `DEBUG=False` in your `.env` file (static files are served by web server, not Django in production)
   - **Reload**: After fixing, reload the web app from the Web tab
   - **Test**: Visit `https://urqrplate.pythonanywhere.com/static/assets/images/alualu.png` directly - it should show the image
   - **Common mistake**: If you see 404, check that the directory path doesn't have a trailing slash
3. **Database errors**: Make sure migrations were run successfully
4. **Import errors**: Verify the virtual environment is activated and dependencies are installed

### Viewing Logs:

- **Error log**: Available in the **Web** tab
- **Server log**: Available in the **Web** tab
- **Console output**: Check Bash console for any errors

## Updating Your Application

To update your application after making changes:

1. Pull the latest changes:
   ```bash
   cd ~/urqrplate
   git pull origin main
   ```

2. Activate virtual environment:
   ```bash
   cd QR_Backend
   source venv/bin/activate
   ```

3. Install any new dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run migrations (if any):
   ```bash
   python manage.py migrate
   ```

5. **Collect static files** (important if you added/changed CSS, images, or JS):
   ```bash
   python manage.py collectstatic --noinput
   ```

6. Reload the web app from the **Web** tab

## Notes

- PythonAnywhere free accounts have some limitations (e.g., only one web app, limited CPU time)
- Make sure your `.env` file is not committed to git (it's already in `.gitignore`)
- Keep your `SECRET_KEY` and email credentials secure
- Consider using a paid plan for production applications

