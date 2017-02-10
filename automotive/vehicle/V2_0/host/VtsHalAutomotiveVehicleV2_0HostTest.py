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
from vts.runners.host import base_test_with_webdb
from vts.runners.host import const
from vts.runners.host import keys
from vts.runners.host import test_runner
from vts.utils.python.controllers import android_device
from vts.utils.python.profiling import profiling_utils
from vts.utils.python.coverage import coverage_utils


class VtsHalAutomotiveVehicleV2_0HostTest(base_test_with_webdb.BaseTestWithWebDbClass):
    """A simple testcase for the VEHICLE HIDL HAL."""

    def setUpClass(self):
        """Creates a mirror and init vehicle hal."""
        self.dut = self.registerController(android_device)[0]

        self.dut.shell.InvokeTerminal("one")
        self.dut.shell.one.Execute("setenforce 0")  # SELinux permissive mode

        results = self.dut.shell.one.Execute("id -u system")
        system_uid = results[const.STDOUT][0].strip()
        logging.info("system_uid: %s", system_uid)

        if getattr(self, keys.ConfigKeys.IKEY_ENABLE_COVERAGE, False):
            coverage_utils.InitializeDeviceCoverage(self.dut)

        self.dut.hal.InitHidlHal(
            target_type="vehicle",
            target_basepaths=self.dut.libPaths,
            target_version=2.0,
            target_package="android.hardware.automotive.vehicle",
            target_component_name="IVehicle",
            bits=64 if self.dut.is64Bit else 32)

        self.vehicle = self.dut.hal.vehicle  # shortcut
        self.vehicle.SetCallerUid(system_uid)
        self.vtypes = self.dut.hal.vehicle.GetHidlTypeInterface("types")
        logging.info("vehicle types: %s", self.vtypes)

    def tearDownClass(self):
        """Disables the profiling.

        If profiling is enabled for the test, collect the profiling data
        and disable profiling after the test is done.
        """
        if self.enable_profiling:
            self.ProcessAndUploadTraceData()

        if getattr(self, keys.ConfigKeys.IKEY_ENABLE_COVERAGE, False):
            self.SetCoverageData(coverage_utils.GetGcdaDict(self.dut))

    def setUpTest(self):
        if self.enable_profiling:
            profiling_utils.EnableVTSProfiling(self.dut.shell.one)

    def tearDownTest(self):
        if self.enable_profiling:
            profiling_trace_path = getattr(
                self, self.VTS_PROFILING_TRACING_PATH, "")
            self.ProcessTraceDataForTestCase(self.dut, profiling_trace_path)
            profiling_utils.DisableVTSProfiling(self.dut.shell.one)

    def testListProperties(self):
        """Checks whether some PropConfigs are returned.

        Verifies that call to getAllPropConfigs is not failing and
        it returns at least 1 vehicle property config.
        """
        allConfigs = self.vehicle.getAllPropConfigs()
        logging.info("all supported properties: %s", allConfigs)
        asserts.assertLess(0, len(allConfigs))

    def testMandatoryProperties(self):
        """Verifies that all mandatory properties are supported."""
        mandatoryProps = set([self.vtypes.DRIVING_STATUS])  # 1 property so far
        logging.info(self.vtypes.DRIVING_STATUS)
        allConfigs = self.dut.hal.vehicle.getAllPropConfigs()

        for config in allConfigs:
            mandatoryProps.discard(config['prop'])

        asserts.assertEqual(0, len(mandatoryProps))

    def getSupportInfo(self):
        """Check whether OBD2_{LIVE|FREEZE}_FRAME is supported."""
        isLiveSupported, isFreezeSupported = False, False
        allConfigs = self.vehicle.getAllPropConfigs()
        for config in allConfigs:
            if config['prop'] == self.vtypes.OBD2_LIVE_FRAME:
                isLiveSupported = True
            elif config['prop'] == self.vtypes.OBD2_FREEZE_FRAME:
                isFreezeSupported = True
            if isLiveSupported and isFreezeSupported:
                break
        return isLiveSupported, isFreezeSupported

    def readVhalProperty(self, propertyId, areaId=0):
        """Reads a specified property from Vehicle HAL.

        Args:
            propertyId: the numeric identifier of the property to be read.
            areaId: the numeric identifier of the vehicle area to retrieve the
                    property for. 0, or omitted, for global.

        Returns:
            the value of the property as read from Vehicle HAL, or None
            if it could not read successfully.
        """
        vp_dict = {
            'prop' : propertyId,
            'timestamp' : 0,
            'areaId' : areaId,
            'value' : {
                'int32Values' : [],
                'floatValues' : [],
                'int64Values' : [],
                'bytes' : [],
                'stringValue' : ""
            }
        }
        vp = self.vtypes.Py2Pb("VehiclePropValue", vp_dict)
        status, value = self.vehicle.get(vp)
        if self.vtypes.OK == status:
            return value
        else:
            logging.warning("attempt to read property %s returned error %d",
                            propertyId, status)

    def testObd2SensorProperties(self):
        """Test reading the live and freeze OBD2 frame properties.

        OBD2 (On-Board Diagnostics 2) is the industry standard protocol
        for retrieving diagnostic sensor information from vehicles.
        """
        class CheckRead(object):
            """This class wraps the logic of an actual property read.

            Attributes:
                testobject: the test case this object is used on behalf of.
                propertyId: the identifier of the Vehiche HAL property to read.
                name: the engineer-readable name of this test operation.
            """

            def __init__(self, testobject, propertyId, name):
                self.testobject = testobject
                self.propertyId = propertyId
                self.name = name

            def onReadSuccess(self, propValue):
                """Override this to perform any post-read validation.

                Args:
                    propValue: the property value obtained from Vehicle HAL.
                """
                pass

            def __call__(self):
                """Reads the specified property and validates the result."""
                propValue = self.testobject.readVhalProperty(self.propertyId)
                asserts.assertNotEqual(propValue, None,
                                       msg="reading %s should not return None" %
                                       self.name)
                logging.info("%s = %s", self.name, propValue)
                self.onReadSuccess(propValue)
                logging.info("%s pass" % self.name)

        def checkLiveFrameRead():
            """Validates reading the OBD2_LIVE_FRAME (if available)."""
            checker = CheckRead(self,
                                self.vtypes.OBD2_LIVE_FRAME,
                                "OBD2_LIVE_FRAME")
            checker()

        def checkFreezeFrameRead():
            """Validates reading the OBD2_FREEZE_FRAME (if available)."""
            checker = CheckRead(self,
                                self.vtypes.OBD2_FREEZE_FRAME,
                                "OBD2_FREEZE_FRAME")
            checker()

        isLiveSupported, isFreezeSupported = self.getSupportInfo()
        logging.info("isLiveSupported = %s, isFreezeSupported = %s",
                     isLiveSupported, isFreezeSupported)
        if isLiveSupported:
            checkLiveFrameRead()
        if isFreezeSupported:
            checkFreezeFrameRead()

    def createVehiclePropValue(self, propId):
        value = {
            "int32Values" : [],
            "floatValues" : [],
            "int64Values" : [],
            "bytes": [],
            "stringValue": ""
        }
        propValue = {
            "prop": propId,
            "timestamp": 0,
            "areaId": 0,
            "value": value
        }
        return self.vtypes.Py2Pb("VehiclePropValue", propValue)

    def testDrivingStatus(self):
        """Checks that DRIVING_STATUS property returns correct result."""
        request = self.createVehiclePropValue(self.vtypes.DRIVING_STATUS)
        logging.info("Driving status request: %s", request)
        response = self.vehicle.get(request)
        logging.info("Driving status response: %s", response)
        status = response[0]
        asserts.assertEqual(self.vtypes.OK, status)
        propValue = response[1]
        assertEqual(1, len(propValue.value.int32Values))
        drivingStatus = propValue.value.int32Values[0]

        allStatuses = (self.vtypes.UNRESTRICTED | self.vtypes.NO_VIDEO
               | self.vtypes.NO_KEYBOARD_INPUT | self.vtypes.NO_VOICE_INPUT
               | self.vtypes.NO_CONFIG | self.vtypes.LIMIT_MESSAGE_LEN)

        assertEqual(allStatuses, allStatuses | drivingStatus)

    def testPropertyRanges(self):
        """Retrieve the property ranges for all areas.

        This checks that the areas noted in the config all give valid area
        configs.  Once these are validated, the values for all these areas
        retrieved from the HIDL must be within the ranges defined."""
        configs = self.vehicle.getAllPropConfigs()
        logging.info("Property list response: %s", configs)
        for c in configs:
            # Continuous properties need to have a sampling frequency.
            if c["changeMode"] & self.vtypes.CONTINUOUS != 0:
                asserts.assertLess(0.0, c["minSampleRate"])
                asserts.assertLess(0.0, c["maxSampleRate"])
                asserts.assertFalse(c["minSampleRate"] > c["maxSampleRate"],
                                    "Prop 0x%x minSampleRate > maxSampleRate" %
                                        c["prop"])

            areasFound = 0
            for a in c["areaConfigs"]:
                # Make sure this doesn't override one of the other areas found.
                asserts.assertEqual(0, areasFound & a["areaId"])
                areasFound |= a["areaId"]

                # Do some basic checking the min and max aren't mixed up.
                checks = [
                    ("minInt32Value", "maxInt32Value"),
                    ("minInt64Value", "maxInt64Value"),
                    ("minFloatValue", "maxFloatValue")
                ]
                for minName, maxName in checks:
                    asserts.assertFalse(
                        a[minName] > a[maxName],
                        "Prop 0x%x Area 0x%X %s > %s: %d > %d" %
                            (c["prop"], a["areaId"],
                             minName, maxName, a[minName], a[maxName]))

                # Get a value and make sure it's within the bounds.
                propVal = self.readVhalProperty(c["prop"], a["areaId"])
                # Some values may not be available, which is not an error.
                if propVal is None:
                    continue
                val = propVal["value"]
                valTypes = {
                    "int32Values": ("minInt32Value", "maxInt32Value"),
                    "int64Values": ("minInt64Value", "maxInt64Value"),
                    "floatValues": ("minFloatValue", "maxFloatValue"),
                }
                for valType, valBoundNames in valTypes.items():
                    for v in val[valType]:
                        # Make sure value isn't less than the minimum.
                        asserts.assertFalse(
                            v < a[valBoundNames[0]],
                            "Prop 0x%x Area 0x%X %s < min: %s < %s" %
                                (c["prop"], a["areaId"],
                                 valType, v, a[valBoundNames[0]]))
                        # Make sure value isn't greater than the maximum.
                        asserts.assertFalse(
                            v > a[valBoundNames[1]],
                            "Prop 0x%x Area 0x%X %s > max: %s > %s" %
                                (c["prop"], a["areaId"],
                                 valType, v, a[valBoundNames[1]]))


if __name__ == "__main__":
    test_runner.main()
