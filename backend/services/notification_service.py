"""
Notification Service — Firebase Cloud Messaging (FCM) push notifications.
Supports GCP FCM or local logging fallback.
"""

import os
import json
import logging

from services.resilience import CircuitBreaker, retry_with_backoff

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, use_gcp: bool = False):
        self.use_gcp = use_gcp
        self.max_attempts = max(1, int(os.getenv("GCP_RETRY_MAX_ATTEMPTS", "3")))
        self.circuit_breaker = CircuitBreaker(
            name="fcm_send",
            failure_threshold=max(1, int(os.getenv("GCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))),
            recovery_timeout_sec=max(1.0, float(os.getenv("GCP_CIRCUIT_BREAKER_TIMEOUT_SEC", "30"))),
        )

        if use_gcp:
            try:
                import firebase_admin
                from firebase_admin import credentials, messaging

                if not firebase_admin._apps:
                    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                    if cred_path:
                        cred = credentials.Certificate(cred_path)
                        firebase_admin.initialize_app(cred)
                    else:
                        firebase_admin.initialize_app()
            except Exception as exc:
                logger.warning(
                    "Firebase initialization failed; falling back to local mode. "
                    "Set USE_GCP=false for local runs or configure ADC/service account for GCP. Error: %s",
                    exc,
                )
                self.use_gcp = False

    def send_to_zones(self, payload: dict):
        """Send push notification to all users in target zones."""
        title = payload.get("title", "Stadium OS Alert")
        body = payload.get("body", "")
        target_zones = payload.get("target_zones", [])
        priority = payload.get("priority", "normal")

        if self.use_gcp:
            from firebase_admin import messaging

            # In production, you'd query Firestore for FCM tokens in target zones
            # For demo, send to a topic per zone
            for zone in target_zones:
                topic = f"zone_{zone}"
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=title,
                        body=body,
                    ),
                    data={
                        "type": payload.get("type", "general"),
                        "venue_id": payload.get("venue_id", ""),
                        "notification_id": payload.get("notification_id", ""),
                    },
                    topic=topic,
                    android=messaging.AndroidConfig(
                        priority="high" if priority == "high" else "normal",
                    ),
                    webpush=messaging.WebpushConfig(
                        notification=messaging.WebpushNotification(
                            title=title,
                            body=body,
                            icon="/icons/icon-192.png",
                            badge="/icons/badge-72.png",
                        ),
                    ),
                )
                try:
                    result = retry_with_backoff(
                        operation=lambda: self.circuit_breaker.call(lambda: messaging.send(message)),
                        operation_name=f"fcm.send.zone.{zone}",
                        max_attempts=self.max_attempts,
                    )
                    logger.info(f"FCM sent to topic {topic}: {result}")
                except Exception as e:
                    logger.error(
                        json.dumps(
                            {
                                "event": "fcm_topic_send_failed",
                                "service": "fcm",
                                "topic": topic,
                                "error": str(e),
                            },
                            separators=(",", ":"),
                        )
                    )
            return
        else:
            logger.info(
                f"[LOCAL FCM] → zones={target_zones} | "
                f"title=\"{title}\" | body=\"{body[:80]}\""
            )

    def send_to_tokens(self, tokens: list[str], title: str, body: str, data: dict = None):
        """Send to specific FCM tokens."""
        if self.use_gcp:
            from firebase_admin import messaging

            message = messaging.MulticastMessage(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                tokens=tokens,
            )
            try:
                result = retry_with_backoff(
                    operation=lambda: self.circuit_breaker.call(
                        lambda: messaging.send_each_for_multicast(message)
                    ),
                    operation_name="fcm.send_multicast",
                    max_attempts=self.max_attempts,
                )
                logger.info(f"FCM multicast: {result.success_count} success, {result.failure_count} failures")
            except Exception as e:
                logger.error(
                    json.dumps(
                        {
                            "event": "fcm_multicast_failed",
                            "service": "fcm",
                            "token_count": len(tokens),
                            "error": str(e),
                        },
                        separators=(",", ":"),
                    )
                )
            return
        else:
            logger.info(f"[LOCAL FCM] → {len(tokens)} tokens | title=\"{title}\"")
