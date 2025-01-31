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
import com.android.compatibility.common.util.PropertyUtil;
import com.android.tradefed.device.DeviceNotAvailableException;
import com.android.tradefed.device.ITestDevice;
import com.android.tradefed.log.LogUtil.CLog;
import com.android.tradefed.invoker.TestInformation;
import com.android.tradefed.testtype.DeviceJUnit4ClassRunner;
import com.android.tradefed.testtype.junit4.BaseHostJUnit4Test;
import com.android.tradefed.testtype.junit4.BeforeClassWithInfo;
import com.android.tradefed.util.RunInterruptedException;
import com.android.tradefed.util.RunUtil;
import com.google.common.base.Strings;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;

import org.junit.Assert;
import org.junit.Assume;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(DeviceJUnit4ClassRunner.class)
public final class VtsAidlUsbHostTest extends BaseHostJUnit4Test {
    public static final String TAG = VtsAidlUsbHostTest.class.getSimpleName();

    private static final String HAL_SERVICE = "android.hardware.usb.IUsb/default";
    private static final long CONN_TIMEOUT = 5000;
    // Extra time to wait for device to be available after being NOT_AVAILABLE state.
    private static final long EXTRA_RECOVERY_TIMEOUT = 1000;
    private static final String PRODUCT_FIRST_API_LEVEL_PROP = "ro.product.first_api_level";
    private static final String BOARD_API_LEVEL_PROP = "ro.board.api_level";
    private static final String BOARD_FIRST_API_LEVEL_PROP = "ro.board.first_api_level";
    // TODO Remove unknown once b/383164760 is fixed.
    private static final Set<String> VSR_54_REQUIRED_HAL_VERSIONS = Set.of("V2_0", "V1_3", "unknown");

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

        Assert.assertTrue("USB port did not reconnect within 6000ms timeout.", mReconnected.get());
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
                                  + roBoardApiLevel + " < 202504",
                roBoardApiLevel >= 202504);
        } else {
            Assume.assumeTrue("Skip on devices with ro.board.first_api_level "
                                  + roBoardFirstApiLevel + " < 202504",
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
        long roProductFirstApiLevel = mDevice.getIntProperty(PRODUCT_FIRST_API_LEVEL_PROP, -1);
        long roBoardApiLevel = mDevice.getIntProperty(BOARD_API_LEVEL_PROP, -1);
        long roBoardFirstApiLevel = mDevice.getIntProperty(BOARD_FIRST_API_LEVEL_PROP, -1);
        Assume.assumeTrue("Skip on devices with ro.product.first_api_level "
                        + roProductFirstApiLevel + "< 36 (Android 16)",
                roProductFirstApiLevel >= 36);
        if (roBoardApiLevel != -1) {
            Assume.assumeTrue(
                    "Skip on devices with ro.board.api_level " + roBoardApiLevel + " < 202504",
                    roBoardApiLevel >= 202504);
        } else {
            Assume.assumeTrue("Skip on devices with ro.board.first_api_level "
                            + roBoardFirstApiLevel + " < 202504",
                    roBoardFirstApiLevel >= 202504);
        }

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
        long roProductFirstApiLevel = mDevice.getIntProperty(PRODUCT_FIRST_API_LEVEL_PROP, -1);
        long roBoardApiLevel = mDevice.getIntProperty(BOARD_API_LEVEL_PROP, -1);
        long roBoardFirstApiLevel = mDevice.getIntProperty(BOARD_FIRST_API_LEVEL_PROP, -1);
        Assume.assumeTrue("Skip on devices with ro.product.first_api_level "
                        + roProductFirstApiLevel + "< 36 (Android 16)",
                roProductFirstApiLevel >= 36);
        if (roBoardApiLevel != -1) {
            Assume.assumeTrue(
                    "Skip on devices with ro.board.api_level " + roBoardApiLevel + " < 202504",
                    roBoardApiLevel >= 202504);
        } else {
            Assume.assumeTrue("Skip on devices with ro.board.first_api_level "
                            + roBoardFirstApiLevel + " < 202504",
                    roBoardFirstApiLevel >= 202504);
        }

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
        long roProductFirstApiLevel = mDevice.getIntProperty(PRODUCT_FIRST_API_LEVEL_PROP, -1);
        long roBoardApiLevel = mDevice.getIntProperty(BOARD_API_LEVEL_PROP, -1);
        long roBoardFirstApiLevel = mDevice.getIntProperty(BOARD_FIRST_API_LEVEL_PROP, -1);
        Assume.assumeTrue("Skip on devices with ro.product.first_api_level "
                        + roProductFirstApiLevel + "< 36 (Android 16)",
                roProductFirstApiLevel >= 36);
        if (roBoardApiLevel != -1) {
            Assume.assumeTrue(
                    "Skip on devices with ro.board.api_level " + roBoardApiLevel + " < 202504",
                    roBoardApiLevel >= 202504);
        } else {
            Assume.assumeTrue("Skip on devices with ro.board.first_api_level "
                            + roBoardFirstApiLevel + " < 202504",
                    roBoardFirstApiLevel >= 202504);
        }

        RunUtil.getDefault().sleep(100);
        String cmd = "mount | grep \"/dev/usb-ffs/aoa\"";
        CLog.i("Invoke shell command [" + cmd + "]");
        String result = mDevice.executeShellCommand(cmd).trim();

        Assert.assertTrue("Expected AOA directory to be mounted as FunctionFS but got: " + result,
                result.contains("functionfs"));
    }

    @Test
    @VsrTest(requirements = {"VSR-5.4-008"})
    public void testAoaEndpointsNotMountedAtBoot() throws Exception {
        Assume.assumeTrue(
                String.format("The device doesn't have service %s", HAL_SERVICE), mHasService);
        Assert.assertNotNull("Target device does not exist", mDevice);
        long roProductFirstApiLevel = mDevice.getIntProperty(PRODUCT_FIRST_API_LEVEL_PROP, -1);
        long roBoardApiLevel = mDevice.getIntProperty(BOARD_API_LEVEL_PROP, -1);
        long roBoardFirstApiLevel = mDevice.getIntProperty(BOARD_FIRST_API_LEVEL_PROP, -1);
        Assume.assumeTrue("Skip on devices with ro.product.first_api_level "
                        + roProductFirstApiLevel + "< 36 (Android 16)",
                roProductFirstApiLevel >= 36);
        if (roBoardApiLevel != -1) {
            Assume.assumeTrue(
                    "Skip on devices with ro.board.api_level " + roBoardApiLevel + " < 202504",
                    roBoardApiLevel >= 202504);
        } else {
            Assume.assumeTrue("Skip on devices with ro.board.first_api_level "
                            + roBoardFirstApiLevel + " < 202504",
                    roBoardFirstApiLevel >= 202504);
        }

        RunUtil.getDefault().sleep(100);
        String cmd = "ls -l /dev/usb-ffs/aoa";
        CLog.i("Invoke shell command [" + cmd + "]");
        String result = mDevice.executeShellCommand(cmd).trim();

        Assert.assertFalse("Expected AOA endpoints to not be mounted but got: " + result,
                result.contains("ep1") || result.contains("ep2"));
    }
}
