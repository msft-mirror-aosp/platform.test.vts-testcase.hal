#!/usr/bin/env python
#
# Copyright 2020 The Android Open Source Project
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
#

import logging
import time

from vts.runners.host import asserts
from vts.runners.host import test_runner
from vts.testcases.template.hal_hidl_host_test import hal_hidl_host_test

from cec_utils import *

TVCEC_V1_0_HAL = "android.hardware.tv.cec@1.0::IHdmiCec"

class TvCecHidlWithClientTest(hal_hidl_host_test.HalHidlHostTest):
    """Host testcase class for the TV HDMI_CEC HIDL HAL."""

    TEST_HAL_SERVICES = {TVCEC_V1_0_HAL}
    def setUpClass(self):
        super(TvCecHidlWithClientTest, self).setUpClass()
        self.initHdmiCecHal()
        self.initCecClient()
        '''Check for Cec-client'''
        self.skipAllTestsIf(self.cec_utils.mCecClientInitialised is False,
                "Cec-client not initialised")
        self.initial_addresses = self.getInitialLogicalAddresses()

    def initHdmiCecHal(self):
        """Creates a mirror and init tv hdmi cec hal service."""
        self.dut.hal.InitHidlHal(
            target_type="tv_cec",
            target_basepaths=self.dut.libPaths,
            target_version=1.0,
            target_package="android.hardware.tv.cec",
            target_component_name="IHdmiCec",
            hw_binder_service_name=self.getHalServiceName(TVCEC_V1_0_HAL),
            bits=int(self.abi_bitness))

        time.sleep(1) # Wait for hal to be ready

        self.vtypes = self.dut.hal.tv_cec.GetHidlTypeInterface("types")
        logging.info("tv_cec types: %s", self.vtypes)

    def initCecClient(self):
        self.cec_utils = CecUtils()

    def tearDownClass(self):
        if self.cec_utils.mCecClientInitialised is not False:
            self.cec_utils.killCecClient()

    def rebootDutAndRestartServices(self):
        '''Reboot the device and wait till the reboot completes.'''
        self.dut.reboot()
        '''Restart services and initHdmiCecHal() to restore the TCP connection to device.'''
        self.cec_utils.killCecClient()
        self.dut.stopServices()
        self.dut.startServices()
        self.initHdmiCecHal()
        self.initCecClient()
        '''Check for Cec-client'''
        self.skipAllTestsIf(self.cec_utils.mCecClientInitialised is False,
                "Cec-client not initialised")
        self.initial_addresses = self.getInitialLogicalAddresses()

    def getDeviceTypes(self):
        '''Gets the device types of DUT

        Returns:
            List of device types of the DUT. None in case of no device_type.
        '''
        types = self.dut.getProp("ro.hdmi.device_type")
        if str(types) is not "":
            device_types = str(types).split(",")
        else:
            device_types = None
        return device_types

    def getInitialLogicalAddresses(self):
        '''Gets the initial logical addresses that the DUT holds

        Returns:
            List of logical addresses DUT has taken.
        '''
        address_list = []
        for i in range(1,15):
            address = hex(i)[2:]
            '''Sending the poll message via Cec-client'''
            self.cec_utils.sendConsoleMessage("poll " + address)
            '''Wait only 1s for POLL response'''
            if self.cec_utils.checkConsoleOutput("POLL sent"):
                address_list.append(address)
        return address_list

    def clearAndAddLogicalAddress(self):
        """Clear and add the initial logical addresses."""
        logical_addresses = self.initial_addresses
        '''Clears the logical address'''
        self.dut.hal.tv_cec.clearLogicalAddress()
        for address in logical_addresses:
            result = self.dut.hal.tv_cec.addLogicalAddress(int(address, 16))
            try:
                asserts.assertEqual(self.vtypes.Result.SUCCESS, result)
            except:
                self.rebootDutAndRestartServices()
                asserts.fail("addLogicalAddress() API failed")

    def testSendRandomMessage(self):
        """A test case which sends a random message and verifies that it has been sent on the
        CEC channel.
        """
        src = self.vtypes.CecLogicalAddress.PLAYBACK_1
        dst = self.vtypes.CecLogicalAddress.TV
        cec_message = {
            "initiator": src,
            "destination": dst,
            "body": [131]
        }
        message = self.vtypes.Py2Pb("CecMessage", cec_message)
        logging.info("message: %s", message)
        result = self.dut.hal.tv_cec.sendMessage(message)
        logging.info("sendMessage result: %s", result)
        src = hex(src)[2:]
        dst = hex(dst)[2:]
        operand = hex(131)[2:]
        asserts.assertNotEqual(self.cec_utils.checkExpectedOutput(src, dst, operand), None)

    def testAddLogicalAddress(self):
        """A test case that adds a logical address and validates it on cec-client console.
        """
        device_types = self.getDeviceTypes()
        asserts.assertNotEqual(device_types, None, "Device types could not be determined")
        '''Clears the logical address'''
        self.dut.hal.tv_cec.clearLogicalAddress()
        '''Assumes that clearLogicalAddress is not faulty and has cleared the logical address'''
        for device_type in device_types:
            '''The first logical address a DUT can take will be the same as the integer value
            of device_type'''
            result = self.dut.hal.tv_cec.addLogicalAddress(int(device_type))
            try:
                asserts.assertEqual(self.vtypes.Result.SUCCESS, result)
            except:
                self.rebootDutAndRestartServices()
                asserts.fail("addLogicalAddress() API failed")
            '''Sending the poll message via Cec-client'''
            self.cec_utils.sendConsoleMessage("poll " + device_type)
            '''POLL sent is proof of acknowledgement of the POLL message.'''
            try:
                asserts.assertEqual(self.cec_utils.checkConsoleOutput("POLL sent"),
                                    True)
            except:
                self.rebootDutAndRestartServices()
                asserts.fail("addLogicalAddress() API does not add the requested address")
        '''Restore the logical addresses'''
        self.clearAndAddLogicalAddress()

if __name__ == "__main__":
    test_runner.main()
