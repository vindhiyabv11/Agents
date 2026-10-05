from pydantic import BaseModel, Field


class WeatherReport(BaseModel):
    city : str
    temperature_c : float = Field(ge=-90, le=60)
    condition : str
    humidity_pct : float = Field(ge=0, le=100)
    

class WeatherToolOutput(BaseModel):
    """Schema that the raw tool response must satisfy"""
    
    temp_c : float = Field(ge=-90 , le=60)
    humidity : float = Field(ge=0, le=100)
    sky : str
    
    
    
    