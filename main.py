import os
from bs4 import BeautifulSoup
import requests
from bs4 import BeautifulSoup
base_dir = "category_wise_products/shampoo/products/"
from urllib.parse import urlparse
page = 1
while True:
    shampoo = f"https://afrotouch-kosmetics.fr/categorie/soins-cheveux/shampooing/page/{page}/"
    response = requests.get(shampoo).text
    soup = BeautifulSoup(response, "html.parser")
    title = soup.title.text
    if title == "Page non trouvée - Afrotouch Kosmetics":
        break
    products_ul = soup.find('ul', class_='products')
    products = products_ul.find_all('li', class_='product')
    for product in products:
        link = product.find('a', class_='woocommerce-loop-product__link')
        href = link.attrs['href']
        res = requests.get(href).text
        clean_path = urlparse(href).path
        file_name = clean_path.rstrip('/').rsplit('/', 1)[-1]
        response = requests.get(href).text
        with open(base_dir+ file_name + ".html", 'w') as f:
            f.write(response)

    page += 1
