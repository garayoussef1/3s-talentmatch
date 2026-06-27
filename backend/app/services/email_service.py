"""
Service d'envoi d'emails — SMTP Gmail.

Utilisé pour :
- Code de vérification email (inscription)
- Code de reset mot de passe (mot de passe oublié)
"""

import os
import base64
import random
import string
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _load_logo_b64() -> str:
    try:
        logo_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "frontend", "src", "assets", "logo_3s.png"
        ))
        with open(logo_path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    except Exception:
        return ""

LOGO_B64 = _load_logo_b64()

def _logo_header() -> str:
    if LOGO_B64:
        return f'<img src="data:image/png;base64,{LOGO_B64}" alt="3S TalentMatch" style="height: 60px; width: auto; margin-bottom: 6px;" />'
    return '<span style="font-size: 32px;">🎯</span>'

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
            {_logo_header()}
            <h2 style="color: #1b4f8a; margin: 4px 0 0;">3S TalentMatch</h2>
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


def send_status_change_email(to_email: str, prenom: str, offer_title: str, new_status: str, cv_name: str = None) -> bool:
    """Notifie le candidat d'un changement de statut de sa candidature."""
    if new_status == "accepte":
        emoji = "🎉"
        title = "Félicitations — Candidature acceptée !"
        color = "#16a34a"
        bg = "#f0fdf4"
        border = "#86efac"
        msg = f"Nous avons le plaisir de vous informer que votre candidature pour le poste <strong>« {offer_title} »</strong> a été <strong>acceptée</strong>."
        action = "Notre équipe vous contactera prochainement pour la suite du processus."
    elif new_status == "refuse":
        emoji = "📋"
        title = "Mise à jour de votre candidature"
        color = "#dc2626"
        bg = "#fef2f2"
        border = "#fca5a5"
        msg = f"Nous vous informons que votre candidature pour le poste <strong>« {offer_title} »</strong> n'a pas été retenue cette fois-ci."
        action = "Nous vous encourageons à postuler à d'autres offres qui correspondent à votre profil."
    else:
        return True  # Pas de notif pour en_attente

    cv_row = ""
    if cv_name:
        cv_row = f"""
            <p style="color: #64748b; font-size: 13px; margin: 8px 0 0;">
                📄 CV concerné : <strong style="color: #334155;">{cv_name}</strong>
            </p>"""

    subject = f"{emoji} {title} — 3S TalentMatch"
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 32px; background: #f8fafc; border-radius: 12px;">
        <div style="text-align: center; margin-bottom: 24px;">
            {_logo_header()}
            <h2 style="color: #1b4f8a; margin: 4px 0 0;">3S TalentMatch</h2>
        </div>
        <div style="background: white; padding: 28px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid {color};">
            <p style="color: #334155; font-size: 16px; margin: 0 0 12px;">Bonjour <strong>{prenom}</strong>,</p>
            <div style="background: {bg}; border: 1px solid {border}; border-radius: 8px; padding: 16px; margin: 16px 0;">
                <p style="color: #1e293b; font-size: 15px; margin: 0;">{msg}</p>
                {cv_row}
            </div>
            <p style="color: #64748b; font-size: 14px;">{action}</p>
            <p style="color: #64748b; font-size: 14px;">Connectez-vous à votre espace candidat pour suivre toutes vos candidatures.</p>
        </div>
        <p style="color: #94a3b8; font-size: 12px; text-align: center; margin-top: 16px;">
            3S Group — L'intelligence au service du recrutement.
        </p>
    </div>
    """
    return _send_email(to_email, subject, html)


def send_interview_invitation_email(to_email: str, prenom: str, offer_title: str, link: str) -> bool:
    """Invite le candidat à passer son entretien IA via un lien personnel."""
    subject = "🎙 Invitation à votre entretien — 3S TalentMatch"
    html = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 32px; background: #f8fafc; border-radius: 12px;">
        <div style="text-align: center; margin-bottom: 24px;">
            {_logo_header()}
            <h2 style="color: #1b4f8a; margin: 4px 0 0;">3S TalentMatch</h2>
        </div>
        <div style="background: white; padding: 28px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-left: 4px solid #1b4f8a;">
            <p style="color: #334155; font-size: 16px; margin: 0 0 12px;">Bonjour <strong>{prenom}</strong>,</p>
            <p style="color: #1e293b; font-size: 15px; line-height: 1.55;">
                Suite à l'étude de votre candidature pour le poste de
                <strong>« {offer_title} »</strong>, nous avons le plaisir de vous inviter
                à réaliser un <strong>entretien d'évaluation en ligne</strong>.
            </p>
            <div style="background: #eef4fb; border: 1px solid #c7d8ef; border-radius: 8px; padding: 16px; margin: 16px 0;">
                <p style="color: #475569; font-size: 14px; margin: 0 0 12px;">
                    L'entretien dure environ 20 minutes. Prenez votre temps et appuyez-vous
                    sur des exemples concrets de votre parcours.
                </p>
                <div style="text-align: center;">
                    <a href="{link}" style="display: inline-block; background: #1b4f8a; color: #fff; text-decoration: none; padding: 12px 28px; border-radius: 8px; font-weight: 600; font-size: 15px;">
                        Commencer mon entretien
                    </a>
                </div>
            </div>
            <p style="color: #94a3b8; font-size: 12px;">
                Si le bouton ne fonctionne pas, copiez ce lien dans votre navigateur :<br/>
                <span style="color: #1b4f8a; word-break: break-all;">{link}</span>
            </p>
        </div>
        <p style="color: #94a3b8; font-size: 12px; text-align: center; margin-top: 16px;">
            3S Group — L'intelligence au service du recrutement.
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
            {_logo_header()}
            <h2 style="color: #1b4f8a; margin: 4px 0 0;">3S TalentMatch</h2>
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
