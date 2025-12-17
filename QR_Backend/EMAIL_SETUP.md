# Email Configuration Setup Guide

## Problem
The SMTP authentication error occurs because Gmail credentials are not properly configured.

## Solution

### Step 1: Create a `.env` file
Create a `.env` file in the `QR_Backend` directory with the following content:

```env
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password-here
```

### Step 2: Get a Gmail App Password

**Important:** Gmail requires an "App Password" instead of your regular password when using SMTP, especially if 2-Step Verification is enabled.

#### How to Generate a Gmail App Password:

1. **Enable 2-Step Verification** (if not already enabled):
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Click on "2-Step Verification" and follow the setup

2. **Generate App Password**:
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Scroll down to "2-Step Verification" section
   - Click on "App passwords" (you may need to search for it)
   - Select "Mail" as the app type
   - Select "Other (Custom name)" as the device
   - Enter "Django QRPlate" as the name
   - Click "Generate"
   - Copy the 16-character password (it will look like: `abcd efgh ijkl mnop`)

3. **Use the App Password**:
   - Remove all spaces from the generated password
   - Use it as `EMAIL_HOST_PASSWORD` in your `.env` file
   - Use your Gmail address as `EMAIL_HOST_USER`

### Step 3: Update your `.env` file

```env
EMAIL_HOST_USER=your-actual-email@gmail.com
EMAIL_HOST_PASSWORD=abcdefghijklmnop
```

**Example:**
```env
EMAIL_HOST_USER=hirwacedric123@gmail.com
EMAIL_HOST_PASSWORD=abcd efgh ijkl mnop
```

### Step 4: Restart your Django server

After updating the `.env` file, restart your Django development server:

```bash
python manage.py runserver
```

## Alternative: Using Environment Variables Directly

If you prefer not to use a `.env` file, you can set environment variables directly:

**Linux/Mac:**
```bash
export EMAIL_HOST_USER="your-email@gmail.com"
export EMAIL_HOST_PASSWORD="your-app-password"
```

**Windows (PowerShell):**
```powershell
$env:EMAIL_HOST_USER="your-email@gmail.com"
$env:EMAIL_HOST_PASSWORD="your-app-password"
```

## Troubleshooting

### Still getting authentication errors?

1. **Verify App Password**: Make sure you're using the App Password, not your regular Gmail password
2. **Check 2-Step Verification**: App Passwords only work if 2-Step Verification is enabled
3. **Remove spaces**: The App Password should not contain spaces
4. **Check email address**: Ensure `EMAIL_HOST_USER` matches the Gmail account where you generated the App Password

### Alternative Email Providers

If you prefer not to use Gmail, you can use other email providers:

**Outlook/Hotmail:**
```python
EMAIL_HOST = 'smtp-mail.outlook.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
```

**Yahoo:**
```python
EMAIL_HOST = 'smtp.mail.yahoo.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
```

## Security Note

- **Never commit your `.env` file to version control**
- The `.env` file is already in `.gitignore`
- Keep your App Password secure and don't share it

