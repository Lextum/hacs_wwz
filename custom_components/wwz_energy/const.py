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
