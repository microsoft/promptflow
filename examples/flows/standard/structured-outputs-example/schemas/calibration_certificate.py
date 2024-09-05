from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime

class CalibrationMark(BaseModel):
    calibration_mark: str 
    laboratory_nr: str
    date: str

class PlaceOfCalibration(BaseModel):
    name: str
    street: str
    house_nr: str
    zip_code: str
    city: str
    country: str

class ConformityDetailsInner(BaseModel):
    nominal_value: str
    marking: str
    conventional_mass: str
    conventional_mass_before_adjustment: str
    uncertainty_k2: str

class ConformityDetails(BaseModel):
    are_within_tolerances: str
    details: ConformityDetailsInner

class CalibrationCertificate(BaseModel):
    calibration_mark: CalibrationMark
    ILAC_logo_available: bool
    subject_of_calibration: str
    manufacturer: Optional[str]
    typ_modell: Optional[str]
    fabrikcat_serial_nr: str
    date_of_calibration: str
    number_of_pages_cover: int
    number_of_pages_header_footer: int
    signature_required: bool
    signature_handwritten: bool
    name_inspector: str
    place_of_calibration: PlaceOfCalibration
    conformity_details: ConformityDetails
    conformity_total: bool

def parse_calibration_certificate(json_obj):
    return CalibrationCertificate(**json_obj)
