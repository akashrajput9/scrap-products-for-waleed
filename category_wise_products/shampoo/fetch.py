import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

with open('./shampoo.html') as f:
    content = f.read()
    soup = BeautifulSoup(content, 'html.parser')
    products_ul = soup.find('ul', class_='products')
    products = products_ul.find_all('li', class_='product')
    for product in products:
        link = product.find('a', class_='woocommerce-loop-product__link')
        href = link.attrs['href']
        clean_path = urlparse(href).path
        file_name = clean_path.rstrip('/').rsplit('/', 1)[-1]
        response = requests.get(href).text
        with open('./products/'+file_name+".html", 'w') as f:
            f.write(response)



