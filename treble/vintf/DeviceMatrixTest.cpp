/*
 * Copyright (C) 2018 The Android Open Source Project
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "DeviceMatrixTest.h"

#include <android-base/parseint.h>
#include <android-base/properties.h>
#include <android/api-level.h>
#include <vintf/VintfObject.h>

using android::base::GetProperty;

namespace android {
namespace vintf {
namespace testing {

const string kVndkVersionProp{"ro.vndk.version"};

void DeviceMatrixTest::SetUp() {
  VtsTrebleVintfTestBase::SetUp();

  vendor_matrix_ = VintfObject::GetDeviceCompatibilityMatrix();
  ASSERT_NE(nullptr, vendor_matrix_)
      << "Failed to get device compatibility matrix." << endl;
}

// @VsrTest = VSR-3.2-014
TEST_F(DeviceMatrixTest, VndkVersion) {
  if (GetBoardApiLevel() < __ANDROID_API_P__) {
    GTEST_SKIP()
        << "VNDK version doesn't need to be set on devices before Android P";
  }

  std::string syspropVndkVersion = GetProperty(kVndkVersionProp, "");

  // TODO(b/306081093) As of VNDK deprecation, there is no good property to
  // check which platform version is used to build vendor. For now, let's assume
  // that any device running board api level Android R or above can be a
  // candidate of Android V, and skip test for those devices. This should be
  // revisited once we have a new property to check platform version used to
  // build vendor.
  if (GetBoardApiLevel() >= __ANDROID_API_R__) {
    // TODO(b/306081093) When vendor's target platform is greater or equal than
    // V, check if vendor VNDK version (both sysprop and VINTF) is empty and
    // fail if not.
    if (syspropVndkVersion.empty()) {
      GTEST_SKIP() << "VNDK version doesn't need to be set on devices built "
                      "with Android V";
    }

    uint64_t syspropVndkVersionNumber;
    if (!android::base::ParseUint(syspropVndkVersion, &syspropVndkVersionNumber)) {
      syspropVndkVersionNumber = 0;
    }

    ASSERT_LE(syspropVndkVersionNumber, __ANDROID_API_V__)
        << kVndkVersionProp << " must be less or equal than "
        << __ANDROID_API_V__;

    if (syspropVndkVersionNumber == __ANDROID_API_V__) {
      GTEST_SKIP()
          << "VNDK version 35 may not have matching VINTF VNDK version.";
    }
  }

  ASSERT_NE("", syspropVndkVersion)
      << kVndkVersionProp << " must not be empty.";

  std::string vintfVndkVersion = vendor_matrix_->getVendorNdkVersion();
  ASSERT_NE("", vintfVndkVersion)
      << "Device compatibility matrix does not declare proper VNDK version.";

  EXPECT_EQ(syspropVndkVersion, vintfVndkVersion)
      << "VNDK version does not match: " << kVndkVersionProp << "="
      << syspropVndkVersion << ", device compatibility matrix requires "
      << vintfVndkVersion << ".";
}

}  // namespace testing
}  // namespace vintf
}  // namespace android
