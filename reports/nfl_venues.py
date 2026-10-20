from __future__ import annotations


ROOF_OVERRIDES = {
    "PAR00": "outdoors",
    "ATL97": "retractable",
    "HOU00": "retractable",
    "PHO00": "retractable",
}

STADIUM_LOCATIONS = {
    "CHI98": {
        "city": "Chicago",
        "latitude": 41.8623,
        "longitude": -87.6167,
        "timezone": "America/Chicago",
    },
    "PAR00": {
        "city": "Saint-Denis",
        "latitude": 48.9245,
        "longitude": 2.3601,
        "timezone": "Europe/Paris",
    },
    "ATL97": {
        "city": "Atlanta",
        "latitude": 33.7554,
        "longitude": -84.4008,
        "timezone": "America/New_York",
    },
    "BAL00": {
        "city": "Baltimore",
        "latitude": 39.2780,
        "longitude": -76.6227,
        "timezone": "America/New_York",
    },
    "CAR00": {
        "city": "Charlotte",
        "latitude": 35.2258,
        "longitude": -80.8528,
        "timezone": "America/New_York",
    },
    "HOU00": {
        "city": "Houston",
        "latitude": 29.6847,
        "longitude": -95.4107,
        "timezone": "America/Chicago",
    },
    "MIN01": {
        "city": "Minneapolis",
        "latitude": 44.9736,
        "longitude": -93.2575,
        "timezone": "America/Chicago",
    },
    "NYC01": {
        "city": "East Rutherford",
        "latitude": 40.8135,
        "longitude": -74.0745,
        "timezone": "America/New_York",
    },
    "NAS00": {
        "city": "Nashville",
        "latitude": 36.1665,
        "longitude": -86.7713,
        "timezone": "America/Chicago",
    },
    "PHO00": {
        "city": "Glendale",
        "latitude": 33.5276,
        "longitude": -112.2626,
        "timezone": "America/Phoenix",
    },
    "DET00": {
        "city": "Detroit",
        "latitude": 42.3400,
        "longitude": -83.0456,
        "timezone": "America/Detroit",
    },
    "VEG00": {
        "city": "Las Vegas",
        "latitude": 36.0909,
        "longitude": -115.1833,
        "timezone": "America/Los_Angeles",
    },
    "SEA00": {
        "city": "Seattle",
        "latitude": 47.5952,
        "longitude": -122.3316,
        "timezone": "America/Los_Angeles",
    },
    "PHI00": {
        "city": "Philadelphia",
        "latitude": 39.9008,
        "longitude": -75.1675,
        "timezone": "America/New_York",
    },
}

def normalize_roof(
    stadium_id,
    source_roof,
):
    stadium_id = (
        None
        if stadium_id is None
        else str(stadium_id)
    )

    if stadium_id in ROOF_OVERRIDES:
        return ROOF_OVERRIDES[stadium_id]

    if source_roof is None:
        return "unknown"

    roof = str(source_roof).strip().lower()

    if roof in {
        "",
        "nan",
        "none",
    }:
        return "unknown"

    if roof in {
        "outdoors",
        "outdoor",
    }:
        return "outdoors"

    if roof in {
        "dome",
        "closed",
    }:
        return "dome"

    if roof in {
        "retractable",
        "retractable roof",
    }:
        return "retractable"

    return "unknown"


def weather_relevant(roof_type):
    return roof_type in {
        "outdoors",
        "retractable",
        "unknown",
    }

def get_stadium_location(stadium_id):
    if stadium_id is None:
        return None

    return STADIUM_LOCATIONS.get(
        str(stadium_id)
    )
