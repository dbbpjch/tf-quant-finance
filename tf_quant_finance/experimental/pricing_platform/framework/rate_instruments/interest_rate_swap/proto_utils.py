# Lint as: python3
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utilities for creating a swap instrument."""
import hashlib
import json

from typing import Any, Dict, List, Tuple, Union

from tf_quant_finance import datetime as dateslib
from tf_quant_finance.experimental.pricing_platform.framework.core import business_days
from tf_quant_finance.experimental.pricing_platform.framework.core import currencies
from tf_quant_finance.experimental.pricing_platform.framework.core import daycount_conventions
from tf_quant_finance.experimental.pricing_platform.framework.core import rate_indices
from tf_quant_finance.experimental.pricing_platform.framework.market_data import utils as market_data_utils
from tf_quant_finance.experimental.pricing_platform.framework.rate_instruments import coupon_specs
from tf_quant_finance.experimental.pricing_platform.framework.rate_instruments import utils as instrument_utils
from tf_quant_finance.experimental.pricing_platform.instrument_protos import interest_rate_swap_pb2 as ir_swap


def leg_from_proto(
    leg_proto: ir_swap.SwapLeg) -> Union[coupon_specs.FixedCouponSpecs,
                                         coupon_specs.FloatCouponSpecs]:
  """Initialized coupon specifications from a proto instance."""
  if leg_proto.HasField("fixed_leg"):
    leg = leg_proto.fixed_leg
    return coupon_specs.FixedCouponSpecs(
        currency=currencies.from_proto_value(leg.currency),
        coupon_frequency=leg.coupon_frequency,
        notional_amount=[instrument_utils.decimal_to_double(
            leg.notional_amount)],
        fixed_rate=[instrument_utils.decimal_to_double(
            leg.fixed_rate)],
        settlement_days=[leg.settlement_days],
        businessday_rule=business_days.convention_from_proto_value(
            leg.business_day_convention),
        daycount_convention=daycount_conventions.from_proto_value(
            leg.daycount_convention),
        calendar=business_days.holiday_from_proto_value(leg.bank_holidays))
  else:
    leg = leg_proto.floating_leg
    # Get the index rate object
    rate_index = leg.floating_rate_type
    rate_index = rate_indices.RateIndex.from_proto(rate_index)
    rate_index.name = [rate_index.name]
    rate_index.source = [rate_index.source]
    return coupon_specs.FloatCouponSpecs(
        currency=currencies.from_proto_value(leg.currency),
        coupon_frequency=leg.coupon_frequency,
        reset_frequency=leg.reset_frequency,
        notional_amount=[instrument_utils.decimal_to_double(
            leg.notional_amount)],
        floating_rate_type=rate_index,
        settlement_days=[leg.settlement_days],
        businessday_rule=business_days.convention_from_proto_value(
            leg.business_day_convention),
        daycount_convention=daycount_conventions.from_proto_value(
            leg.daycount_convention),
        spread=[instrument_utils.decimal_to_double(leg.spread)],
        calendar=business_days.holiday_from_proto_value(leg.bank_holidays))


def leg_from_proto_v2(
    leg_proto: ir_swap.SwapLeg) -> Union[coupon_specs.FixedCouponSpecs,
                                         coupon_specs.FloatCouponSpecs]:
  """Initialized coupon specifications from a proto instance."""
  if leg_proto.HasField("fixed_leg"):
    leg = leg_proto.fixed_leg
    coupon_freq = leg.coupon_frequency.type
    coupon_freq, coupon_freq_multiplier = _frequency_and_multiplier(coupon_freq)
    return coupon_specs.FixedCouponSpecs(
        currency=[currencies.from_proto_value(leg.currency)],
        coupon_frequency=(
            coupon_freq,
            [coupon_freq_multiplier * leg.coupon_frequency.amount]),
        notional_amount=[instrument_utils.decimal_to_double(
            leg.notional_amount)],
        fixed_rate=[instrument_utils.decimal_to_double(
            leg.fixed_rate)],
        settlement_days=[leg.settlement_days],
        businessday_rule=business_days.convention_from_proto_value(
            leg.business_day_convention),
        daycount_convention=daycount_conventions.from_proto_value(
            leg.daycount_convention),
        calendar=business_days.holiday_from_proto_value(leg.bank_holidays))
  else:
    leg = leg_proto.floating_leg
    # Get the index rate object
    rate_index = leg.floating_rate_type
    rate_index = rate_indices.RateIndex.from_proto(rate_index)
    rate_index.name = [rate_index.name]
    rate_index.source = [rate_index.source]
    coupon_freq = leg.coupon_frequency.type
    coupon_freq, coupon_freq_multiplier = _frequency_and_multiplier(coupon_freq)
    reset_freq = leg.reset_frequency.type
    reset_freq, reset_freq_multiplier = _frequency_and_multiplier(reset_freq)
    return coupon_specs.FloatCouponSpecs(
        currency=[currencies.from_proto_value(leg.currency)],
        coupon_frequency=(
            coupon_freq,
            [coupon_freq_multiplier * leg.coupon_frequency.amount]),
        reset_frequency=(
            reset_freq,
            [reset_freq_multiplier * leg.reset_frequency.amount]),
        notional_amount=[instrument_utils.decimal_to_double(
            leg.notional_amount)],
        floating_rate_type=[rate_index],
        settlement_days=[leg.settlement_days],
        businessday_rule=business_days.convention_from_proto_value(
            leg.business_day_convention),
        daycount_convention=daycount_conventions.from_proto_value(
            leg.daycount_convention),
        spread=[instrument_utils.decimal_to_double(leg.spread)],
        calendar=business_days.holiday_from_proto_value(leg.bank_holidays))


def update_leg(
    current_leg: Union[coupon_specs.FixedCouponSpecs,
                       coupon_specs.FloatCouponSpecs],
    leg: Union[coupon_specs.FixedCouponSpecs, coupon_specs.FloatCouponSpecs]):
  """Adds new leg info to the current leg."""
  if isinstance(current_leg, coupon_specs.FixedCouponSpecs):
    if not isinstance(leg, coupon_specs.FixedCouponSpecs):
      raise ValueError("Both `current_leg` and `leg` should beof the same "
                       "fixed or float type.")
    current_leg.notional_amount += leg.notional_amount
    current_leg.fixed_rate += leg.fixed_rate
    current_leg.settlement_days += leg.settlement_days
  else:
    if not isinstance(leg, coupon_specs.FloatCouponSpecs):
      raise ValueError("Both `current_leg` and `leg` should beof the same "
                       "fixed or float type.")
    current_leg.notional_amount += leg.notional_amount
    update_rate_index(current_leg.floating_rate_type, leg.floating_rate_type)
    current_leg.settlement_days += leg.settlement_days
    current_leg.spread += leg.spread


def update_leg_v2(
    current_leg: Union[coupon_specs.FixedCouponSpecs,
                       coupon_specs.FloatCouponSpecs],
    leg: Union[coupon_specs.FixedCouponSpecs, coupon_specs.FloatCouponSpecs]):
  """Adds new leg info to the current leg."""
  if isinstance(current_leg, coupon_specs.FixedCouponSpecs):
    if not isinstance(leg, coupon_specs.FixedCouponSpecs):
      raise ValueError("Both `current_leg` and `leg` should beof the same "
                       "fixed or float type.")
    current_leg.currency += leg.currency
    current_leg.notional_amount += leg.notional_amount
    current_leg.fixed_rate += leg.fixed_rate
    current_leg.settlement_days += leg.settlement_days
    current_leg.coupon_frequency = (
        current_leg.coupon_frequency[0],
        current_leg.coupon_frequency[1] + leg.coupon_frequency[1])
  else:
    if not isinstance(leg, coupon_specs.FloatCouponSpecs):
      raise ValueError("Both `current_leg` and `leg` should beof the same "
                       "fixed or float type.")
    current_leg.currency += leg.currency
    current_leg.notional_amount += leg.notional_amount
    current_leg.floating_rate_type += leg.floating_rate_type
    current_leg.settlement_days += leg.settlement_days
    current_leg.spread += leg.spread
    current_leg.coupon_frequency = (
        current_leg.coupon_frequency[0],
        current_leg.coupon_frequency[1] + leg.coupon_frequency[1])
    current_leg.reset_frequency = (
        current_leg.reset_frequency[0],
        current_leg.reset_frequency[1] + leg.reset_frequency[1])


def update_rate_index(
    current_index: rate_indices.RateIndex,
    index: rate_indices.RateIndex):
  """Creates a dictionary of grouped protos."""
  if current_index.type != index.type:
    raise ValueError(f"Can not join {current_index.type} and {index.type}")
  current_index.name = current_index.name + index.name
  current_index.source = current_index.source + index.source


def get_hash(swap_proto: ir_swap.InterestRateSwap) -> Tuple[int, bool]:
  """Computes hash key for the batching strategy."""
  pay_leg = swap_proto.pay_leg
  receive_leg = swap_proto.receive_leg
  flip_legs, key = _get_legs_hash_key(pay_leg, receive_leg)
  currency = swap_proto.currency
  bank_holidays = swap_proto.bank_holidays
  h = _hasher(tuple(key + [currency] + [bank_holidays]))
  return h, flip_legs


def get_hash_v2(swap_proto: ir_swap.InterestRateSwap) -> Tuple[int, bool]:
  """Computes hash key for the batching strategy."""
  pay_leg = swap_proto.pay_leg
  receive_leg = swap_proto.receive_leg
  flip_legs, key = _get_legs_hash_key_v2(pay_leg, receive_leg)
  bank_holidays = swap_proto.bank_holidays
  h = _hasher(tuple(key + [bank_holidays]))
  return h, flip_legs


def group_protos(
    proto_list: List[ir_swap.InterestRateSwap],
    swap_config: "InterestRateSwapConfig" = None
    ) -> Dict[str, Any]:
  """Creates a dictionary of grouped protos."""
  del swap_config  # swap_config does not impact the batching
  grouped_swaps = {}
  for swap_proto in proto_list:
    h, _ = get_hash(swap_proto)
    if h in grouped_swaps:
      grouped_swaps[h].append(swap_proto)
    else:
      grouped_swaps[h] = [swap_proto]
  return grouped_swaps


def group_protos_v2(
    proto_list: List[ir_swap.InterestRateSwap],
    swap_config: "InterestRateSwapConfig" = None
    ) -> Dict[str, Any]:
  """Creates a dictionary of grouped protos."""
  del swap_config  # swap_config does not impact the batching
  grouped_swaps = {}
  for swap_proto in proto_list:
    h, _ = get_hash_v2(swap_proto)
    if h in grouped_swaps:
      grouped_swaps[h].append(swap_proto)
    else:
      grouped_swaps[h] = [swap_proto]
  return grouped_swaps


def from_protos(
    proto_list: List[ir_swap.InterestRateSwap],
    swap_config: "InterestRateSwapConfig" = None
    ) -> Dict[str, Any]:
  """Creates a dictionary of preprocessed swap data."""
  prepare_swaps = {}
  for swap_proto in proto_list:
    pay_leg = swap_proto.pay_leg
    receive_leg = swap_proto.receive_leg
    h, flip_legs = get_hash(swap_proto)
    start_date = swap_proto.effective_date
    start_date = [start_date.year,
                  start_date.month,
                  start_date.day]
    maturity_date = swap_proto.maturity_date
    maturity_date = [maturity_date.year,
                     maturity_date.month,
                     maturity_date.day]
    pay_leg_shuffled = leg_from_proto(pay_leg)
    receive_leg_shuffled = leg_from_proto(receive_leg)
    if flip_legs:
      notional_amount = receive_leg_shuffled.notional_amount
      receive_leg_shuffled.notional_amount = [-el for el in notional_amount]
      notional_amount = pay_leg_shuffled.notional_amount
      pay_leg_shuffled.notional_amount = [-el for el in notional_amount]
      pay_leg = receive_leg_shuffled
      receive_leg = pay_leg_shuffled
    else:
      pay_leg = pay_leg_shuffled
      receive_leg = receive_leg_shuffled
    name = swap_proto.metadata.id
    instrument_type = swap_proto.metadata.instrument_type
    if h in prepare_swaps:
      current_pay_leg = prepare_swaps[h]["pay_leg"]
      current_receive_leg = prepare_swaps[h]["receive_leg"]
      update_leg(current_pay_leg, pay_leg)
      update_leg(current_receive_leg, receive_leg)
      prepare_swaps[h]["start_date"].append(start_date)
      prepare_swaps[h]["maturity_date"].append(maturity_date)
      prepare_swaps[h]["batch_names"].append([name, instrument_type])
    else:
      prepare_swaps[h] = {"start_date": [start_date],
                          "maturity_date": [maturity_date],
                          "pay_leg": pay_leg,
                          "receive_leg": receive_leg,
                          "swap_config": swap_config,
                          "batch_names": [[name, instrument_type]]}
  return prepare_swaps


def from_protos_v2(
    proto_list: List[ir_swap.InterestRateSwap],
    swap_config: "InterestRateSwapConfig" = None
    ) -> Dict[str, Any]:
  """Creates a dictionary of preprocessed swap data."""
  prepare_swaps = {}
  for swap_proto in proto_list:
    pay_leg = swap_proto.pay_leg
    receive_leg = swap_proto.receive_leg
    h, flip_legs = get_hash_v2(swap_proto)
    start_date = swap_proto.effective_date
    start_date = [start_date.year,
                  start_date.month,
                  start_date.day]
    maturity_date = swap_proto.maturity_date
    maturity_date = [maturity_date.year,
                     maturity_date.month,
                     maturity_date.day]
    pay_leg_shuffled = leg_from_proto_v2(pay_leg)
    receive_leg_shuffled = leg_from_proto_v2(receive_leg)
    if flip_legs:
      notional_amount = receive_leg_shuffled.notional_amount
      receive_leg_shuffled.notional_amount = [-el for el in notional_amount]
      notional_amount = pay_leg_shuffled.notional_amount
      pay_leg_shuffled.notional_amount = [-el for el in notional_amount]
      pay_leg = receive_leg_shuffled
      receive_leg = pay_leg_shuffled
    else:
      pay_leg = pay_leg_shuffled
      receive_leg = receive_leg_shuffled
    name = swap_proto.metadata.id
    instrument_type = swap_proto.metadata.instrument_type
    if h in prepare_swaps:
      current_pay_leg = prepare_swaps[h]["pay_leg"]
      current_receive_leg = prepare_swaps[h]["receive_leg"]
      update_leg_v2(current_pay_leg, pay_leg)
      update_leg_v2(current_receive_leg, receive_leg)
      prepare_swaps[h]["start_date"].append(start_date)
      prepare_swaps[h]["maturity_date"].append(maturity_date)
      prepare_swaps[h]["batch_names"].append([name, instrument_type])
    else:
      prepare_swaps[h] = {"start_date": [start_date],
                          "maturity_date": [maturity_date],
                          "pay_leg": pay_leg,
                          "receive_leg": receive_leg,
                          "swap_config": swap_config,
                          "batch_names": [[name, instrument_type]]}
  return prepare_swaps


def update_frequency(leg: Tuple[int, List[int]]) -> dateslib.PeriodTensor:
  """Updates frequencies of a leg to an instance of PeriodTensor."""
  leg.coupon_frequency = market_data_utils.period_from_list(
      leg.coupon_frequency)
  try:
    leg.reset_frequency = market_data_utils.period_from_list(
        leg.reset_frequency)
  except AttributeError:
    pass


def _fixed_leg_key(leg: ir_swap.FixedLeg) -> List[Any]:
  return [leg.coupon_frequency.type, leg.coupon_frequency.amount,
          leg.daycount_convention, leg.business_day_convention]


def _floating_leg_key(leg: ir_swap.FloatingLeg) -> List[Any]:
  rate_index = leg.floating_rate_type
  return [leg.coupon_frequency.type, leg.coupon_frequency.amount,
          leg.reset_frequency.type, leg.reset_frequency.amount,
          leg.daycount_convention, leg.business_day_convention, rate_index.type]


def _get_keys(leg: ir_swap.SwapLeg) -> Tuple[List[Any], List[Any]]:
  """Computes key values for a function that partitions swaps into batches."""
  if leg.HasField("fixed_leg"):
    fixed_leg = leg.fixed_leg
    key_1 = _fixed_leg_key(fixed_leg)
    key_2 = 7 * [None]
  else:
    floating_leg = leg.floating_leg
    key_1 = 4 * [None]
    key_2 = _floating_leg_key(floating_leg)
  # len(key_1) + len(key_2) = 11 - this is the number of features involved into
  # the batching procedure
  return key_1, key_2


def _get_legs_hash_key(
    leg_1: ir_swap.SwapLeg,
    leg_2: ir_swap.SwapLeg) -> Tuple[bool, List[Any]]:
  """Computes hash keys for the legs in order to perform batching."""
  # Batching is performed on start_date, end_date, float_rate_type (if it is
  # associated with the same CurveType), fixed_rate, notional amount,
  # settlement days, and basis points.
  pay_leg_key_1, pay_leg_key_2 = _get_keys(leg_1)
  receive_leg_key_1, receive_leg_key_2 = _get_keys(leg_2)
  key_1 = pay_leg_key_1 + pay_leg_key_2
  key_2 = receive_leg_key_1 + receive_leg_key_2
  flip_legs = False
  # If this is a vanilla swap, keep pay_leg fixed and receive_leg float
  if (pay_leg_key_1[0] is None
      and receive_leg_key_1[0] is not None):
    flip_legs = True
  if flip_legs:
    return flip_legs, key_2 + key_1
  else:
    return flip_legs, key_1 + key_2


def _fixed_leg_key_v2(leg: ir_swap.FixedLeg) -> List[Any]:
  coupon_freq_type = leg.coupon_frequency.type
  if coupon_freq_type == 5:
    coupon_freq_type = 3
  return [coupon_freq_type,
          leg.daycount_convention, leg.business_day_convention]


def _floating_leg_key_v2(leg: ir_swap.FloatingLeg) -> List[Any]:
  coupon_freq_type = leg.coupon_frequency.type
  coupon_freq_type, _ = _frequency_and_multiplier(coupon_freq_type)
  reset_freq_type = leg.reset_frequency.type
  reset_freq_type, _ = _frequency_and_multiplier(reset_freq_type)
  return [coupon_freq_type,
          reset_freq_type,
          leg.daycount_convention, leg.business_day_convention]


def _get_keys_v2(leg: ir_swap.SwapLeg) -> Tuple[List[Any], List[Any]]:
  """Computes key values for a function that partitions swaps into batches."""
  if leg.HasField("fixed_leg"):
    fixed_leg = leg.fixed_leg
    key_1 = _fixed_leg_key_v2(fixed_leg)
    key_2 = 4 * [None]
  else:
    floating_leg = leg.floating_leg
    key_1 = 3 * [None]
    key_2 = _floating_leg_key_v2(floating_leg)
  # len(key_1) + len(key_2) = 7 - this is the number of features involved into
  # the batching procedure
  return key_1, key_2


def _get_legs_hash_key_v2(
    leg_1: ir_swap.SwapLeg,
    leg_2: ir_swap.SwapLeg) -> Tuple[bool, List[Any]]:
  """Computes hash keys for the legs in order to perform batching."""
  # Batching is performed on start_date, end_date, float_rate_type (if it is
  # associated with the same CurveType), fixed_rate, notional amount,
  # settlement days, and basis points.
  pay_leg_key_1, pay_leg_key_2 = _get_keys_v2(leg_1)
  receive_leg_key_1, receive_leg_key_2 = _get_keys_v2(leg_2)
  key_1 = pay_leg_key_1 + pay_leg_key_2
  key_2 = receive_leg_key_1 + receive_leg_key_2
  flip_legs = False
  # If this is a vanilla swap, keep pay_leg fixed and receive_leg float
  if (pay_leg_key_1[0] is None
      and receive_leg_key_1[0] is not None):
    flip_legs = True
  if flip_legs:
    return flip_legs, key_2 + key_1
  else:
    return flip_legs, key_1 + key_2


def _frequency_and_multiplier(freq_type):
  """Converts frequency type to MONTH and returns the computes multiplier."""
  multiplier = 1
  if freq_type == 5:
    freq_type = 3
  return freq_type, multiplier


# TODO(b/168411151): extract the non-cryptographic hasher to the common
# utilities
def _hasher(obj):
  """Computes non-cryptographic hash of an object."""
  h = hashlib.md5(json.dumps(obj).encode())
  return h.hexdigest()
