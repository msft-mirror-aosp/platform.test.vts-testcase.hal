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

from vts.proto import ComponentSpecificationMessage_pb2 as CompSpecMsg
from vts.runners.host import asserts
from vts.runners.host import base_test_with_webdb
from vts.runners.host import const
from vts.runners.host import keys
from vts.runners.host import test_runner
from vts.utils.python.controllers import android_device
from vts.utils.python.coverage import coverage_utils
from vts.utils.python.profiling import profiling_utils


class TvCecHidlTest(base_test_with_webdb.BaseTestWithWebDbClass):
    """Host testcase class for the TV HDMI_CEC HIDL HAL."""

    def setUpClass(self):
        """Creates a mirror and init tv hdmi cec hal service."""
        self.dut = self.registerController(android_device)[0]

        self.dut.shell.InvokeTerminal("one")
        self.dut.shell.one.Execute("setenforce 0")  # SELinux permissive mode

        self.dut.shell.one.Execute(
            "setprop vts.hal.vts.hidl.get_stub true")

        if getattr(self, keys.ConfigKeys.IKEY_ENABLE_COVERAGE, False):
            coverage_utils.InitializeDeviceCoverage(self.dut)

        if self.enable_profiling:
            profiling_utils.EnableVTSProfiling(self.dut.shell.one)

        self.dut.hal.InitHidlHal(
            target_type="tv_cec",
            target_basepaths=self.dut.libPaths,
            target_version=1.0,
            target_package="android.hardware.tv.cec",
            target_component_name="IHdmiCec",
            hw_binder_service_name="cec-hal-1-0",
            bits=64 if self.dut.is64Bit else 32)

    def setUpTest(self):
        """Setup function that will be called every time before executing each
        test case in the test class."""
        if self.enable_profiling:
            profiling_utils.EnableVTSProfiling(self.dut.shell.one)

    def tearDownTest(self):
        """TearDown function that will be called every time after executing each
        test case in the test class."""
        if self.enable_profiling:
            profiling_trace_path = getattr(
                self, self.VTS_PROFILING_TRACING_PATH, "")
            self.ProcessTraceDataForTestCase(self.dut, profiling_trace_path)
            profiling_utils.DisableVTSProfiling(self.dut.shell.one)

    def tearDownClass(self):
        """To be executed when all test cases are finished."""
        if getattr(self, keys.ConfigKeys.IKEY_ENABLE_COVERAGE, False):
            self.SetCoverageData(coverage_utils.GetGcdaDict(self.dut))

        if self.enable_profiling:
            self.ProcessAndUploadTraceData()

    def testGetCecVersion1(self):
        """A simple test case which queries the cec version."""
        logging.info('DIR HAL %s', dir(self.dut.hal))
        version = self.dut.hal.tv_cec.getCecVersion()
        logging.info('Cec version: %s', version)

    def testSendRandomMessage(self):
        """A test case which sends a random message."""
        self.vtypes = self.dut.hal.tv_cec.GetHidlTypeInterface("types")
        logging.info("tv_cec types: %s", self.vtypes)

        cec_message = {
            "initiator": self.vtypes.TV,
            "destination": self.vtypes.PLAYBACK_1,
            "body": [1, 2, 3]
        }
        message = self.vtypes.Py2Pb("CecMessage", cec_message)
        logging.info("message: %s", message)
        result = self.dut.hal.tv_cec.sendMessage(message)
        logging.info('sendMessage result: %s', result)

if __name__ == "__main__":
    test_runner.main()
