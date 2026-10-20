#
# Copyright (C) 2026 The Android Open Source Project
# Copyright (C) 2026 SebaUbuntu's TWRP device tree generator
#
# SPDX-License-Identifier: Apache-2.0
#

# Inherit from those products. Most specific first.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)
# Installs gsi keys into ramdisk, to boot a developer GSI with verified boot.
$(call inherit-product, $(SRC_TARGET_DIR)/product/gsi_keys.mk)

# Inherit some common TWRP stuff.
$(call inherit-product, vendor/twrp/config/common.mk)

# Inherit from the device tree (path agnostic, works in any folder name)
LOCAL_PATH := $(call my-dir)

$(call inherit-product, $(LOCAL_PATH)/device.mk)

PRODUCT_DEVICE := RMX3933
PRODUCT_NAME := twrp_RMX3933
PRODUCT_BRAND := realme
PRODUCT_MODEL := realme Note 60
PRODUCT_MANUFACTURER := realme

PRODUCT_GMS_CLIENTID_BASE := android-oppo

PRODUCT_BUILD_PROP_OVERRIDES += \
    PRIVATE_BUILD_DESC="ums9230_latte_Natv-user 16 BP2A.250605.031.A3 18 release-keys"

BUILD_FINGERPRINT := realme/RMX3933/RE6057:16/BP2A.250605.031.A3/U.R4T2.1785291165:user/release-keys
