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