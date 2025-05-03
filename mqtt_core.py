# Copyright (c) 2025 Belal. All rights reserved.
#
# This source code is the intellectual property of Belal.
# Unauthorized use, reproduction, modification, or distribution of this code,
# in whole or in part, is strictly prohibited.
#
# This code is NOT open-source and may not be copied, shared, or reused
# in any form without explicit written permission from the author.

""" ----------- IMPORTS ----------- """

# Python standard libraries
from time import sleep, time
from enum import Enum
from typing import List
from logging import getLogger

# Downloaded 3rd party libraries
import paho.mqtt.client
from paho.mqtt.client import Client as mqtt_client
from paho.mqtt.client import MQTTMessage, MQTTMessageInfo

# Developed test environment libraries
from environment_core import TestResult, getTimeRelative


""" ----------- HELPER ENUM CLASSES ----------- """


class RequestStatus(Enum):
    """An enumerator class that contains the possible states for an MQTT \
    request.
    """

    # NotProcessed: No response was received yet. This is the default value.
    NotProcessed = 0
    # A valid response was received.
    Accepted = 1
    # An invalid response was received (e.g. broker refused or denied the request).
    Refused = 2


class ConnReturnCode(Enum):
    """An enumerator class that contains the possible relevant MQTT broker \
    responses to a connection request.
    """

    ConnectionAccepted = 0
    ConnectionRefusedNotAuthorized = 5


class MonitorResult(Enum):
    """An enumerator class that contains the values for all possible results \
    after the execution of a test monitor.
    """

    Passed = 0
    NoMessageReceived = 1
    IncorrectMessageReceived = 2
    NotTested = 3


""" ----------- HELPER CLASSES ----------- """


class MQTTMessage:
    """A class for a generic MQTT message."""

    def __init__(self, payload: str, topic: str, timestamp: float):
        """
        :param payload {str}: The message payload.
        :param topic {str}: The message topic.
        :param timestamp {float}: The timestamp of the message.
        """

        self.payload: str = payload
        self.topic: str = topic
        self.timestamp: float = timestamp


""" ----------- MAIN HANDLER CLASS ----------- """


class MQTTHandler:
    """A class that handles the creation of an MQTT Client and establishing \
    a connection with a broker. It provides the basic MQTT functionalities, \
    such as publishing messages, subscribing to topics, and monitoring \
    topics for certain messages.

    To use this class, you need to create an instance, then call \
    'configureClient' to configure the MQTT Client with the required \
    parameters.

    To connect to the desired broker, call 'connect' after calling \
    'configureClient'.

    After successfully connecting to a broker, you can call 'subscribe' or \
    'publish' to subscribe to topics or to publish messages on the desired \
    topics.

    All MQTT traffic is handled by a separate thread, which is started when \
    you call the 'connect' method. The methods that the new thread interact \
    with are the callback methods '__onConnect', '__onSubscribe', and \
    '__onMessage'. You can extend these methods in any subclass to implement \
    other functionalities within the callback methods.

    Call 'testWaitForMessage' to wait for an expected message.

    Each methods in this class return an integer value. Use enumerator class \
    'TestResult' in 'environment_core.py' to decode the returned values and \
    process them accordingly.
    """

    def __init__(self):
        """Returns an MQTTHandler instance"""

        # This list of variables should contain all the self.
        # Logging variables
        self.logger = getLogger("MQTT Handler Logger")
        self.startTime: float = 0.0
        self.errorReason: str = ""
        # MQTT client
        self.mqttc: mqtt_client = None
        # An enumerator flag indicating the status of the last request. A single
        # flag is sufficient because requests are handled serially, i.e. the
        # main thread is blocked until a response is received or timeout occurs.
        self.requestStatus: RequestStatus = RequestStatus.NotProcessed
        # A list of received messages from all subscribed topics.
        self.receivedMessages: List[MQTTMessage] = []

    """ ----------- PUBLIC METHODS ----------- """

    def setStartTime(self, startTime: float) -> None:
        """Synchronizes all timings within the class with the test case start \
        time. Useful to log all timings relative to test case start.

        :param startTime {float}: The absolute time of test case start in \
        seconds, usually obtained using time.time().
        """

        self.startTime = round(startTime, 2)

    def configureClient(
        self,
        clientId: str = "",
        username: str = "",
        password: str = "",
        isTLSEnabled: bool = False,
    ) -> TestResult:
        """Creates and configures an MQTT Client using the provided parameters. \
        This method must be called before calling 'connect'.

        This also binds the thread that will run the client to the following \
        callback methods: '__onConnect', '__onSubscribe', and '__onMessage'.

        The used protocol version is MQTT v3.1.1, but this can be adjusted by \
        manually adjusting this method. Note that when using MQTT v5, the \
        callback methods will need to be updated to match the message formats.

        To connect the client to the desired broker, call 'connect' after \
        calling this method.

        This method will not raise any exceptions.

        :param clientId {str}: The desired client ID. Leave empty to obtain a \
        random ID from the broker. Default is empty.
        :param username {str}: The desired username. Leave empty if a username \
        is not necessary. Default is empty.
        :param password {str}: The desired password. Leave empty if a password \
        is not necessary. Default is empty.
        :param isTLSEnabled {bool}: Whether to enable TLS encryption or not. \
        Default is False.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """
        # This method is fully surrounded by try-catch block.
        # Will not raise exceptions.
        try:
            # Create and configure the MQTT client
            self.mqttc = mqtt_client(
                client_id=clientId, protocol=paho.mqtt.client.MQTTv311
            )
            # if isTLSEnabled == True:
            #     self.mqttc.tls_set(tls_version=paho.mqtt.client.ssl.PROTOCOL_TLS)
            self.mqttc.username_pw_set(username=username, password=password)
            # Bind the thread that will process the MQTT traffic to the callback methods.
            self.mqttc.on_connect = self.__onConnect
            self.mqttc.on_subscribe = self.__onSubscribe
            self.mqttc.on_message = self.__onMessage
            # No exceptions were raised. Report result as Passed.
            return TestResult.Passed
        # An exception occured during the client configuration.
        # Report result as Failed.
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An error occurred while configuring the mqtt client,
            caused by the following exception {e}"""
            return TestResult.EnvironmentIssue

    def connect(
        self, brokerAddress: str, port: int = 1883, timeout: float = 10
    ) -> TestResult:
        """Attempts to connect the configured client to the desired MQTT broker.

        The client must be configured first by calling 'configureClient' before \
        calling this method.

        This function blocks the calling thread until the broker provides a \
        response or timeout occurs. It also starts a new thread that will loop \
        forever to process MQTT traffic.

        In case of any event, the new thread will use the callback methods \
        '__onConnect', '__onSubscribe', and '__onMessage'.

        This method will not raise any exceptions.

        :param brokerAddress {str}: The broker address to connect to. \
        :param port {int}: The broker port to connect to. Default port is 1883. \
        :param timeout {float}: The timeout in seconds to wait for a response \
        from the broker. Default is 10 seconds.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """

        # This method is fully surrounded by try-catch block.
        # Will not raise exceptions.
        try:
            # Report result as Failed if a client was not configured using
            # configureClient before calling this method
            if self.mqttc == None:
                self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An error occurred
                when attempting to connect to the broker because no client was found. A client
                needs to be configured first by calling configureClient before attempting to
                connect to a broker!"""
                return TestResult.EnvironmentIssue
            # Client was correctly configured using configureClient.
            # Reset the request status flag before sending a connection request.
            self.requestStatus = RequestStatus.NotProcessed
            # Attempt to connect to the provided broker
            self.mqttc.connect(host=brokerAddress, port=port)
            # Starts a thread that loops forever.
            self.mqttc.loop_start()
            return self.__waitForConnect(timeout)
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An error occurred
            when attempting to connect to the broker, caused by the following exception:
            {e}"""
            return TestResult.EnvironmentIssue

    def subscribe(self, topic: str, qos: int = 0, timeout: float = 10) -> TestResult:
        """Attempts to subscribe to the desired topic with the desired quality \
        of service.

        The client must be connected to the broker first using 'connect'.

        This function blocks the calling thread until the broker provides a \
        response or timeout occurs.

        This method will not raise any exceptions.

        :param topic {str}: The topic to subscribe to.
        :param qos {int}: The desired quality of service. Default is 0.
        :param timeout {float}: The timeout in seconds to wait for a response \
        from the broker. Default is 10 seconds.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """

        # This method is fully surrounded by try-catch block.
        # Will not raise exceptions.
        try:
            # If the last request was not accepted (connection request), report
            # result as Failed.
            if self.requestStatus != RequestStatus.Accepted:
                self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An error occurred
                when attempting to subscribe to topic because the client is not connected to a
                broker. Please call 'connect' before attempting to subscribe to a topic!"""
                return TestResult.EnvironmentIssue
            # Reset the request status flag before sending a subscribe request.
            self.requestStatus = RequestStatus.NotProcessed
            # Attempt to subscribe to the desired topic then wait for a response.
            self.mqttc.subscribe(topic=topic, qos=qos)
            return self.__waitForSubscribe(timeout=timeout)
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An error occurred
            when attempting to subscribe to topic, caused by the following exception: {e}"""
            return TestResult.EnvironmentIssue

    def publish(
        self, payload: str, topic: str, qos: int = 0, timeout: float = 10
    ) -> TestResult:
        """Publish the provided message to the desired topic.

        The client must be connected to the broker first using 'connect'.

        This method blocks the calling thread until the message is published \
        or timeout occurs.

        This method will not raise any exceptions.

        :param payload {str}: The payload to publish.
        :param topic {str}: The topic to subscribe to.
        :param qos {int}: The desired quality of service. Default is 0.
        :param timeout {float}: The timeout in seconds to wait for the message \
        to be published. Default is 10 seconds.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """

        # This method is fully surrounded by try-catch block.
        # Will not raise exceptions.
        try:
            # Attempt to publish message.
            messageInfo: MQTTMessageInfo = self.mqttc.publish(
                topic=topic, payload=payload, qos=qos
            )
            # Wait until message is published or until timeout occurred.
            messageInfo.wait_for_publish(timeout=timeout)
            # If message was published, report result as Passed.
            if messageInfo.is_published() == True:
                self.logger.info(
                    f"""Message was successfully published. Payload: {payload}. Topic: {topic}.
                    Timestamp: {getTimeRelative(self.startTime)}"""
                )
                return TestResult.Passed
            # If message was not published, report result as Failed.
            else:
                self.errorReason = f"""{
                    TestResult.EnvironmentIssue.name}: Failed to publish message, timeout was
                    reached!"""
                return TestResult.EnvironmentIssue
        # If an exception was raised because the publish queue is full, report
        # result as Failed.
        except ValueError as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: Failed to publish
            message because outgoing publish queue is full! This was indicated from the
            following exception: {e}"""
            return TestResult.EnvironmentIssue
        # If any other exception is raised, report result as Failed.
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: Failed to publish
            message because of the following exception: {e}"""
            return TestResult.EnvironmentIssue

    def testWaitForMessage(
        self,
        topic: str = "",
        payload: str = "",
        timestamp: float = 0.0,
        timeout: float = 10,
    ) -> TestResult:
        """Checks whether the given message was received on the given topic \
        after the provided timestamp or not.

        This method blocks the calling thread to keeps checking the received \
        messages until the message is received or until timeout occurs.

        Note that this method will return on the last instance received of the \
        provided message.

        If desired, you can clear the list of already received messages before \
        calling this method by calling 'clearReceivedMessages' first.

        This method will not raise any exceptions.

        :param topic {str}: The topic of the message. Default is empty. If no \
        topic was provided, the method will check that the message was received \
        on any topic.
        :param payload {str}: The payload to check for. Default is empty. If no \
        payload was provided, the method will return on any payload received on \
        the desired topic.
        :param timestamp {float}: A timestamp to check that the message was \
        received after. Default is 0.
        :param timeout {float}: The max timeout to wait for the message to be \
        received. Default is 10.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """

        # This method is fully surrounded by try-catch block.
        # Will not raise exceptions.
        try:
            startTime = time()
            self.logger.info(
                f"Started waiting for message. Payload: {payload}. Topic: {topic}"
            )
            # No topic was provided.
            if (topic is None) or (len(topic) == 0):
                # No topic and no payload was provided.
                if (payload is None) or (len(payload) == 0):
                    # Keep checking until timeout.
                    # A do-while loop
                    while True:
                        for message in reversed(self.receivedMessages):
                            # If a match was found, report result as Passed.
                            if message.timestamp >= timestamp:
                                self.logger.info(
                                    f"""The desired message was received. Payload: {message.payload}. Topic:
                                    {message.topic}. Timestamp: {message.timestamp}"""
                                )
                                return TestResult.Passed
                            # Skip checking older messages to save time.
                            else:
                                break
                        if (time() - startTime) > timeout:
                            break
                    # If no match was found, report result as Failed.
                    if len(self.receivedMessages) == 0:
                        self.errorReason = f"""{TestResult.Failed.name}: Expected payload '{payload}' was
                        not received on topic '{topic}'! No messages were found in the receive buffer."""
                        return TestResult.Failed
                    else:
                        self.errorReason = f"""{TestResult.Failed.name}: Expected payload '{payload}' was
                        not received on topic '{topic}'! Other messages were found in the receive buffer."""
                        self.logger.info(
                            f"""Expected payload '{payload}' was not received on topic '{topic}' after
                            timestamp '{timestamp}'."""
                        )
                        self.printAllReceivedMessages()
                        return TestResult.Failed
                # A payload was provided, but no topic was provided.
                else:
                    # Keep checking until timeout.
                    # A do-while loop
                    while True:
                        for message in reversed(self.receivedMessages):
                            if message.timestamp >= timestamp:
                                # If a match was found, report result as Passed.
                                if message.payload == payload:
                                    self.logger.info(
                                        f"""The desired message was received. Payload: {message.payload}. Topic:
                                        {message.topic}. Timestamp: {message.timestamp}"""
                                    )
                                    return TestResult.Passed
                            # Skip checking older messages to save time.
                            else:
                                break
                        if (time() - startTime) > timeout:
                            break
                    # If no match was found, report result as Failed.
                    if len(self.receivedMessages) == 0:
                        self.errorReason = f"""{TestResult.Failed.name}: Expected payload '{payload}' was
                        not received on topic '{topic}'! No messages were found in the receive buffer."""
                        return TestResult.Failed
                    else:
                        self.errorReason = f"""{TestResult.Failed.name}: Expected payload '{payload}' was
                        not received on topic '{topic}'! Other messages were found in the receive buffer."""
                        self.logger.info(
                            f"""Expected payload '{payload}' was not received on topic '{topic}' after
                            timestamp '{timestamp}'."""
                        )
                        self.printAllReceivedMessages()
                        return TestResult.Failed
            # A topic was provided.
            else:
                # A topic was provided, but no payload was provided.
                if (payload is None) or (len(payload) == 0):
                    # A do-while loop
                    # Keep checking until timeout.
                    while True:
                        for message in reversed(self.receivedMessages):
                            if message.timestamp >= timestamp:
                                # If a match was found, report result as Passed.
                                if message.topic == topic:
                                    self.logger.info(
                                        f"""The desired message was received. Payload: {message.payload}. Topic:
                                        {message.topic}. Timestamp: {message.timestamp}"""
                                    )
                                    return TestResult.Passed
                            # Skip checking older messages to save time.
                            else:
                                break
                        if (time() - startTime) > timeout:
                            break
                    # If no match was found, report result as Failed.
                    if len(self.receivedMessages) == 0:
                        self.errorReason = f"""{TestResult.Failed.name}: Expected payload '{payload}' was
                        not received on topic '{topic}'! No messages were found in the receive buffer."""
                        return TestResult.Failed
                    else:
                        self.errorReason = f"""{TestResult.Failed.name}: Expected payload '{payload}' was
                        not received on topic '{topic}'! Other messages were found in the receive buffer."""
                        self.logger.info(
                            f"""Expected payload '{payload}' was not received on topic '{topic}' after
                            timestamp '{timestamp}'."""
                        )
                        self.printAllReceivedMessages()
                        return TestResult.Failed
                # A topic and a payload were provided.
                else:
                    # Keep checking until timeout.
                    # A do-while loop
                    while True:
                        for message in reversed(self.receivedMessages):
                            if message.timestamp >= timestamp:
                                if message.topic == topic:
                                    # If a match was found, report result as Passed.
                                    if message.payload == payload:
                                        self.logger.info(
                                            f"""The desired message was received. Payload: {message.payload}. Topic:
                                        {message.topic}. Timestamp: {message.timestamp}"""
                                        )
                                        return TestResult.Passed
                            # Skip checking older messages to save time.
                            else:
                                break
                        if (time() - startTime) > timeout:
                            break
                    # If no match was found, report result as Failed.
                    if len(self.receivedMessages) == 0:
                        self.errorReason = f"""{TestResult.Failed.name}: Expected payload '{payload}' was
                        not received on topic '{topic}'! No messages were found in the receive buffer."""
                        return TestResult.Failed
                    else:
                        self.errorReason = f"""{TestResult.Failed.name}: Expected payload '{payload}' was
                        not received on topic '{topic}'! Other messages were found in the receive buffer."""
                        self.logger.info(
                            f"""Expected payload '{payload}' was not received on topic '{topic}' after
                            timestamp '{timestamp}'."""
                        )
                        self.printAllReceivedMessages()
                        return TestResult.Failed
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An error was
            encountered when waiting for an MQTT message, caused by the following
            exception: {e}"""
            return TestResult.EnvironmentIssue

    def printAllReceivedMessages(self) -> None:
        """Logs all the messages in the receive buffer as info."""

        if len(self.receivedMessages) == 0:
            self.logger.info("No messages were received!")
        else:
            self.logger.info("List of messages in the receive buffer:")
            for message in self.receivedMessages:
                self.logger.info(
                    f"""Payload: {message.payload}. Topic: {message.topic}. Timestamp:
                    {message.timestamp}"""
                )

    def clearReceivedMessages(self) -> None:
        """Clears all received messages from the receive buffer."""

        self.receivedMessages = []
        self.logger.info(
            f"""Cleared all messages received before timestamp
            {getTimeRelative(self.startTime)}"""
        )

    """ ----------- PRIVATE METHODS ----------- """

    def __waitForConnect(self, timeout: float) -> TestResult:
        """Blocks the calling thread until the client successfully connects to \
        the broker or until timeout occurs.

        This method uses the 'requestStatus' flag, which is updated by the \
        '__onConnect' callback method when a response is received to the \
        connection request. The flag is updated by the callback method according \
        to the received response code.

        This method will not raise any exceptions.

        :param timeout {float}: The timeout in seconds to wait for a response \
        from the broker.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """

        # This method is fully surrounded by try-catch block.
        # Will not raise exceptions.
        try:
            startTime: float = time()
            # A do-while loop
            while True:
                # If connection succeeds, report result as Passed.
                if self.requestStatus == RequestStatus.Accepted:
                    self.logger.info("Connection to broker succeeded!")
                    return TestResult.Passed
                # If connection was refused by the broker, report result as Failed.
                elif self.requestStatus == RequestStatus.Refused:
                    self.errorReason = f"""{
                        TestResult.EnvironmentIssue.name}: An error was encountered when attempting to
                        connect to the broker. The broker refused the connection!"""
                    return TestResult.EnvironmentIssue
                # If no response was received from the broker, sleep 0.5 seconds before
                # rechecking again for a response.
                elif self.requestStatus == RequestStatus.NotProcessed:
                    sleep(0.5)
                if (time() - startTime) > timeout:
                    break
            # Report result as Failed if a connection timeout occured.
            self.errorReason = f"""{
                TestResult.EnvironmentIssue.name}: Timeout was reached when attempting to
                connect to broker!"""
            return TestResult.EnvironmentIssue
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An unexpected error
            was encountered when waiting for the broker to respond to the connection
            request, caused by the following exception: {e}"""
            return TestResult.EnvironmentIssue

    def __waitForSubscribe(self, timeout: float) -> int:
        """Blocks the calling thread until the client provides a response to the \
        subscribe request or until timeout occurs.

        This method uses the 'requestStatus' flag, which is updated by the \
        '__onSubscribe' callback method when a response is received to the \
        connection request. The flag is updated by the callback method according \
        to the received response code.

        This method will not raise any exceptions.

        :param timeout {float}: The timeout in seconds to wait for a response \
        from the broker.

        :returns {TestResult}: The result of the method call according to the \
        'TestResult' enumerator class.
        """

        # This method is fully surrounded by try-catch block.
        # Will not raise exceptions.
        try:
            startTime: float = time()
            # A do-while loop
            while True:
                # If subscription succeeds, report result as Passed.
                if self.requestStatus == RequestStatus.Accepted:
                    return TestResult.Passed
                # If subscription was refused, report result as Failed.
                elif self.requestStatus == RequestStatus.Refused:
                    self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An error was
                    encountered when attempting to subscribe to a topic. The broker refused the
                    subscription request!"""
                    return TestResult.EnvironmentIssue
                # If no response was received from the broker, sleep 0.5 seconds before
                # rechecking again for a response.
                elif self.requestStatus == RequestStatus.NotProcessed:
                    sleep(0.5)
                if (time() - startTime) > timeout:
                    break
            # If timeout occurs, disconnect from the broker and report result as
            # Failed.
            self.mqttc.loop_stop()
            self.mqttc.disconnect()
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: Timeout was reached
            when attempting to subscribe to topic!"""
            return TestResult.EnvironmentIssue
        except Exception as e:
            self.errorReason = f"""{TestResult.EnvironmentIssue.name}: An unexpected error
            was encountered when waiting for the broker to respond to the subscribe
            request, caused by the following exception: {e}"""
            return TestResult.EnvironmentIssue

    """ ----------- PRIVATE CALLBACK METHODS ----------- """

    def __onConnect(self, client, userdata, flags, rc) -> None:
        """Callback for when a response to a connection request is received.

        This method sets updates the 'requestStatus' flag based on the response \
        code received from the broker to the connection request.

        This function can be extended in a subclass to add additional \
        functionality.
        """

        if rc == ConnReturnCode.ConnectionAccepted.value:
            self.requestStatus = RequestStatus.Accepted
        else:
            self.requestStatus = RequestStatus.Refused

    def __onSubscribe(self, client, userdata, mid, granted_qos: List[int]) -> None:
        """Callback for when a response to a subscribe request is received.

        This method sets updates the 'requestStatus' flag based on the response \
        received from the broker to the subscribe request.

        This function can be extended in a subclass to add additional \
        functionality.
        """

        if (granted_qos[0] != 0) and (granted_qos[0] != 1) and (granted_qos[0] != 2):
            self.requestStatus = RequestStatus.Refused
        else:
            self.requestStatus = RequestStatus.Accepted
            self.logger.info(
                f"Successfully subscribed to topic with QoS = {granted_qos[0]}"
            )

    def __onMessage(self, client, userdata, message: MQTTMessage) -> None:
        """Callback for when a message is received.

        The received message is appended to the receive buffer 'receivedMessages'.

        This function can be extended in a subclass to add additional \
        functionality.
        """

        receivedMessage = MQTTMessage(
            payload=message.payload.decode(),
            topic=message.topic,
            timestamp=getTimeRelative(self.startTime),
        )
        self.receivedMessages.append(receivedMessage)
        self.logger.info(
            f"""Message received: {receivedMessage.payload}. Topic: {receivedMessage.topic}.
            Timestamp: {receivedMessage.timestamp}"""
        )
