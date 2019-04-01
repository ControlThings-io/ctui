"""
Control Things User Interface, aka ctui.py

# Copyright (C) 2019  Justin Searle
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details at <http://www.gnu.org/licenses/>.
"""
import re
from typing import List, NewType


Hex = NewType('Hex', bytes)
Bin = NewType('Bin', bool)
# These Greedy types can only be used on the last argument of functions
GreedyStr = NewType('GreedyStr', str)
GreedyBytes = NewType('GreedyBytes', bytes)
GreedyHex = NewType('GreedyHex', bytes)
GreedyBin = NewType('GreedyBin', List[bool])
GreedyInt = NewType('GreedyInt', List[int])
GreedyFloat = NewType('GreedyFloat', List[float])

def is_greedy(argtype):
    return argtype in [GreedyStr, GreedyBytes, GreedyHex, GreedyBin, GreedyInt, GreedyFloat]

def to_type(value, kwarg):
    if kwarg.type == str:
        return value

    elif kwarg.type == int:
        assert (value.isdigit), f'{kwarg.name} must be an digit'
        return int(value)

    elif kwarg.type == float:
        assert (value.isdecimal), f'{kwarg.name} must be an decimal'
        return float(value)

    elif kwarg.type == GreedyStr:
        return value

    elif kwarg.type == GreedyBytes:
        return value

    elif kwarg.type == GreedyHex or kwarg.type == Hex:
        data = value.lower().replace("0x", "")
        if re.match('^[0123456789abcdef\\\\x ]+$', data):
            raw_hex = re.sub('[\\\\x ]', '', data)
            if len(raw_hex) % 2 == 0:
                return bytes.fromhex(raw_hex)
        else:
            raise AssertionError(f'{kwarg.name} must be hex characters')

    elif kwarg.type == GreedyInt or kwarg.type == List[int]:
        list_int = []
        for digit in value.split():
            assert (digit.isdigit), f'{kwarg.name} must a sequence of digits'
            list_int.append(int(digit))
        return list_int

    elif kwarg.type == GreedyFloat or kwarg.type == List[float]:
        list_float = []
        for decimal in value.split():
            assert (decimal.isdecimal), f'{kwarg.name} must a sequence of decimals'
            list_float.append(float(decimal))
        return list_float

    elif kwarg.type == GreedyBin or kwarg.type == List[Bin]:
        data = value.lower().replace("0b", "")
        if re.match('^[01\\\\b ]+$', data):
            raw_bin = re.sub('[\\\\b ]', '', data)
            list_bool = []
            for bit in raw_bin:
                list_bool.append(bool(bit))
            return list_bool
        else:
            raise AssertionError(f'{kwarg.name} must be sequence of 1s and 0s')

    else:
        raise AssertionError('type not implimented yet')
