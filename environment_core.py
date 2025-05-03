# Copyright (c) 2025 Ahmed Belal. All rights reserved.
#
# This source code is the intellectual property of Ahmed Belal.
# Permission is granted to use and execute this code privately for evaluation or personal testing purposes only.
# Redistribution, modification, or commercial use is strictly prohibited without explicit written permission.
#
# This code is NOT open-source and may not be shared or reused in any form without authorization.

from enum import Enum
from time import time


class TestResult(Enum):
    """
    An enumerator class that contains the possible result values for each test step.
    """

    Passed = 0
    Failed = 1
    EnvironmentIssue = 2


def getTimeRelative(startTime: float = 0.0) -> float:
    """
    Returns the current time relative to the test case start.

    @param startTime: The absolute time in seconds of test case start.

    @returns float: The current time in seconds relative to test case start.
    """

    return abs(round(time() - startTime, 2))
