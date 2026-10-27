"""Constants for the WWZ Energy integration."""

DOMAIN = "wwz_energy"

API_BASE_URL = "https://www.wwz.ch"
API_PORTAL_PATH = "/energieportal"
API_READ_TOKEN_PATH = "/api/authorization/readtoken"
API_CONTRACT_ACCOUNTS_PATH = "/api/stromportal/contractaccounts"
API_METER_POINTS_PATH = "/api/stromportal/getMeterPoints"
API_METER_POINT_ID_PATH = "/api/stromportal/getMeterPointId"
API_DATA_PATH = "/api/stromportal/getDiagramValues"

IAM_REST_URL = "https://cockpit.wwz.ch/auth-login/rest/public/authentication"
IAM_AUTHORIZE_PATH = "/oauth2/authorization-servers/wwz/authorize"
IAM_PASSWORD_CHECK_PATH = "/password/check"

CONF_ENABLE_PRICE_SENSOR = "enable_price_sensor"
CONF_FULL_DAYS_ONLY = "full_days_only"
CONF_LOOKBACK_DAYS = "lookback_days"
DEFAULT_LOOKBACK_DAYS = 2

CONF_ENERGY_TARIFF = "energy_tariff"
CONF_GRID_TARIFF = "grid_tariff"
CONF_MUNICIPALITY = "municipality"
DEFAULT_ENERGY_TARIFF = "Energietarif; WWZ Naturstrom"
DEFAULT_GRID_TARIFF = "Netztarif Basis (NE 7)"

TARIFF_URL_TEMPLATE = "https://www.wwz.ch/-/media/privatpersonen/energie/strom/tarife/{year}/stromtarfie-{year}-json.json"

ZUG_MUNICIPALITIES = [
    "Baar",
    "Cham",
    "Hünenberg",
    "Menzingen",
    "Neuheim",
    "Oberägeri",
    "Risch",
    "Steinhausen",
    "Unterägeri",
    "Walchwil",
    "Zug",
]
