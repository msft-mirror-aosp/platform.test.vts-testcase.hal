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

    private static final String BOARD_API_LEVEL_PROP = "ro.board.api_level";

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

    @Before
    public void setUp() {
        mDevice = getDevice();
    }

    private void assumeMinimumBoardApiLevel(long minApiLevel) throws Exception {
        long roBoardApiLevel = mDevice.getIntProperty(BOARD_API_LEVEL_PROP, -1);
        Assume.assumeTrue(String.format("Skip on devices with %s (%d) less than %d",
                                  BOARD_API_LEVEL_PROP, roBoardApiLevel, minApiLevel),
                roBoardApiLevel >= minApiLevel);
    }

    private String joinToPath(String base, String file) {
        return new File(base, file).getPath();
    }

    private void assertFileHasLabel(String filePath, String label) throws Exception {
        CLog.i("Checking for label [%s] on [%s]", label, filePath);
        String result = mDevice.executeShellCommand(String.format("ls -Z %s", filePath));
        String foundLabel = result.split("\\s++")[0];
        Assert.assertEquals(
                String.format("Wanted %s, cmd result: %s", label, result), label, foundLabel);
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

    // Test that typec ports and altmodes have the necessary selinux labels.
    @Test
    @VsrTest(requirements = {"VSR-5.4-012", "VSR-5.4-017"})
    @RequiresDevice
    public void testTypecPortsAndChildrenHaveSelinuxLabel() throws Exception {
        // Test only applies for boards starting after 202604
        assumeMinimumBoardApiLevel(202604);

        // All systems must have at least one Type-C receptacle.
        Assert.assertTrue("VSR-5.4-0012: All systems must have at least one Type-C receptacle "
                        + "(port0 missing)",
                mDevice.doesFileExist(SYSFS_TYPEC_PORT0_PATH));

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
        assumeMinimumBoardApiLevel(202604);

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
