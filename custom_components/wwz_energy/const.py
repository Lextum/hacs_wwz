"""Constants for the WWZ Energy integration."""

DOMAIN = "wwz_energy"

API_BASE_URL = "https://cpp01.wwz.ch"
API_LOGIN_PATH = "//loginRegistration/rest/loginService/login"
API_VALIDATION_PATH = "//loginRegistration/rest/loginService/validation"
API_CONTRACT_ACCOUNTS_PATH = (
    "//switchContractAccount/rest/switchContractAccount/contractAccounts"
)
API_METER_POINTS_PATH = "//wwz/rest/WWZMeterProfileViewWWZService/getMeterPoints"
API_METER_POINT_ID_PATH = "//wwz/rest/WWZMeterProfileViewWWZService/getMeterPointId"
API_DATA_PATH = "//wwz/rest/WWZSmartMeterService/getDiagramValues"

CONF_LOOKBACK_DAYS = "lookback_days"
DEFAULT_LOOKBACK_DAYS = 2

CONF_ENERGY_TARIFF = "energy_tariff"
CONF_GRID_TARIFF = "grid_tariff"
CONF_MUNICIPALITY = "municipality"
DEFAULT_ENERGY_TARIFF = "Energietarif; WWZ Naturstrom"
DEFAULT_GRID_TARIFF = "Netztarif Basis (NE 7)"

TARIFF_URL_TEMPLATE = "https://www.wwz.ch/-/media/privatpersonen/energie/strom/tarife/{year}/stromtarfie-{year}-json.json"
