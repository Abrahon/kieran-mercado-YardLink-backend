# from django.core.mail import EmailMultiAlternatives
# from django.conf import settings
# from django.utils.html import strip_tags
# import random


# def generate_otp():
#     return str(random.randint(100000, 999999))


# def send_otp_email(email, otp_code, name="User"):
#     subject = "🔐 Your OTP Code for Verification"
    
#     html_content = f"""
#     <div style="font-family:Arial,sans-serif;max-width:600px;margin:20px auto;
#                 border:1px solid #e2e2e2;padding:20px;border-radius:10px;background-color:#f9f9f9;">
#         <h2 style="color:#2c3e50;">Hello {name} 👋,</h2>
#         <p style="font-size:16px;color:#333;">
#             Your One-Time Password (OTP) for account verification is:
#         </p>
#         <div style="text-align:center;margin:20px 0;">
#             <span style="display:inline-block;background-color:#007bff;color:#fff;
#                         font-size:24px;font-weight:bold;padding:10px 20px;border-radius:8px;">
#                 {otp_code}
#             </span>
#         </div>
#         <p style="font-size:14px;color:#555;">
#             This OTP is valid for <strong>5 minutes</strong>. Do not share it with anyone.
#         </p>
#         <hr style="margin:30px 0;border:none;border-top:1px solid #ddd;">
#         <p style="font-size:13px;color:#888;text-align:center;">
#             If you did not request this code, please ignore this email.
#         </p>
#     </div>
#     """
#     plain_text = strip_tags(html_content)
#     from_email = settings.DEFAULT_FROM_EMAIL
#     recipient_list = [email]

#     email_message = EmailMultiAlternatives(subject, plain_text, from_email, recipient_list)
#     email_message.attach_alternative(html_content, "text/html")
#     email_message.send()

# accounts/utils.py
import logging
import smtplib
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, BadHeaderError
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

def generate_otp():
    import random
    return str(random.randint(100000, 999999))

def send_otp_email(to_email, otp_code, name="User"):
    """
    Sends OTP email. Uses the authenticated SMTP mailbox as the envelope sender
    to avoid 'Sender address rejected' errors on providers like Hostinger.
    Returns True on success, False on failure (and logs the error).
    """
    subject = "🔐 Your OTP Code for Verification"
    html_content = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:20px auto;
                border:1px solid #e2e2e2;padding:20px;border-radius:10px;background-color:#f9f9f9;">
        <h2 style="color:#2c3e50;">Hello {name} 👋,</h2>
        <p style="font-size:16px;color:#333;">
            Your One-Time Password (OTP) for account verification is:
        </p>
        <div style="text-align:center;margin:20px 0;">
            <span style="display:inline-block;background-color:#007bff;color:#fff;
                        font-size:24px;font-weight:bold;padding:10px 20px;border-radius:8px;">
                {otp_code}
            </span>
        </div>
        <p style="font-size:14px;color:#555;">
            This OTP is valid for <strong>5 minutes</strong>. Do not share it with anyone.
        </p>
        <hr style="margin:30px 0;border:none;border-top:1px solid #ddd;">
        <p style="font-size:13px;color:#888;text-align:center;">
            If you did not request this code, please ignore this email.
        </p>
    </div>
    """
    plain_text = strip_tags(html_content)

    # Ensure the envelope sender is the authenticated SMTP user
    from_email = settings.EMAIL_HOST_USER  # critical: use SMTP-authenticated mailbox

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,
            from_email=from_email,
            to=[to_email],
            headers={"Reply-To": from_email}  # option: you can set reply-to to another
        )
        msg.attach_alternative(html_content, "text/html")
        # fail_silently=False will raise exceptions, we catch them below
        msg.send(fail_silently=False)
        logger.info("OTP email sent to %s", to_email)
        return True
    except (smtplib.SMTPException, ConnectionRefusedError, BadHeaderError) as exc:
        logger.exception("Failed sending OTP to %s: %s", to_email, exc)
        return False
    except Exception as exc:
        logger.exception("Unexpected error sending OTP to %s: %s", to_email, exc)
        return False
