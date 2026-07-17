#!/usr/bin/env python3
import os
import sys
import argparse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import (
    app,
    get_users_list,
    get_serializer,
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SENDER_EMAIL
)

def build_welcome_email(username, password, reset_link, sender_email):
    """
    Constructs the welcome email with the exact greeting, signature, and requirements requested.
    """
    subject = "🎉 APAR Oil Sample Monitoring System - Account Welcome & Credentials"
    
    # Text version matches structure exactly
    text_content = f"""Greetings all, 
Our oil sample monitoring system is now online and is ready to implement kindly to the needful

Your login credentials are:
--------------------------------------
Username: {username}
Password: {password}
--------------------------------------

Next Steps & Security Guidelines:
1. If this email landed in your Spam/Junk folder, please add this sender email address ({sender_email}) to your contacts/inbox or mark it as "Not Spam".
2. For security reasons, please change your password after your first login. You can reset your password directly using the link below:
{reset_link}

Visit Portal Website: https://apar-oil-sampling-monitoring-system-eight.vercel.app/login

Regards,
APAR Oil Sample Monitoring System Administrator
{sender_email}
"""

    # HTML version with premium styling
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: 'Outfit', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                color: #1e293b;
                background-color: #f8fafc;
                margin: 0;
                padding: 20px;
                line-height: 1.6;
            }}
            .container {{
                max-width: 600px;
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.05);
                margin: 0 auto;
            }}
            .header {{
                background-color: #111827;
                color: #ffffff;
                padding: 24px;
                text-align: center;
                border-bottom: 2px solid #3b82f6;
            }}
            .header h2 {{
                margin: 0;
                font-size: 1.5rem;
                letter-spacing: 0.5px;
                font-weight: 700;
            }}
            .body {{
                padding: 32px 24px;
            }}
            .greetings {{
                font-size: 1.05rem;
                color: #0f172a;
                margin-bottom: 24px;
                white-space: pre-line;
            }}
            .credentials-box {{
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                padding: 20px;
                border-radius: 12px;
                margin: 24px 0;
            }}
            .credentials-title {{
                font-weight: 700;
                color: #0f172a;
                margin-bottom: 10px;
                font-size: 0.95rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .credential-item {{
                font-size: 1.1rem;
                margin: 6px 0;
            }}
            .code-val {{
                font-family: 'Courier New', Courier, monospace;
                font-weight: bold;
                color: #2563eb;
                background-color: #eff6ff;
                padding: 2px 6px;
                border-radius: 4px;
            }}
            .instruction-box {{
                background-color: #fffbeb;
                border-left: 4px solid #f59e0b;
                padding: 16px;
                border-radius: 8px;
                margin: 24px 0;
                font-size: 0.95rem;
                color: #78350f;
            }}
            .action-wrapper {{
                text-align: center;
                margin: 32px 0;
            }}
            .btn-reset {{
                background-color: #2563eb;
                color: #ffffff !important;
                text-decoration: none;
                padding: 14px 28px;
                border-radius: 8px;
                font-weight: 600;
                display: inline-block;
                font-size: 1rem;
                box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2);
                transition: background-color 0.2s;
            }}
            .btn-reset:hover {{
                background-color: #1d4ed8;
            }}
            .btn-website {{
                background-color: #0f172a;
                color: #ffffff !important;
                text-decoration: none;
                padding: 14px 28px;
                border-radius: 8px;
                font-weight: 600;
                display: inline-block;
                font-size: 1rem;
                box-shadow: 0 4px 6px rgba(15, 23, 42, 0.15);
                transition: background-color 0.2s;
                margin: 5px;
            }}
            .btn-website:hover {{
                background-color: #1e293b;
            }}
            .signature-box {{
                margin-top: 32px;
                padding-top: 24px;
                border-top: 1px solid #e2e8f0;
                font-size: 0.95rem;
                color: #475569;
                white-space: pre-line;
            }}
            .footer {{
                background-color: #f8fafc;
                padding: 16px;
                text-align: center;
                font-size: 0.8rem;
                color: #64748b;
                border-top: 1px solid #e2e8f0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>APAR Oil Sample Monitoring System</h2>
            </div>
            <div class="body">
                <div class="greetings">Greetings all, <br>Our oil sample monitoring system is now online and is ready to implement kindly to the needful</div>
                
                <div class="credentials-box">
                    <div class="credentials-title">🔑 Your Login Credentials</div>
                    <div class="credential-item"><strong>Username:</strong> <span class="code-val">{username}</span></div>
                    <div class="credential-item"><strong>Password:</strong> <span class="code-val">{password}</span></div>
                </div>

                <div class="instruction-box">
                    <strong>✉️ Safe Sender Instructions:</strong><br>
                    If this email landed in your <strong>Spam</strong> or <strong>Junk</strong> folder, please mark it as <strong>"Not Spam"</strong> and add our sender address (<code>{sender_email}</code>) to your contacts or safe sender list.
                </div>

                <p>For security reasons, we highly request and recommend you to change your password immediately after your first login by clicking below:</p>

                <div class="action-wrapper">
                    <a href="{reset_link}" class="btn-reset" style="margin: 5px;">Change Your Password</a>
                    <a href="https://apar-oil-sampling-monitoring-system-eight.vercel.app/login" class="btn-website">Visit Website</a>
                </div>

                <div class="signature-box">Regards,<br>
<strong>APAR Oil Sample Monitoring Team</strong><br>
{sender_email}</div>
            </div>
            <div class="footer">
                APAR Industries &copy; 2026. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """
    
    return subject, text_content, html_content

def send_single_welcome_email(user_email, username, password, reset_link):
    """
    Connects to SMTP and sends the welcome email to a single user.
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("❌ Error: SMTP credentials are not set in the environment.")
        return False

    try:
        msg = MIMEMultipart('alternative')
        subject, text_content, html_content = build_welcome_email(username, password, reset_link, SENDER_EMAIL)
        
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = user_email

        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
        
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, user_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {user_email}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Send automated welcome and credential emails to APAR Oil Sample Monitoring System users.")
    parser.add_argument("--send", action="store_true", help="Actually dispatch emails (otherwise runs a dry-run).")
    parser.add_argument("--email", type=str, help="Send a test email ONLY to this address.")
    parser.add_argument("--user", type=str, help="Send ONLY to this username from the Google Sheet list.")
    parser.add_argument("--base-url", type=str, default="http://localhost:5001", help="Base URL of the application for password reset links.")
    
    args = parser.parse_args()

    print("==================================================")
    print("🚀 APAR welcome email system initialized")
    print("==================================================")
    print(f"SMTP Server: {SMTP_SERVER}:{SMTP_PORT}")
    print(f"Sender Email: {SENDER_EMAIL}")
    print(f"Target App Base URL: {args.base_url}")
    print(f"Execution Mode: {'ACTIVE DISPATCH' if args.send else 'DRY RUN (Preview)'}")
    print("==================================================")

    # 1. Fetch users from Google Sheet (or local fallback)
    print("Fetching users from Google Sheet...")
    try:
        users = get_users_list()
    except Exception as e:
        print(f"❌ Failed to retrieve users: {e}")
        sys.exit(1)

    if not users:
        print("⚠️ No users found in the system.")
        sys.exit(0)

    print(f"Found {len(users)} users in the system.\n")

    # 2. Filter users if requested
    if args.user:
        users = [u for u in users if u["username"].lower() == args.user.lower()]
        if not users:
            print(f"❌ User '{args.user}' not found in the retrieved user list.")
            sys.exit(1)
        print(f"Filtered to user: {users[0]['username']} ({users[0]['email']})")

    # 3. Process each user
    serializer = get_serializer()
    
    success_count = 0
    fail_count = 0
    skipped_count = 0

    for idx, user in enumerate(users, 1):
        username = user["username"]
        password = user["password"]
        
        # Determine recipient email
        if args.email:
            # Overriding target email for testing
            user_email = args.email
        else:
            user_email = user["email"]

        if not user_email or "@" not in user_email:
            print(f"[{idx}/{len(users)}] ⚠️ User '{username}' has no valid email configured: '{user_email}'. Skipping.")
            skipped_count += 1
            continue

        # Generate unique password reset token
        token = serializer.dumps(username, salt='password-reset-salt')
        reset_link = f"{args.base_url}/reset_password?token={token}"

        if not args.send:
            # Dry-run logging
            print(f"[{idx}/{len(users)}] DRY-RUN Preview:")
            print(f"  - Username: {username}")
            print(f"  - Password: {password}")
            print(f"  - Recipient Email: {user_email}")
            print(f"  - Reset Password Link: {reset_link}")
            print("-" * 50)
            success_count += 1
        else:
            # Actual send
            print(f"[{idx}/{len(users)}] Sending to {username} ({user_email})...", end="", flush=True)
            success = send_single_welcome_email(user_email, username, password, reset_link)
            if success:
                print(" ✅ SENT")
                success_count += 1
            else:
                print(" ❌ FAILED")
                fail_count += 1

    print("\n==================================================")
    print("📊 Execution Summary:")
    print("==================================================")
    if args.send:
        print(f"  - Successfully sent: {success_count}")
        print(f"  - Failed: {fail_count}")
    else:
        print(f"  - Dry-run previews generated: {success_count}")
    print(f"  - Skipped (no valid email): {skipped_count}")
    print("==================================================")
    if not args.send:
        print("💡 Tip: Add the '--send' flag to actually dispatch the emails.")
        print("💡 Tip: Use '--email test@example.com' to send a single preview to your own email.")
    print("==================================================")

if __name__ == '__main__':
    # Make sure we load the local app secret key environment variables
    main()
