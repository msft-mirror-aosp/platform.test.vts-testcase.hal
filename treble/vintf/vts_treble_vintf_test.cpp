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

#include <chrono>
#include <functional>
#include <future>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

#include <android-base/properties.h>
#include <android-base/strings.h>
#include <android/hidl/manager/1.0/IServiceManager.h>
#include <gtest/gtest.h>
#include <hidl-hash/Hash.h>
#include <hidl-util/FQName.h>
#include <hidl/ServiceManagement.h>
#include <procpartition/procpartition.h>
#include <vintf/HalManifest.h>
#include <vintf/VintfObject.h>
#include <vintf/parse_string.h>

using android::FQName;
using android::Hash;
using android::sp;
using android::base::GetUintProperty;
using android::hardware::hidl_array;
using android::hardware::hidl_string;
using android::hardware::hidl_vec;
using android::hardware::Return;
using android::hidl::base::V1_0::IBase;
using android::hidl::manager::V1_0::IServiceManager;
using android::procpartition::Partition;
using android::vintf::HalManifest;
using android::vintf::Level;
using android::vintf::ManifestHal;
using android::vintf::Transport;
using android::vintf::Version;
using android::vintf::VintfObject;
using android::vintf::operator<<;
using android::vintf::to_string;

using std::cout;
using std::endl;
using std::map;
using std::set;
using std::string;
using std::vector;
using HalVerifyFn = std::function<void(const FQName &fq_name,
                                       const string &instance_name, Transport)>;
using HashCharArray = hidl_array<unsigned char, 32>;
using HalManifestPtr = std::shared_ptr<const HalManifest>;

// Path to directory on target containing test data.
static const string kDataDir = "/data/local/tmp/";

// Name of file containing HAL hashes.
static const string kHashFileName = "current.txt";

// Map from package name to package root.
static const map<string, string> kPackageRoot = {
    {"android.frameworks", "frameworks/hardware/interfaces/"},
    {"android.hardware", "hardware/interfaces/"},
    {"android.hidl", "system/libhidl/transport/"},
    {"android.system", "system/hardware/interfaces/"},
};

// HALs that are allowed to be passthrough under Treble rules.
static const set<string> kPassthroughHals = {
    "android.hardware.graphics.mapper", "android.hardware.renderscript",
    "android.hidl.memory",
};

// kFcm2ApiLevelMap is associated with API level. There can be multiple
// Framework Compatibility Matrix Version (FCM Version) per API level, or
// multiple API levels per FCM version.
// kFcm2ApiLevelMap is defined apart from android::vintf::Level. Level is an
// integer designed to be irrelevant with API level; the O / O_MR1 values are
// historic values for convenience, and should be removed (b/70628538). Hence
// these values are not used here.
// For example:
//    ...
//    // Assume devices launch with Android X must implement FCM version >= 9
//    X = 9,
//    // Assume devices launch with Android Y and Android Z must implement
//    // FCM version >= 11
//    Y = 11,
//    Z = 11
static const map<size_t /* Shipping API Level */, Level /* FCM Version */>
    kFcm2ApiLevelMap{{// N. The test runs on devices that launch with N and
                      // become a Treble device when upgrading to O.
                      {25, static_cast<Level>(1)},
                      // O
                      {26, static_cast<Level>(1)},
                      // O MR-1
                      {27, static_cast<Level>(2)},
                      // P
                      {28, static_cast<Level>(3)}}};

static const string kShippingApiLevelProp = "ro.product.first_api_level";

// For a given interface returns package root if known. Returns empty string
// otherwise.
static const string PackageRoot(const FQName &fq_iface_name) {
  for (const auto &package_root : kPackageRoot) {
    if (fq_iface_name.inPackage(package_root.first)) {
      return package_root.second;
    }
  }
  return "";
}

// Returns true iff HAL interface is Google-defined.
static bool IsGoogleDefinedIface(const FQName &fq_iface_name) {
  // Package roots are only known for Google-defined packages.
  return !PackageRoot(fq_iface_name).empty();
}

// Returns the set of released hashes for a given HAL interface.
static set<string> ReleasedHashes(const FQName &fq_iface_name) {
  set<string> released_hashes{};
  string err = "";

  string file_path = kDataDir + PackageRoot(fq_iface_name) + kHashFileName;
  auto hashes = Hash::lookupHash(file_path, fq_iface_name.string(), &err);
  released_hashes.insert(hashes.begin(), hashes.end());
  return released_hashes;
}

// Returns the partition that a HAL is associated with.
static Partition PartitionOfProcess(int32_t pid) {
  auto partition = android::procpartition::getPartition(pid);

  // TODO(b/70033981): remove once ODM and Vendor manifests are distinguished
  if (partition == Partition::ODM) {
    partition = Partition::VENDOR;
  }

  return partition;
}

class VtsTrebleVintfTest : public ::testing::Test {
 public:
  virtual void SetUp() override {
    default_manager_ = ::android::hardware::defaultServiceManager();
    ASSERT_NE(default_manager_, nullptr)
        << "Failed to get default service manager." << endl;

    passthrough_manager_ = ::android::hardware::getPassthroughServiceManager();
    ASSERT_NE(passthrough_manager_, nullptr)
        << "Failed to get passthrough service manager." << endl;

    vendor_manifest_ = VintfObject::GetDeviceHalManifest();
    ASSERT_NE(vendor_manifest_, nullptr)
        << "Failed to get vendor HAL manifest." << endl;

    fwk_manifest_ = VintfObject::GetFrameworkHalManifest();
    ASSERT_NE(fwk_manifest_, nullptr)
        << "Failed to get framework HAL manifest." << endl;
  }

  // Applies given function to each HAL instance in VINTF.
  void ForEachHalInstance(const HalManifestPtr &, HalVerifyFn);
  // Retrieves an existing HAL service.
  sp<IBase> GetHalService(const FQName &fq_name, const string &instance_name,
                          Transport, bool log = true);

  static vector<string> GetInterfaceChain(const sp<IBase> &service);

  // Default service manager.
  sp<IServiceManager> default_manager_;
  // Passthrough service manager.
  sp<IServiceManager> passthrough_manager_;
  // Vendor hal manifest.
  HalManifestPtr vendor_manifest_;
  // Framework hal manifest.
  HalManifestPtr fwk_manifest_;
};

void VtsTrebleVintfTest::ForEachHalInstance(const HalManifestPtr &manifest,
                                            HalVerifyFn fn) {
  auto hal_names = manifest->getHalNames();
  for (const string &hal_name : hal_names) {
    for (const ManifestHal *hal : manifest->getHals(hal_name)) {
      for (const Version &version : hal->versions) {
        for (const auto &it : hal->interfaces) {
          string iface_name = it.first;
          set<string> instances = it.second.instances;
          for (const string &instance_name : instances) {
            string major_ver = std::to_string(version.majorVer);
            string minor_ver = std::to_string(version.minorVer);
            string full_ver = major_ver + "." + minor_ver;
            FQName fq_name{hal_name, full_ver, iface_name};
            Transport transport = hal->transport();

            auto future_result =
                std::async([&]() { fn(fq_name, instance_name, transport); });
            auto timeout = std::chrono::milliseconds(500);
            std::future_status status = future_result.wait_for(timeout);
            if (status != std::future_status::ready) {
              cout << "Timed out on: " << fq_name.string() << " "
                   << instance_name << endl;
            }
          }
        }
      }
    }
  }
}

sp<IBase> VtsTrebleVintfTest::GetHalService(const FQName &fq_name,
                                            const string &instance_name,
                                            Transport transport, bool log) {
  string hal_name = fq_name.package();
  Version version{fq_name.getPackageMajorVersion(),
                  fq_name.getPackageMinorVersion()};
  string iface_name = fq_name.name();
  string fq_iface_name = fq_name.string();

  if (log) {
    cout << "Getting service of: " << fq_iface_name << " " << instance_name
         << endl;
  }

  android::sp<IBase> hal_service = nullptr;
  if (transport == Transport::HWBINDER) {
    hal_service = default_manager_->get(fq_iface_name, instance_name);
  } else if (transport == Transport::PASSTHROUGH) {
    hal_service = passthrough_manager_->get(fq_iface_name, instance_name);
  }
  return hal_service;
}

vector<string> VtsTrebleVintfTest::GetInterfaceChain(const sp<IBase> &service) {
  vector<string> iface_chain{};
  service->interfaceChain([&iface_chain](const hidl_vec<hidl_string> &chain) {
    for (const auto &iface_name : chain) {
      iface_chain.push_back(iface_name);
    }
  });
  return iface_chain;
}

// Tests that all HAL entries in VINTF has all required fields filled out.
TEST_F(VtsTrebleVintfTest, HalEntriesAreComplete) {
  auto hal_names = vendor_manifest_->getHalNames();
  for (const string &hal_name : hal_names) {
    for (const ManifestHal *hal : vendor_manifest_->getHals(hal_name)) {
      EXPECT_FALSE(hal->versions.empty())
          << hal_name << " has no version specified in VINTF.";
      EXPECT_FALSE(hal->interfaces.empty())
          << hal_name << " has no interface specified in VINTF.";
      for (const auto &it : hal->interfaces) {
        EXPECT_FALSE(it.second.instances.empty())
            << hal_name << " has no instance specified in VINTF.";
      }
    }
  }
}

// Tests that no HAL outside of the allowed set is specified as passthrough in
// VINTF.
TEST_F(VtsTrebleVintfTest, HalsAreBinderized) {
  // Verifies that HAL is binderized unless it's allowed to be passthrough.
  HalVerifyFn is_binderized = [](const FQName &fq_name,
                                 const string & /* instance_name */,
                                 Transport transport) {
    cout << "Verifying transport method of: " << fq_name.string() << endl;
    string hal_name = fq_name.package();
    Version version{fq_name.getPackageMajorVersion(),
                    fq_name.getPackageMinorVersion()};
    string iface_name = fq_name.name();

    EXPECT_NE(transport, Transport::EMPTY)
        << hal_name << " has no transport specified in VINTF.";

    if (transport == Transport::PASSTHROUGH) {
      EXPECT_NE(kPassthroughHals.find(hal_name), kPassthroughHals.end())
          << hal_name << " can't be passthrough under Treble rules.";
    }
  };

  ForEachHalInstance(vendor_manifest_, is_binderized);
  ForEachHalInstance(fwk_manifest_, is_binderized);
}

// Tests that all HALs specified in the VINTF are available through service
// manager.
// This tests (HAL in manifest) => (HAL is served)
TEST_F(VtsTrebleVintfTest, HalsAreServed) {
  // Returns a function that verifies that HAL is available through service
  // manager and is served from a specific set of partitions.
  auto is_available_from = [this](Partition expected_partition) -> HalVerifyFn {
    return [this, expected_partition](const FQName &fq_name,
                                      const string &instance_name,
                                      Transport transport) {
      sp<IBase> hal_service = GetHalService(fq_name, instance_name, transport);
      EXPECT_NE(hal_service, nullptr)
          << fq_name.string() << " not available." << endl;

      if (hal_service == nullptr || !hal_service->isRemote()) return;

      auto ret = hal_service->getDebugInfo([&](const auto &info) {
        Partition partition = PartitionOfProcess(info.pid);
        if (partition == Partition::UNKNOWN) return;
        EXPECT_EQ(expected_partition, partition)
            << fq_name.string() << " is in partition " << partition
            << " but is expected to be in " << expected_partition;
      });
      EXPECT_TRUE(ret.isOk());
    };
  };

  ForEachHalInstance(vendor_manifest_, is_available_from(Partition::VENDOR));
  ForEachHalInstance(fwk_manifest_, is_available_from(Partition::SYSTEM));
}

// Tests that all HALs which are served are specified in the VINTF
// This tests (binderized HAL is served) => (binderized HAL in manifest)
TEST_F(VtsTrebleVintfTest, ServedHalsAreInManifest) {
  std::set<std::string> manifest_hwbinder_hals_;

  auto add_manifest_hwbinder_hals = [&manifest_hwbinder_hals_](
                                        const FQName &fq_name,
                                        const string &instance_name,
                                        Transport transport) {
    if (transport != Transport::HWBINDER) return;

    // 1.n in manifest => 1.0, 1.1, ... 1.n are all served
    FQName fq = fq_name;
    while (true) {
      manifest_hwbinder_hals_.insert(fq.string() + "/" + instance_name);
      if (fq.getPackageMinorVersion() <= 0) {
        break;
      }
      fq = fq.downRev();
    }
  };

  ForEachHalInstance(vendor_manifest_, add_manifest_hwbinder_hals);
  ForEachHalInstance(fwk_manifest_, add_manifest_hwbinder_hals);

  Return<void> ret = default_manager_->list([&](const auto &list) {
    for (const auto &name : list) {
      // TODO(b/73774955): use standardized parsing code for fqinstancename
      if (std::string(name).find(IBase::descriptor) == 0) continue;

      EXPECT_NE(manifest_hwbinder_hals_.find(name),
                manifest_hwbinder_hals_.end())
          << name << " is being served, but it is not in a manifest.";
    }
  });
  EXPECT_TRUE(ret.isOk());
}

// Tests that HAL interfaces are officially released.
TEST_F(VtsTrebleVintfTest, InterfacesAreReleased) {
  // Verifies that HAL are released by fetching the hash of the interface and
  // comparing it to the set of known hashes of released interfaces.
  HalVerifyFn is_released = [this](const FQName &fq_name,
                                   const string &instance_name,
                                   Transport transport) {
    sp<IBase> hal_service = GetHalService(fq_name, instance_name, transport);

    if (hal_service == nullptr) {
      ADD_FAILURE() << fq_name.string() << " not available." << endl;
      return;
    }

    vector<string> iface_chain = GetInterfaceChain(hal_service);

    vector<string> hash_chain{};
    hal_service->getHashChain(
        [&hash_chain](const hidl_vec<HashCharArray> &chain) {
          for (const HashCharArray &hash_array : chain) {
            vector<uint8_t> hash{hash_array.data(),
                                 hash_array.data() + hash_array.size()};
            hash_chain.push_back(Hash::hexString(hash));
          }
        });

    ASSERT_EQ(iface_chain.size(), hash_chain.size());
    for (size_t i = 0; i < iface_chain.size(); ++i) {
      FQName fq_iface_name;
      if (!FQName::parse(iface_chain[i], &fq_iface_name)) {
        ADD_FAILURE() << "Could not parse iface name " << iface_chain[i]
                      << " from interface chain of " << fq_name.string();
        return;
      }
      string hash = hash_chain[i];
      // No interface is allowed to have an empty hash.
      EXPECT_NE(hash, Hash::hexString(Hash::kEmptyHash))
          << fq_iface_name.string()
          << " has an empty hash. This is because it was compiled without"
             " being frozen in a corresponding current.txt file.";

      if (IsGoogleDefinedIface(fq_iface_name)) {
        set<string> released_hashes = ReleasedHashes(fq_iface_name);
        EXPECT_NE(released_hashes.find(hash), released_hashes.end())
            << "Hash not found. This interface was not released." << endl
            << "Interface name: " << fq_iface_name.string() << endl
            << "Hash: " << hash << endl;
      }
    }
  };

  ForEachHalInstance(vendor_manifest_, is_released);
  ForEachHalInstance(fwk_manifest_, is_released);
}

// Tests that vendor and framework are compatible.
TEST(CompatiblityTest, VendorFrameworkCompatibility) {
  string error;

  EXPECT_TRUE(VintfObject::GetDeviceHalManifest()->checkCompatibility(
      *VintfObject::GetFrameworkCompatibilityMatrix(), &error))
      << error;

  EXPECT_TRUE(VintfObject::GetFrameworkHalManifest()->checkCompatibility(
      *VintfObject::GetDeviceCompatibilityMatrix(), &error))
      << error;

  // AVB version is not a compliance requirement.
  EXPECT_TRUE(VintfObject::GetRuntimeInfo()->checkCompatibility(
      *VintfObject::GetFrameworkCompatibilityMatrix(), &error,
      ::android::vintf::DISABLE_AVB_CHECK))
      << error;

  EXPECT_EQ(android::vintf::COMPATIBLE,
            VintfObject::CheckCompatibility(
                {}, &error, ::android::vintf::DISABLE_AVB_CHECK))
      << error;
}

class DeprecateTest : public VtsTrebleVintfTest {};

// Tests that Shipping FCM Version in the device manifest is at least the
// minimum Shipping FCM Version as required by Shipping API level.
TEST_F(DeprecateTest, ShippingFcmVersion) {
  uint64_t shipping_api_level =
      GetUintProperty<uint64_t>(kShippingApiLevelProp, 0);

  ASSERT_NE(shipping_api_level, 0u) << "sysprop " << kShippingApiLevelProp
                                    << " is missing or cannot be parsed.";
  Level shipping_fcm_version = VintfObject::GetDeviceHalManifest()->level();
  if (shipping_fcm_version == Level::UNSPECIFIED) {
    // O / O-MR1 vendor image doesn't have shipping FCM version declared and
    // shipping FCM version is inferred from Shipping API level, hence it always
    // meets the requirement.
    return;
  }

  ASSERT_GE(shipping_api_level, kFcm2ApiLevelMap.begin()->first /* 25 */)
      << "Pre-N devices should not run this test.";

  auto it = kFcm2ApiLevelMap.find(shipping_api_level);
  ASSERT_TRUE(it != kFcm2ApiLevelMap.end())
      << "No launch requirement is set yet for Shipping API level "
      << shipping_api_level << ". Please update the test.";

  Level required_fcm_version = it->second;

  ASSERT_GE(shipping_fcm_version, required_fcm_version)
      << "Shipping API level == " << shipping_api_level
      << " requires Shipping FCM Version >= " << required_fcm_version
      << " (but is " << shipping_fcm_version << ")";
}

// Tests that deprecated HALs are not served, unless a higher, non-deprecated
// minor version is served.
TEST_F(DeprecateTest, NoDeprcatedHalsOnManager) {
  // Predicate for whether an instance is served through service manager.
  // Return {is instance in service manager, highest minor version}
  // where "highest minor version" is the first element in getInterfaceChain()
  // that has the same "package", major version as "version", "interface" and
  // "instance", but a higher minor version than "version".
  VintfObject::IsInstanceInUse is_instance_served =
      [this](const string &package, Version version, const string &interface,
             const string &instance) {
        FQName fq_name(package, to_string(version), interface);
        for (auto transport : {Transport::HWBINDER, Transport::PASSTHROUGH}) {
          auto service =
              GetHalService(fq_name, instance, transport, false /* log */);
          if (service == nullptr) {
            continue;  // try next transport
          }
          vector<string> iface_chain = GetInterfaceChain(service);
          for (const auto &fq_interface_str : iface_chain) {
            FQName fq_interface;
            if (!FQName::parse(fq_interface_str, &fq_interface)) {
              // Allow CheckDeprecation to proceed with some sensible default
              ADD_FAILURE() << "'" << fq_interface_str
                            << "' (returned by getInterfaceChain())"
                            << "is not a valid fully-qualified name.";
              return std::make_pair(true, version);
            }
            if (fq_interface.package() == package) {
              Version fq_version{fq_interface.getPackageMajorVersion(),
                                 fq_interface.getPackageMinorVersion()};
              if (fq_version.minorAtLeast(version)) {
                return std::make_pair(true, fq_version);
              }
            }
          }
          // Allow CheckDeprecation to proceed with some sensible default
          ADD_FAILURE() << "getInterfaceChain() does not return interface name "
                        << "with at least minor version'" << package << "@"
                        << version << "'; returned values are ["
                        << android::base::Join(iface_chain, ", ") << "]";
          return std::make_pair(true, version);
        }

        return std::make_pair(false, Version{});
      };
  string error;
  EXPECT_EQ(android::vintf::NO_DEPRECATED_HALS,
            VintfObject::CheckDeprecation(is_instance_served, &error))
      << error;
}

// Tests that deprecated HALs are not in the manifest, unless a higher,
// non-deprecated minor version is in the manifest.
TEST_F(DeprecateTest, NoDeprcatedHalsOnManifest) {
  string error;
  EXPECT_EQ(android::vintf::NO_DEPRECATED_HALS,
            VintfObject::CheckDeprecation(&error));
}

int main(int argc, char **argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
