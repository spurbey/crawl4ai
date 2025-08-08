import asyncio
import json
import re
from datetime import datetime
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

def extract_sku_from_title(title):
   """Extract SKU from title like 'Product Name (SGRZ-30-CB)'"""
   if not title:
       return ""
   match = re.search(r'\(([A-Z0-9\-]+)\)$', title.strip())
   return match.group(1) if match else ""

def detect_series(title):
   """Detect which series this variant belongs to"""
   title_lower = title.lower()
   if 'paramount' in title_lower:
       return 'paramount'
   elif 'classic' in title_lower:
       return 'classic'
   elif 'select' in title_lower:
       return 'select'
   else:
       return 'unknown'

def extract_variant_details(title):
   """Extract size, fuel type, finish, accent, door color, burner type from title"""
   import re
   
   # Size
   size_match = re.search(r'(\d+)\s*(?:in\.|inch)', title)
   size = f"{size_match.group(1)} Inch" if size_match else ""
   
   # Fuel type
   if 'dual fuel' in title.lower():
       fuel_type = 'Dual Fuel'
   elif 'gas' in title.lower():
       fuel_type = 'Gas'
   else:
       fuel_type = ""
   
   # Base finish
   title_lower = title.lower()
   if 'black stainless steel' in title_lower:
       base_finish = 'Black Stainless Steel'
   elif 'satin stainless steel' in title_lower:
       base_finish = 'Satin Stainless Steel'
   elif 'stainless steel' in title_lower:
       base_finish = 'Stainless Steel'
   else:
       base_finish = ""
   
   # Accent
   if 'champagne bronze' in title_lower:
       accent = 'Champagne Bronze'
   elif 'polished gold' in title_lower:
       accent = 'Polished Gold'
   elif 'matte black' in title_lower:
       accent = 'Matte Black'
   else:
       accent = ""
   
   # Door color
   door_color = ""
   if 'white matte door' in title_lower or 'white matte' in title_lower:
       door_color = 'White Matte'
   
   # Burner type
   burner_type = ""
   if 'brass burner' in title_lower:
       burner_type = 'Brass Burners'
   elif 'duopro' in title_lower:
       burner_type = 'DuoPro Burners'
   elif 'porcelain' in title_lower:
       burner_type = 'Porcelain'
   
   # Build result dict - only include non-empty values
   result = {
       'size': size,
       'fuel_type': fuel_type,
       'base_finish': base_finish,
       'accent': accent
   }
   
   # Only add if they exist
   if door_color:
       result['door_color'] = door_color
       
   if burner_type:
       result['burner_type'] = burner_type
   
   return result

class ZLineRangeSeriesManager:
   def __init__(self):
       self.series_data = {
           'paramount': {'variants': []},
           'classic': {'variants': []},
           'select': {'variants': []},
           'unknown': {'variants': []}
       }
   
   def add_variant(self, variant_data):
       """Add a variant to the appropriate series"""
       series = detect_series(variant_data.get('title', ''))
       
       # Extract variant details
       details = extract_variant_details(variant_data.get('title', ''))
       
       # Build structured variant data
       structured_variant = {
           'sku': extract_sku_from_title(variant_data.get('title', '')),
           'title': variant_data.get('title', ''),
           'price': int(variant_data.get('price', 0)),
           'url': f"https://zlinekitchen.com{variant_data.get('url', '')}",
           'images': variant_data.get('images', []),
           'description': variant_data.get('description', ''),
           **details
       }
       
       self.series_data[series]['variants'].append(structured_variant)
   
   def get_structured_data(self):
       """Get final structured data by series"""
       final_data = {
           'scrape_metadata': {
               'timestamp': datetime.now().isoformat(),
               'total_series': len([s for s in self.series_data.values() if s['variants']]),
               'total_variants': sum(len(s['variants']) for s in self.series_data.values())
           },
           'range_series': {}
       }
       
       for series_key, series_info in self.series_data.items():
           if series_info['variants']:
               final_data['range_series'][series_key] = {
                   'series_name': series_key.capitalize(),
                   'total_variants': len(series_info['variants']),
                   'variants': sorted(series_info['variants'], 
                                    key=lambda x: (x['size'], x['fuel_type'], x.get('accent', '')))
               }
       
       return final_data

async def get_all_variants_demo(start_url, crawler, config, max_urls=10):
   visited = set()
   queue = [start_url]
   series_manager = ZLineRangeSeriesManager()
   
   print(f"🎯 Demo mode: Will stop after {max_urls} URLs")
   
   while queue and len(visited) < max_urls:
       current_url = queue.pop(0)
       
       if current_url in visited:
           continue
       
       visited.add(current_url)
       print(f"\n[{len(visited)}/{max_urls}] 🔍 Scraping: {current_url}")
       
       result = await crawler.arun(f"https://zlinekitchen.com{current_url}", config=config)
       
       if result.success:
           try:
               data = json.loads(result.extracted_content)[0]
               
               variant_data = {
                   'url': current_url,
                   'title': data.get("title", "N/A"),
                   'price': data.get("price", "0"),
                   'description': data.get("description", ""),
                   'images': data.get("images", [])
               }
               
               series_manager.add_variant(variant_data)
               
               unique_urls = set()
               for variant in data.get("variant_urls", []):
                   variant_url = variant.get("url")
                   if variant_url:
                       unique_urls.add(variant_url)
               
               print(f"✅ Found {len(unique_urls)} variant URLs | Series: {detect_series(variant_data['title'])}")
               
               new_added = 0
               for new_url in unique_urls:
                   if new_url not in visited and new_url not in queue:
                       queue.append(new_url)
                       new_added += 1
               
               print(f" Added {new_added} new URLs to queue")
               
           except Exception as e:
               print(f" Error parsing result from {current_url}: {e}")
       else:
           print(f" Failed to scrape: {current_url}")
   
   return series_manager.get_structured_data()

async def Zipline():
   browser_config = BrowserConfig(
       headless=True,
       user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
   )
   
   css_extraction = {
       "name": "Zipline Products",
       "baseSelector": ".ecom-sections",
       "fields": [
           {
               "name": "title",
               "selector": ".ecom-product__heading",
               "type": "text"
           },
           {
               "name": "price",
               "selector": "[data-price]",
               "type": "attribute",
               "attribute": "data-price"
           },
           {
               "name": "description",
               "selector": ".ecom-html-des",
               "type": "text"
           },
           {
               "name": "images",
               "selector": ".ecom-product-thumbnail img, .ecom-splide-slide img",
               "type": "list",
               "fields": [
                   {
                       "name": "url",
                       "type": "attribute",
                       "attribute": "src"
                   }
               ]
           },
           {
               "name": "variant_urls",
               "selector": "[swatch-url]",
               "type": "list",
               "fields": [
                   {
                       "name": "url",
                       "type": "attribute",
                       "attribute": "swatch-url"
                   }
               ]
           }
       ]
   }
   
   extraction_strategy = JsonCssExtractionStrategy(css_extraction)
   
   config = CrawlerRunConfig(
       extraction_strategy=extraction_strategy,
       js_code="""
       await new Promise(resolve => setTimeout(resolve, 2000));
       const swatchElements = document.querySelectorAll('[swatch-url]');
       swatchElements.forEach(el => {
           el.dispatchEvent(new Event('mouseenter'));
       });
       await new Promise(resolve => setTimeout(resolve, 1000));
       """,
       wait_for="css:.ecom-sections",
       delay_before_return_html=2.0
   )
   
   start_url = "/products/zline-autograph-edition-30-paramount-gas-range-stainless-steel-champagne-bronze-sgrz-30-cb"
   
   async with AsyncWebCrawler(config=browser_config) as crawler:
       structured_data = await get_all_variants_demo(start_url, crawler, config, max_urls=10)
       
       timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
       output_file = f"zline_range_series_{timestamp}.json"
       
       with open(output_file, 'w', encoding='utf-8') as f:
           json.dump(structured_data, f, indent=2, ensure_ascii=False)
       
       print(f"\n STRUCTURED RESULTS:")
       print(f" Data saved to: {output_file}")
       print("-" * 80)
       
       for series_key, series_data in structured_data['range_series'].items():
           print(f"\n {series_key.upper()} SERIES: {series_data['total_variants']} variants")
           for variant in series_data['variants'][:3]:
               price = f"${variant['price']/100:.2f}"
               print(f"   • {variant['size']} {variant['fuel_type']} - {price} ({variant['sku']})")
           
           if series_data['total_variants'] > 3:
               print(f"   ... and {series_data['total_variants'] - 3} more variants")

if __name__ == "__main__":
   asyncio.run(Zipline())