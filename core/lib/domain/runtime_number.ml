open Bioc_wire

type t = Behavior.number = Integer of Z.t | Real of float

let zero = Integer Z.zero
let of_int value = Integer (Z.of_int value)
let raw_float = function Integer value -> Z.to_float value | Real value -> value
let check_finite ?path value =
  Diagnostic.require ?path (Float.is_finite (raw_float value)) "evaluation_nonfinite"
    "Execution numbers must have a finite binary64 conversion.";
  value
let of_behavior value = check_finite value
let of_json ?path = function
  | Json.Int value -> check_finite ?path (Integer value)
  | Json.Float value -> check_finite ?path (Real value)
  | _ -> Diagnostic.fail ?path "evaluation_numeric_type" "Expected a finite integer or float, not a Boolean."
let to_json value = match check_finite value with
  | Integer value -> Json.Int value | Real value -> Json.Float value
let to_float value = raw_float (check_finite value)

let result value =
  Diagnostic.require (Float.is_finite (raw_float value)) "evaluation_overflow"
    "Execution arithmetic produced a non-finite result.";
  value
let binary integer floating left right =
  let left = check_finite left and right = check_finite right in
  result (match left, right with
      | Integer left, Integer right -> Integer (integer left right)
      | _ -> Real (floating (raw_float left) (raw_float right)))
let add = binary Z.add ( +. )
let sub = binary Z.sub ( -. )
let mul = binary Z.mul ( *. )
let compare left right = Json.number_compare (to_json left) (to_json right)
let equal left right = compare left right = 0
let min left right = if compare left right <= 0 then left else right
let max left right = if compare left right >= 0 then left else right
let div left right =
  let left = check_finite left and right = check_finite right in
  Diagnostic.require (not (equal right zero)) "evaluation_division_by_zero"
    "Division by zero during reference execution.";
  result (match left, right with
      | Integer numerator, Integer denominator ->
          (* Dividing converted operands loses low bits and can double-round.
             Integer true division rounds the exact ratio once. Rational zero
             has no sign, so preserve Python's 0 / negative-integer result. *)
          let quotient = Q.to_float (Q.make numerator denominator) in
          Real (if quotient = 0. && Z.sign denominator < 0 && Z.sign numerator >= 0 then -. 0. else quotient)
      | _ -> Real (raw_float left /. raw_float right))
let neg value = result (match check_finite value with
    | Integer value -> Integer (Z.neg value) | Real value -> Real (-. value))

(* A binary64 value is an integer multiple of 2^-1074. Accumulate those units
   exactly, then round the final rational once. Alongside that independent exact
   accumulator, a floating expansion detects the same intermediate-overflow
   condition as Python math.fsum. A plain exact sum alone would wrongly accept
   [max_float; max_float; -max_float].

   Compatibility reference (algorithm and overflow contract):
   https://github.com/python/cpython/blob/v3.14.0/Modules/mathmodule.c#L1231
   CPython is distributed under the Python Software Foundation license. This
   implementation uses exact integer units for final rounding rather than
   CPython's rounded collapse of its floating expansion. *)
let binary64_units value =
  let bits = Int64.bits_of_float value in
  let negative = Int64.compare bits 0L < 0 in
  let exponent = Int64.to_int (Int64.logand (Int64.shift_right_logical bits 52) 0x7ffL) in
  let fraction = Z.of_int64 (Int64.logand bits 0x000fffffffffffffL) in
  let magnitude = if exponent = 0 then fraction
    else Z.shift_left (Z.add fraction (Z.shift_left Z.one 52)) (exponent - 1) in
  if negative then Z.neg magnitude else magnitude

let add_expansion partials value =
  let residuals, carry = List.fold_left (fun (residuals, carry) partial ->
      let dominant, smaller = if Float.abs carry >= Float.abs partial then carry, partial else partial, carry in
      let combined = dominant +. smaller in
      Diagnostic.require (Float.is_finite combined) "evaluation_overflow" "Intermediate overflow in accurate summation.";
      let residual = smaller -. (combined -. dominant) in
      (if residual = 0. then residuals else residual :: residuals), combined)
      ([], value) partials in
  List.rev (if carry = 0. then residuals else carry :: residuals)

let fsum values =
  Diagnostic.require (List.length values <= Limits.max_json_nodes) "evaluation_number_limit"
    "Accurate summation exceeds the bounded numeric input inventory.";
  let _, total = List.fold_left (fun (partials, total) value ->
      let value = to_float value in
      add_expansion partials value, Z.add total (binary64_units value)) ([], Z.zero) values in
  result (Real (if Z.equal total Z.zero then 0. else Q.to_float (Q.make total (Z.shift_left Z.one 1074))))

let advance now duration =
  let deadline = add now duration in
  Diagnostic.require (compare duration zero > 0 && compare deadline now > 0) "evaluation_nonadvancing_time"
    "A positive duration must advance the representable timer deadline.";
  deadline
