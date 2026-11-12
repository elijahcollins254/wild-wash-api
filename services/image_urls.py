import re
from urllib.parse import quote


DEFAULT_SERVICE_IMAGE_BASE_URL = (
    "https://wildwash-images.s3.eu-north-1.amazonaws.com/images/"
)

SERVICE_IMAGE_FILES = {
    "standard wash": "Standard Wash.png",
    "express wash": "Express Wash.png",
    "dry cleaning": "Dry Cleaning.png",
    "duvet cleaning": "Duvet Cleaning.png",
    "4x6 duvet cleaning": "4×6 Duvet Cleaning.png",
    "clean now pay later": "Clean Now Pay Later.png",
    "bedsitter fumigation": "Bedsitter Fumigation.png",
    "fumigation": "Bedsitter Fumigation.png",
    "carpet cleaning": "Carpet Cleaning.png",
    "ironing service": "Ironing Service.png",
    "bedsheet cleaning": "Bedsheet Cleaning.png",
    "laundry cleaning": "Laundry Cleaning.png",
    "storage": "Storage.png",
    "storage services": "Storage.png",
    "repairs": "Repairs.png",
    "repair services": "Repairs.png",
    "moving": "Moving.png",
    "moving services": "Moving.png",
    "sofa cleaning": "Sofa Cleaning.png",
    "house cleaning": "House Cleaning.png",
    "mattress cleaning": "Mattress Cleaning.png",
    "shoes cleaning": "Shoes Cleaning.png",
    "shoe cleaning": "Shoes Cleaning.png",
    "folding service": "Folding Service.png",
    "shirt cleaning": "Shirt Cleaning.png",
    "jacket cleaning": "Jacket Cleaning.png",
    "trenchcoat cleaning": "Trenchcoat Cleaning.png",
    "trench coat cleaning": "Trenchcoat Cleaning.png",
    "trouser cleaning": "Trouser Cleaning.png",
    "trousers cleaning": "Trouser Cleaning.png",
    "tv installation": "Tv Installation.png",
    "tv mounting": "Tv Installation.png",
    "shower installation": "Shower Installation.png",
    "hot shower installation": "Shower Installation.png",
}


def get_service_image_filename(service_name):
    normalized_name = service_name.casefold().replace("×", "x")
    normalized_name = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", normalized_name)
    normalized_name = " ".join(normalized_name.split())

    image_filename = SERVICE_IMAGE_FILES.get(normalized_name)
    if image_filename:
        return image_filename

    if "clean now pay later" in normalized_name:
        return "Clean Now Pay Later.png"
    if "trenchcoat" in normalized_name or "trench coat" in normalized_name:
        return "Trenchcoat Cleaning.png"
    if "trouser" in normalized_name:
        return "Trouser Cleaning.png"
    if "shirt" in normalized_name:
        return "Shirt Cleaning.png"
    if "jacket" in normalized_name:
        return "Jacket Cleaning.png"
    if "shoe" in normalized_name:
        return "Shoes Cleaning.png"
    if "fold" in normalized_name:
        return "Folding Service.png"
    if "bedsheet" in normalized_name:
        return "Bedsheet Cleaning.png"
    if "iron" in normalized_name:
        return "Ironing Service.png"
    if "mattress" in normalized_name:
        return "Mattress Cleaning.png"
    if any(token in normalized_name for token in ("sofa", "couch", "seater")):
        return "Sofa Cleaning.png"
    if "carpet" in normalized_name:
        return "Carpet Cleaning.png"
    if "duvet" in normalized_name or "blanket" in normalized_name:
        return "Duvet Cleaning.png"
    if "fumigation" in normalized_name:
        return "Bedsitter Fumigation.png"
    if "storage" in normalized_name:
        return "Storage.png"
    if "moving" in normalized_name:
        return "Moving.png"
    if "tv" in normalized_name or "mounting" in normalized_name:
        return "Tv Installation.png"
    if "shower" in normalized_name or "hotshower" in normalized_name:
        return "Shower Installation.png"
    if "repair" in normalized_name:
        return "Repairs.png"
    if any(token in normalized_name for token in ("house", "bedroom", "bedsitter")):
        return "House Cleaning.png"
    if "dry clean" in normalized_name or "dryclean" in normalized_name:
        return "Dry Cleaning.png"
    if "express" in normalized_name or "speed wash" in normalized_name:
        return "Express Wash.png"
    if "standard wash" in normalized_name:
        return "Standard Wash.png"
    if "laundry" in normalized_name or "sock" in normalized_name:
        return "Laundry Cleaning.png"
    if "wash" in normalized_name or "clean" in normalized_name:
        return "Standard Wash.png"
    return None


def build_service_image_url(base_url, filename):
    return f"{base_url.rstrip('/')}/{quote(filename, safe='')}"


def get_service_image_url(service_name, base_url=DEFAULT_SERVICE_IMAGE_BASE_URL):
    filename = get_service_image_filename(service_name)
    if filename is None:
        return None
    return build_service_image_url(base_url, filename)
