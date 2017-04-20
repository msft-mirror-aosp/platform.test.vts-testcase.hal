/*
 * Copyright (C) 2017 The Android Open Source Project
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

#include <functional>
#include <iostream>
#include <set>
#include <string>

#include <android/hidl/manager/1.0/IServiceManager.h>
#include <gtest/gtest.h>
#include <hidl-util/FQName.h>
#include <hidl/ServiceManagement.h>
#include <vintf/HalManifest.h>
#include <vintf/VintfObject.h>

using android::FQName;
using android::hidl::manager::V1_0::IServiceManager;
using android::sp;
using android::vintf::HalManifest;
using android::vintf::Transport;
using android::vintf::Version;

using std::cout;
using std::endl;
using std::set;
using std::string;
using HalVerifyFn =
    std::function<void(const FQName &fq_name, const string &instance_name)>;

// HALs that are allowed to be passthrough under Treble rules.
static const set<string> kPassthroughHals = {
    "android.hardware.graphics.mapper",
    "android.hardware.renderscript",
};

class VtsTrebleVintfTest : public ::testing::Test {
 public:
  virtual void SetUp() override {
    default_manager_ = ::android::hardware::defaultServiceManager();
    ASSERT_NE(default_manager_, nullptr)
        << "Failed to get default service manager." << endl;

    passthrough_manager_ = ::android::hardware::getPassthroughServiceManager();
    ASSERT_NE(passthrough_manager_, nullptr)
        << "Failed to get passthrough service manager." << endl;

    vendor_manifest_ = ::android::vintf::VintfObject::GetDeviceHalManifest();
    ASSERT_NE(passthrough_manager_, nullptr)
        << "Failed to get vendor HAL manifest." << endl;
  }

  // Applies given function to each HAL instance in VINTF.
  void ForEachHalInstance(HalVerifyFn);

  // Default service manager.
  sp<IServiceManager> default_manager_;
  // Passthrough service manager.
  sp<IServiceManager> passthrough_manager_;
  // Vendor hal manifest.
  const HalManifest *vendor_manifest_;
};

void VtsTrebleVintfTest::ForEachHalInstance(HalVerifyFn fn) {
  auto hal_names = vendor_manifest_->getHalNames();
  for (const auto &hal_name : hal_names) {
    auto versions = vendor_manifest_->getSupportedVersions(hal_name);
    auto iface_names = vendor_manifest_->getInterfaceNames(hal_name);
    for (const auto &iface_name : iface_names) {
      auto instance_names =
          vendor_manifest_->getInstances(hal_name, iface_name);
      for (const auto &version : versions) {
        for (const auto &instance_name : instance_names) {
          string major_ver = std::to_string(version.majorVer);
          string minor_ver = std::to_string(version.minorVer);
          string full_ver = major_ver + "." + minor_ver;
          FQName fq_name{hal_name, full_ver, iface_name};
          fn(fq_name, instance_name);
        }
      }
    }
  }
}

// Tests that all HAL entries in VINTF has all required fields filled out.
TEST_F(VtsTrebleVintfTest, HalEntriesAreComplete) {
  auto hal_names = vendor_manifest_->getHalNames();
  for (const auto &hal_name : hal_names) {
    auto versions = vendor_manifest_->getSupportedVersions(hal_name);
    EXPECT_FALSE(versions.empty())
        << hal_name << " has no version specified in VINTF.";
    auto iface_names = vendor_manifest_->getInterfaceNames(hal_name);
    EXPECT_FALSE(iface_names.empty())
        << hal_name << " has no interface specified in VINTF.";
    for (const auto &iface_name : iface_names) {
      auto instances = vendor_manifest_->getInstances(hal_name, iface_name);
      EXPECT_FALSE(instances.empty())
          << hal_name << " has no instance specified in VINTF.";
    }
  }
}

// Tests that no HAL outside of the allowed set is specified as passthrough in
// VINTF.
TEST_F(VtsTrebleVintfTest, HalsAreBinderized) {
  // Verifies that HAL is binderized unless it's allowed to be passthrough.
  HalVerifyFn is_binderized = [this](const FQName &fq_name,
                                     const string &instance_name) {
    cout << "Verifying transport method of: " << fq_name.string() << endl;
    string hal_name = fq_name.package();
    Version version{fq_name.getPackageMajorVersion(),
                    fq_name.getPackageMinorVersion()};
    string iface_name = fq_name.name();

    Transport transport = vendor_manifest_->getTransport(
        hal_name, version, iface_name, instance_name);

    EXPECT_NE(transport, Transport::EMPTY)
        << hal_name << " has no transport specified in VINTF.";

    if (transport == Transport::PASSTHROUGH) {
      EXPECT_NE(kPassthroughHals.find(hal_name), kPassthroughHals.end())
          << hal_name << " can't be passthrough under Treble rules.";
    }
  };

  ForEachHalInstance(is_binderized);
}

// Tests that all HALs specified in the VINTF are available through service
// manager.
TEST_F(VtsTrebleVintfTest, VintfHalsAreServed) {
  // Verifies that HAL is available through service manager.
  HalVerifyFn is_available = [this](const FQName &fq_name,
                                    const string &instance_name) {
    string hal_name = fq_name.package();
    Version version{fq_name.getPackageMajorVersion(),
                    fq_name.getPackageMinorVersion()};
    string iface_name = fq_name.name();
    string fq_iface_name = fq_name.string();
    cout << "Attempting to get service of: " << fq_iface_name << endl;

    Transport transport = vendor_manifest_->getTransport(
        hal_name, version, iface_name, instance_name);

    if (transport == Transport::HWBINDER) {
      android::sp<android::hidl::base::V1_0::IBase> hal_service =
          default_manager_->get(fq_iface_name, instance_name);
      EXPECT_NE(hal_service, nullptr);
    } else if (transport == Transport::PASSTHROUGH) {
      android::sp<android::hidl::base::V1_0::IBase> hal_service =
          passthrough_manager_->get(fq_iface_name, instance_name);
      EXPECT_NE(hal_service, nullptr);
    } else {
      FAIL() << hal_name << "has unknown transport method.";
    }
  };

  ForEachHalInstance(is_available);
}

int main(int argc, char **argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
