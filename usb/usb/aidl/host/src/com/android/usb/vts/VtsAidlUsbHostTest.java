/*
 * Copyright (C) 2022 The Android Open Source Project
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

package com.android.tests.usbport;

import com.android.compatibility.common.util.VsrTest;
import com.android.tradefed.device.DeviceNotAvailableException;
import com.android.tradefed.device.ITestDevice;
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.log.LogUtil.CLog;
import com.android.tradefed.testtype.DeviceJUnit4ClassRunner;
import com.android.tradefed.testtype.junit4.BaseHostJUnit4Test;
import com.android.tradefed.testtype.junit4.BeforeClassWithInfo;
import com.android.tradefed.util.RunInterruptedException;
import com.android.tradefed.util.RunUtil;
import com.google.common.base.Strings;
import java.io.File;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.junit.Assert;
import org.junit.Assume;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(DeviceJUnit4ClassRunner.class)
public final class VtsAidlUsbHostTest extends BaseHostJUnit4Test {
    public static final String TAG = VtsAidlUsbHostTest.class.getSimpleName();

    private static final String HAL_SERVICE = "android.hardware.usb.IUsb/default";
    private static final long CONN_TIMEOUT = 29000;
    // Extra time to wait for device to be available after being NOT_AVAILABLE state.
    private static final long EXTRA_RECOVERY_TIMEOUT = 1000;
    private static final String PRODUCT_FIRST_API_LEVEL_PROP = "ro.product.first_api_level";
    private static final String BOARD_API_LEVEL_PROP = "ro.board.api_level";
    private static final String BOARD_FIRST_API_LEVEL_PROP = "ro.board.first_api_level";
    // TODO Remove unknown once b/383164760 is fixed.
    private static final Set<String> VSR_54_REQUIRED_HAL_VERSIONS = Set.of("V2_0", "V1_3", "unknown");

    // Regex for USB root hub at /sys/bus/usb/devices.
    private static final Pattern RE_USB_ROOT_HUB = Pattern.compile("^usb[0-9]+$");
    private static final String SYS_BUS_USB_DEVICES = "/sys/bus/usb/devices";
    private static final String SELINUX_USB_LABEL = "u:object_r:sysfs_usb:s0";

    // Critical files for USB root hub. All of these must exist and have the right selinux labels
    // applied to them.
    private static final Set<String> CRIT_USB_FILES =
            Set.of("authorized", "authorized_default", "busnum", "descriptors", "devnum",
                    "idProduct", "idVendor", "interface_authorized_default", "removable", "speed");

    private static boolean mHasService;

    private ITestDevice mDevice;
    private AtomicBoolean mReconnected = new AtomicBoolean(false);

    @Before
    public void setUp() {
        mDevice = getDevice();
    }

    @BeforeClassWithInfo
    public static void beforeClassWithDevice(TestInformation testInfo) throws Exception {
        String serviceFound =
                testInfo.getDevice()
                        .executeShellCommand(String.format("dumpsys -l | grep \"%s\"", HAL_SERVICE))
                        .trim();
        mHasService = !Strings.isNullOrEmpty(serviceFound);
    }

    @Test
    public void testResetUsbPort() throws Exception {
        Assume.assumeTrue(
                String.format("The device doesn't have service %s", HAL_SERVICE), mHasService);
        Assert.assertNotNull("Target device does not exist", mDevice);

        String portResult, content;
        String deviceSerialNumber = mDevice.getSerialNumber();
        HashSet<String> noSupportCases =
                    new HashSet<>(Arrays.asList("No USB ports",
                        "There is no available reset USB port"));

        CLog.i("testResetUsbPort on device [%s]", deviceSerialNumber);

        new Thread(new Runnable() {
            public void run() {
                try {
                    mDevice.waitForDeviceNotAvailable(CONN_TIMEOUT);
                    RunUtil.getDefault().sleep(500);
                    mDevice.waitForDeviceAvailable(CONN_TIMEOUT);
                    mReconnected.set(true);
                } catch (DeviceNotAvailableException dnae) {
                    CLog.e("Device is not available");
                } catch (RunInterruptedException ie) {
                    CLog.w("Thread.sleep interrupted");
                }
            }
        }).start();

        RunUtil.getDefault().sleep(100);
        String cmd = "svc usb resetUsbPort";
        CLog.i("Invoke shell command [" + cmd + "]");
        long startTime = System.currentTimeMillis();
        portResult = mDevice.executeShellCommand(cmd);
        content = portResult.trim();

        if (portResult != null && (noSupportCases.contains(content))) {
            CLog.i("portResult: %s", portResult);
            return;
        }

        RunUtil.getDefault().sleep(100);
        while (!mReconnected.get() && System.currentTimeMillis() - startTime < CONN_TIMEOUT + EXTRA_RECOVERY_TIMEOUT) {
            RunUtil.getDefault().sleep(300);
        }

        Assert.assertTrue("USB port did not reconnect within 30000ms timeout.", mReconnected.get());
    }

    @Test
    @VsrTest(requirements = {"VSR-5.4-009"})
    public void testVerifyUsbHalVersion() throws Exception {
        Assume.assumeTrue(
            String.format("The device doesn't have service %s", HAL_SERVICE),
            mHasService);
        Assert.assertNotNull("Target device does not exist", mDevice);
        long roBoardApiLevel = mDevice.getIntProperty(BOARD_API_LEVEL_PROP, -1);
        long roBoardFirstApiLevel = mDevice.getIntProperty(BOARD_FIRST_API_LEVEL_PROP, -1);
        if(roBoardApiLevel != -1) {
            Assume.assumeTrue("Skip on devices with ro.board.api_level "
                                  + roBoardApiLevel + " less than 202504",
                roBoardApiLevel >= 202504);
        } else {
            Assume.assumeTrue("Skip on devices with ro.board.first_api_level "
                                  + roBoardFirstApiLevel + " less than 202504",
                roBoardFirstApiLevel >= 202504);
        }

        RunUtil.getDefault().sleep(100);
        String cmd = "svc usb getUsbHalVersion";
        CLog.i("Invoke shell command [" + cmd + "]");
        String result = mDevice.executeShellCommand(cmd).trim();

        Assert.assertTrue("Expected HAL version to be one of "
                              + VSR_54_REQUIRED_HAL_VERSIONS.toString()
                              + " but got: " + result,
            VSR_54_REQUIRED_HAL_VERSIONS.contains(result));
    }

    @Test
    @VsrTest(requirements = {"VSR-5.4-006", "VSR-5.4-007"})
    public void testAoaDirectoryExists() throws Exception {
        Assume.assumeTrue(
                String.format("The device doesn't have service %s", HAL_SERVICE), mHasService);
        Assert.assertNotNull("Target device does not exist", mDevice);
        checkAoaRequirements();

        RunUtil.getDefault().sleep(100);
        String cmd = "ls -l /dev/usb-ffs/aoa";
        CLog.i("Invoke shell command [" + cmd + "]");
        String result = mDevice.executeShellCommand(cmd).trim();

        Assert.assertTrue(
                "Expected AOA directory to exist but got: " + result, result.contains("ep0"));
    }

    @Test
    @VsrTest(requirements = {"VSR-5.4-006", "VSR-5.4-007"})
    public void testAoaControlDirectoryExists() throws Exception {
        Assume.assumeTrue(
                String.format("The device doesn't have service %s", HAL_SERVICE), mHasService);
        Assert.assertNotNull("Target device does not exist", mDevice);
        checkAoaRequirements();

        RunUtil.getDefault().sleep(100);
        String cmd = "ls -l /dev/usb-ffs/ctrl";
        CLog.i("Invoke shell command [" + cmd + "]");
        String result = mDevice.executeShellCommand(cmd).trim();

        Assert.assertTrue("Expected AOA control directory to exist but got: " + result,
                result.contains("ep0"));
    }

    @Test
    @VsrTest(requirements = {"VSR-5.4-005"})
    public void testAoaDirectoryMountedAsFfs() throws Exception {
        Assume.assumeTrue(
                String.format("The device doesn't have service %s", HAL_SERVICE), mHasService);
        Assert.assertNotNull("Target device does not exist", mDevice);
        checkAoaRequirements();

        RunUtil.getDefault().sleep(100);
        String cmd = "mount | grep \"/dev/usb-ffs/aoa\"";
        CLog.i("Invoke shell command [" + cmd + "]");
        String result = mDevice.executeShellCommand(cmd).trim();

        Assert.assertTrue("Expected AOA directory to be mounted as FunctionFS but got: " + result,
                result.contains("functionfs"));
    }

    private void checkAoaRequirements() throws Exception {
        long roProductFirstApiLevel = mDevice.getIntProperty(PRODUCT_FIRST_API_LEVEL_PROP, -1);
        long roBoardApiLevel = mDevice.getIntProperty(BOARD_API_LEVEL_PROP, -1);
        long roBoardFirstApiLevel = mDevice.getIntProperty(BOARD_FIRST_API_LEVEL_PROP, -1);

        RunUtil.getDefault().sleep(100);
        String cmd = "uname -r";
        CLog.i("Invoke shell command [" + cmd + "]");
        String osVersion = mDevice.executeShellCommand(cmd).trim();

        Assume.assumeTrue("Skip on devices with ro.product.first_api_level "
                        + roProductFirstApiLevel + " less than 37 (Android 17)",
                roProductFirstApiLevel >= 37);
        if (roBoardApiLevel != -1) {
            Assume.assumeTrue(
                    "Skip on devices with ro.board.api_level " + roBoardApiLevel
                        + " less than 202604",
                    roBoardApiLevel >= 202604);
        } else {
            Assume.assumeTrue("Skip on devices with ro.board.first_api_level "
                            + roBoardFirstApiLevel + " less than 202604",
                    roBoardFirstApiLevel >= 202604);
        }

        Assume.assumeTrue("Skip on devices with kernel version "
                        + osVersion + " less than 6.18 ",
                isKernelVersionAtLeast(osVersion, 6,18));
    }

    private boolean isKernelVersionAtLeast(String osVersion,
            int major, int minor) {
        Pattern p = Pattern.compile("^(\\d+)\\.(\\d+)");
        Matcher m1 = p.matcher(osVersion);
        Assert.assertTrue("Unable to parse kernel release version: %s"
                              .format(osVersion), m1.find());
        return Integer.parseInt(m1.group(1)) > major
                || (Integer.parseInt(m1.group(1)) == major
                && Integer.parseInt(m1.group(2)) > minor);
    }

    private String getSelinuxLabelForFile(String filePath) throws Exception {
        String result = mDevice.executeShellCommand(String.format("ls -Z %s", filePath));

        String[] words = result.split("\\s++");
        return words[0];
    }

    private String joinToPath(String base, String file) {
        return new File(base, file).getPath();
    }

    private void assertFileHasLabel(String filePath, String label) throws Exception {
        CLog.i("Checking for label [%s] on [%s]", label, filePath);
        String foundLabel = getSelinuxLabelForFile(filePath);
        Assert.assertEquals(label, foundLabel);
    }

    private void assertUsbRootFiles(String usbPath) throws Exception {
        CLog.i("assertUsbRootFiles on [%s]", usbPath);

        String[] children = mDevice.getChildren(usbPath);
        HashSet<String> seen = new HashSet<>();

        for (String entry : children) {
            CLog.i("Usb file seen: [%s]", entry);

            if (CRIT_USB_FILES.contains(entry)) {
                seen.add(entry);
                assertFileHasLabel(joinToPath(usbPath, entry), SELINUX_USB_LABEL);
            }
        }

        // Make sure we saw all critical usb files.
        Assert.assertEquals(seen, CRIT_USB_FILES);
    }

    // Test that typec ports have the necessary selinux labels. We only check the root hub ports as
    // we expect labels to be recursively applied and all other ports are sub-directories under
    // a root hub (instead of a symlink to another subsystem, i.e. pci).
    //
    // This also tests that all critical USB sysfs nodes are added and at least 1 root hub is
    // listed.
    @Test
    @VsrTest(requirements = {"VSR-5.4-0026"})
    public void testUsbPortsHaveSelinuxLabel() throws Exception {
        long roBoardApiLevel = mDevice.getIntProperty(BOARD_API_LEVEL_PROP, -1);

        Assume.assumeTrue(String.format("Skip on devices with %s (%d) less than %d",
                                  BOARD_API_LEVEL_PROP, roBoardApiLevel, 202604),
                roBoardApiLevel >= 202604);

        String[] usbEntries = mDevice.getChildren(SYS_BUS_USB_DEVICES);

        boolean hubDevicesFound = false;

        for (String entry : usbEntries) {
            String childPath = joinToPath(SYS_BUS_USB_DEVICES, entry);

            Matcher hubMatcher = RE_USB_ROOT_HUB.matcher(entry);
            if (hubMatcher.find()) {
                hubDevicesFound = true;
                assertUsbRootFiles(childPath);
            }
        }

        Assert.assertTrue("Expect at least 1 hub device found.", hubDevicesFound);
    }
}
