from enum import Enum

class ProductCategory(str, Enum):
    TOPS = "Tops"
    BOTTOMS = "Bottoms"
    OUTERWEAR = "Outerwear"
    DRESSES = "Dresses"
    SHOES = "Shoes"
    ACCESSORIES = "Accessories"

    @classmethod
    def list(cls):
        return [c.value for c in cls]