# Copyright (C) 2019 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_PACKAGE_NAME := VtsHalNeuralnetworksV1_3BenchmarkTestCases

# Don't include this package in any target
LOCAL_MODULE_TAGS := optional
# And when built explicitly put it in the data partition
LOCAL_MODULE_PATH := $(TARGET_OUT_DATA_APPS)

# Include both the 32 and 64 bit versions
LOCAL_MULTILIB := both

# TODO: This is from the CTS app. Figure out the proper way to do this in VTS.
# Tag this module as a cts test artifact
LOCAL_COMPATIBILITY_SUITE := cts vts10

LOCAL_STATIC_JAVA_LIBRARIES := androidx.test.rules \
    compatibility-device-util-axt ctstestrunner-axt junit NeuralNetworksApiBenchmark_Lib
LOCAL_JNI_SHARED_LIBRARIES := libnnbenchmark_jni

LOCAL_SRC_FILES := $(call all-java-files-under, src)
LOCAL_ASSET_DIR := test/mlts/models/assets

LOCAL_SDK_VERSION := current

include $(BUILD_CTS_PACKAGE)
