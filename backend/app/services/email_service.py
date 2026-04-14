"""
Service d'envoi d'emails — SMTP Gmail.

Utilisé pour :
- Code de vérification email (inscription)
- Code de reset mot de passe (mot de passe oublié)
"""

import os
import random
import string
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# ── Configuration SMTP ───────────────────────────────────────
EMAIL_MODE = os.getenv("EMAIL_MODE", "smtp").strip().lower()  # smtp | log
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "garayoussef0@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # App Password Gmail
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "3S TalentMatch")

# Durée de validité des codes (minutes)
VERIFICATION_CODE_EXPIRE_MINUTES = int(os.getenv("VERIFICATION_CODE_EXPIRE_MINUTES", "15"))


def generate_otp(length: int = 6) -> str:
    """Génère un code OTP numérique de N chiffres."""
    return "".join(random.choices(string.digits, k=length))


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Envoie un email via SMTP Gmail.
    Retourne True si envoyé, False sinon.
    """
    if EMAIL_MODE == "log":
        # Mode dev: ne pas envoyer réellement, mais logguer le sujet
        # (le code OTP est inclus dans le subject)
        # ⚠️ Sous Windows, quand stdout est redirigé vers un fichier, l'encodage
        # peut être non-UTF8 (cp1252), ce qui fait planter sur certains caractères
        # (ex: emojis dans le subject). On rend le message ASCII-safe.
        safe_subject = subject.encode("ascii", errors="backslashreplace").decode("ascii")
        msg = f"EMAIL_MODE=log - email simulated to {to_email} : {safe_subject}"
        # `logger.info` peut ne pas apparaître si le logging n'est pas configuré,
        # donc on écrit aussi sur stdout.
        logger.info(msg)
        print(msg, flush=True)
        return True

    if not SMTP_PASSWORD:
        logger.warning(
            "SMTP_PASSWORD non configuré — email NON envoyé à %s. "
            "Configurez la variable d'environnement SMTP_PASSWORD avec un App Password Gmail.",
            to_email,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
        msg["To"] = to_email

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        logger.info("Email envoyé à %s : %s", to_email, subject)
        return True
    except Exception as e:
        logger.error("Erreur envoi email à %s : %s", to_email, e)
        return False


def send_verification_email(to_email: str, prenom: str, code: str) -> bool:
    """Envoie le code de vérification d'email à un nouvel utilisateur."""
    subject = f"🔐 Votre code de vérification — {code}"
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #f8fafc; border-radius: 12px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <span style="font-size: 32px;">🎯</span>
            <h2 style="color: #1e293b; margin: 8px 0 0;">3S TalentMatch</h2>
        </div>
        <div style="background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <p style="color: #334155; font-size: 16px;">Bonjour <strong>{prenom}</strong>,</p>
            <p style="color: #64748b; font-size: 14px;">Voici votre code de vérification pour activer votre compte :</p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #2563eb; background: #eff6ff; padding: 16px 32px; border-radius: 8px; border: 2px dashed #93c5fd;">
                    {code}
                </span>
            </div>
            <p style="color: #94a3b8; font-size: 13px; text-align: center;">
                Ce code expire dans <strong>{VERIFICATION_CODE_EXPIRE_MINUTES} minutes</strong>.
            </p>
        </div>
        <p style="color: #94a3b8; font-size: 12px; text-align: center; margin-top: 16px;">
            Si vous n'avez pas créé de compte, ignorez cet email.
        </p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_password_reset_email(to_email: str, prenom: str, code: str) -> bool:
    """Envoie le code de reset de mot de passe."""
    subject = f"🔑 Réinitialisation de votre mot de passe — {code}"
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 32px; background: #f8fafc; border-radius: 12px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <span style="font-size: 32px;">🎯</span>
            <h2 style="color: #1e293b; margin: 8px 0 0;">3S TalentMatch</h2>
        </div>
        <div style="background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <p style="color: #334155; font-size: 16px;">Bonjour <strong>{prenom}</strong>,</p>
            <p style="color: #64748b; font-size: 14px;">Vous avez demandé la réinitialisation de votre mot de passe. Voici votre code :</p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #dc2626; background: #fef2f2; padding: 16px 32px; border-radius: 8px; border: 2px dashed #fca5a5;">
                    {code}
                </span>
            </div>
            <p style="color: #94a3b8; font-size: 13px; text-align: center;">
                Ce code expire dans <strong>{VERIFICATION_CODE_EXPIRE_MINUTES} minutes</strong>.
            </p>
        </div>
        <p style="color: #94a3b8; font-size: 12px; text-align: center; margin-top: 16px;">
            Si vous n'avez pas fait cette demande, ignorez cet email. Votre mot de passe reste inchangé.
        </p>
    </div>
    """
    return _send_email(to_email, subject, html)
