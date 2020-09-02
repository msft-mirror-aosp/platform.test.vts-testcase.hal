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
import mock
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
            self.dut.reboot()

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
        '''Gets the initial logical addresses that the DUT holds. If DUT has no logical address(es)
        allocated, add logical address based on the device type.

        Returns:
            List of logical addresses DUT has taken.
        '''
        address_list = []
        for i in range(0,15):
            address = hex(i)[2:]
            '''Sending the poll message via Cec-client'''
            self.cec_utils.sendConsoleMessage("poll " + address)
            '''Wait only 1s for POLL response'''
            if self.cec_utils.checkConsoleOutput("POLL sent"):
                address_list.append(address)

        if len(address_list) is 0:
            '''If DUT has no logical address(es) allocated, add logical address based on the device
            type.'''
            device_types = self.getDeviceTypes()
            asserts.assertNotEqual(device_types, None, "Device types could not be determined")
            for device_type in device_types:
                '''The first logical address a DUT can take will be the same as the integer value
                of device_type'''
                self.dut.hal.tv_cec.addLogicalAddress(int(device_type))
                address_list.append(device_type)
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

    def setSystemCecControl(self, value_to_be_set):
        '''Set the SYSYEM_CEC_CONTROL flag.

        Args:
            value_to_be_set: Boolean value to which the flag is to be set.
        '''
        self.dut.hal.tv_cec.setOption(self.vtypes.OptionKey.SYSTEM_CEC_CONTROL, value_to_be_set)

    def checkForOnCecMessageCallback(self, callback, message):
        '''Checks for on_cec_message callback from the HAL.

        Args:
            callback: Callback object.
            message: CEC message, the callback function should receive.

        Returns:
            Returns boolean. True if the callback function received message from HAL.
        '''
        startTime = int(round(time.time()))
        endTime = startTime
        while (endTime - startTime <= 5):
            try:
                callback.on_cec_message.assert_called_with(message)
                return True
            except:
                pass
            endTime = int(round(time.time()))
        return False

    def registerCallback(self):
        '''Initialises a callback object and registers this callback with the HDMI HAL.

        Returns:
            Returns the Callback object.
        '''
        callback_utils = mock.create_autospec(self.CallbackUtils())
        callback = self.dut.hal.tv_cec.GetHidlCallbackInterface(
            "IHdmiCecCallback",
            onCecMessage=callback_utils.on_cec_message,
            onHotplugEvent=callback_utils.on_hotplug_event)

        self.dut.hal.tv_cec.setCallback(callback)
        return callback_utils

    class CallbackUtils(object):
        """Callback utils class"""

        def on_cec_message(self, CecMessage):
            logging.info("Received message: %s", CecMessage)

        def on_hotplug_event(self, HotplugEvent):
            logging.info("Got a hotplug event")

    def setEnableCec(self, value_to_be_set):
        '''Set the ENABLE_CEC flag.

        Args:
            value_to_be_set: Boolean value to which the flag is to be set.
        '''
        self.dut.hal.tv_cec.setOption(self.vtypes.OptionKey.ENABLE_CEC, value_to_be_set)

    def pollDutLogicalAddressAndCheckResponse(self, string_to_check = "POLL sent"):
        '''Send Poll messages to DUT logical addresses and check for the response.

        Args:
            string_to_check: String to check for after poll message is sent.
        '''
        logical_addresses = self.initial_addresses
        for address in logical_addresses:
            self.cec_utils.sendConsoleMessage("poll " + address)
            asserts.assertEqual(self.cec_utils.checkConsoleOutput(string_to_check), True,
                                ", Did not receive " + string_to_check + ".")

    def testSendRandomMessage(self):
        """A test case which sends a random message and verifies that it has been sent on the
        CEC channel.
        """
        src = self.vtypes.CecLogicalAddress.PLAYBACK_1
        dst = self.vtypes.CecLogicalAddress.RECORDER_1
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

    def testClearLogicalAddress(self):
        """Test case which clears logical address and validates it on cec-client console.
        """
        logical_addresses = self.initial_addresses
        '''Clears the logical address'''
        self.dut.hal.tv_cec.clearLogicalAddress()
        for address in logical_addresses:
            '''Sending the poll message via Cec-client'''
            self.cec_utils.sendConsoleMessage("poll " + address)
            try:
                asserts.assertEqual(self.cec_utils.checkConsoleOutput("POLL sent"),
                                    False)
            except:
                self.rebootDutAndRestartServices()
                asserts.fail("clearLogicalAddress() API failed to clear the address")
        '''Add back the initial addresses'''
        self.clearAndAddLogicalAddress()

    def testPollResponse_cecControlOff(self):
        """Test that sends a POLL to the DUT's logical addresses and checks for acknowledgement.
        """
        # TODO: Remove skip after b/162912390 is resolved.
        asserts.skip("Skip test (refer b/162912390).")
        '''Set SYSTEM_CEC_CONTROL flag to false.'''
        self.setSystemCecControl(False)
        try:
            self.pollDutLogicalAddressAndCheckResponse()
        finally:
            '''Set SYSTEM_CEC_CONTROL flag to true.'''
            self.setSystemCecControl(True)

    def testPowerQueryResponse(self):
        """Test case which checks for HAL response to power query."""
        logical_addresses = self.initial_addresses
        src = hex(self.vtypes.CecLogicalAddress.RECORDER_1)[2:]
        dst = logical_addresses[0]
        power_status_on = 0x0
        GIVE_DEVICE_POWER_STATUS = hex(self.vtypes.CecMessageType.GIVE_DEVICE_POWER_STATUS)[2:]
        REPORT_POWER_STATUS = hex(self.vtypes.CecMessageType.REPORT_POWER_STATUS )[2:]

        '''Set SYSTEM_CEC_CONTROL flag to false.'''
        self.setSystemCecControl(False)
        self.cec_utils.sendCecMessage(src, dst, GIVE_DEVICE_POWER_STATUS)
        message = self.cec_utils.checkExpectedOutput(dst, src, REPORT_POWER_STATUS)
        try:
            asserts.assertNotEqual(message, None,
                                   ", DUT did not respond to GIVE_DEVICE_POWER_STATUS CEC message")
            status = self.cec_utils.getParamsFromMessage(message, 0, 2)
            asserts.assertEqual(status, power_status_on,
                                ", DUT responded to GIVE_DEVICE_POWER_STATUS with status as " +
                                str(status) + ", expected 0")
        finally:
            self.setSystemCecControl(True)

    def testReceiveCallback(self):
        """Check that the onCecMessage callback is called correctly after callback registry."""
        GIVE_PHYSICAL_ADDRESS = self.vtypes.CecMessageType.GIVE_PHYSICAL_ADDRESS
        RECORDER_1 = self.vtypes.CecLogicalAddress.RECORDER_1
        logical_addresses = self.initial_addresses

        hdmi_cec_callback = self.registerCallback()

        src = hex(RECORDER_1)[2:]
        dst = logical_addresses[0]
        operand = hex(GIVE_PHYSICAL_ADDRESS)[2:]
        cec_message = {
            'body': [GIVE_PHYSICAL_ADDRESS],
            'initiator': RECORDER_1,
            'destination': int(dst, 16)
        }

        self.cec_utils.sendCecMessage(src, dst, operand)
        '''Callback function should receive the message from HAL.'''
        asserts.assertEqual(
            self.checkForOnCecMessageCallback(hdmi_cec_callback, cec_message),
            True, ", callback function did not receive the message")

    def testCallbackRegistry(self):
        """Check that a callback is registered successfully."""
        self.registerCallback()

    def testRegisterSecondCallback(self):
        """Test case which registers two callback functions and verifies that only the second
        callback receives messages."""
        GIVE_PHYSICAL_ADDRESS = self.vtypes.CecMessageType.GIVE_PHYSICAL_ADDRESS
        RECORDER_1 = self.vtypes.CecLogicalAddress.RECORDER_1
        logical_addresses = self.initial_addresses

        hdmi_cec_first_callback = self.registerCallback()
        hdmi_cec_second_callback = self.registerCallback()

        src = hex(RECORDER_1)[2:]
        dst = logical_addresses[0]
        operand = hex(GIVE_PHYSICAL_ADDRESS)[2:]
        cec_message = {
            'body': [GIVE_PHYSICAL_ADDRESS],
            'initiator': RECORDER_1,
            'destination': int(dst, 16)
        }

        self.cec_utils.sendCecMessage(src, dst, operand)
        '''First callback function should not receive the message from HAL'''
        asserts.assertEqual(
            self.checkForOnCecMessageCallback(hdmi_cec_first_callback,
                                              cec_message), False,
            ", first callback function received the message")
        '''Second callback function should receive the message from HAL.'''
        asserts.assertEqual(
            self.checkForOnCecMessageCallback(hdmi_cec_second_callback,
                                              cec_message), True,
            ", second callback function did not receive the message")

    def testSetOption_enableCecFlag(self):
        """Test case which checks that no acknowledgement for POLL message when sets the
        ENABLE_CEC flag to false and there is acknowledgement when sets the flag to true."""
        # TODO: Remove skip after b/162912390 is resolved.
        asserts.skip("Skip test (refer b/162912390).")
        try:
            '''Set ENABLE_CEC to false.'''
            self.setEnableCec(False)
            self.pollDutLogicalAddressAndCheckResponse("POLL not sent")
            '''Set ENABLE_CEC to true.'''
            self.setEnableCec(True)
            self.pollDutLogicalAddressAndCheckResponse("POLL sent")
        finally:
            self.setEnableCec(True)

if __name__ == "__main__":
    test_runner.main()
