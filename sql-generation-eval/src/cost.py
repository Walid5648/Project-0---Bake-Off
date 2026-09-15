"""Transparent local operating-cost estimates; never invent power measurements."""

import argparse
import json


def estimate(mean_latency_ms: float, hardware_hourly: float, power_watts: float,
             electricity_kwh: float, operator_hours: float, operator_hourly: float,
             monthly_requests: int) -> dict:
    if mean_latency_ms <= 0 or monthly_requests <= 0:
        raise ValueError("Latency and request volume must be positive")
    if min(hardware_hourly, power_watts, electricity_kwh, operator_hours, operator_hourly) < 0:
        raise ValueError("Cost assumptions cannot be negative")
    hours_per_request = mean_latency_ms / 3_600_000
    hourly_cost = hardware_hourly + power_watts / 1000 * electricity_kwh
    operating_per_request = hours_per_request * hourly_cost
    operator_cost = operator_hours * operator_hourly
    return {
        "api_charge_usd": 0,
        "operating_cost_per_1000_requests_usd": operating_per_request * 1000,
        "operator_cost_per_month_usd": operator_cost,
        "baseline_requests_per_month": monthly_requests,
        "baseline_monthly_cost_usd": monthly_requests * operating_per_request + operator_cost,
        "100x_monthly_cost_usd": 100 * monthly_requests * operating_per_request + operator_cost,
        "baseline_busy_hours_per_month": monthly_requests * hours_per_request,
        "100x_busy_hours_per_month": 100 * monthly_requests * hours_per_request,
        "100x_fits_720_available_hours": 100 * monthly_requests * hours_per_request <= 720,
        "assumptions": "Hardware allocated per busy hour; fixed monthly operator time; constant observed sequential latency. Excludes idle power. Validate capacity and operator effort before extrapolating.",
        "api_break_even": "Not applicable: the experiment has no API model",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mean-latency-ms", type=float, required=True)
    parser.add_argument("--hardware-hourly", type=float, required=True)
    parser.add_argument("--power-watts", type=float, required=True)
    parser.add_argument("--electricity-kwh", type=float, required=True)
    parser.add_argument("--operator-hours", type=float, required=True)
    parser.add_argument("--operator-hourly", type=float, required=True)
    parser.add_argument("--monthly-requests", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(estimate(**vars(args)), indent=2))


if __name__ == "__main__":
    main()
