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
from vts.runners.host import base_test
from vts.runners.host import const
from vts.runners.host import keys
from vts.runners.host import test_runner
from vts.utils.python.controllers import android_device


class VtsHalAutomotiveVehicleV2_0HostTest(base_test.BaseTestClass):
    """A simple testcase for the VEHICLE HIDL HAL."""

    def setUpClass(self):
        """Creates a mirror and init vehicle hal."""
        self.dut = self.registerController(android_device)[0]

        self.dut.shell.InvokeTerminal("one")
        self.dut.shell.one.Execute("setenforce 0")  # SELinux permissive mode

        results = self.dut.shell.one.Execute("id -u system")
        system_uid = results[const.STDOUT][0].strip()
        logging.info("system_uid: %s", system_uid)

        if self.coverage.enabled:
            self.coverage.LoadArtifacts()
            self.coverage.InitializeDeviceCoverage(self.dut)

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
        asserts.assertEqual(0x00ff0000, self.vtypes.VehiclePropertyType.MASK)
        asserts.assertEqual(0x0f000000, self.vtypes.VehicleArea.MASK)

    def tearDownClass(self):
        """Disables the profiling.

        If profiling is enabled for the test, collect the profiling data
        and disable profiling after the test is done.
        """
        if self.profiling.enabled:
            self.profiling.ProcessAndUploadTraceData()

        if self.coverage.enabled:
            self.coverage.SetCoverageData(dut=self.dut, isGlobal=True)

    def setUpTest(self):
        if self.profiling.enabled:
            self.profiling.EnableVTSProfiling(self.dut.shell.one)

        self.propToConfig = {}
        for config in self.vehicle.getAllPropConfigs():
            self.propToConfig[config['prop']] = config
        self.configList = self.propToConfig.values()

    def tearDownTest(self):
        if self.profiling.enabled:
            self.profiling.ProcessTraceDataForTestCase(self.dut)
            self.profiling.DisableVTSProfiling(self.dut.shell.one)

    def testListProperties(self):
        """Checks whether some PropConfigs are returned.

        Verifies that call to getAllPropConfigs is not failing and
        it returns at least 1 vehicle property config.
        """
        logging.info("all supported properties: %s", self.configList)
        asserts.assertLess(0, len(self.configList))

    def testMandatoryProperties(self):
        """Verifies that all mandatory properties are supported."""
        # 1 property so far
        mandatoryProps = set([self.vtypes.VehicleProperty.DRIVING_STATUS])
        logging.info(self.vtypes.VehicleProperty.DRIVING_STATUS)

        for config in self.configList:
            mandatoryProps.discard(config['prop'])

        asserts.assertEqual(0, len(mandatoryProps))

    def emptyValueProperty(self, propertyId, areaId=0):
        """Creates a property structure for use with the Vehicle HAL.

        Args:
            propertyId: the numeric identifier of the output property.
            areaId: the numeric identifier of the vehicle area of the output
                    property. 0, or omitted, for global.

        Returns:
            a property structure for use with the Vehicle HAL.
        """
        return {
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
        vp = self.vtypes.Py2Pb("VehiclePropValue",
                               self.emptyValueProperty(propertyId, areaId))
        logging.info("0x%08X get request: %s", propertyId, vp)
        status, value = self.vehicle.get(vp)
        logging.info("0x%08X get response: %s, %s", propertyId, status, value)
        if self.vtypes.StatusCode.OK == status:
            return value
        else:
            logging.warning("attempt to read property 0x%08X returned error %d",
                            propertyId, status)

    def setVhalProperty(self, propertyId, value, areaId=0,
                        expectedStatus=0):
        """Sets a specified property in the Vehicle HAL.

        Args:
            propertyId: the numeric identifier of the property to be set.
            value: the value of the property, formatted as per the Vehicle HAL
                   (use emptyValueProperty() as a helper).
            areaId: the numeric identifier of the vehicle area to set the
                    property for. 0, or omitted, for global.
            expectedStatus: the StatusCode expected to be returned from setting
                    the property. 0, or omitted, for OK.
        """
        propValue = self.emptyValueProperty(propertyId, areaId)
        for k in propValue["value"]:
            if k in value:
                if k == "stringValue":
                    propValue["value"][k] += value[k]
                else:
                    propValue["value"][k].extend(value[k])
        vp = self.vtypes.Py2Pb("VehiclePropValue", propValue)
        logging.info("0x%x set request: %s", propertyId, vp)
        status = self.vehicle.set(vp)
        logging.info("0x%x set response: %s", propertyId, status)
        if 0 == expectedStatus:
            expectedStatus = self.vtypes.StatusCode.OK
        asserts.assertEqual(expectedStatus, status, "Prop 0x%x" % propertyId)

    def setAndVerifyIntProperty(self, propertyId, value, areaId=0):
        """Sets a integer property in the Vehicle HAL and reads it back.

        Args:
            propertyId: the numeric identifier of the property to be set.
            value: the int32 value of the property to be set.
            areaId: the numeric identifier of the vehicle area to set the
                    property for. 0, or omitted, for global.
        """
        self.setVhalProperty(propertyId, {"int32Values" : [value]})

        propValue = self.readVhalProperty(propertyId)
        asserts.assertEqual(1, len(propValue["value"]["int32Values"]))
        asserts.assertEqual(value, propValue["value"]["int32Values"][0])

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
                                self.vtypes.VehicleProperty.OBD2_LIVE_FRAME,
                                "OBD2_LIVE_FRAME")
            checker()

        def checkFreezeFrameRead():
            """Validates reading the OBD2_FREEZE_FRAME (if available)."""
            checker = CheckRead(self,
                                self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME,
                                "OBD2_FREEZE_FRAME")
            checker()

        isLiveSupported = self.vtypes.VehicleProperty.OBD2_LIVE_FRAME in self.propToConfig
        isFreezeSupported = self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME in self.propToConfig
        logging.info("isLiveSupported = %s, isFreezeSupported = %s",
                     isLiveSupported, isFreezeSupported)
        if isLiveSupported:
            checkLiveFrameRead()
        if isFreezeSupported:
            checkFreezeFrameRead()

    def testDrivingStatus(self):
        """Checks that DRIVING_STATUS property returns correct result."""
        propValue = self.readVhalProperty(
            self.vtypes.VehicleProperty.DRIVING_STATUS)
        asserts.assertEqual(1, len(propValue["value"]["int32Values"]))
        drivingStatus = propValue["value"]["int32Values"][0]

        allStatuses = (self.vtypes.VehicleDrivingStatus.UNRESTRICTED
                       | self.vtypes.VehicleDrivingStatus.NO_VIDEO
                       | self.vtypes.VehicleDrivingStatus.NO_KEYBOARD_INPUT
                       | self.vtypes.VehicleDrivingStatus.NO_VOICE_INPUT
                       | self.vtypes.VehicleDrivingStatus.NO_CONFIG
                       | self.vtypes.VehicleDrivingStatus.LIMIT_MESSAGE_LEN)

        asserts.assertEqual(allStatuses, allStatuses | drivingStatus)

    def extractZonesAsList(self, supportedAreas):
        """Converts bitwise area flags to list of zones"""
        allZones = [
            self.vtypes.VehicleAreaZone.ROW_1_LEFT,
            self.vtypes.VehicleAreaZone.ROW_1_CENTER,
            self.vtypes.VehicleAreaZone.ROW_1_RIGHT,
            self.vtypes.VehicleAreaZone.ROW_1,
            self.vtypes.VehicleAreaZone.ROW_2_LEFT,
            self.vtypes.VehicleAreaZone.ROW_2_CENTER,
            self.vtypes.VehicleAreaZone.ROW_2_RIGHT,
            self.vtypes.VehicleAreaZone.ROW_2,
            self.vtypes.VehicleAreaZone.ROW_3_LEFT,
            self.vtypes.VehicleAreaZone.ROW_3_CENTER,
            self.vtypes.VehicleAreaZone.ROW_3_RIGHT,
            self.vtypes.VehicleAreaZone.ROW_3,
            self.vtypes.VehicleAreaZone.ROW_4_LEFT,
            self.vtypes.VehicleAreaZone.ROW_4_CENTER,
            self.vtypes.VehicleAreaZone.ROW_4_RIGHT,
            self.vtypes.VehicleAreaZone.ROW_4,
            self.vtypes.VehicleAreaZone.WHOLE_CABIN,
        ]

        extractedZones = []
        for zone in allZones:
            if (zone & supportedAreas == zone):
                extractedZones.append(zone)
        return extractedZones


    def testHvacPowerOn(self):
        """Test power on/off and properties associated with it.

        Gets the list of properties that are affected by the HVAC power state
        and validates them.

        Turns power on to start in a defined state, verifies that power is on
        and properties are available.  State change from on->off and verifies
        that properties are no longer available, then state change again from
        off->on to verify properties are now available again.
        """

        # Checks that HVAC_POWER_ON property is supported and returns valid
        # result initially.
        hvacPowerOnConfig = self.propToConfig[self.vtypes.VehicleProperty.HVAC_POWER_ON]
        if hvacPowerOnConfig is None:
            logging.info("HVAC_POWER_ON not supported")
            return

        zones = self.extractZonesAsList(hvacPowerOnConfig['supportedAreas'])
        asserts.assertLess(0, len(zones))

        # TODO(pavelm): consider to check for all zones
        zone = zones[0]

        propValue = self.readVhalProperty(
            self.vtypes.VehicleProperty.HVAC_POWER_ON, areaId=zone)

        asserts.assertEqual(1, len(propValue["value"]["int32Values"]))
        asserts.assertTrue(
            propValue["value"]["int32Values"][0] in [0, 1],
            "%d not a valid value for HVAC_POWER_ON" %
                propValue["value"]["int32Values"][0]
            )

        # Checks that HVAC_POWER_ON config string returns valid result.
        requestConfig = [self.vtypes.Py2Pb(
            "VehicleProperty", self.vtypes.VehicleProperty.HVAC_POWER_ON)]
        logging.info("HVAC power on config request: %s", requestConfig)
        responseConfig = self.vehicle.getPropConfigs(requestConfig)
        logging.info("HVAC power on config response: %s", responseConfig)
        hvacTypes = set([
            self.vtypes.VehicleProperty.HVAC_FAN_SPEED,
            self.vtypes.VehicleProperty.HVAC_FAN_DIRECTION,
            self.vtypes.VehicleProperty.HVAC_TEMPERATURE_CURRENT,
            self.vtypes.VehicleProperty.HVAC_TEMPERATURE_SET,
            self.vtypes.VehicleProperty.HVAC_DEFROSTER,
            self.vtypes.VehicleProperty.HVAC_AC_ON,
            self.vtypes.VehicleProperty.HVAC_MAX_AC_ON,
            self.vtypes.VehicleProperty.HVAC_MAX_DEFROST_ON,
            self.vtypes.VehicleProperty.HVAC_RECIRC_ON,
            self.vtypes.VehicleProperty.HVAC_DUAL_ON,
            self.vtypes.VehicleProperty.HVAC_AUTO_ON,
            self.vtypes.VehicleProperty.HVAC_ACTUAL_FAN_SPEED_RPM,
        ])
        status = responseConfig[0]
        asserts.assertEqual(self.vtypes.StatusCode.OK, status)
        configString = responseConfig[1][0]["configString"]
        configProps = []
        if configString != "":
            for prop in configString.split(","):
                configProps.append(int(prop, 16))
        for prop in configProps:
            asserts.assertTrue(prop in hvacTypes,
                               "0x%X not an HVAC type" % prop)

        # Turn power on.
        self.setAndVerifyIntProperty(
            self.vtypes.VehicleProperty.HVAC_POWER_ON, 1, areaId=zone)

        # Check that properties that require power to be on can be set.
        propVals = {}
        for prop in configProps:
            v = self.readVhalProperty(prop, areaId=zone)["value"]
            self.setVhalProperty(prop, v, areaId=zone)
            # Save the value for use later when trying to set the property when
            # HVAC is off.
            propVals[prop] = v

        # Turn power off.
        self.setAndVerifyIntProperty(
            self.vtypes.VehicleProperty.HVAC_POWER_ON, 0, areaId=zone)

        # Check that properties that require power to be on can't be set.
        for prop in configProps:
            self.setVhalProperty(
                prop, propVals[prop],
                areaId=zone,
                expectedStatus=self.vtypes.StatusCode.NOT_AVAILABLE)

        # Turn power on.
        self.setAndVerifyIntProperty(
            self.vtypes.VehicleProperty.HVAC_POWER_ON, 1, areaId=zone)

        # Check that properties that require power to be on can be set.
        for prop in configProps:
            self.setVhalProperty(prop, propVals[prop], areaId=zone)

    def testVehicleStaticProps(self):
        """Verifies that static properties are configured correctly"""
        staticProperties = set([
            self.vtypes.VehicleProperty.INFO_VIN,
            self.vtypes.VehicleProperty.INFO_MAKE,
            self.vtypes.VehicleProperty.INFO_MODEL,
            self.vtypes.VehicleProperty.INFO_MODEL_YEAR,
            self.vtypes.VehicleProperty.INFO_FUEL_CAPACITY,
            self.vtypes.VehicleProperty.HVAC_FAN_DIRECTION_AVAILABLE,
            self.vtypes.VehicleProperty.AUDIO_HW_VARIANT,
            self.vtypes.VehicleProperty.AP_POWER_BOOTUP_REASON,
        ])
        for c in self.configList:
            prop = c['prop']
            msg = "Prop 0x%x" % prop
            if (c["prop"] in staticProperties):
                asserts.assertEqual(self.vtypes.VehiclePropertyChangeMode.STATIC, c["changeMode"], msg)
                asserts.assertEqual(self.vtypes.VehiclePropertyAccess.READ, c["access"], msg)
                propValue = self.readVhalProperty(prop)
                asserts.assertEqual(prop, propValue['prop'])
                self.setVhalProperty(prop, propValue["value"],
                    expectedStatus=self.vtypes.StatusCode.ACCESS_DENIED)
            else:  # Non-static property
                asserts.assertNotEqual(self.vtypes.VehiclePropertyChangeMode.STATIC, c["changeMode"], msg)

    def testPropertyRanges(self):
        """Retrieve the property ranges for all areas.

        This checks that the areas noted in the config all give valid area
        configs.  Once these are validated, the values for all these areas
        retrieved from the HIDL must be within the ranges defined."""
        for c in self.configList:
            # Continuous properties need to have a sampling frequency.
            if c["changeMode"] & self.vtypes.VehiclePropertyChangeMode.CONTINUOUS != 0:
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

    def testDebugDump(self):
        """Verifies that call to IVehicle#debugDump is not failing"""
        dumpStr = self.vehicle.debugDump()
        asserts.assertNotEqual(None, dumpStr)

if __name__ == "__main__":
    test_runner.main()
