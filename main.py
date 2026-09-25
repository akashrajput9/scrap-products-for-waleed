import os
import shutil
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse


endpoints = [
    "soins-cheveux",
    "soins-cheveux/shampooing",
    "soins-cheveux/coiffants",
    "bebe-et-enfant/soins-cheveux-enfant",
    "hommes/cheveux-homme",
    "soins-cheveux/accessoires-cheveux",

    "coiffures",
    "coiffures/accessoires-de-coiffures",
    "coiffures/extensions",
    "coiffures/tissage",
    "coiffures/soins-cheveux-coiffures",
    "coiffures/lace-wig",
    "coiffures/meches-a-tresser",
    "coiffures/postiches",
    "soins-cheveux/complement-alimentaire",

    "perruques",

    "visages-et-corps",
    "visages-et-corps/corps",
    "visages-et-corps/visages",
    "hommes/soin-visage-homme",
    "hommes/soins-barbes",
    "hommes/soins-corps-homme",
    "hommes/accessoires-homme",

    "make-up",
    "make-up/teint",
    "make-up/yeux",
]


ROOT_DIR = "category_wise_products"


# ==================================================
# BUILD INDEX OF EXISTING PRODUCT FILES
# ==================================================

existing_products = {}


for root, dirs, files in os.walk(ROOT_DIR):

    for file in files:

        if not file.endswith(".html"):
            continue

        slug = os.path.splitext(file)[0]

        full_path = os.path.join(root, file)

        # Store where the existing product is located
        if slug not in existing_products:
            existing_products[slug] = full_path


print(
    "Existing unique products:",
    len(existing_products)
)


# ==================================================
# SCRAPER
# ==================================================

def scrap_and_save(endpoint):

    print("\n======================================")
    print("SCRAPING:", endpoint)
    print("======================================")

    base_dir = os.path.join(
        ROOT_DIR,
        endpoint,
        "products"
    )

    os.makedirs(
        base_dir,
        exist_ok=True
    )

    url = (
        "https://afrotouch-kosmetics.fr/categorie/"
        + endpoint
    )

    page = 1

    while True:

        print("\nProcessing page:", page)

        req_url = f"{url}/page/{page}/"

        try:

            response = requests.get(
                req_url,
                timeout=30
            )
            if response.status_code == 404:
                print("404 - No more pages.")

                break

            response.raise_for_status()

        except Exception as e:

            print(
                "Failed category request:",
                req_url,
                e
            )

            continue

        html = response.text

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        title = (
            soup.title.text.strip()
            if soup.title
            else ""
        )

        if title == "Page non trouvée - Afrotouch Kosmetics":

            print("No more pages.")

            break

        products_ul = soup.find(
            "ul",
            class_="products"
        )

        if not products_ul:

            print("No products found.")

            break

        products = products_ul.find_all(
            "li",
            class_="product"
        )

        if not products:

            print("No products found.")

            break

        for product in products:

            link = product.find(
                "a",
                class_="woocommerce-loop-product__link"
            )

            if not link:
                continue

            href = link.get("href")

            if not href:
                continue

            # ======================================
            # PRODUCT SLUG
            # ======================================

            clean_path = urlparse(href).path

            file_name = (
                clean_path
                .rstrip("/")
                .rsplit("/", 1)[-1]
            )

            destination = os.path.join(
                base_dir,
                file_name + ".html"
            )

            # ======================================
            # ALREADY EXISTS IN CURRENT CATEGORY
            # ======================================

            if os.path.exists(destination):

                print(
                    "SKIP - already exists:",
                    destination
                )

                continue

            # ======================================
            # PRODUCT EXISTS SOMEWHERE ELSE
            # ======================================

            if file_name in existing_products:

                source = existing_products[file_name]

                print(
                    "COPY existing product:"
                )

                print(
                    "FROM:",
                    source
                )

                print(
                    "TO:",
                    destination
                )

                shutil.copy2(
                    source,
                    destination
                )

                continue

            # ======================================
            # PRODUCT DOES NOT EXIST
            # DOWNLOAD IT
            # ======================================

            print(
                "DOWNLOADING:",
                href
            )

            try:

                product_response = requests.get(
                    href,
                    timeout=30
                )

                product_response.raise_for_status()

            except Exception as e:

                print(
                    "Failed product request:",
                    href,
                    e
                )

                continue

            # ======================================
            # SAVE
            # ======================================

            with open(
                destination,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    product_response.text
                )

            print(
                "DOWNLOADED:",
                destination
            )

            # Add to index immediately.
            # This means if the same product
            # appears later, it will be copied
            # instead of downloaded again.

            existing_products[file_name] = destination

        page += 1


# ==================================================
# RUN
# ==================================================

for endpoint in endpoints:

    scrap_and_save(endpoint)