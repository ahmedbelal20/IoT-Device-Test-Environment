# Copyright (c) 2025 Belal. All rights reserved.
#
# This source code is the intellectual property of Belal.
# Unauthorized use, reproduction, modification, or distribution of this code,
# in whole or in part, is strictly prohibited.
#
# This code is NOT open-source and may not be copied, shared, or reused
# in any form without explicit written permission from the author.

from pymodbus.server import StartSerialServer, ServerStop
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore.store import ModbusSparseDataBlock, ModbusSequentialDataBlock
from time import time, sleep
import xml.etree.ElementTree as ET
from environment_core import *
from logging import getLogger
from threading import Thread
from modbus_adapter import Register


class FunctionCode(Enum):
    readHoldingRegister = 0x03
    writeSignleHoldingRegister = 0x06
    controlSetting = 0x08


class ModbusHandler:

    def __init__(self):
        """Returns a ModbusHandler instance"""

        self.server = None
        self.port: str = None
        self.baudRate: int = None
        self.slaveAddress: int = None
        self.dataBlock = None
        self.dataContext = None
        self.serverContext = None
        self.logger = getLogger("Modbus Handler Logger")
        self.errorReason: str = None

    def setStartTime(self, startTime: float) -> None:
        """Synchronizes all timings within the class with the test case start \
        time. Useful to log all timings relative to test case start.

        :param startTime {float}: The absolute time of test case start in \
        seconds, usually obtained using time.time().
        """

        self.startTime = round(startTime, 2)

    def configureModbus(self, path: str, config: str) -> TestResult:
        """Parses an xml file that is expected to contain the configuration parameters for
        modbus connection, then configures the modbus client with the parameters obtained
        from a parsed XML file.

        @param path: A string path to the XML file
        @param config: A string of the selected configuration tag in the XML file

        @returns TestResult: Execution result according to the TestResult enumerator class
        """

        try:
            result = self.__parseXML(path=path, selectedConfig=config)
            if result != TestResult.Passed:
                return result
            self.dataBlock = ModbusSequentialDataBlock(0x0000, [0] * 50000)
            self.dataContext = ModbusSlaveContext(
                di=None, co=None, hr=self.dataBlock, ir=None
            )
            self.serverContext = ModbusServerContext(
                slaves=self.dataContext, single=True
            )
            return TestResult.Passed
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An error occurred while configuring the modbus client,
            caused by the following exception {e}"""
            return TestResult.EnvironmentIssue

    def start(self) -> TestResult:
        try:
            serverThread = Thread(target=self.__runServer)
            serverThread.start()
            return TestResult.Passed
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: Failed to start the server thread because
            of the following exception: {e}"""
            return TestResult.EnvironmentIssue

    def __runServer(self):
        StartSerialServer(
            self.serverContext,
            port=self.port,
            baudrate=self.baudRate,
            stopbits=1,
            bytesize=8,
            broadcast_enable=True,
        )

    def terminate(self) -> None:
        ServerStop()

    def __parseXML(self, path: str, selectedConfig: str) -> TestResult:
        """
        Parses an xml file that is expected to contain the configuration parameters
        for the modbus communication

        @param path: A string path to the XML file
        @param selectedConfig: A string of the selected configuration tag in the XML file

        @returns TestResult: Execution result according to the TestResult enumerator class
        """

        tree: ET.ElementTree = ET.parse(source=path)
        root: ET.Element = tree.getroot()
        for configType in root:
            if configType.tag == "modbus-configs":
                for config in configType:
                    if config.tag == selectedConfig:
                        for parameter in config:
                            if parameter.tag == "port":
                                self.port = parameter.text
                            elif parameter.tag == "baud_rate":
                                self.baudRate = int(parameter.text)
                            elif parameter.tag == "slave_address":
                                self.slaveAddress = int(parameter.text)
                            else:
                                self.errorReason = f"""{TestResult.EnvironmentIssue.name}: Unknown modbus element 
                                tag was found when parsing the XML!"""
                                return TestResult.EnvironmentIssue
        return TestResult.Passed

    def setRegister(self, address: int, value: int) -> TestResult:
        """Updates the given register address to the desired value.

        :param address {int}: The register address.
        :param value {int}: The desired value.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """
        try:
            register = 3
            self.serverContext[0].setValues(register, address, [value])
            self.logger.info(
                f"Register '{address}' was updated to the value '{self.serverContext[0].getValues(register, address, 1)[0]}'"
            )
            return TestResult.Passed
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.value}: An error was
            encountered when trying to set a value in a register, caused by the following
            exception: {e}"""
            return TestResult.EnvironmentIssue

    def testWaitForRegister(
        self, address: int, value: int, timeout: float = 35
    ) -> TestResult:
        """Checks for the given value in the provided address until the value is \
        found or timeout occurs.

        This method blocks the calling thread to keeps checking the register \
        until the value is found or until timeout occurs.

        :param address {int}: The register address.
        :param value {int}: The expected value.
        :param timeout {float}: The max timeout to keep checking the register \
        for the desired value. Default is 10.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """
        try:
            startTime = time()
            self.logger.info(
                f"Waiting for register '{address}' to be equal to '{value}'"
            )
            register = 3
            # A do-while loop
            while True:
                if self.serverContext[0].getValues(register, address, 1)[0] == value:
                    self.logger.info(
                        f"The desired value '{value}' was found in register '{address}'."
                    )
                    return TestResult.Passed
                sleep(0.5)
                if (time() - startTime) > timeout:
                    break
            self.errorReason = f"""{TestResult.Failed.value}: Timeout occurred when waiting
            for the value '{value}' in register '{address}'. The final value was
            '{self.serverContext[0].getValues(register, address, 1)[0]}'"""
            return TestResult.Failed
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.value}: An error was
            encountered when checking for a value in a register, caused by the following
            exception: {e}"""
            return TestResult.EnvironmentIssue
