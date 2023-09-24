"""
Utilities
"""
import io
from typing import Dict, Any, List
from dataclasses import is_dataclass, asdict


def custom_asdict(obj):
    # Custom asdict function that excludes _io.BufferedWriter objects
    obj_dict = {}
    for field in obj.__dataclass_fields__.values():
        value = getattr(obj, field.name)
        if not isinstance(value, io.BufferedWriter):
            obj_dict[field.name] = to_dict(value)
    return obj_dict

def to_dict(obj) -> Dict[str, Any]:    
    if is_dataclass(obj):
        # If the object is a data class, use asdict to convert it to a dictionary
        return to_dict(custom_asdict(obj))
    
    if isinstance(obj, (int, str, bool, float)):
        # If the object is a basic type, return it as is
        return obj

    if isinstance(obj, list):
        # If the object is a list, recursively call to_dict on its elements
        return [to_dict(item) for item in obj]

    if isinstance(obj, dict):
        # If the object is a dictionary, recursively call to_dict on its values
        return {key: to_dict(value) for key, value in obj.items() if not key.startswith('_')}

    if hasattr(obj, '__dict__'):
        # If the object has a __dict__ attribute, recursively call to_dict on its attributes
        return {key: to_dict(value) for key, value in obj.__dict__.items() if not key.startswith('_')}
    
    # If none of the above conditions match, return None (or handle as needed)
    return None