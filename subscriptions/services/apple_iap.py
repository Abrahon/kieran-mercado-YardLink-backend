import os

from django.conf import settings

from appstoreserverlibrary.api_client import (
    AppStoreServerAPIClient,
)
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.signed_data_verifier import (
    SignedDataVerifier,
)

from appstoreserverlibrary.models.JWSTransactionDecodedPayload import (
    JWSTransactionDecodedPayload,
)

from appstoreserverlibrary.models.ResponseBodyV2DecodedPayload import (
    ResponseBodyV2DecodedPayload,
)


# ============================================================
# Apple configuration
# ============================================================

APPLE_KEY_ID = settings.APPLE_KEY_ID
APPLE_ISSUER_ID = settings.APPLE_ISSUER_ID
APPLE_BUNDLE_ID = settings.APPLE_BUNDLE_ID

APPLE_PRIVATE_KEY_PATH = settings.APPLE_PRIVATE_KEY_PATH

APPLE_ROOT_CERTIFICATES_PATH = (
    settings.APPLE_ROOT_CERTIFICATES_PATH
)


def get_apple_private_key():
    """
    Reads Apple's App Store Connect private key.
    """

    with open(
        APPLE_PRIVATE_KEY_PATH,
        "rb"
    ) as file:

        return file.read()


def get_apple_root_certificates():
    """
    Loads Apple's root certificates used
    to verify signed JWS payloads.
    """

    certificates = []

    for filename in os.listdir(
        APPLE_ROOT_CERTIFICATES_PATH
    ):

        if not filename.endswith(
            (".cer", ".pem")
        ):
            continue

        file_path = os.path.join(
            APPLE_ROOT_CERTIFICATES_PATH,
            filename
        )

        with open(
            file_path,
            "rb"
        ) as file:

            certificates.append(
                file.read()
            )

    return certificates


# ============================================================
# Environment
# ============================================================

def get_apple_environment():
    """
    Returns Apple's configured environment.
    """

    environment = getattr(
        settings,
        "APPLE_ENVIRONMENT",
        "sandbox"
    ).lower()

    if environment == "production":

        return Environment.PRODUCTION

    return Environment.SANDBOX


# ============================================================
# Apple API Client
# ============================================================

def get_apple_api_client():

    private_key = get_apple_private_key()

    environment = get_apple_environment()

    client = AppStoreServerAPIClient(
        signing_key=private_key,
        key_id=APPLE_KEY_ID,
        issuer_id=APPLE_ISSUER_ID,
        bundle_id=APPLE_BUNDLE_ID,
        environment=environment,
    )

    return client


# ============================================================
# Verify transaction
# ============================================================

def verify_apple_transaction(transaction_id):
    """
    Retrieves transaction information from Apple's
    App Store Server API.

    Returns decoded transaction information.
    """

    client = get_apple_api_client()

    response = client.get_transaction_info(
        transaction_id
    )

    signed_transaction_info = (
        response.signedTransactionInfo
    )

    if not signed_transaction_info:
        raise ValueError(
            "Apple did not return signed transaction information."
        )

    verifier = SignedDataVerifier(
        root_certificates=get_apple_root_certificates(),
        enable_online_checks=True,
        environment=get_apple_environment(),
        bundle_id=APPLE_BUNDLE_ID,
        app_apple_id=None,
    )

    decoded_transaction = (
        verifier.verify_and_decode_signed_transaction(
            signed_transaction_info
        )
    )

    return decoded_transaction


# ============================================================
# Verify Apple Notification V2
# ============================================================

def verify_apple_notification(
    signed_payload
):
    """
    Verifies Apple's App Store Server
    Notification V2 signedPayload.

    Returns the decoded notification payload.
    """

    if not signed_payload:

        raise ValueError(
            "signedPayload is required."
        )

    verifier = SignedDataVerifier(
        root_certificates=get_apple_root_certificates(),
        enable_online_checks=True,
        environment=get_apple_environment(),
        bundle_id=APPLE_BUNDLE_ID,
        app_apple_id=None,
    )

    decoded_notification = (
        verifier.verify_and_decode_notification(
            signed_payload
        )
    )

    return decoded_notification


def verify_signed_transaction_info(
    signed_transaction_info
):
    """
    Verify and decode the signed transaction
    contained inside an Apple notification.
    """

    if not signed_transaction_info:

        raise ValueError(
            "signedTransactionInfo is missing."
        )

    verifier = SignedDataVerifier(
        root_certificates=get_apple_root_certificates(),
        enable_online_checks=True,
        environment=get_apple_environment(),
        bundle_id=APPLE_BUNDLE_ID,
        app_apple_id=None,
    )

    transaction = (
        verifier.verify_and_decode_signed_transaction(
            signed_transaction_info
        )
    )

    return transaction
# ============================================================
# Process Apple Subscription Notification
# ============================================================

def process_apple_subscription_notification(notification):
    """
    Process a verified App Store Server Notification V2.

    The notification must already be verified using
    verify_apple_notification().

    Updates the local Subscription record based on
    Apple's notification type/subtype.
    """

    from django.utils import timezone
    from subscriptions.models import Subscription, SubscriptionStatus

    # --------------------------------------------------------
    # Get notification type
    # --------------------------------------------------------

    notification_type = getattr(
        notification,
        "notificationType",
        None
    )

    subtype = getattr(
        notification,
        "subtype",
        None
    )

    data = getattr(
        notification,
        "data",
        None
    )

    if not data:
        return {
            "processed": False,
            "message": "Notification data is missing."
        }

    # --------------------------------------------------------
    # Get signed transaction information
    # --------------------------------------------------------

    signed_transaction_info = getattr(
        data,
        "signedTransactionInfo",
        None
    )

    if not signed_transaction_info:
        return {
            "processed": False,
            "message": "signedTransactionInfo is missing."
        }

    # --------------------------------------------------------
    # Verify transaction
    # --------------------------------------------------------

    transaction = verify_signed_transaction_info(
        signed_transaction_info
    )

    # --------------------------------------------------------
    # Extract Apple transaction IDs
    # --------------------------------------------------------

    transaction_id = getattr(
        transaction,
        "transactionId",
        None
    )

    original_transaction_id = getattr(
        transaction,
        "originalTransactionId",
        None
    )

    product_id = getattr(
        transaction,
        "productId",
        None
    )

    expires_date = getattr(
        transaction,
        "expiresDate",
        None
    )

    purchase_date = getattr(
        transaction,
        "purchaseDate",
        None
    )

    if not original_transaction_id:
        return {
            "processed": False,
            "message": "originalTransactionId is missing."
        }

    # --------------------------------------------------------
    # Find local subscription
    # --------------------------------------------------------

    subscription = (
        Subscription.objects
        .select_related("user", "plan")
        .filter(
            apple_original_transaction_id=
                original_transaction_id
        )
        .order_by("-created_at")
        .first()
    )

    if not subscription:

        # Fallback to current transaction ID
        if transaction_id:
            subscription = (
                Subscription.objects
                .select_related("user", "plan")
                .filter(
                    apple_transaction_id=transaction_id
                )
                .order_by("-created_at")
                .first()
            )

    if not subscription:

        return {
            "processed": False,
            "message": "Subscription not found.",
            "original_transaction_id":
                original_transaction_id,
            "transaction_id":
                transaction_id,
            "product_id":
                product_id,
        }

    # --------------------------------------------------------
    # Update Apple transaction information
    # --------------------------------------------------------

    subscription.apple_original_transaction_id = (
        original_transaction_id
    )

    if transaction_id:
        subscription.apple_transaction_id = transaction_id

    subscription.payment_provider = "apple"

    # --------------------------------------------------------
    # Process notification types
    # --------------------------------------------------------

    # --------------------------------------------------------
    # DID_RENEW
    # --------------------------------------------------------

    if notification_type == "DID_RENEW":

        subscription.status = (
            SubscriptionStatus.ACTIVE
        )

        subscription.is_active = True
        subscription.is_trial = False

        if purchase_date:
            subscription.start_date = (
                timezone.datetime.fromtimestamp(
                    purchase_date / 1000,
                    tz=timezone.utc
                )
            )

        if expires_date:
            subscription.end_date = (
                timezone.datetime.fromtimestamp(
                    expires_date / 1000,
                    tz=timezone.utc
                )
            )

        subscription.auto_renew = True

    # --------------------------------------------------------
    # DID_CHANGE_RENEWAL_STATUS
    # --------------------------------------------------------

    elif notification_type == "DID_CHANGE_RENEWAL_STATUS":

        if subtype == "AUTO_RENEW_DISABLED":

            subscription.auto_renew = False

        elif subtype == "AUTO_RENEW_ENABLED":

            subscription.auto_renew = True

    # --------------------------------------------------------
    # DID_FAIL_TO_RENEW
    # --------------------------------------------------------

    elif notification_type == "DID_FAIL_TO_RENEW":

        subscription.status = (
            SubscriptionStatus.PAST_DUE
            if hasattr(
                SubscriptionStatus,
                "PAST_DUE"
            )
            else "past_due"
        )

        subscription.is_active = False

    # --------------------------------------------------------
    # EXPIRED
    # --------------------------------------------------------

    elif notification_type == "EXPIRED":

        subscription.status = (
            SubscriptionStatus.EXPIRED
            if hasattr(
                SubscriptionStatus,
                "EXPIRED"
            )
            else "expired"
        )

        subscription.is_active = False
        subscription.auto_renew = False

        if expires_date:
            subscription.end_date = (
                timezone.datetime.fromtimestamp(
                    expires_date / 1000,
                    tz=timezone.utc
                )
            )

    # --------------------------------------------------------
    # GRACE_PERIOD_EXPIRED
    # --------------------------------------------------------

    elif notification_type == "GRACE_PERIOD_EXPIRED":

        subscription.status = (
            SubscriptionStatus.EXPIRED
            if hasattr(
                SubscriptionStatus,
                "EXPIRED"
            )
            else "expired"
        )

        subscription.is_active = False

    # --------------------------------------------------------
    # REFUND
    # --------------------------------------------------------

    elif notification_type == "REFUND":

        subscription.status = (
            SubscriptionStatus.CANCELLED
            if hasattr(
                SubscriptionStatus,
                "CANCELLED"
            )
            else "cancelled"
        )

        subscription.is_active = False
        subscription.auto_renew = False

    # --------------------------------------------------------
    # REVOKE
    # --------------------------------------------------------

    elif notification_type == "REVOKE":

        subscription.status = (
            SubscriptionStatus.CANCELLED
            if hasattr(
                SubscriptionStatus,
                "CANCELLED"
            )
            else "cancelled"
        )

        subscription.is_active = False
        subscription.auto_renew = False

    # --------------------------------------------------------
    # DID_RENEW / other events with expiration
    # --------------------------------------------------------

    if expires_date:

        subscription.end_date = (
            timezone.datetime.fromtimestamp(
                expires_date / 1000,
                tz=timezone.utc
            )
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    subscription.save()

    return {
        "processed": True,
        "notification_type": notification_type,
        "subtype": subtype,
        "subscription_id": subscription.id,
        "transaction_id": transaction_id,
        "original_transaction_id":
            original_transaction_id,
        "product_id": product_id,
        "status": subscription.status,
        "is_active": subscription.is_active,
    }