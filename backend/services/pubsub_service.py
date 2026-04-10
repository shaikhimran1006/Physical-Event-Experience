"""
Pub/Sub Service — Message publishing and subscribing.
Supports GCP Pub/Sub or local logging fallback.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)


class PubSubService:
    def __init__(self, use_gcp: bool = False):
        self.use_gcp = use_gcp
        self.project_id = os.getenv("GCP_PROJECT_ID", "stadium-os-copilot")
        self.publisher = None

        if use_gcp:
            try:
                from google.cloud import pubsub_v1
                self.publisher = pubsub_v1.PublisherClient()
            except Exception as exc:
                logger.warning(
                    "Pub/Sub initialization failed; falling back to local mode. "
                    "Set USE_GCP=false for local runs or configure ADC/service account for GCP. Error: %s",
                    exc,
                )
                self.use_gcp = False

    def publish(self, topic_name: str, data: dict):
        """Publish a message to a Pub/Sub topic."""
        if self.use_gcp and self.publisher:
            try:
                topic_path = self.publisher.topic_path(self.project_id, topic_name)
                message_bytes = json.dumps(data).encode("utf-8")
                future = self.publisher.publish(topic_path, data=message_bytes)
                result = future.result()
                logger.info(f"Published to {topic_name}: {result}")
                return result
            except Exception as exc:
                logger.error(
                    "Pub/Sub publish failed; using local fallback for topic %s. Error: %s",
                    topic_name,
                    exc,
                )
        else:
            logger.info(f"[LOCAL PubSub] {topic_name}: {json.dumps(data)[:200]}")
            return "local-message-id"

        logger.info(f"[LOCAL PubSub] {topic_name}: {json.dumps(data)[:200]}")
        return "local-message-id"

    def create_subscription(self, topic_name: str, subscription_name: str):
        """Create a pull subscription (for setup only)."""
        if not self.use_gcp:
            logger.info(f"[LOCAL] Would create subscription {subscription_name} for {topic_name}")
            return

        from google.cloud import pubsub_v1
        subscriber = pubsub_v1.SubscriberClient()
        topic_path = self.publisher.topic_path(self.project_id, topic_name)
        sub_path = subscriber.subscription_path(self.project_id, subscription_name)

        try:
            subscriber.create_subscription(
                request={"name": sub_path, "topic": topic_path, "ack_deadline_seconds": 60}
            )
            logger.info(f"Created subscription {subscription_name}")
        except Exception as e:
            logger.warning(f"Subscription may already exist: {e}")
