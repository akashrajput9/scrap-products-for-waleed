
import os
from bs4 import BeautifulSoup
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse


endpoints = [
    "soins-cheveux",
    "soins-cheveux/shampooing",
    "soins-cheveux/coiffants",
    "bebe-et-enfant/soins-cheveux-enfant",
    "hommes/cheveux-homme",
    "soins-cheveux/accessoires-cheveux",
    #sub new
    "coiffures",
    "coiffures/accessoires-de-coiffures",
    "coiffures/extensions",
    "coiffures/tissage",
    "coiffures/soins-cheveux-coiffures",
    "coiffures/lace-wig",
    "coiffures/meches-a-tresser",
    "coiffures/postiches",
    "soins-cheveux/complement-alimentaire",
    #wigs second 
    "perruques",
    #3rd
    "visages-et-corps",
    "visages-et-corps/corps",
    "visages-et-corps/visages",
    "hommes/soin-visage-homme",
    "hommes/soins-barbes",
    "hommes/soins-corps-homme",
    "hommes/accessoires-homme",
    "hommes/accessoires-homme",
    
    #4th 
    "make-up",
    "make-up/teint",
    "make-up/yeux",


]



def scrap_and_save(endpoint):
    print("scraping " + endpoint)
    # endpoint_break = urlparse(endpoint).path.rstrip('/').rsplit('/', 1)
    base_dir = f"category_wise_products/{endpoint}/products/"
    os.makedirs(base_dir, exist_ok=True)
    url = "https://afrotouch-kosmetics.fr/categorie/"+ str(endpoint)

    page = 1
    while True:
        print("processing page " + str(page))
        req_url = f"{url}/page/{page}/"
        response = requests.get(req_url).text
        print("response got success")
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
            print("got inner page response of " + str(href))
            file_name = base_dir + file_name + ".html"
            with open(file_name, 'w') as f:
                f.write(response)
            print('file created' + str(file_name))
        page += 1


for endpoint in endpoints:
    scrap_and_save(endpoint)
