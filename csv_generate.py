import os
import csv
import json
import re
import html
import unicodedata
from collections import OrderedDict
from urllib.parse import urlparse

from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

ROOT_DIR = "category_wise_products"

SHOPIFY_TEMPLATE = "shopify_product_template.csv"

OUTPUT_CSV = "shopify_products_import.csv"

# Generic site images that are not real product photos.
PLACEHOLDER_IMAGES = (
    "/og-home.jpg",
)


# ============================================================
# CATEGORIES
# ============================================================
#
# Keys are the folder names under ROOT_DIR, as produced by
# slug_to_title(). Values are the display names used for
# Type and Tags (so automated collections can be built with
# "Tag is equal to ...").
#

CATEGORY_LABELS = {
    "Soins Cheveux": "Soins Cheveux",
    "Shampooing": "Shampooing",
    "Coiffants": "Coiffants",
    "Accessoires Cheveux": "Accessoires Cheveux",
    "Complement Alimentaire": "Complément Alimentaire",
    "Bebe Et Enfant": "Bébé et Enfant",
    "Soins Cheveux Enfant": "Soins Cheveux Enfant",
    "Hommes": "Hommes",
    "Cheveux Homme": "Cheveux Homme",
    "Soin Visage Homme": "Soin Visage Homme",
    "Soins Barbes": "Soins Barbes",
    "Soins Corps Homme": "Soins Corps Homme",
    "Accessoires Homme": "Accessoires Homme",
    "Coiffures": "Coiffures",
    "Accessoires De Coiffures": "Accessoires de Coiffures",
    "Extensions": "Extensions",
    "Tissage": "Tissage",
    "Soins Cheveux Coiffures": "Soins Cheveux Coiffures",
    "Lace Wig": "Lace Wig",
    "Meches A Tresser": "Mèches à Tresser",
    "Postiches": "Postiches",
    "Perruques": "Perruques",
    "Visages Et Corps": "Visages et Corps",
    "Corps": "Corps",
    "Visages": "Visages",
    "Make Up": "Make Up",
    "Teint": "Teint",
    "Yeux": "Yeux",
}

# Shopify standard product taxonomy ("Product category" column).
# Paths must match https://github.com/Shopify/product-taxonomy
# exactly, otherwise Shopify ignores them.

HAIR_CARE = "Health & Beauty > Personal Care > Hair Care"
HAIR_ACCESSORIES = (
    "Apparel & Accessories > Clothing Accessories > Hair Accessories"
)
SKIN_CARE = "Health & Beauty > Personal Care > Cosmetics > Skin Care"
MAKEUP = "Health & Beauty > Personal Care > Cosmetics > Makeup"
GROOMING = "Health & Beauty > Personal Care > Shaving & Grooming"

SHOPIFY_TAXONOMY = {
    # Subcategories (most specific, checked first)
    "Shampooing": HAIR_CARE + " > Shampoo & Conditioner > Shampoo",
    "Coiffants": HAIR_CARE + " > Hair Styling Products",
    "Accessoires Cheveux": HAIR_ACCESSORIES,
    "Complement Alimentaire": (
        "Health & Beauty > Health Care > Fitness & Nutrition"
        " > Vitamins & Supplements"
    ),
    "Soins Cheveux Enfant": HAIR_CARE,
    "Cheveux Homme": HAIR_CARE,
    "Soin Visage Homme": SKIN_CARE,
    "Soins Barbes": GROOMING,
    "Soins Corps Homme": SKIN_CARE,
    "Accessoires Homme": GROOMING,
    "Accessoires De Coiffures": HAIR_ACCESSORIES,
    "Extensions": HAIR_ACCESSORIES + " > Hair Extensions",
    "Tissage": HAIR_ACCESSORIES + " > Hair Extensions",
    "Meches A Tresser": HAIR_ACCESSORIES + " > Hair Extensions",
    "Postiches": HAIR_ACCESSORIES + " > Hair Extensions",
    "Lace Wig": HAIR_ACCESSORIES + " > Wigs",
    "Soins Cheveux Coiffures": HAIR_CARE,
    "Corps": SKIN_CARE,
    "Visages": SKIN_CARE,
    "Teint": MAKEUP + " > Face Makeup",
    "Yeux": MAKEUP + " > Eye Makeup",
    # Main categories (fallback)
    "Soins Cheveux": HAIR_CARE,
    "Bebe Et Enfant": HAIR_CARE,
    "Hommes": GROOMING,
    "Coiffures": HAIR_ACCESSORIES + " > Hair Extensions",
    "Perruques": HAIR_ACCESSORIES + " > Wigs",
    "Visages Et Corps": SKIN_CARE,
    "Make Up": MAKEUP,
}


# ============================================================
# SHOPIFY TEMPLATE COLUMNS
# ============================================================

SHOPIFY_COLUMNS = [
    "Title",
    "URL handle",
    "Description",
    "Vendor",
    "Product category",
    "Type",
    "Tags",
    "Published on online store",
    "Status",
    "SKU",
    "Barcode",
    "Option1 name",
    "Option1 value",
    "Option1 Linked To",
    "Option2 name",
    "Option2 value",
    "Option2 Linked To",
    "Option3 name",
    "Option3 value",
    "Option3 Linked To",
    "Price",
    "Compare-at price",
    "Cost per item",
    "Charge tax",
    "Tax code",
    "Unit price total measure",
    "Unit price total measure unit",
    "Unit price base measure",
    "Unit price base measure unit",
    "Inventory tracker",
    "Inventory quantity",
    "Continue selling when out of stock",
    "Weight value (grams)",
    "Weight unit for display",
    "Requires shipping",
    "Fulfillment service",
    "Product image URL",
    "Image position",
    "Image alt text",
    "Variant image URL",
    "Gift card",
    "SEO title",
    "SEO description",
    "Color (product.metafields.shopify.color-pattern)",
    "Google Shopping / Google product category",
    "Google Shopping / Gender",
    "Google Shopping / Age group",
    "Google Shopping / Manufacturer part number (MPN)",
    "Google Shopping / Ad group name",
    "Google Shopping / Ads labels",
    "Google Shopping / Condition",
    "Google Shopping / Custom product",
    "Google Shopping / Custom label 0",
    "Google Shopping / Custom label 1",
    "Google Shopping / Custom label 2",
    "Google Shopping / Custom label 3",
    "Google Shopping / Custom label 4",
]


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    """Clean HTML entities and whitespace."""

    if value is None:
        return ""

    value = html.unescape(str(value))

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def slug_to_title(value):
    """
    Convert:

        soins-cheveux
        bebe-et-enfant

    into:

        Soins Cheveux
        Bebe Et Enfant
    """

    if not value:
        return ""

    value = value.replace("-", " ")
    value = value.replace("_", " ")

    return value.title()


def unique_list(values):
    """Remove duplicates while preserving order."""

    result = []

    seen = set()

    for value in values:

        value = clean_text(value)

        if not value:
            continue

        key = value.lower()

        if key not in seen:

            seen.add(key)

            result.append(value)

    return result


def get_meta(soup, attr, value):

    tag = soup.find(
        "meta",
        attrs={attr: value}
    )

    if tag:

        return tag.get(
            "content",
            ""
        )

    return ""


def get_first_text(soup, selectors):
    """Return text from the first matching selector."""

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element:

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if text:
                return text

    return ""


def get_first_attr(
    soup,
    selectors,
    attribute
):

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element:

            value = element.get(
                attribute
            )

            if value:

                return clean_text(
                    value
                )

    return ""


def parse_price(value):
    """
    Convert:

        9.90 €
        9,90 €
        9.90

    into:

        9.90
    """

    if value is None:
        return ""

    value = clean_text(value)

    if not value:
        return ""

    match = re.search(
        r"(\d+(?:[.,]\d+)?)",
        value
    )

    if not match:
        return ""

    return match.group(1).replace(
        ",",
        "."
    )


def parse_stock(value):
    """
    Extract:

        200 en stock

    into:

        200
    """

    if not value:
        return ""

    match = re.search(
        r"(\d+)",
        str(value)
    )

    if match:

        return match.group(1)

    return ""


def parse_weight(value):
    """
    Extract weight from text.

    Examples:

        280 g       -> 280
        0.28 kg     -> 280
        1.5 kg      -> 1500
        500 grammes -> 500
    """

    if not value:
        return ""

    value = clean_text(
        value
    ).lower()

    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(kg|kgs|g|gram|grams|gramme|grammes)",
        value,
        re.I
    )

    if not match:
        return ""

    number = float(
        match.group(1).replace(
            ",",
            "."
        )
    )

    unit = match.group(2).lower()

    if unit in [
        "kg",
        "kgs"
    ]:

        number *= 1000

    return str(
        int(number)
        if number.is_integer()
        else number
    )


def normalize_url(url):
    """
    Remove tracking/query strings from URLs.
    """

    if not url:
        return ""

    url = html.unescape(
        str(url)
    ).strip()

    parsed = urlparse(url)

    if not parsed.scheme:

        return url

    return "{}://{}{}".format(
        parsed.scheme,
        parsed.netloc,
        parsed.path
    )


# ============================================================
# CATEGORY FROM DIRECTORY STRUCTURE
# ============================================================

def get_categories_from_path(
    file_path
):
    """
    Expected:

        category_wise_products/
            coiffures/
                products/
                    product.html

    OR:

        category_wise_products/
            coiffures/
                extensions/
                    products/
                        product.html
    """

    relative_path = os.path.relpath(
        file_path,
        ROOT_DIR
    )

    parts = relative_path.split(
        os.sep
    )

    directories = parts[:-1]

    directories = [
        x
        for x in directories
        if x.lower() != "products"
    ]

    category = ""

    subcategory = ""

    if len(directories) >= 1:

        category = directories[0]

    if len(directories) >= 2:

        subcategory = directories[1]

    return (
        slug_to_title(category),
        slug_to_title(subcategory)
    )


# ============================================================
# HANDLE
# ============================================================

def extract_handle(
    soup,
    filename
):
    """
    Prefer canonical product URL.

    Example:

        https://afrotouch-kosmetics.fr/produit/
        dream-hair-3x-french-curl-braid/

    becomes:

        dream-hair-3x-french-curl-braid
    """

    canonical = soup.find(
        "link",
        rel="canonical"
    )

    if canonical:

        url = canonical.get(
            "href",
            ""
        )

        path = urlparse(
            url
        ).path.strip("/")

        if path:

            parts = path.split("/")

            if "produit" in parts:

                index = parts.index(
                    "produit"
                )

                if index + 1 < len(parts):

                    return parts[
                        index + 1
                    ]

            return parts[-1]

    return os.path.splitext(
        os.path.basename(
            filename
        )
    )[0]


# ============================================================
# DESCRIPTION
# ============================================================

def extract_description(
    soup
):
    """
    Extract WooCommerce product description.
    """

    selectors = [
        ".woocommerce-product-details__short-description",
        ".woocommerce-Tabs-panel--description",
        "#tab-description",
        ".product-description",
    ]

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if not element:
            continue

        for tag in element.select(
            "script, style, iframe, form"
        ):

            tag.decompose()

        text = clean_text(
            element.get_text(
                " ",
                strip=True
            )
        )

        if len(text) > 30:

            return text

    # Elementor fallback

    title = soup.find(
        class_=lambda x:
        x and "productView-title" in x
    )

    if title:

        parent = title.parent

        text_parts = []

        for element in parent.find_all_next(
            limit=15
        ):

            if element.name in [
                "script",
                "style",
                "form"
            ]:

                continue

            text = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if len(text) > 50:

                text_parts.append(
                    text
                )

        if text_parts:

            return " ".join(
                unique_list(
                    text_parts
                )
            )

    description = get_meta(
        soup,
        "name",
        "description"
    )

    return clean_text(
        description
    )


# ============================================================
# IMAGES
# ============================================================

def extract_images(
    soup
):
    """
    Extract original/high-resolution
    product images.

    Avoid:

        - thumbnails
        - logos
        - SVGs
        - data URLs
    """

    images = []

    # --------------------------------------------------------
    # WooCommerce gallery
    # --------------------------------------------------------

    for image in soup.select(
        ".woocommerce-product-gallery img"
    ):

        url = (
            image.get(
                "data-large_image"
            )
            or image.get(
                "data-src"
            )
            or image.get(
                "src"
            )
        )

        if not url:
            continue

        url = normalize_url(
            url
        )

        if (
            url
            and not url.startswith(
                "data:"
            )
            and ".svg" not in url.lower()
        ):

            images.append(
                {
                    "url": url,
                    "alt": clean_text(
                        image.get(
                            "alt",
                            ""
                        )
                    )
                }
            )

    # --------------------------------------------------------
    # OpenGraph images
    # --------------------------------------------------------

    for image in soup.find_all(
        "meta",
        property="og:image"
    ):

        url = normalize_url(
            image.get(
                "content",
                ""
            )
        )

        if url:

            images.append(
                {
                    "url": url,
                    "alt": ""
                }
            )

    # --------------------------------------------------------
    # Product images anywhere in page
    # --------------------------------------------------------

    if not images:

        for image in soup.select(
            "img"
        ):

            url = (
                image.get(
                    "data-large_image"
                )
                or image.get(
                    "data-src"
                )
                or image.get(
                    "src"
                )
            )

            if not url:
                continue

            url = normalize_url(
                url
            )

            if not url:
                continue

            if url.startswith(
                "data:"
            ):
                continue

            if ".svg" in url.lower():
                continue

            # Ignore obvious site logos
            lower_url = url.lower()

            if any(
                x in lower_url
                for x in [
                    "logo",
                    "icon",
                    "facebook",
                    "instagram",
                    "twitter",
                ]
            ):

                continue

            images.append(
                {
                    "url": url,
                    "alt": clean_text(
                        image.get(
                            "alt",
                            ""
                        )
                    )
                }
            )

    # --------------------------------------------------------
    # Remove duplicate images
    # --------------------------------------------------------

    final_images = []

    seen = set()

    for image in images:

        url = image["url"]

        if not url:
            continue

        if url in seen:
            continue

        seen.add(url)

        final_images.append(
            image
        )

    return final_images


# ============================================================
# VENDOR / BRAND
# ============================================================

def extract_vendor(
    soup
):
    """
    Try structured brand data first.
    """

    brand = get_meta(
        soup,
        "property",
        "product:brand"
    )

    if brand:

        return clean_text(
            brand
        )

    # JSON-LD

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):

        try:

            data = json.loads(
                script.string
                or script.get_text()
            )

        except Exception:

            continue

        objects = []

        if isinstance(
            data,
            dict
        ):

            if "@graph" in data:

                graph = data[
                    "@graph"
                ]

                if isinstance(
                    graph,
                    list
                ):

                    objects.extend(
                        graph
                    )

            else:

                objects.append(
                    data
                )

        elif isinstance(
            data,
            list
        ):

            objects.extend(
                data
            )

        for obj in objects:

            if not isinstance(
                obj,
                dict
            ):

                continue

            brand = obj.get(
                "brand"
            )

            if isinstance(
                brand,
                dict
            ):

                brand = brand.get(
                    "name"
                )

            if brand:

                return clean_text(
                    brand
                )

    return ""


# ============================================================
# OPTIONS
# ============================================================

def extract_option_names(
    soup
):
    """
    Get variation option names.

    Example:

        Longueur
        Choisir la Couleur
    """

    names = []

    form = soup.select_one(
        "form.variations_form"
    )

    if not form:

        return names

    for select in form.select(
        "select[name]"
    ):

        name = select.get(
            "name",
            ""
        )

        if not name.startswith(
            "attribute_"
        ):

            continue

        name = name.replace(
            "attribute_",
            "",
            1
        )

        name = name.replace(
            "pa_",
            "",
            1
        )

        label = ""

        select_id = select.get(
            "id"
        )

        if select_id:

            label_element = soup.find(
                "label",
                attrs={
                    "for": select_id
                }
            )

            if label_element:

                label = clean_text(
                    label_element.get_text()
                )

        if not label:

            label = slug_to_title(
                name
            )

        names.append(
            (
                name,
                label
            )
        )

    return names


# ============================================================
# VARIATIONS
# ============================================================

def extract_variations(
    soup
):
    """
    WooCommerce stores variations
    inside data-product_variations.
    """

    form = soup.select_one(
        "form.variations_form"
    )

    if not form:

        return []

    raw = form.get(
        "data-product_variations",
        ""
    )

    if not raw:

        return []

    raw = html.unescape(
        raw
    )

    try:

        variations = json.loads(
            raw
        )

    except Exception as e:

        print(
            "Could not parse variations:",
            e
        )

        return []

    if not isinstance(
        variations,
        list
    ):

        return []

    return variations


# ============================================================
# PRODUCT PRICE
# ============================================================

def extract_product_price(
    soup
):
    """
    Extract product price.
    """

    selectors = [
        ".summary .price",
        ".product .price",
        ".woocommerce-Price-amount",
        "p.price",
    ]

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element:

            price = parse_price(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if price:

                return price

    return ""


# ============================================================
# PRODUCT STOCK
# ============================================================

def extract_product_stock(
    soup
):
    """
    Extract stock quantity from
    WooCommerce stock elements.
    """

    selectors = [
        ".stock",
        ".availability",
        ".woocommerce-product-details__stock",
    ]

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element:

            stock = parse_stock(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if stock:

                return stock

    return ""


# ============================================================
# PRODUCT WEIGHT
# ============================================================

def extract_product_weight(
    soup
):
    """
    Try WooCommerce weight first,
    then product description.
    """

    selectors = [
        ".product_meta .weight",
        ".weight",
    ]

    for selector in selectors:

        element = soup.select_one(
            selector
        )

        if element:

            weight = parse_weight(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if weight:

                return weight

    description = extract_description(
        soup
    )

    return parse_weight(
        description
    )


# ============================================================
# HTML PRODUCT CATEGORIES
# ============================================================

def extract_html_categories(
    soup
):
    """
    Extract WooCommerce categories.
    """

    categories = []

    selectors = [
        ".product_meta .posted_in a",
        ".posted_in a",
    ]

    for selector in selectors:

        for element in soup.select(
            selector
        ):

            category = clean_text(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if category:

                categories.append(
                    category
                )

    return unique_list(
        categories
    )


# ============================================================
# PRODUCT PARSER
# ============================================================

def parse_product(
    file_path
):

    with open(
        file_path,
        "r",
        encoding="utf-8",
        errors="ignore"
    ) as f:

        html_content = f.read()

    soup = BeautifulSoup(
        html_content,
        "html.parser"
    )

    # --------------------------------------------------------
    # HANDLE
    # --------------------------------------------------------

    handle = extract_handle(
        soup,
        file_path
    )

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = get_first_text(
        soup,
        [
            "h1.product_title",
            ".product_title",
            ".productView-title",
        ]
    )

    if not title:

        title = get_meta(
            soup,
            "property",
            "og:title"
        )

        title = re.sub(
            r"\s*-\s*Afrotouch.*$",
            "",
            title,
            flags=re.I
        )

        title = clean_text(
            title
        )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    description = extract_description(
        soup
    )

    # --------------------------------------------------------
    # VENDOR
    # --------------------------------------------------------

    vendor = extract_vendor(
        soup
    )

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    price = extract_product_price(
        soup
    )

    # --------------------------------------------------------
    # STOCK
    # --------------------------------------------------------

    stock = extract_product_stock(
        soup
    )

    # --------------------------------------------------------
    # WEIGHT
    # --------------------------------------------------------

    weight = extract_product_weight(
        soup
    )

    # --------------------------------------------------------
    # SEO
    # --------------------------------------------------------

    seo_title = get_meta(
        soup,
        "property",
        "og:title"
    )

    if not seo_title:

        seo_title = title

    seo_description = get_meta(
        soup,
        "name",
        "description"
    )

    # --------------------------------------------------------
    # SKU
    # --------------------------------------------------------

    sku = get_first_text(
        soup,
        [
            ".product_meta .sku",
            ".sku",
        ]
    )

    if sku.upper() in [
        "N/A",
        "NA",
    ]:

        sku = ""

    # --------------------------------------------------------
    # CATEGORIES
    # --------------------------------------------------------

    html_categories = (
        extract_html_categories(
            soup
        )
    )

    # --------------------------------------------------------
    # IMAGES
    # --------------------------------------------------------

    images = extract_images(
        soup
    )

    # --------------------------------------------------------
    # OPTIONS
    # --------------------------------------------------------

    option_names = (
        extract_option_names(
            soup
        )
    )

    # --------------------------------------------------------
    # VARIATIONS
    # --------------------------------------------------------

    variations = extract_variations(
        soup
    )

    return {
        "handle": handle,
        "title": title,
        "description": description,
        "vendor": vendor,
        "price": price,
        "stock": stock,
        "weight": weight,
        "sku": sku,
        "seo_title": seo_title,
        "seo_description": seo_description,
        "html_categories": html_categories,
        "images": images,
        "option_names": option_names,
        "variations": variations,
    }


# ============================================================
# VARIATION KEY
# ============================================================

def get_variation_key(
    variation
):
    """
    Create a stable key for a WooCommerce variation.

    Example:

        attribute_longueur = 28"
        attribute_pa_choisir-la-couleur = 1

    becomes a unique key based on attributes.
    """

    attributes = variation.get(
        "attributes",
        {}
    )

    if not isinstance(
        attributes,
        dict
    ):

        return ""

    normalized = []

    for key in sorted(
        attributes.keys()
    ):

        value = clean_text(
            attributes.get(
                key,
                ""
            )
        )

        key = clean_text(
            key
        ).lower()

        value = value.lower()

        if key or value:

            normalized.append(
                "{}={}".format(
                    key,
                    value
                )
            )

    return "|".join(
        normalized
    )


# ============================================================
# MERGE PRODUCT DATA
# ============================================================

def merge_product_data(
    existing,
    incoming
):
    """
    Merge duplicate product data.

    The first product remains the
    primary record, while missing
    information from duplicates is
    added to it.
    """

    # --------------------------------------------------------
    # Simple fields
    # --------------------------------------------------------

    fields = [
        "title",
        "description",
        "vendor",
        "price",
        "stock",
        "weight",
        "sku",
        "seo_title",
        "seo_description",
    ]

    for field in fields:

        if not existing.get(field):

            if incoming.get(field):

                existing[field] = (
                    incoming[field]
                )

    # --------------------------------------------------------
    # HTML categories
    # --------------------------------------------------------

    existing["html_categories"] = (
        unique_list(
            existing.get(
                "html_categories",
                []
            )
            + incoming.get(
                "html_categories",
                []
            )
        )
    )

    # --------------------------------------------------------
    # Images
    # --------------------------------------------------------

    existing_images = {
        image["url"]
        for image in existing.get(
            "all_images",
            []
        )
        if image.get("url")
    }

    for image in incoming.get(
        "images",
        []
    ):

        url = image.get(
            "url",
            ""
        )

        if not url:
            continue

        if url not in existing_images:

            existing[
                "all_images"
            ].append(
                image
            )

            existing_images.add(
                url
            )

    # --------------------------------------------------------
    # Option names
    # --------------------------------------------------------

    existing_option_names = (
        existing.get(
            "option_names",
            []
        )
    )

    for incoming_name in incoming.get(
        "option_names",
        []
    ):

        if incoming_name not in (
            existing_option_names
        ):

            existing_option_names.append(
                incoming_name
            )

    # --------------------------------------------------------
    # Variations
    # --------------------------------------------------------

    existing_variations = (
        existing.get(
            "variations",
            []
        )
    )

    variation_keys = set()

    for variation in existing_variations:

        key = get_variation_key(
            variation
        )

        if key:

            variation_keys.add(
                key
            )

    for variation in incoming.get(
        "variations",
        []
    ):

        key = get_variation_key(
            variation
        )

        # If variation has attributes,
        # deduplicate by attributes.
        if key:

            if key in variation_keys:

                continue

            variation_keys.add(
                key
            )

        # If no attributes exist,
        # only keep one empty variation.
        else:

            if existing_variations:

                continue

        existing_variations.append(
            variation
        )

    return existing


# ============================================================
# CATEGORY TAGS
# ============================================================

def category_label(name):
    return CATEGORY_LABELS.get(
        name,
        name
    )


def fold_text(value):
    """Lowercase + strip accents, for duplicate detection."""

    value = unicodedata.normalize(
        "NFKD",
        value
    )

    value = "".join(
        ch
        for ch in value
        if not unicodedata.combining(ch)
    )

    return value.lower().strip()


def build_category_tags(
    category_paths,
    extra_tags=()
):
    """
    Example:

        Coiffures > Extensions
        Coiffures > Mèches À Tresser

    becomes:

        Coiffures, Extensions, Mèches à Tresser

    Plain names so automated collections can use
    "Tag is equal to Extensions". Extra tags (from the
    product page) are added only if they are not the
    same name with different case/accents.
    """

    tags = []

    for category, subcategory in (
        category_paths
    ):

        if category:
            tags.append(
                category_label(category)
            )

        if subcategory:
            tags.append(
                category_label(subcategory)
            )

    for tag in extra_tags:

        tag = clean_text(tag)

        if tag:
            tags.append(tag)

    unique_tags = []

    seen = set()

    for tag in tags:

        key = fold_text(tag)

        if key in seen:
            continue

        seen.add(key)

        unique_tags.append(tag)

    return unique_tags


def get_shopify_category(
    category_paths
):
    """
    Pick one Shopify taxonomy path. Subcategories are
    more specific, so they win over main categories.
    """

    for category, subcategory in (
        category_paths
    ):

        if subcategory in SHOPIFY_TAXONOMY:
            return SHOPIFY_TAXONOMY[
                subcategory
            ]

    for category, subcategory in (
        category_paths
    ):

        if category in SHOPIFY_TAXONOMY:
            return SHOPIFY_TAXONOMY[
                category
            ]

    return ""


# ============================================================
# FIND ALL PRODUCTS
# ============================================================

products = OrderedDict()

html_count = 0

duplicate_count = 0

error_count = 0


for root, dirs, files in os.walk(
    ROOT_DIR
):

    for filename in files:

        if not filename.lower().endswith(
            ".html"
        ):

            continue

        file_path = os.path.join(
            root,
            filename
        )

        html_count += 1

        try:

            product = parse_product(
                file_path
            )

        except Exception as e:

            error_count += 1

            print()
            print(
                "ERROR:",
                file_path
            )

            print(e)

            continue

        handle = clean_text(
            product.get(
                "handle",
                ""
            )
        )

        title = clean_text(
            product.get(
                "title",
                ""
            )
        )

        # ----------------------------------------------------
        # PRODUCT IDENTITY
        # ----------------------------------------------------
        #
        # Handle is the primary identity.
        #
        # This means:
        #
        # category-a/products/foo.html
        #
        # and
        #
        # category-b/products/foo.html
        #
        # become ONE product when both have
        # the same WooCommerce canonical handle.
        #
        # ----------------------------------------------------

        if handle:

            product_key = (
                "handle:"
                + handle.lower()
            )

        elif title:

            product_key = (
                "title:"
                + title.lower()
            )

        else:

            print(
                "Skipping product without handle/title:",
                file_path
            )

            continue

        # ----------------------------------------------------
        # CATEGORY FROM DIRECTORY
        # ----------------------------------------------------

        category, subcategory = (
            get_categories_from_path(
                file_path
            )
        )

        category_path = (
            category,
            subcategory
        )

        # ----------------------------------------------------
        # FIRST OCCURRENCE
        # ----------------------------------------------------

        if product_key not in products:

            product["category_paths"] = []

            product["all_images"] = []

            product["source_files"] = []

            products[
                product_key
            ] = product

        else:

            duplicate_count += 1

        current_product = products[
            product_key
        ]

        # ----------------------------------------------------
        # CATEGORY PATH
        # ----------------------------------------------------

        if category_path not in (
            current_product[
                "category_paths"
            ]
        ):

            current_product[
                "category_paths"
            ].append(
                category_path
            )

        # ----------------------------------------------------
        # SOURCE FILE
        # ----------------------------------------------------

        if file_path not in (
            current_product[
                "source_files"
            ]
        ):

            current_product[
                "source_files"
            ].append(
                file_path
            )

        # ----------------------------------------------------
        # MERGE PRODUCT DATA
        # ----------------------------------------------------

        if current_product is not product:

            merge_product_data(
                current_product,
                product
            )

        else:

            # First product still needs
            # its images copied into all_images.

            current_product[
                "all_images"
            ] = list(
                product.get(
                    "images",
                    []
                )
            )


# ============================================================
# REMOVE DUPLICATE IMAGES AFTER MERGE
# ============================================================

for product in products.values():

    final_images = []

    seen_images = set()

    for image in product.get(
        "all_images",
        []
    ):

        url = image.get(
            "url",
            ""
        )

        if not url:
            continue

        if url in seen_images:
            continue

        seen_images.add(
            url
        )

        final_images.append(
            image
        )

    product[
        "all_images"
    ] = final_images


# ============================================================
# SHOPIFY ROW HELPERS
# ============================================================

def empty_row():

    return {
        column: ""
        for column in SHOPIFY_COLUMNS
    }


def fill_common_product_fields(
    row,
    product,
    tags,
    category,
    subcategory
):

    row["Title"] = product.get(
        "title",
        ""
    )

    row["URL handle"] = product.get(
        "handle",
        ""
    )

    row["Description"] = product.get(
        "description",
        ""
    )

    row["Vendor"] = product.get(
        "vendor",
        ""
    )

    # --------------------------------------------------------
    # Product category
    # --------------------------------------------------------
    #
    # Shopify standard taxonomy path (see SHOPIFY_TAXONOMY).
    # The store's own categories are kept in Type + Tags.
    #

    row["Product category"] = product.get(
        "shopify_category",
        ""
    )

    # Main directory category

    row["Type"] = category

    row["Tags"] = ", ".join(
        tags
    )

    row[
        "Published on online store"
    ] = "TRUE"

    row["Status"] = "Active"

    row["Charge tax"] = "TRUE"

    row["Requires shipping"] = "TRUE"

    row["Fulfillment service"] = "manual"

    row["Gift card"] = "FALSE"

    row[
        "Continue selling when out of stock"
    ] = "DENY"

    row[
        "Inventory tracker"
    ] = "shopify"

    row[
        "Google Shopping / Condition"
    ] = "New"

    # IMPORTANT:
    # Exact Shopify column name.
    row[
        "Google Shopping / Custom product"
    ] = "FALSE"

    row[
        "SEO title"
    ] = product.get(
        "seo_title",
        ""
    )

    row[
        "SEO description"
    ] = product.get(
        "seo_description",
        ""
    )


# ============================================================
# BUILD SHOPIFY ROWS
# ============================================================

shopify_rows = []


for product_key, product in products.items():

    handle = product.get(
        "handle",
        ""
    )

    category_paths = product.get(
        "category_paths",
        []
    )

    # --------------------------------------------------------
    # CATEGORY TAGS
    # --------------------------------------------------------

    category_tags = (
        build_category_tags(
            category_paths,
            product.get(
                "html_categories",
                []
            )
        )
    )

    product["shopify_category"] = (
        get_shopify_category(
            category_paths
        )
    )

    # --------------------------------------------------------
    # MAIN CATEGORY
    # --------------------------------------------------------

    main_category = ""

    subcategories = []

    for category, subcategory in (
        category_paths
    ):

        if category and not main_category:

            main_category = category_label(
                category
            )

        if subcategory:

            subcategories.append(
                subcategory
            )

    subcategories = unique_list(
        subcategories
    )

    # --------------------------------------------------------
    # VARIATIONS
    # --------------------------------------------------------

    variations = product.get(
        "variations",
        []
    )

    if not variations:

        fallback_variation = {
            "attributes": {},
            "display_price":
                product.get(
                    "price",
                    ""
                ),
            "display_regular_price":
                "",
            "sku":
                product.get(
                    "sku",
                    ""
                ),
            "availability_html":
                "",
            "is_in_stock":
                True,
        }

        variations = [
            fallback_variation
        ]

    # --------------------------------------------------------
    # OPTION NAMES
    # --------------------------------------------------------

    option_names = product.get(
        "option_names",
        []
    )

    # --------------------------------------------------------
    # FIRST VARIANT
    # --------------------------------------------------------

    first_product_row = True

    for variation_index, variation in enumerate(
        variations,
        start=1
    ):

        row = empty_row()

        # ----------------------------------------------------
        # Common product fields
        # ----------------------------------------------------

        if first_product_row:

            fill_common_product_fields(
                row,
                product,
                category_tags,
                main_category,
                subcategories
            )

        else:

            row[
                "URL handle"
            ] = handle

        # ----------------------------------------------------
        # VARIATION ATTRIBUTES
        # ----------------------------------------------------

        attributes = variation.get(
            "attributes",
            {}
        )

        if not isinstance(
            attributes,
            dict
        ):

            attributes = {}

        option_values = []

        for attribute_key, value in (
            attributes.items()
        ):

            value = clean_text(
                value
            )

            if not value:
                continue

            normalized_key = (
                attribute_key
                .replace(
                    "attribute_",
                    "",
                    1
                )
            )

            normalized_key = (
                normalized_key
                .replace(
                    "pa_",
                    "",
                    1
                )
            )

            option_name = ""

            for raw_name, human_name in (
                option_names
            ):

                if (
                    raw_name.lower()
                    == normalized_key.lower()
                ):

                    option_name = (
                        human_name
                    )

                    break

            if not option_name:

                option_name = (
                    slug_to_title(
                        normalized_key
                    )
                )

            option_values.append(
                (
                    option_name,
                    value
                )
            )

        # ----------------------------------------------------
        # Shopify supports maximum 3 options
        # ----------------------------------------------------

        for index, (
            option_name,
            option_value
        ) in enumerate(
            option_values[:3],
            start=1
        ):

            row[
                "Option{} name".format(
                    index
                )
            ] = option_name

            row[
                "Option{} value".format(
                    index
                )
            ] = option_value

        # ----------------------------------------------------
        # SKU
        # ----------------------------------------------------

        variation_sku = clean_text(
            variation.get(
                "sku",
                ""
            )
        )

        if variation_sku:

            row[
                "SKU"
            ] = variation_sku

        elif first_product_row:

            row[
                "SKU"
            ] = product.get(
                "sku",
                ""
            )

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        display_price = variation.get(
            "display_price"
        )

        if (
            display_price is not None
            and display_price != ""
        ):

            try:

                row[
                    "Price"
                ] = str(
                    float(
                        display_price
                    )
                )

            except (
                ValueError,
                TypeError
            ):

                row[
                    "Price"
                ] = clean_text(
                    display_price
                )

        else:

            row[
                "Price"
            ] = product.get(
                "price",
                ""
            )

        # ----------------------------------------------------
        # COMPARE AT PRICE
        # ----------------------------------------------------

        regular_price = variation.get(
            "display_regular_price"
        )

        if (
            regular_price is not None
            and regular_price != ""
            and str(
                regular_price
            ) != str(
                display_price
            )
        ):

            try:

                row[
                    "Compare-at price"
                ] = str(
                    float(
                        regular_price
                    )
                )

            except (
                ValueError,
                TypeError
            ):

                row[
                    "Compare-at price"
                ] = clean_text(
                    regular_price
                )

        # ----------------------------------------------------
        # INVENTORY
        # ----------------------------------------------------

        availability = variation.get(
            "availability_html",
            ""
        )

        stock = parse_stock(
            BeautifulSoup(
                availability,
                "html.parser"
            ).get_text(
                " ",
                strip=True
            )
        )

        if stock:

            row[
                "Inventory quantity"
            ] = stock

        elif first_product_row:

            row[
                "Inventory quantity"
            ] = product.get(
                "stock",
                ""
            )

        elif variation.get(
            "is_in_stock"
        ):

            row[
                "Inventory quantity"
            ] = ""

        # ----------------------------------------------------
        # WEIGHT
        # ----------------------------------------------------

        row[
            "Weight value (grams)"
        ] = product.get(
            "weight",
            ""
        )

        row[
            "Weight unit for display"
        ] = "g"

        # ----------------------------------------------------
        # VARIATION IMAGE
        # ----------------------------------------------------

        variation_image = ""

        image_data = variation.get(
            "image",
            {}
        )

        if isinstance(
            image_data,
            dict
        ):

            variation_image = (
                image_data.get(
                    "full_src",
                    ""
                )
                or image_data.get(
                    "src",
                    ""
                )
            )

        if variation_image:

            variation_image = (
                normalize_url(
                    variation_image
                )
            )

            row[
                "Variant image URL"
            ] = variation_image

        # ----------------------------------------------------
        # COMMON DEFAULTS
        # ----------------------------------------------------

        row[
            "Requires shipping"
        ] = "TRUE"

        row[
            "Fulfillment service"
        ] = "manual"

        row[
            "Gift card"
        ] = "FALSE"

        row[
            "Published on online store"
        ] = "TRUE"

        row[
            "Status"
        ] = "Active"

        row[
            "Charge tax"
        ] = "TRUE"

        row[
            "Continue selling when out of stock"
        ] = "DENY"

        row[
            "Inventory tracker"
        ] = "shopify"

        row[
            "Weight unit for display"
        ] = "g"

        row[
            "Google Shopping / Condition"
        ] = "New"

        row[
            "Google Shopping / Custom product"
        ] = "FALSE"

        # ----------------------------------------------------
        # PRODUCT IMAGES
        # ----------------------------------------------------
        #
        # No image-only rows (they repeat the handle).
        # Image 1 goes on the first row, and extra images
        # ride along on the existing variant rows.
        #

        images = [
            image
            for image in product.get(
                "all_images",
                []
            )
            if image.get("url")
            and not image["url"].endswith(
                PLACEHOLDER_IMAGES
            )
        ]

        if variation_index <= len(images):

            image = images[
                variation_index - 1
            ]

            row[
                "Product image URL"
            ] = image.get(
                "url",
                ""
            )

            row[
                "Image position"
            ] = str(
                variation_index
            )

            row[
                "Image alt text"
            ] = (
                image.get(
                    "alt",
                    ""
                )
                or product.get(
                    "title",
                    ""
                )
            )

        shopify_rows.append(
            row
        )

        first_product_row = False


# ============================================================
# SANITIZE FOR SHOPIFY
# ============================================================

CONTROL_CHARS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏  ﻿]"
)


def sanitize_cell(value):
    """
    Shopify's CSV importer is strict and fails with
    "Illegal quoting" on stray double quotes (e.g. 18"
    used as inches) and invisible control characters.
    """

    if value is None:
        return ""

    value = str(value)

    value = CONTROL_CHARS.sub("", value)

    # Newlines inside a cell are not needed and
    # confuse Shopify's line counting.
    value = re.sub(r"[\r\n]+", " ", value)

    # Double quote -> double prime (inch mark).
    value = value.replace('"', "″")

    return value.strip()


shopify_rows = [
    {
        key: sanitize_cell(value)
        for key, value in row.items()
    }
    for row in shopify_rows
]


# ============================================================
# WRITE CSV
# ============================================================

with open(
    OUTPUT_CSV,
    "w",
    newline="",
    encoding="utf-8-sig"
) as csv_file:

    writer = csv.DictWriter(
        csv_file,
        fieldnames=SHOPIFY_COLUMNS,
        extrasaction="ignore",
        doublequote=True,
        quoting=csv.QUOTE_ALL,
        lineterminator="\n"
    )

    writer.writeheader()

    writer.writerows(
        shopify_rows
    )


# ============================================================
# REPORT
# ============================================================

print()
print("=" * 70)
print("SHOPIFY CSV CREATED")
print("=" * 70)

print(
    "HTML files scanned:",
    html_count
)

print(
    "Unique products:",
    len(products)
)

print(
    "Duplicate product files merged:",
    duplicate_count
)

print(
    "Errors:",
    error_count
)

print(
    "Shopify CSV rows:",
    len(shopify_rows)
)

print(
    "Output:",
    OUTPUT_CSV
)

print("=" * 70)


# ============================================================
# CATEGORY SUMMARY
# ============================================================

print()
print("CATEGORY SUMMARY")
print("-" * 70)

for product_key, product in products.items():

    paths = []

    for category, subcategory in (
        product.get(
            "category_paths",
            []
        )
    ):

        if subcategory:

            paths.append(
                "{} > {}".format(
                    category,
                    subcategory
                )
            )

        elif category:

            paths.append(
                category
            )

    print(
        product.get(
            "handle",
            product_key
        ),
        "=>",
        " | ".join(
            unique_list(
                paths
            )
        )
    )


# ============================================================
# DUPLICATE DETAILS
# ============================================================

print()
print("PRODUCT SOURCE SUMMARY")
print("-" * 70)

for product_key, product in products.items():

    source_files = product.get(
        "source_files",
        []
    )

    if len(source_files) > 1:

        print()
        print(
            "MERGED PRODUCT:",
            product.get(
                "title",
                ""
            )
        )

        print(
            "Handle:",
            product.get(
                "handle",
                ""
            )
        )

        print(
            "Occurrences:",
            len(source_files)
        )

        print(
            "Categories:"
        )

        for category, subcategory in (
            product.get(
                "category_paths",
                []
            )
        ):

            if subcategory:

                print(
                    "  - {} > {}".format(
                        category,
                        subcategory
                    )
                )

            else:

                print(
                    "  - {}"
                    .format(
                        category
                    )
                )