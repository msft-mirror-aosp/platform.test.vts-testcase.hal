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

#include "DeviceManifestTest.h"

#include <android-base/result.h>
#include <libvts_vintf_test_common/common.h>
#include <vintf/VintfObject.h>

#include "SingleManifestTest.h"

namespace android {
namespace vintf {
namespace testing {

void DeviceManifestTest::SetUp() {
  VtsTrebleVintfTestBase::SetUp();

  vendor_manifest_ = VintfObject::GetDeviceHalManifest();
  ASSERT_NE(vendor_manifest_, nullptr)
      << "Failed to get vendor HAL manifest." << endl;
}

// Tests that Shipping FCM Version in the device manifest is at least the
// minimum Shipping FCM Version as required by Shipping API level.
TEST_F(DeviceManifestTest, ShippingFcmVersion) {
  uint64_t shipping_api_level = GetShippingApiLevel();
  Level shipping_fcm_version = VintfObject::GetDeviceHalManifest()->level();
  auto res = TestTargetFcmVersion(shipping_fcm_version, shipping_api_level);
  ASSERT_RESULT_OK(res);
}

// Tests that deprecated HALs are not in the manifest, unless a higher,
// non-deprecated minor version is in the manifest.
TEST_F(DeviceManifestTest, NoDeprecatedHalsOnManifest) {
  string error;
  EXPECT_EQ(android::vintf::NO_DEPRECATED_HALS,
            VintfObject::GetInstance()->checkDeprecation(
                HidlInterfaceMetadata::all(), &error))
      << error;
}

static std::vector<HalManifestPtr> GetTestManifests() {
  return {
      VintfObject::GetDeviceHalManifest(),
  };
}

INSTANTIATE_TEST_CASE_P(DeviceManifest, SingleManifestTest,
                        ::testing::ValuesIn(GetTestManifests()));

}  // namespace testing
}  // namespace vintf
}  // namespace android
