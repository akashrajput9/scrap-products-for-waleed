# 🛍️ WooCommerce → Shopify Product Migration Scraper

> A Python pipeline that crawls a French e-commerce store (WooCommerce), archives every product page, and converts the whole catalogue into a **ready-to-import Shopify product CSV** — with variants, images, categories, SEO fields and Shopify's standard taxonomy.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup4-HTML_Parsing-4B8BBE?style=flat-square)
![Requests](https://img.shields.io/badge/Requests-HTTP-2C5BB4?style=flat-square)
![WooCommerce](https://img.shields.io/badge/Source-WooCommerce-96588A?style=flat-square&logo=woocommerce&logoColor=white)
![Shopify](https://img.shields.io/badge/Target-Shopify-7AB55C?style=flat-square&logo=shopify&logoColor=white)

---

## 📌 Overview

The client was moving a French beauty & hair-care store (**afrotouch-kosmetics.fr**, built on WordPress/WooCommerce) to **Shopify**. Rebuilding more than a thousand products by hand — each with multiple variants, prices, stock levels and image galleries — wasn't realistic.

This project automates the whole migration in two stages:

1. **Crawl** – walk every category listing page, discover each product, and save the raw product HTML into a category-structured archive.
2. **Transform** – parse the archived HTML offline, merge duplicates, map categories to Shopify's taxonomy, and write a Shopify-compliant CSV.

Splitting crawl and transform means the site is hit **once**, and the parser can be re-run and tuned as often as needed without re-scraping.

## 📊 Results

| Metric | Value |
|---|---|
| Category endpoints crawled | **26** (7 top-level sections) |
| Product HTML pages archived | **2,438** |
| Unique products after de-duplication | **1,305** |
| Shopify CSV rows (products + variants) | **2,161** |
| Distinct brands / vendors extracted | **144** |

---

## 🏗️ Architecture

```text
 afrotouch-kosmetics.fr (WooCommerce)
                │
                ▼
 ┌──────────────────────────────┐
 │  main.py  — Crawler          │
 │  • 26 category endpoints     │
 │  • paginate /page/N/ → 404   │
 │  • slug-based de-duplication │
 └──────────────┬───────────────┘
                ▼
 category_wise_products/<category>/<sub>/products/<slug>.html
                │
                ▼
 ┌──────────────────────────────┐
 │  csv_generate.py — Transform │
 │  • parse title/price/stock…  │
 │  • WooCommerce variations    │
 │  • merge duplicate handles   │
 │  • map → Shopify taxonomy    │
 │  • sanitize for importer     │
 └──────────────┬───────────────┘
                ▼
     shopify_products_import.csv  ──►  Shopify Admin → Import
```

---

## ⚙️ How It Works

### 1. Crawler — `main.py`

- Iterates over **26 category paths** (hair care, hairstyles/extensions, wigs, face & body, men, kids, make-up).
- Paginates each category (`/categorie/<path>/page/N/`) until it gets a 404 or the "Page non trouvée" page.
- Extracts product links from the WooCommerce loop (`ul.products li.product a.woocommerce-loop-product__link`).
- **Smart de-duplication:** before starting, it indexes every product already on disk by slug.
  - Already in this category → **skip**
  - Already downloaded under another category → **copy locally** instead of re-downloading
  - New → **download** and add to the index immediately
- Result: products that appear in several categories are fetched only once, while each category folder still holds a full copy — so category membership is preserved for later.

### 2. Transformer — `csv_generate.py`

For each archived HTML page it extracts:

| Field | Strategy |
|---|---|
| **Handle** | Canonical URL slug (`/produit/<slug>/`), fallback to file name |
| **Title** | `h1.product_title` → `og:title` (brand suffix stripped) |
| **Description** | Short description → description tab → Elementor fallback → meta description |
| **Vendor** | `product:brand` meta → JSON-LD `brand` (incl. `@graph`) |
| **Price / Compare-at** | `display_price` / `display_regular_price` from variation data |
| **Stock** | Parsed from `availability_html` ("200 en stock" → `200`) |
| **Weight** | Weight field or parsed from description (`0.28 kg` → `280` g) |
| **Variants** | JSON in `form.variations_form[data-product_variations]`, max 3 options (Shopify limit) |
| **Images** | Full-size gallery images + `og:image`; thumbnails, SVGs, logos and placeholders filtered out |
| **SEO** | `og:title` and meta description |

Then it:

- **Merges duplicates** – the same handle found in several category folders becomes one product; missing fields, images, option names and variants are merged in (variants de-duplicated by their attribute set).
- **Builds tags from folder structure** – e.g. `Coiffures > Extensions` → tags `Coiffures, Extensions`, with accent-/case-insensitive de-duplication, so Shopify **automated collections** can use `Tag is equal to …`.
- **Maps to Shopify's standard product taxonomy** – subcategories win over parents (e.g. `Lace Wig` → `Apparel & Accessories > Clothing Accessories > Hair Accessories > Wigs`).
- **Sanitizes for Shopify's strict importer** – removes control/zero-width characters and newlines, and converts stray `"` (inches, e.g. `18"`) to `″` to avoid *"Illegal quoting"* errors.
- Writes a UTF-8 (BOM) CSV using Shopify's current column template, then prints a report: files scanned, unique products, merged duplicates, errors, and per-product category paths.

---

## 📁 Project Structure

```text
.
├── main.py                      # Stage 1 – crawler / HTML archiver
├── csv_generate.py              # Stage 2 – HTML → Shopify CSV transformer
├── category_wise_products/      # Archived product pages, grouped by category
│   ├── soins-cheveux/…
│   ├── coiffures/…
│   ├── perruques/…
│   ├── visages-et-corps/…
│   ├── hommes/…
│   ├── bebe-et-enfant/…
│   └── make-up/…
├── shopify_products_import.csv  # Final Shopify import file
├── product_categories.csv       # Handle → category / subcategory map
└── passenger_wsgi.py            # Health-check app used when running on cPanel/Passenger hosting
```

---

## 🚀 Usage

```bash
python -m venv .venv && source .venv/bin/activate
pip install requests beautifulsoup4

# 1) Crawl the store and archive product pages
python main.py

# 2) Build the Shopify import CSV from the archive
python csv_generate.py
```

Then in Shopify: **Products → Import → upload `shopify_products_import.csv`**.

Re-running `main.py` is incremental — already-archived products are skipped, so it can resume after interruptions.

---

## 🧠 Key Engineering Decisions

- **Crawl once, parse many times** – raw HTML is kept on disk, so parser fixes never require re-scraping the live site.
- **Folder structure = category data** – no extra database; the path encodes category and subcategory.
- **Handle as primary identity** – guarantees one Shopify product per WooCommerce product even when it's listed in many categories.
- **Layered fallbacks for every field** – WooCommerce themes and Elementor pages vary, so each extractor tries several selectors before giving up.
- **Importer-safe output** – designed around Shopify's CSV quirks (3-option limit, exact column names, quoting rules, no image-only rows).

## 🛠️ Tech Stack

`Python` · `requests` · `BeautifulSoup4` · `csv` / `json` / `re` / `unicodedata` (stdlib) · `WooCommerce` · `Shopify CSV import`

---

<sub>Built by <a href="https://github.com/akashrajput9">Akash Ahmed</a> as a client e-commerce migration project.</sub>
