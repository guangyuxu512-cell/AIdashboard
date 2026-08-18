from enum import Enum


class VerificationChannel(str, Enum):
    MANUAL = "manual"
    EMAIL = "email"
    SMS_HARDWARE = "sms_hardware"
