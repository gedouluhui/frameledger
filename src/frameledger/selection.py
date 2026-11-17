"""Exact policies on observed presentation times, not estimated frame rates."""
from bisect import bisect_right
from fractions import Fraction
import re
from .errors import InputError


def parse_time(value,*,derived=False):
    if not isinstance(value,str) or len(value)>(160 if derived else 96) or not re.fullmatch(r'-?(?:\d+(?:\.\d+)?|\d+/\d+)',value):
        raise InputError('time must be a bounded exact decimal or rational string')
    try:
        result=Fraction(value)
    except (ValueError,ZeroDivisionError) as exc:
        raise InputError('invalid rational time') from exc
    # Derived errors/origin sums can multiply request and native timebase denominators.
    if abs(result.numerator)>(10**48 if derived else 10**24) or result.denominator>(10**36 if derived else 10**18):
        raise InputError('time exceeds rational magnitude budget')
    return result


def select_indices(timestamps,requests,policy):
    if policy not in ('nearest','previous'):
        raise InputError('policy must be nearest or previous')
    if not isinstance(timestamps,list) or not timestamps or not isinstance(requests,list) or not requests:
        raise InputError('timestamps and requests must be nonempty lists')
    if any(not isinstance(t,Fraction) for t in timestamps+requests):
        raise InputError('selection requires exact Fraction values')
    if any(a>=b for a,b in zip(timestamps,timestamps[1:])):
        raise InputError('observed PTS must be strictly increasing')
    result=[]
    for t in requests:
        if not timestamps[0]<=t<=timestamps[-1]:
            raise InputError('request is outside the first-to-last observed PTS domain')
        left=bisect_right(timestamps,t)-1
        if policy=='nearest' and left+1<len(timestamps) and timestamps[left+1]-t<t-timestamps[left]:
            left+=1
        result.append(left)
    return result
