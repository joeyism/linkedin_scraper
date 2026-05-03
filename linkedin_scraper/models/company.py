"""Pydantic models for LinkedIn Company data."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, field_validator


class Company(BaseModel):
    """
    LinkedIn Company model with validation.

    Represents a complete LinkedIn company page with all scraped data.
    """
    linkedin_url: str
    name: Optional[str] = None
    about_us: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    headquarters: Optional[str] = None
    founded: Optional[str] = None
    industry: Optional[str] = None
    company_type: Optional[str] = None
    company_size: Optional[str] = None
    specialties: Optional[str] = None
    
    @field_validator('linkedin_url')
    @classmethod
    def validate_linkedin_url(cls, v: str) -> str:
        """Validate that URL is a LinkedIn company URL."""
        if 'linkedin.com/company/' not in v:
            raise ValueError('Must be a valid LinkedIn company URL (contains /company/)')
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation of the company
        """
        return self.model_dump()
    
    def to_json(self, **kwargs) -> str:
        """
        Convert to JSON string.
        
        Args:
            **kwargs: Additional arguments for model_dump_json (e.g., indent=2)
        
        Returns:
            JSON string representation
        """
        return self.model_dump_json(**kwargs)
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Company {self.name}\n"
            f"  Industry: {self.industry}\n"
            f"  Size: {self.company_size}\n"
            f"  Headquarters: {self.headquarters}>"
        )
