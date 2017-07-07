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


class VtsHalAutomotiveVehicleV2_1HostTest(base_test.BaseTestClass):
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

        if self.profiling.enabled:
            self.profiling.EnableVTSProfiling(self.dut.shell.one)

        self.dut.hal.InitHidlHal(
            target_type="vehicle",
            target_basepaths=self.dut.libPaths,
            target_version=2.1,
            target_package="android.hardware.automotive.vehicle",
            target_component_name="IVehicle",
            bits=64 if self.dut.is64Bit else 32)

        self.vehicle = self.dut.hal.vehicle  # shortcut
        self.vehicle.SetCallerUid(system_uid)
        self.vtypes = self.dut.hal.vehicle.GetHidlTypeInterface("types")
        logging.info("vehicle types: %s", self.vtypes)
        self.halProperties = {}

    def tearDownClass(self):
        """Disables the profiling.

        If profiling is enabled for the test, collect the profiling data
        and disable profiling after the test is done.
        """
        if self.profiling.enabled:
            self.profiling.ProcessTraceDataForTestCase(self.dut)
            self.profiling.ProcessAndUploadTraceData()

        if self.coverage.enabled:
            self.coverage.SetCoverageData(dut=self.dut, isGlobal=True)

    def isPropertySupported(self, propertyId):
        """Check whether a Vehicle HAL property is supported.

           Args:
               propertyId: the numeric identifier of the vehicle property.

           Returns:
                  True if the HAL implementation supports the property, False otherwise.
        """
        if propertyId in self.halProperties:
            return self.halProperties[propertyId] is not None
        ok, config = self.vehicle.getPropConfigs([propertyId])
        logging.info("propertyId = %s, ok = %s, config = %s",
            propertyId, ok, config)
        if ok == self.vtypes.StatusCode.OK:
            self.halProperties[propertyId] = config
            return True
        else:
            self.halProperties[propertyId] = None
            return False

    def getDiagnosticSupportInfo(self):
        """Check which of the OBD2 diagnostic properties are supported."""
        properties = [self.vtypes.VehicleProperty.OBD2_LIVE_FRAME,
            self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME,
            self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_INFO,
            self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_CLEAR]
        return {x:self.isPropertySupported(x) for x in properties}

    class CheckRead(object):
        """An object whose job it is to read a Vehicle HAL property and run
           routine validation checks on the result."""

        def __init__(self, test, propertyId, areaId=0):
            """Creates a CheckRead instance.

            Args:
                test: the containing testcase object.
                propertyId: the numeric identifier of the vehicle property.
            """
            self.test = test
            self.propertyId = propertyId
            self.areaId = 0

        def validateGet(self, status, value):
            """Validate the result of IVehicle.get.

            Args:
                status: the StatusCode returned from Vehicle HAL.
                value: the VehiclePropValue returned from Vehicle HAL.

            Returns: a VehiclePropValue instance, or None on failure."""
            asserts.assertEqual(self.test.vtypes.StatusCode.OK, status)
            asserts.assertNotEqual(value, None)
            asserts.assertEqual(self.propertyId, value['prop'])
            return value

        def prepareRequest(self, propValue):
            """Setup this request with any property-specific data.

            Args:
                propValue: a dictionary in the format of a VehiclePropValue.

            Returns: a dictionary in the format of a VehclePropValue."""
            return propValue

        def __call__(self):
            asserts.assertTrue(self.test.isPropertySupported(self.propertyId), "error")
            request = {
                'prop' : self.propertyId,
                'timestamp' : 0,
                'areaId' : self.areaId,
                'value' : {
                    'int32Values' : [],
                    'floatValues' : [],
                    'int64Values' : [],
                    'bytes' : [],
                    'stringValue' : ""
                }
            }
            request = self.prepareRequest(request)
            requestPropValue = self.test.vtypes.Py2Pb("VehiclePropValue",
                request)
            status, responsePropValue = self.test.vehicle.get(requestPropValue)
            return self.validateGet(status, responsePropValue)

    class CheckWrite(object):
        """An object whose job it is to write a Vehicle HAL property and run
           routine validation checks on the result."""

        def __init__(self, test, propertyId, areaId=0):
            """Creates a CheckWrite instance.

            Args:
                test: the containing testcase object.
                propertyId: the numeric identifier of the vehicle property.
                areaId: the numeric identifier of the vehicle area.
            """
            self.test = test
            self.propertyId = propertyId
            self.areaId = 0

        def validateSet(self, status):
            """Validate the result of IVehicle.set.
            Reading back the written-to property to ensure a consistent
            value is fair game for this method.

            Args:
                status: the StatusCode returned from Vehicle HAL.

            Returns: None."""
            asserts.assertEqual(self.test.vtypes.StatusCode.OK, status)

        def prepareRequest(self, propValue):
            """Setup this request with any property-specific data.

            Args:
                propValue: a dictionary in the format of a VehiclePropValue.

            Returns: a dictionary in the format of a VehclePropValue."""
            return propValue

        def __call__(self):
            asserts.assertTrue(self.test.isPropertySupported(self.propertyId), "error")
            request = {
                'prop' : self.propertyId,
                'timestamp' : 0,
                'areaId' : self.areaId,
                'value' : {
                    'int32Values' : [],
                    'floatValues' : [],
                    'int64Values' : [],
                    'bytes' : [],
                    'stringValue' : ""
                }
            }
            request = self.prepareRequest(request)
            requestPropValue = self.test.vtypes.Py2Pb("VehiclePropValue",
                request)
            status = self.test.vehicle.set(requestPropValue)
            return self.validateSet(status)

    def testReadObd2LiveFrame(self):
        """Test that one can correctly read the OBD2 live frame."""
        supportInfo = self.getDiagnosticSupportInfo()
        if supportInfo[self.vtypes.VehicleProperty.OBD2_LIVE_FRAME]:
            checkRead = self.CheckRead(self,
                self.vtypes.VehicleProperty.OBD2_LIVE_FRAME)
            checkRead()
        else:
            # live frame not supported by this HAL implementation. done
            logging.info("OBD2_LIVE_FRAME not supported.")

    def testReadObd2FreezeFrameInfo(self):
        """Test that one can read the list of OBD2 freeze timestamps."""
        supportInfo = self.getDiagnosticSupportInfo()
        if supportInfo[self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_INFO]:
            checkRead = self.CheckRead(self,
                self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_INFO)
            checkRead()
        else:
            # freeze frame info not supported by this HAL implementation. done
            logging.info("OBD2_FREEZE_FRAME_INFO not supported.")

    def testReadValidObd2FreezeFrame(self):
        """Test that one can read the OBD2 freeze frame data."""
        class FreezeFrameCheckRead(self.CheckRead):
            def __init__(self, test, timestamp):
                self.test = test
                self.propertyId = \
                    self.test.vtypes.VehicleProperty.OBD2_FREEZE_FRAME
                self.timestamp = timestamp
                self.areaId = 0

            def prepareRequest(self, propValue):
                propValue['value']['int64Values'] = [self.timestamp]
                return propValue

            def validateGet(self, status, value):
                # None is acceptable, as a newer fault could have overwritten
                # the one we're trying to read
                if value is not None:
                    asserts.assertEqual(self.test.vtypes.StatusCode.OK, status)
                    asserts.assertEqual(self.propertyId, value['prop'])
                    asserts.assertEqual(self.timestamp, value['timestamp'])

        supportInfo = self.getDiagnosticSupportInfo()
        if supportInfo[self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_INFO] \
            and supportInfo[self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME]:
            infoCheckRead = self.CheckRead(self,
                self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_INFO)
            frameInfos = infoCheckRead()
            timestamps = frameInfos["value"]["int64Values"]
            for timestamp in timestamps:
                freezeCheckRead = FreezeFrameCheckRead(self, timestamp)
                freezeCheckRead()
        else:
            # freeze frame not supported by this HAL implementation. done
            logging.info("OBD2_FREEZE_FRAME and _INFO not supported.")

    def testReadInvalidObd2FreezeFrame(self):
        """Test that trying to read freeze frame at invalid timestamps
            behaves correctly (i.e. returns an error code)."""
        class FreezeFrameCheckRead(self.CheckRead):
            def __init__(self, test, timestamp):
                self.test = test
                self.propertyId = self.test.vtypes.VehicleProperty.OBD2_FREEZE_FRAME
                self.timestamp = timestamp
                self.areaId = 0

            def prepareRequest(self, propValue):
                propValue['value']['int64Values'] = [self.timestamp]
                return propValue

            def validateGet(self, status, value):
                asserts.assertEqual(
                    self.test.vtypes.StatusCode.INVALID_ARG, status)

        supportInfo = self.getDiagnosticSupportInfo()
        invalidTimestamps = [0,482005800]
        if supportInfo[self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME]:
            for timestamp in invalidTimestamps:
                freezeCheckRead = FreezeFrameCheckRead(self, timestamp)
                freezeCheckRead()
        else:
            # freeze frame not supported by this HAL implementation. done
            logging.info("OBD2_FREEZE_FRAME not supported.")

    def testClearValidObd2FreezeFrame(self):
        """Test that deleting a diagnostic freeze frame works.
        Given the timing behavor of OBD2_FREEZE_FRAME, the only sensible
        definition of works here is that, after deleting a frame, trying to read
        at its timestamp, will not be successful."""
        class FreezeFrameClearCheckWrite(self.CheckWrite):
            def __init__(self, test, timestamp):
                self.test = test
                self.propertyId = self.test.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_CLEAR
                self.timestamp = timestamp
                self.areaId = 0

            def prepareRequest(self, propValue):
                propValue['value']['int64Values'] = [self.timestamp]
                return propValue

            def validateSet(self, status):
                asserts.assertTrue(status in [
                    self.test.vtypes.StatusCode.OK,
                    self.test.vtypes.StatusCode.INVALID_ARG], "error")

        class FreezeFrameCheckRead(self.CheckRead):
            def __init__(self, test, timestamp):
                self.test = test
                self.propertyId = \
                    self.test.vtypes.VehicleProperty.OBD2_FREEZE_FRAME
                self.timestamp = timestamp
                self.areaId = 0

            def prepareRequest(self, propValue):
                propValue['value']['int64Values'] = [self.timestamp]
                return propValue

            def validateGet(self, status, value):
                asserts.assertEqual(
                    self.test.vtypes.StatusCode.INVALID_ARG, status)

        supportInfo = self.getDiagnosticSupportInfo()
        if supportInfo[self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_INFO] \
            and supportInfo[self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME] \
            and supportInfo[self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_CLEAR]:
            infoCheckRead = self.CheckRead(self,
                self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_INFO)
            frameInfos = infoCheckRead()
            timestamps = frameInfos["value"]["int64Values"]
            for timestamp in timestamps:
                checkWrite = FreezeFrameClearCheckWrite(self, timestamp)
                checkWrite()
                checkRead = FreezeFrameCheckRead(self, timestamp)
                checkRead()
        else:
            # freeze frame not supported by this HAL implementation. done
            logging.info("OBD2_FREEZE_FRAME, _CLEAR and _INFO not supported.")

    def testClearInvalidObd2FreezeFrame(self):
        """Test that deleting an invalid freeze frame behaves correctly."""
        class FreezeFrameClearCheckWrite(self.CheckWrite):
            def __init__(self, test, timestamp):
                self.test = test
                self.propertyId = \
                    self.test.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_CLEAR
                self.timestamp = timestamp
                self.areaId = 0

            def prepareRequest(self, propValue):
                propValue['value']['int64Values'] = [self.timestamp]
                return propValue

            def validateSet(self, status):
                asserts.assertEqual(self.test.vtypes.StatusCode.INVALID_ARG,
                    status)

        supportInfo = self.getDiagnosticSupportInfo()
        if supportInfo[self.vtypes.VehicleProperty.OBD2_FREEZE_FRAME_CLEAR]:
            invalidTimestamps = [0,482005800]
            for timestamp in invalidTimestamps:
                checkWrite = FreezeFrameClearCheckWrite(self, timestamp)
                checkWrite()
        else:
            # freeze frame not supported by this HAL implementation. done
            logging.info("OBD2_FREEZE_FRAME_CLEAR not supported.")

if __name__ == "__main__":
    test_runner.main()
