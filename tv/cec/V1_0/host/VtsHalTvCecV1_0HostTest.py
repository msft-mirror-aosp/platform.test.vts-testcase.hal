#!/usr/bin/env python
#
# Copyright (C) 2016 The Android Open Source Project
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

TVCEC_V1_0_HAL = "android.hardware.tv.cec@1.0::IHdmiCec"

class TvCecHidlTest(hal_hidl_host_test.HalHidlHostTest):
    """Host testcase class for the TV HDMI_CEC HIDL HAL."""

    TEST_HAL_SERVICES = {TVCEC_V1_0_HAL}
    def setUpClass(self):
        """Creates a mirror and init tv hdmi cec hal service."""
        super(TvCecHidlTest, self).setUpClass()

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

    def testClearAndAddLogicalAddress(self):
        """A simple test case which sets logical address and clears it."""
        self.dut.hal.tv_cec.clearLogicalAddress()
        result = self.dut.hal.tv_cec.addLogicalAddress(
                self.vtypes.CecLogicalAddress.PLAYBACK_3)
        asserts.assertEqual(self.vtypes.Result.SUCCESS, result)
        logging.info("addLogicalAddress result: %s", result)

    def testGetPhysicalAddress(self):
        """A simple test case which queries the physical address and validates it."""
        status, paddr = self.dut.hal.tv_cec.getPhysicalAddress()
        asserts.assertEqual(self.vtypes.Result.SUCCESS, status)
        logging.info("getPhysicalAddress status: %s, paddr: %s", status, paddr)
        device_types = self.getDeviceTypes()
        asserts.assertNotEqual(device_types, None, "Device types could not be determined")
        if '0' not in device_types:
            asserts.assertNotEqual(paddr, 0)
            asserts.assertNotEqual(paddr, 65535)
        else:
            asserts.assertEqual(paddr, 0)

    def testSendRandomMessage(self):
        """A test case which sends a random message."""
        cec_message = {
            "initiator": self.vtypes.CecLogicalAddress.TV,
            "destination": self.vtypes.CecLogicalAddress.PLAYBACK_1,
            "body": [1, 2, 3]
        }
        message = self.vtypes.Py2Pb("CecMessage", cec_message)
        logging.info("message: %s", message)
        result = self.dut.hal.tv_cec.sendMessage(message)
        logging.info("sendMessage result: %s", result)

    def testGetCecVersion1(self):
        """A simple test case which queries the cec version and validates its response."""
        version = self.dut.hal.tv_cec.getCecVersion()
        logging.info("getCecVersion version: %s", version)
        '''The value 5 represents CEC version 1.4'''
        asserts.assertEqual(version, 5)

    def testGetVendorId(self):
        """A simple test case which queries vendor id and validates that it is not 0."""
        vendor_id = self.dut.hal.tv_cec.getVendorId()
        asserts.assertEqual(0, 0xff000000 & vendor_id)
        logging.info("getVendorId vendor_id: %s", vendor_id)
        asserts.assertNotEqual(vendor_id, 0)

    def testGetPortInfo(self):
        """A simple test case which queries port information and validates the response fields."""
        port_infos = self.dut.hal.tv_cec.getPortInfo()
        logging.info("getPortInfo port_infos: %s", port_infos)
        device_types = self.getDeviceTypes()
        asserts.assertNotEqual(device_types, None, "Device types could not be determined")
        cec_supported_on_device = False
        for port_info in port_infos:
            asserts.assertEqual(port_info.get("type") in
                    [self.vtypes.HdmiPortType.INPUT, self.vtypes.HdmiPortType.OUTPUT], True)
            asserts.assertLess(-1, port_info.get("portId"), ", PortId is less than 0")
            cec_supported_on_device = cec_supported_on_device or port_info.get("cecSupported")
            if '0' not in device_types:
                '''Since test setup mandates the DUT is connected to a sink, address cannot be 0
                for non-TV device.'''
                asserts.assertNotEqual(port_info.get("physicalAddress"), 0)
        asserts.assertNotEqual(cec_supported_on_device, False,
                               ", at least one port should support CEC.")

    def testSetOption(self):
        """A simple test case which changes CEC options."""
        self.dut.hal.tv_cec.setOption(self.vtypes.OptionKey.WAKEUP, True)
        self.dut.hal.tv_cec.setOption(self.vtypes.OptionKey.ENABLE_CEC, True)
        self.dut.hal.tv_cec.setOption(
                self.vtypes.OptionKey.SYSTEM_CEC_CONTROL, True)

    def testSetLanguage(self):
        """A simple test case which updates language information."""
        self.dut.hal.tv_cec.setLanguage("eng")

    def testEnableAudioReturnChannel(self):
        """Checks whether Audio Return Channel can be enabled."""
        port_infos = self.dut.hal.tv_cec.getPortInfo()
        for port_info in port_infos:
            if "portId" in port_info and port_info.get("arcSupported"):
                self.dut.hal.tv_cec.enableAudioReturnChannel(
                        port_info["portId"], True)

    def testIsConnected(self):
        """A simple test case which queries the connected status and validates it."""
        device_types = self.getDeviceTypes()
        asserts.assertNotEqual(device_types, None, "Device types could not be determined")
        paddr_status, paddr = self.dut.hal.tv_cec.getPhysicalAddress()
        status = False
        port_infos = self.dut.hal.tv_cec.getPortInfo()
        '''Connection status will be true if at least one of the DUT port is connected.'''
        for port_info in port_infos:
            status = status or self.dut.hal.tv_cec.isConnected(port_info.get("portId"))

        logging.info("isConnected status: %s", status)
        if '0' in device_types:
            asserts.assertEqual(status, True)
        elif paddr is 0 or paddr is 65535:
            asserts.assertEqual(status, False)
        else:
            asserts.assertEqual(status, True)

if __name__ == "__main__":
    test_runner.main()
