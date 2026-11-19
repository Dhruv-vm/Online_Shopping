import abc
from typing import Any


class CarrierProvider(abc.ABC):
    """Abstract base class for carrier integrations.

    Implementations can integrate with live third-party logistics APIs (e.g. Delhivery,
    BlueDart, Shiprocket) or operate in manual/internal sandbox mode.
    External API calls are never faked.
    """

    @abc.abstractmethod
    def validate_tracking_number(self, carrier_code: str, tracking_number: str) -> bool:
        """Validate tracking number format for carrier."""
        ...

    @abc.abstractmethod
    def build_tracking_url(self, carrier_code: str, tracking_number: str) -> str | None:
        """Build public customer tracking URL for carrier."""
        ...

    @abc.abstractmethod
    def fetch_tracking_updates(
        self, carrier_code: str, tracking_number: str
    ) -> list[dict[str, Any]]:
        """Fetch tracking updates from carrier (if supported)."""
        ...


class ManualCarrierProvider(CarrierProvider):
    """Authoritative carrier provider for manual & internal fulfillment.

    Relies on system shipment records and manual status updates without faking
    external API responses.
    """

    KNOWN_CARRIERS = {
        "DELHIVERY": {
            "name": "Delhivery",
            "url_pattern": "https://www.delhivery.com/track/package/{tracking_number}",
        },
        "BLUEDART": {
            "name": "Blue Dart",
            "url_pattern": "https://www.bluedart.com/tracking?trackNumber={tracking_number}",
        },
        "EKART": {
            "name": "Ekart Logistics",
            "url_pattern": "https://ekartlogistics.com/shipmenttrack/{tracking_number}",
        },
        "DTDC": {
            "name": "DTDC Express",
            "url_pattern": "https://www.dtdc.in/tracking/shipment-tracking.asp?strCnno={tracking_number}",
        },
        "INTERNAL": {
            "name": "BASKET Express",
            "url_pattern": None,
        },
    }

    def validate_tracking_number(self, carrier_code: str, tracking_number: str) -> bool:
        if not tracking_number or len(tracking_number.strip()) < 3:
            return False
        return True

    def build_tracking_url(self, carrier_code: str, tracking_number: str) -> str | None:
        code = carrier_code.strip().upper()
        carrier = self.KNOWN_CARRIERS.get(code)
        if carrier and carrier.get("url_pattern"):
            return carrier["url_pattern"].format(tracking_number=tracking_number)
        return None

    def fetch_tracking_updates(
        self, carrier_code: str, tracking_number: str
    ) -> list[dict[str, Any]]:
        # In manual carrier mode, tracking updates are driven exclusively by database shipment events.
        return []


carrier_provider: CarrierProvider = ManualCarrierProvider()


def get_carrier_provider() -> CarrierProvider:
    return carrier_provider
