/*
 * Copyright (C) 2026 The Android Open Source Project
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

package com.android.tests.usbtypec;

import android.platform.test.annotations.RequiresDevice;
import com.android.compatibility.common.util.PropertyUtil;
import com.android.compatibility.common.util.VsrTest;
import com.android.tradefed.device.ITestDevice;
import com.android.tradefed.log.LogUtil.CLog;
import com.android.tradefed.testtype.DeviceJUnit4ClassRunner;
import com.android.tradefed.testtype.junit4.BaseHostJUnit4Test;
import java.io.File;
import java.util.HashSet;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.Assert;
import org.junit.Assume;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(DeviceJUnit4ClassRunner.class)
public final class VtsUsbTypecTest extends BaseHostJUnit4Test {
    public static final String TAG = VtsUsbTypecTest.class.getSimpleName();

    private ITestDevice mDevice;

    private static final Pattern RE_PORT = Pattern.compile("^port(\\d+)$");
    private static final Pattern RE_PORT_ALTMODE = Pattern.compile("^port(\\d+)\\.(\\d+)$");
    private static final Pattern RE_TBT_DEV = Pattern.compile("^(\\d+)-(\\d+)$");

    private static final String SYSFS_TYPEC_PATH = "/sys/class/typec";
    private static final String SYSFS_TYPEC_PORT0_PATH = "/sys/class/typec/port0";
    private static final String SYSFS_THUNDERBOLT_PATH = "/sys/bus/thunderbolt/devices";

    private static final String SELINUX_TYPEC_LABEL = "u:object_r:sysfs_typec:s0";
    private static final String SELINUX_THUNDERBOLT_LABEL = "u:object_r:sysfs_thunderbolt:s0";

    private static final Set<String> CRIT_PORT_FILES = Set.of("data_role", "power_role");
    private static final Set<String> CRIT_ALTMODE_FILES = Set.of("active", "svid");
    private static final Set<String> CRIT_TBT_FILES = Set.of("authorized");

    // Strings to detect certain form factors.
    private static final String FEATURE_TV = "android.hardware.type.television";
    private static final String FEATURE_WATCH = "android.hardware.type.watch";

    // Strings to detect emulators.
    private static final String PROP_BOOT_QEMU = "ro.boot.qemu";
    private static final String PROP_KERNEL_QEMU = "ro.kernel.qemu";
    private static final String PROP_PRODUCT_DEVICE = "ro.product.device";
    private static final String PROP_PRODUCT_MODEL = "ro.product.model";
    private static final String PROP_PRODUCT_NAME = "ro.product.name";
    private static final String PROP_HARDWARE = "ro.hardware";

    @Before
    public void setUp() {
        mDevice = getDevice();
    }

    private void assumeMinimumVsrApiLevel(long minApiLevel) throws Exception {
        long vsrApiLevel = PropertyUtil.getVsrApiLevel(mDevice);
        Assume.assumeTrue(String.format("Skip on devices with VSR API level (%d) less than %d",
                                  vsrApiLevel, minApiLevel),
                vsrApiLevel >= minApiLevel);
    }

    private String joinToPath(String base, String file) {
        return new File(base, file).getPath();
    }

    private String getFullyResolvedPath(String filePath) throws Exception {
        String result = mDevice.executeShellCommand("readlink -f " + filePath);
        return result.trim();
    }

    private void assertFileHasLabel(String filePath, String label) throws Exception {
        CLog.i("Checking for label [%s] on [%s]", label, filePath);
        String result = mDevice.executeShellCommand(String.format("ls -Z %s", filePath));
        String foundLabel = result.split("\\s++")[0];

        if (!label.equals(foundLabel)) {
            String resolvedPath = getFullyResolvedPath(filePath);
            Assert.assertEquals(String.format("Selinux label mismatch at %s: %s wanted vs %s found",
                                        resolvedPath, label, foundLabel),
                    label, foundLabel);
        }
    }

    private void assertPortFiles(String portPath) throws Exception {
        CLog.i("assertPortFiles on [%s]", portPath);

        String[] children = mDevice.getChildren(portPath);
        HashSet<String> seen = new HashSet<>();

        for (String entry : children) {
            CLog.i("Port file seen: [%s]", entry);
            Matcher matcher = RE_PORT_ALTMODE.matcher(entry);
            String childPath = joinToPath(portPath, entry);

            if (CRIT_PORT_FILES.contains(entry)) {
                seen.add(entry);
                assertFileHasLabel(joinToPath(portPath, entry), SELINUX_TYPEC_LABEL);
            } else if (matcher.find()) {
                assertAltmodeFiles(childPath);
            }
        }

        // Make sure we saw all critical port files.
        Assert.assertEquals(seen, CRIT_PORT_FILES);
    }

    private void assertAltmodeFiles(String altmodePath) throws Exception {
        CLog.i("assertAltmodeFiles on [%s]", altmodePath);

        String[] children = mDevice.getChildren(altmodePath);
        HashSet<String> seen = new HashSet<>();

        for (String entry : children) {
            CLog.i("Altmode file seen: [%s]", entry);

            if (CRIT_ALTMODE_FILES.contains(entry)) {
                seen.add(entry);
                assertFileHasLabel(joinToPath(altmodePath, entry), SELINUX_TYPEC_LABEL);
            }
        }

        // Make sure we saw all critical altmode files.
        Assert.assertEquals(seen, CRIT_ALTMODE_FILES);
    }

    private String getStringProperty(String id) throws Exception {
        String prop = mDevice.getProperty(id);

        if (prop == null) {
            return "";
        }

        return prop;
    }

    private boolean isEmulator() throws Exception {
        // First use the provided check (which only checks serial at this time).
        if (mDevice.getIDevice().isEmulator()) {
            return true;
        }

        // Next check for QEMU.
        boolean isQemu = mDevice.getBooleanProperty(PROP_BOOT_QEMU, false)
                || mDevice.getBooleanProperty(PROP_KERNEL_QEMU, false);
        if (isQemu) {
            return true;
        }

        // Check for specific emulator VM names.
        String device = getStringProperty(PROP_PRODUCT_DEVICE);
        String model = getStringProperty(PROP_PRODUCT_MODEL);
        String name = getStringProperty(PROP_PRODUCT_NAME);
        String hardware = getStringProperty(PROP_HARDWARE);

        return device.startsWith("vsoc_") || model.startsWith("Cuttlefish")
                || name.startsWith("cf_") || name.startsWith("aosp_cf_")
                || hardware.startsWith("cutf") || hardware.startsWith("ranchu")
                || hardware.startsWith("goldfish");
    }

    // Check whether we should assert at least 1 Type-C port on the system (VSR-5.4-0012).
    // On some systems, we will turn the assert into an Assume instead if there's a legitimate
    // reason to skip the test.
    private boolean shouldAssertAtLeastOneTypec() throws Exception {
        // Emulators may not populate any USB-C ports.
        if (isEmulator()) {
            return false;
        }

        // TVs and Watches don't yet REQUIRE physical Type-C ports.
        boolean isTv = mDevice.hasFeature(FEATURE_TV);
        boolean isWatch = mDevice.hasFeature(FEATURE_WATCH);

        return !(isTv || isWatch);
    }

    // Test that typec ports and altmodes have the necessary selinux labels.
    @Test
    @VsrTest(requirements = {"VSR-5.4-012", "VSR-5.4-017"})
    @RequiresDevice
    public void testTypecPortsAndChildrenHaveSelinuxLabel() throws Exception {
        // Test only applies for boards starting after 202604
        assumeMinimumVsrApiLevel(202604);

        String vsrMessage = "VSR-5.4-0012: All systems must have at least one Type-C receptacle "
                + "(port0 missing)";
        boolean portZeroExists = mDevice.doesFileExist(SYSFS_TYPEC_PORT0_PATH);

        // Most systems must have at least one Type-C receptacle. For those systems, assert that we
        // have at least 1 TypeC (i.e. they will fail the test). For others, use assume so that the
        // test is only applicable if there is at least 1 Type-C port.
        if (shouldAssertAtLeastOneTypec()) {
            Assert.assertTrue(vsrMessage, portZeroExists);
        } else {
            Assume.assumeTrue(vsrMessage, portZeroExists);
        }

        String[] typecEntries = mDevice.getChildren(SYSFS_TYPEC_PATH);

        for (String entry : typecEntries) {
            String childPath = joinToPath(SYSFS_TYPEC_PATH, entry);

            Matcher portMatcher = RE_PORT.matcher(entry);
            if (portMatcher.find()) {
                assertPortFiles(childPath);
            }
        }
    }

    private void assertTbtDeviceFiles(String tbtDevicePath) throws Exception {
        CLog.i("assertTbtDeviceFiles on [%s]", tbtDevicePath);

        String[] children = mDevice.getChildren(tbtDevicePath);
        HashSet<String> seen = new HashSet<>();

        for (String entry : children) {
            CLog.i("Thunderbolt file seen: [%s]", entry);

            if (CRIT_TBT_FILES.contains(entry)) {
                seen.add(entry);
                assertFileHasLabel(joinToPath(tbtDevicePath, entry), SELINUX_THUNDERBOLT_LABEL);
            }
        }

        // Make sure we saw all critical thunderbolt files.
        Assert.assertEquals(seen, CRIT_TBT_FILES);
    }

    // Test that thunderbolt devices (if they exist) have the necessary selinux labels.
    @Test
    @VsrTest(requirements = {"VSR-5.4-020"})
    @RequiresDevice
    public void testThunderboltDevicesHaveSelinuxLabel() throws Exception {
        // Test only applies for boards starting after 202604
        assumeMinimumVsrApiLevel(202604);

        // First make sure this platform actually has thunderbolt enabled.
        Assume.assumeTrue(mDevice.doesFileExist(SYSFS_THUNDERBOLT_PATH));

        String[] thunderboltEntries = mDevice.getChildren(SYSFS_THUNDERBOLT_PATH);

        for (String entry : thunderboltEntries) {
            String childPath = joinToPath(SYSFS_THUNDERBOLT_PATH, entry);

            Matcher tbtDeviceMatcher = RE_TBT_DEV.matcher(entry);
            if (tbtDeviceMatcher.find()) {
                assertTbtDeviceFiles(childPath);
            }
        }
    }
}
