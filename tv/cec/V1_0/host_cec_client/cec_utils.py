#!/usr/bin/env python
# Copyright 2020 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility file for VTS CEC testing..
Common functions for performing vts cec testing like starting the client, sending message to
cec-console, reading the messages from the cec-console.
"""

import fcntl
import logging
import os
import re
import subprocess
import time

TIMEOUT_SEC = 20
SECONDS_TO_READY = 1
CLIENT_CONSOLE_READY = "waiting for input"
QUIT_CLIENT = "q"


class CecUtils(object):
    mCecClientInitialised = False
    process = None

    def __init__(self):
        '''Start the client as Recorder connected to port 2, so it takes the
        physical address 2.0.0.0
        '''
        list = []
        list.append("cec-client")
        list.append("-p")
        list.append("2")
        list.append("-t")
        list.append("r")
        self.process = subprocess.Popen(list,
                                        shell=False,
                                        stdout=subprocess.PIPE,
                                        stdin=subprocess.PIPE)
        ''' Wait for the client to become ready '''
        if not self.checkConsoleOutput(CLIENT_CONSOLE_READY, 10):
            self.mCecClientInitialised = False
            return
        stdoutFlags = fcntl.fcntl(self.process.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self.process.stdout, fcntl.F_SETFL,
                    stdoutFlags | os.O_NONBLOCK)
        self.mCecClientInitialised = True

    def sendConsoleMessage(self, message):
        '''Sends a message to the output console of the cec-client

        Args:
            message: message sent to the console.
        '''
        if self.mCecClientInitialised is False:
            return None
        self.process.stdin.write(message + '\n')
        self.process.stdin.flush()

    def sendCecMessage(self, source, destination, message):
        '''Sends a CEC message from source device to a destination device through the output
        console of the cec-communication.

        Args:
            source: logical address of the source.
            destination: logical address of the destination.
            message: opcode of the CEC message.
        '''
        if self.mCecClientInitialised is False:
            return None
        self.process.stdin.write("tx " + source + destination + ":" + message + '\n')
        self.process.stdin.flush()

    def getNibbles(self, message):
        '''Extract raw bytes from a CEC message

        Args:
            message: The CEC message.

        Returns:
            The raw bytes as a string without any separators.
        '''
        nibbles = ''
        pattern = re.compile(r"(.*[>>|<<].*?)" + "([0-9a-f]{2}:)" + "([0-9a-z]{2})(.*)")
        matches = pattern.search(message)
        if matches is not None:
            groups = matches.groups()
            nibbles = ''.join(groups[1:]).replace(':', '')
        return nibbles

    def getParamsFromMessage(self, message, start, end):
        '''From the params of a CEC message, gets the nibbles from position start to position end.
        The start and end are relative to the beginning of the params. For example, in the following
        message - 4F:82:10:00:04, getParamsFromMessage(message, 0, 4) will return 0x1000 and
        getParamsFromMessage(message, 4, 6) will return 0x04.

        Args:
            message: CEC message whose params has to be extracted.
            start: Start index of the params required.
            end: End index of the params required.

        Returns:
            Returns the params of the CEC message.
        '''
        if message is not None:
            return int(self.getNibbles(message)[4+start:4+end], 16)
        else:
            return None

     def checkConsoleOutput(self, expectedMessage, waitingTime = SECONDS_TO_READY):
        '''Check for an expectedMessage on the input console of cec-client within the waitingTime

        Args:
            expectedMessage: message to be search for in the console.
            waitingTime: waiting time in seconds for the message to be captured on console.
                         Default is 1s

        Returns:
            boolean: expectedMessage found or not found.
        '''
        startTime = int(round(time.time()))
        endTime = startTime
        while (endTime - startTime <= waitingTime):
            if (self.process.poll() is None):
                try:
                    line = self.process.stdout.readline()
                    if expectedMessage in line:
                        return True
                except IOError:
                    '''Nothing to read from cec-client console, wait for a message/timeout.'''
                    pass
            endTime = int(round(time.time()))
        return False

    def killCecClient(self):
        '''Kills the cec-client process.'''
        if self.mCecClientInitialised is False:
            return
        self.sendConsoleMessage(QUIT_CLIENT)
        self.mCecClientInitialised = False
        if self.process.poll() is None:
            '''Use a process.kill() if the cec-client process is not dead in spite of the quit
            above
            '''
            self.process.kill()
        return

    def checkExpectedOutput(self, src, dst, operand, waitingTime = TIMEOUT_SEC):
        '''Looks for the CEC message with "operand" sent from logical address "src" to logical
        address "dst" on the cec-client communication channel and returns the first line that
        contains that message. If the CEC message is not found within 20s, it will return None.

        Args:
            src: logical address of the source.
            dst: logical address of the destination.
            operand: opcode of the cec-message.
            waitingTime: waiting time in seconds for the message to be captured on console.
                         Default is 20s.

        Returns:
            line: The line of the cec-console which has the required pattern. If pattern does not
                  found it will return None.
        '''
        if self.mCecClientInitialised is False:
            return None
        startTime = int(round(time.time()))
        endTime = startTime
        if operand is None:
            pattern = re.compile(r"(.*>>)(.*?)" + "(" + src + dst + ")")
        else:
            pattern = re.compile(r"(.*>>)(.*?)" + "(" + src + dst + "):" + "(" +
                                 operand + ")(.*)")
        while (endTime - startTime <= waitingTime):
            if (self.process.poll() is None):
                try:
                    line = self.process.stdout.readline()
                    if pattern.search(line):
                        return line
                except IOError:
                    '''Nothing to read from cec-client console, wait for a message/timeout.'''
                    pass
            endTime = int(round(time.time()))
        return None
